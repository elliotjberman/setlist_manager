import json
import os
import socket
import struct
import threading
import time
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

from platform_adapters import get_platform_adapter


def get_env_float(name, default):
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default

    try:
        return max(0.0, float(raw_value))
    except ValueError:
        print(f"Ignoring invalid {name}={raw_value!r}; using {default}")
        return default


DEFAULT_SERVER_PORT = 8000
DEFAULT_UDP_OPEN_DELAY_SECONDS = 1.0
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SETLIST_PATH = os.path.join(SCRIPT_DIR, "setlist.json")
PLATFORM_ADAPTER = get_platform_adapter()
DIALOG_HANDLER = PLATFORM_ADAPTER.create_save_dialog_handler()
SERVER_PORT = DEFAULT_SERVER_PORT
UDP_PORT = DEFAULT_SERVER_PORT
CURRENT_INDEX = None
CURRENT_PATH = None
# Ableton is so raw that it actually segfaults if you hit it too quick
# with the reload while Max is unloading, so we do this bullshit.
UDP_OPEN_DELAY_SECONDS = get_env_float("SETLIST_UDP_OPEN_DELAY", DEFAULT_UDP_OPEN_DELAY_SECONDS)


def send_cors_headers(handler):
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")


def send_json(handler, status_code, payload):
    response = json.dumps(payload).encode("utf-8")
    handler.send_response(status_code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(response)))
    send_cors_headers(handler)
    handler.end_headers()
    handler.wfile.write(response)
    handler.wfile.flush()


def load_setlist():
    try:
        with open(SETLIST_PATH, "r") as f:
            setlist = json.load(f)
        if not isinstance(setlist, dict):
            return {}, "setlist.json must contain a JSON object"
        return setlist, None
    except FileNotFoundError:
        return {}, f"setlist.json not found at {SETLIST_PATH}"
    except Exception as e:
        return {}, f"Error loading setlist.json: {e}"


def get_configured_port(setlist):
    port = setlist.get("serverPort")
    if isinstance(port, int):
        return port, None
    return SERVER_PORT, "serverPort missing or not an integer in setlist.json"


def get_configured_udp_port(setlist, server_port):
    raw_env_port = os.environ.get("SETLIST_UDP_PORT")
    if raw_env_port is not None:
        try:
            return int(raw_env_port), None
        except ValueError:
            return server_port, f"SETLIST_UDP_PORT is not an integer: {raw_env_port!r}"

    port = setlist.get("udpPort", server_port)
    if isinstance(port, int):
        return port, None
    return server_port, "udpPort is not an integer in setlist.json"


def get_status_payload():
    setlist, setlist_error = load_setlist()
    server_port, port_error = get_configured_port(setlist)
    udp_port, udp_port_error = get_configured_udp_port(setlist, server_port)
    error = setlist_error or port_error or udp_port_error

    return {
        "ok": error is None,
        "error": error,
        "platform": PLATFORM_ADAPTER.name,
        "serverPort": server_port,
        "udpPort": udp_port,
        "basePath": setlist.get("basePath"),
        "sets": setlist.get("sets", []),
        "current_index": CURRENT_INDEX,
        "current_path": CURRENT_PATH,
        "setlistPath": SETLIST_PATH,
    }


def resolve_set_path(file_path, setlist):
    base_path = setlist.get("basePath")
    if base_path and not os.path.isabs(file_path):
        return os.path.join(base_path, file_path)
    return file_path


def open_ableton_set(file_path, current_index=None):
    global CURRENT_INDEX, CURRENT_PATH

    PLATFORM_ADAPTER.open_file(file_path)
    DIALOG_HANDLER.handle_after_open()
    CURRENT_PATH = file_path
    CURRENT_INDEX = current_index


def start_open_thread(file_path, current_index=None, delay_seconds=0.0):
    opener = threading.Thread(
        target=delayed_open_ableton_set,
        args=(file_path, current_index, delay_seconds),
        daemon=True,
    )
    opener.start()
    return opener


def delayed_open_ableton_set(file_path, current_index=None, delay_seconds=0.0):
    if delay_seconds > 0:
        print(f"Waiting {delay_seconds:.3f}s before opening set: {file_path}")
        time.sleep(delay_seconds)

    try:
        print(f"Loading set: {file_path}")
        open_ableton_set(file_path, current_index)
    except Exception as e:
        print(f"Error opening file after response: {file_path}\n{e}")
        traceback.print_exc()


def normalize_index(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.lstrip("-").isdigit():
            return int(stripped)
    return None


def resolve_load_target(data):
    setlist, setlist_error = load_setlist()
    if setlist_error:
        return None, 500, {"ok": False, "error": setlist_error}

    current_index = normalize_index(data.get("index"))
    file_path = data.get("path")

    if file_path:
        file_path = resolve_set_path(file_path, setlist)
    elif current_index is not None:
        sets = setlist.get("sets")
        if not isinstance(sets, list):
            return None, 500, {"ok": False, "error": "No valid sets list in setlist.json"}
        if current_index < 0 or current_index >= len(sets):
            return None, 404, {
                "ok": False,
                "error": "Set index out of range",
                "index": current_index,
                "set_count": len(sets),
            }
        file_path = sets[current_index].get("path")
        if not file_path:
            return None, 404, {"ok": False, "error": "Set index has no path", "index": current_index}
        file_path = resolve_set_path(file_path, setlist)
    else:
        return None, 400, {"ok": False, "error": "Missing path or index"}

    if not os.path.isfile(file_path):
        print(f"Error: File not found - {file_path}")
        return None, 404, {"ok": False, "error": "File not found", "path": file_path}

    return (file_path, current_index), 200, {"ok": True, "path": file_path, "current_index": current_index}


def read_osc_string(packet, offset):
    end = packet.index(b"\x00", offset)
    value = packet[offset:end].decode("utf-8")
    next_offset = (end + 4) & ~0x03
    return value, next_offset


def parse_osc_packet(packet):
    if not packet:
        return None

    try:
        address, offset = read_osc_string(packet, 0)
        type_tags, offset = read_osc_string(packet, offset)
    except (ValueError, UnicodeDecodeError):
        return None

    if not type_tags.startswith(","):
        return None

    args = []
    try:
        for tag in type_tags[1:]:
            if tag == "i":
                args.append(struct.unpack(">i", packet[offset:offset + 4])[0])
                offset += 4
            elif tag == "f":
                args.append(struct.unpack(">f", packet[offset:offset + 4])[0])
                offset += 4
            elif tag == "s":
                value, offset = read_osc_string(packet, offset)
                args.append(value)
            else:
                return None
    except (struct.error, ValueError, UnicodeDecodeError):
        return None

    action = address.lstrip("/")
    if action == "rawbytes":
        raw = []
        for arg in args:
            if not isinstance(arg, int) or arg < 0 or arg > 255:
                return None
            raw.append(arg)
        return parse_udp_payload(bytes(raw))

    if action in {"load_index", "setlist/load_index"} and args:
        return {"action": "load_index", "index": args[0]}

    return None


def parse_udp_json(text):
    stripped = text.strip().strip("\x00").strip().rstrip(";").strip()
    if not stripped:
        return None

    if stripped.startswith("{"):
        return json.loads(stripped)

    return None


def parse_udp_payload(packet):
    data = parse_osc_packet(packet)
    if data is not None:
        return data

    try:
        text = packet.decode("utf-8")
    except UnicodeDecodeError:
        return None

    try:
        return parse_udp_json(text)
    except json.JSONDecodeError as e:
        print(f"UDP JSON parse error: {e}")
        return None


def handle_udp_packet(packet, address):
    data = parse_udp_payload(packet)
    if data is None:
        print(f"Ignoring unrecognized UDP packet from {address}: {packet!r}")
        return

    target, status_code, payload = resolve_load_target(data)
    if status_code != 200:
        print(f"Ignoring invalid UDP load request from {address}: {payload}")
        return

    file_path, current_index = target
    print(f"UDP load request from {address}: index={current_index} path={file_path}")
    start_open_thread(file_path, current_index, UDP_OPEN_DELAY_SECONDS)


def serve_udp(stop_event, port):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", port))
        sock.settimeout(0.5)
    except Exception as e:
        print(f"Error starting UDP listener on 127.0.0.1:{port}: {e}")
        traceback.print_exc()
        return

    print(f"UDP fire-and-forget listener started on udp://127.0.0.1:{port}")
    try:
        while not stop_event.is_set():
            try:
                packet, address = sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                if not stop_event.is_set():
                    traceback.print_exc()
                break
            handle_udp_packet(packet, address)
    finally:
        sock.close()


class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        send_cors_headers(self)
        self.end_headers()

    def do_GET(self):
        route = urlparse(self.path).path
        if route == "/status":
            send_json(self, 200, get_status_payload())
            return

        send_json(self, 404, {"ok": False, "error": f"Unknown path: {route}"})

    def do_POST(self):
        route = urlparse(self.path).path
        if route != '/load-set':
            send_json(self, 404, {"ok": False, "error": f"Unknown path: {route}"})
            return

        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length <= 0:
                send_json(self, 400, {"ok": False, "error": "Missing request body"})
                return

            data = json.loads(self.rfile.read(content_length))
            target, status_code, payload = resolve_load_target(data)
            if status_code != 200:
                send_json(self, status_code, payload)
                return

            file_path, current_index = target
            try:
                print(f"Loading set: {file_path}")
                open_ableton_set(file_path, current_index)
            except Exception as e:
                print(f"Error opening file: {file_path}\n{e}")
                traceback.print_exc()
                send_json(self, 500, {"ok": False, "error": "Failed to open file", "path": file_path})
                return
            send_json(self, 200, {"ok": True, "path": file_path, "current_index": CURRENT_INDEX})
        except Exception as e:
            print(f"Error processing request: {e}")
            traceback.print_exc()
            send_json(self, 400, {"ok": False, "error": "Bad request"})


def ensure_ableton_session_open(setlist):
    """Check if Ableton Live is running, and if not, open the first session in setlist.json."""
    try:
        ableton_running = PLATFORM_ADAPTER.is_ableton_running()
    except Exception as e:
        print(f"Error checking Ableton Live process: {e}")
        traceback.print_exc()
        ableton_running = False

    if ableton_running:
        return

    sets = setlist.get("sets")
    if not sets or not isinstance(sets, list):
        print("No sets found in setlist.json")
        return

    file_path = sets[0].get("path")
    if not file_path:
        print("First set path missing in setlist.json")
        return

    file_path = resolve_set_path(file_path, setlist)
    if not os.path.isfile(file_path):
        print(f"First set file not found: {file_path}")
        return

    print(f"Opening first Ableton set: {file_path}")
    try:
        open_ableton_set(file_path, 0)
    except Exception as e:
        print(f"Error opening set file: {file_path}\n{e}")
        traceback.print_exc()


def main():
    global SERVER_PORT, UDP_PORT

    setlist, setlist_error = load_setlist()
    if setlist_error:
        print(setlist_error)

    port, port_error = get_configured_port(setlist)
    udp_port, udp_port_error = get_configured_udp_port(setlist, port)
    if setlist_error:
        print(f"Using default server port {port} so /status can report the problem.")
    elif port_error:
        print(port_error)
        print(f"Using default server port {port} so /status can report the problem.")
    elif udp_port_error:
        print(udp_port_error)
        print(f"Using HTTP server port {port} for UDP.")
    SERVER_PORT = port
    UDP_PORT = udp_port

    if not setlist_error and not port_error:
        ensure_ableton_session_open(setlist)

    DIALOG_HANDLER.start()
    udp_stop_event = threading.Event()
    udp_thread = threading.Thread(
        target=serve_udp,
        args=(udp_stop_event, udp_port),
        daemon=True,
    )
    udp_thread.start()

    try:
        http_server = HTTPServer(('localhost', port), Handler)
        print(f"Ableton Set Manager server started successfully on http://localhost:{port}")
        print(f"UDP port: {udp_port}")
        print(f"Platform adapter: {PLATFORM_ADAPTER.name}")
        print(f"UDP open delay: {UDP_OPEN_DELAY_SECONDS:.3f}s")
        print("Press Ctrl+C to stop the server")
        http_server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Error starting server on port {port}: {e}")
        traceback.print_exc()
    finally:
        udp_stop_event.set()
        udp_thread.join(timeout=1.0)
        DIALOG_HANDLER.stop()


if __name__ == "__main__":
    main()

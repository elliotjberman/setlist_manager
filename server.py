import json
import os
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

from platform_adapters import get_platform_adapter


DEFAULT_SERVER_PORT = 8000
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SETLIST_PATH = os.path.join(SCRIPT_DIR, "setlist.json")
PLATFORM_ADAPTER = get_platform_adapter()
DIALOG_HANDLER = PLATFORM_ADAPTER.create_save_dialog_handler()
SERVER_PORT = DEFAULT_SERVER_PORT
CURRENT_INDEX = None
CURRENT_PATH = None


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


def get_status_payload():
    setlist, setlist_error = load_setlist()
    server_port, port_error = get_configured_port(setlist)
    error = setlist_error or port_error

    return {
        "ok": error is None,
        "error": error,
        "platform": PLATFORM_ADAPTER.name,
        "serverPort": server_port,
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
            file_path = data.get('path')
            if not file_path:
                send_json(self, 400, {"ok": False, "error": "Missing path"})
                return

            setlist, setlist_error = load_setlist()
            if setlist_error:
                send_json(self, 500, {"ok": False, "error": setlist_error})
                return

            file_path = resolve_set_path(file_path, setlist)
            if not os.path.isfile(file_path):
                print(f"Error: File not found - {file_path}")
                send_json(self, 404, {"ok": False, "error": "File not found", "path": file_path})
                return
            try:
                print(f"Loading set: {file_path}")
                open_ableton_set(file_path, data.get("index"))
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
    global SERVER_PORT

    setlist, setlist_error = load_setlist()
    if setlist_error:
        print(setlist_error)

    port, port_error = get_configured_port(setlist)
    if setlist_error:
        print(f"Using default server port {port} so /status can report the problem.")
    elif port_error:
        print(port_error)
        print(f"Using default server port {port} so /status can report the problem.")
    SERVER_PORT = port

    if not setlist_error and not port_error:
        ensure_ableton_session_open(setlist)

    DIALOG_HANDLER.start()

    try:
        http_server = HTTPServer(('localhost', port), Handler)
        print(f"Ableton Set Manager server started successfully on http://localhost:{port}")
        print(f"Platform adapter: {PLATFORM_ADAPTER.name}")
        print("Press Ctrl+C to stop the server")
        http_server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Error starting server on port {port}: {e}")
        traceback.print_exc()
    finally:
        DIALOG_HANDLER.stop()


if __name__ == "__main__":
    main()

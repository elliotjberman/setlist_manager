import json
import os
import traceback
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from save_dialog_handler import AbletonSaveDialogHandler

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != '/load-set':
            return
        
        content_length = int(self.headers['Content-Length'])
        try:
            data = json.loads(self.rfile.read(content_length))
            file_path = data['path']
            # Use basePath from setlist.json if present and file_path is not absolute
            script_dir = os.path.dirname(os.path.abspath(__file__))
            setlist_path = os.path.join(script_dir, 'setlist.json')
            with open(setlist_path, 'r') as f:
                setlist = json.load(f)
            base_path = setlist.get('basePath')
            if base_path and not os.path.isabs(file_path):
                file_path = os.path.join(base_path, file_path)
            if not os.path.isfile(file_path):
                print(f"Error: File not found - {file_path}")
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b'File not found')
                return
            try:
                print(f"Loading set: {file_path}")
                os.startfile(file_path)
            except Exception as e:
                print(f"Error opening file: {file_path}\n{e}")
                traceback.print_exc()
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b'Failed to open file')
                return
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'OK')
        except Exception as e:
            print(f"Error processing request: {e}")
            traceback.print_exc()
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'Bad request')

def ensure_ableton_session_open(setlist):
    """Check if Ableton Live is running, and if not, open the first session in setlist.json."""
    ableton_running = False
    try:
        result = subprocess.run(["tasklist"], capture_output=True, text=True)
        if "Ableton Live" in result.stdout:
            print(result.stdout)
            ableton_running = True
    except Exception as e:
        print(f"Error checking Ableton Live process: {e}")
        traceback.print_exc()

    if not ableton_running:
        sets = setlist.get("sets")
        if sets and isinstance(sets, list) and len(sets) > 0:
            first_set = sets[0]
            file_path = first_set.get("path")
            base_path = setlist.get("basePath")
            if file_path:
                if base_path and not os.path.isabs(file_path):
                    file_path = os.path.join(base_path, file_path)
                if os.path.isfile(file_path):
                    print(f"Opening first Ableton set: {file_path}")
                    try:
                        os.startfile(file_path)
                    except Exception as e:
                        print(f"Error opening set file: {file_path}\n{e}")
                        traceback.print_exc()
                else:
                    print(f"First set file not found: {file_path}")
            else:
                print("First set path missing in setlist.json")
        else:
            print("No sets found in setlist.json")

def main():
    # Load from setlist.json in the same directory as the script itself, not caller, and use the serverPort field on the object
    script_dir = os.path.dirname(os.path.abspath(__file__))
    setlist_path = os.path.join(script_dir, 'setlist.json')
    try:
        with open(setlist_path, 'r') as f:
            setlist = json.load(f)
    except FileNotFoundError:
        print(f"Error: setlist.json not found at {setlist_path}")
        return
    except Exception as e:
        print(f"Error loading setlist.json: {e}")
        traceback.print_exc()
        return
    port = setlist.get('serverPort')
    if not isinstance(port, int):
        print("Error: serverPort missing or not an integer in setlist.json")
        return

    ensure_ableton_session_open(setlist)

    # Start the save dialog handler
    dialog_handler = AbletonSaveDialogHandler()
    dialog_handler.start()

    try:
        print(f"Ableton Set Manager server started successfully on http://localhost:{port}")
        print("Save dialog handler is running in background")
        print("Press Ctrl+C to stop the server")
        HTTPServer(('localhost', port), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        dialog_handler.stop()
    except Exception as e:
        print(f"Error starting server on port {port}: {e}")
        traceback.print_exc()
        dialog_handler.stop()

if __name__ == "__main__":
    main()
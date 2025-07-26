import json
import os
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != '/load-set':
            return
        
        content_length = int(self.headers['Content-Length'])
        try:
            data = json.loads(self.rfile.read(content_length))
            file_path = data['path']
            if not os.path.isfile(file_path):
                print(f"Error: File not found - {file_path}")
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b'File not found')
                return
            try:
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
    try:
        print(f"Ableton Set Manager server started successfully on http://localhost:{port}")
        print("Press Ctrl+C to stop the server")
        HTTPServer(('localhost', port), Handler).serve_forever()
    except Exception as e:
        print(f"Error starting server on port {port}: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
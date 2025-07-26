import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        print("Posted")
        if self.path != '/load-set':
            return
        
        content_length = int(self.headers['Content-Length'])
        data = json.loads(self.rfile.read(content_length))
        
        os.startfile(data['path'])
        
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'OK')

HTTPServer(('localhost', 8080), Handler).serve_forever()
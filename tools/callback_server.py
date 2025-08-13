import http.server, socketserver, urllib.parse, webbrowser

PORT = 5000
class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/callback"):
            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            code = params.get("code", [None])[0]
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<h2>OK! Du kan lukke dette vinduet.</h2>")
            if code:
                print("\nAUTHORIZATION CODE:\n", code, "\n")
        else:
            self.send_response(404); self.end_headers()

with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
    print(f"Callback server lytter på http://127.0.0.1:{PORT}/callback")
    webbrowser.open(f"http://127.0.0.1:{PORT}/callback")
    httpd.serve_forever()

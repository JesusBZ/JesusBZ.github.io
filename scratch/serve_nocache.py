import http.server, functools, sys

ROOT = r"C:\Users\jesus\OneDrive\Documentos\GitHub\JesusBZ.github.io"

class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def send_head(self):
        # Ignore conditional requests so the browser never gets a stale 304
        if "If-Modified-Since" in self.headers:
            del self.headers["If-Modified-Since"]
        return super().send_head()

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    handler = functools.partial(NoCacheHandler, directory=ROOT)
    with http.server.ThreadingHTTPServer(("", port), handler) as httpd:
        print(f"No-cache server on http://localhost:{port}")
        httpd.serve_forever()

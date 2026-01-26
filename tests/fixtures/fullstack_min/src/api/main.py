"""Minimal API module for testing."""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json


class HealthHandler(BaseHTTPRequestHandler):
    """Simple health check handler."""
    
    def do_GET(self):
        """Handle GET requests."""
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Suppress logging."""
        pass


def create_app():
    """Create the HTTP server."""
    return HTTPServer(("127.0.0.1", 8000), HealthHandler)


def main():
    """Run the server."""
    server = create_app()
    print("Server running on http://127.0.0.1:8000")
    server.serve_forever()


if __name__ == "__main__":
    main()

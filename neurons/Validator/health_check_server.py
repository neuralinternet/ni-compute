#!/usr/bin/env python3
"""
Health Check Server Script

This script runs on the miner to provide an HTTP health check endpoint.
"""

import http.server
import socketserver
import time
import sys
import argparse


class HealthCheckHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for health check endpoint"""

    def do_GET(self):
        """Handle GET requests to the health check endpoint"""
        if self.path == '/health' or self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"Health OK")
        else:
            self.send_response(404)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"Not Found")

    def do_HEAD(self):
        """Handle HEAD requests (for health checks that don't need body)"""
        if self.path == '/health' or self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
        else:
            self.send_response(404)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()

    def log_message(self, format, *args):
        """Override to use our custom logging format"""
        print(f"Health check server: {format % args}")


class TimeoutHTTPServer(socketserver.TCPServer):
    """HTTP server with timeout functionality"""

    def __init__(self, server_address, RequestHandlerClass, timeout=60):
        self.timeout = timeout
        self.start_time = time.time()
        super().__init__(server_address, RequestHandlerClass)
        self.allow_reuse_address = True

    def verify_request(self, request, client_address):
        """Check if we should continue accepting requests based on timeout"""
        if time.time() - self.start_time > self.timeout:
            print(f"Health check server: Timeout reached ({self.timeout}s) - stopping")
            return False
        return True


def create_health_check_server(port=27015, timeout=60, host='0.0.0.0'):
    """
    Creates a HTTP server for health check.

    Args:
        port (int): Port to listen on
        timeout (int): Maximum wait time in seconds (default 60 seconds)
        host (str): Host to bind to (default '0.0.0.0' for all interfaces)
    """
    try:
        print(f"Health check server: Starting on {host}:{port} (timeout: {timeout}s)")

        # Create the server
        server = TimeoutHTTPServer((host, port), HealthCheckHandler, timeout)

        print(f"Health check server: Ready - endpoints: /health, /")

        # Start the server
        server.serve_forever()

    except OSError as e:
        print(f"Health check server: Error - {e}")
        if e.errno == 98:  # Address already in use
            print(f"Health check server: Port {port} is already in use")
        elif e.errno == 13:  # Permission denied
            print(f"Health check server: Permission denied to bind to port {port}")
        sys.exit(1)
    except KeyboardInterrupt:
        print(f"Health check server: Shutting down")
    except Exception as e:
        print(f"Health check server: Unexpected error - {e}")
        sys.exit(1)
    finally:
        if 'server' in locals():
            server.shutdown()
            server.server_close()


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Health Check HTTP Server')
    parser.add_argument('--port', type=int, default=27015,
                       help='Port for health check server (default: 27015)')
    parser.add_argument('--timeout', type=int, default=60,
                       help='Timeout in seconds for server (default: 60)')
    parser.add_argument('--host', type=str, default='0.0.0.0',
                       help='Host to bind to (default: 0.0.0.0)')

    args = parser.parse_args()

    create_health_check_server(args.port, args.timeout, args.host)


if __name__ == "__main__":
    main()

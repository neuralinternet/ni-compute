#!/usr/bin/env python3
"""
Health Check Server Script

This script runs on the miner to provide an HTTP health check endpoint.
It runs in the background using Paramiko channels.
"""

import socket
import threading
import time
import sys
import os

def create_health_check_server(port=27015, timeout=30):
    """
    Creates a simple HTTP server for health check.

    Args:
        port (int): Port to listen on
        timeout (int): Maximum wait time in seconds
    """
    try:
        print(f"Health check server: Initializing on port {port} with timeout {timeout}s")
        print(f"Health check server: Current working directory: {os.getcwd()}")
        print(f"Health check server: Python executable: {sys.executable}")
        print(f"Health check server: Process ID: {os.getpid()}")
        print(f"Health check server: User ID: {os.getuid() if hasattr(os, 'getuid') else 'N/A'}")

        # Create socket
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Bind to all interfaces
        print(f"Health check server: Attempting to bind to 0.0.0.0:{port}")
        server_socket.bind(('0.0.0.0', port))
        server_socket.listen(1)
        server_socket.settimeout(timeout)

        print(f"Health check server: Successfully started on port {port}, waiting for connection (timeout: {timeout}s)...")
        print(f"Health check server: Socket bound to 0.0.0.0:{port}")
        print(f"Health check server: Server is listening and ready for connections")

        # Wait for connection
        try:
            print(f"Health check server: Waiting for incoming connection...")
            client_socket, address = server_socket.accept()
            print(f"Health check server: Received connection from {address}")

            # Send simple HTTP response
            response = "HTTP/1.1 200 OK\r\n"
            response += "Content-Type: text/plain\r\n"
            response += "Content-Length: 13\r\n"
            response += "\r\n"
            response += "Health OK"

            client_socket.send(response.encode())
            client_socket.close()
            print(f"Health check server: Sent response and shutting down")

        except socket.timeout:
            print(f"Health check server: Timed out after {timeout} seconds - no connections received")
        finally:
            server_socket.close()
            print(f"Health check server: Socket closed")

    except socket.error as e:
        print(f"Health check server: Socket error - {e}")
        print(f"Health check server: Error type: {type(e).__name__}")
        if e.errno == 98:  # Address already in use
            print(f"Health check server: Port {port} is already in use")
        elif e.errno == 13:  # Permission denied
            print(f"Health check server: Permission denied to bind to port {port}")
        import traceback
        print(f"Health check server: Traceback: {traceback.format_exc()}")
        sys.exit(1)
    except Exception as e:
        print(f"Health check server: Error - {e}")
        print(f"Health check server: Error type: {type(e).__name__}")
        import traceback
        print(f"Health check server: Traceback: {traceback.format_exc()}")
        sys.exit(1)

def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description='Health Check Server')
    parser.add_argument('--port', type=int, default=27015,
                       help='Port for health check server (internal container port)')
    parser.add_argument('--timeout', type=int, default=30,
                       help='Timeout in seconds for waiting connection')

    args = parser.parse_args()

    print(f"Health check server: Starting with args: port={args.port}, timeout={args.timeout}")
    create_health_check_server(args.port, args.timeout)

if __name__ == "__main__":
    main()

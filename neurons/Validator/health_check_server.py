#!/usr/bin/env python3
"""
Health Check Server Script

This script runs on the miner to provide an HTTP health check endpoint.
It waits for a single connection from the validator, responds with "Health OK",
and then terminates successfully.
"""

import socket
import threading
import time
import sys
import os

def create_health_check_server(port=27015, timeout=None):
    """
    Creates a simple HTTP server for health check.

    Args:
        port (int): Port to listen on
        timeout (int): Maximum wait time in seconds (None for infinite wait)
    """
    try:
        print(f"Health check server: Initializing on port {port}")
        print(f"Health check server: Current working directory: {os.getcwd()}")
        print(f"Health check server: Python executable: {sys.executable}")
        print(f"Health check server: Process ID: {os.getpid()}")
        print(f"Health check server: User ID: {os.getuid() if hasattr(os, 'getuid') else 'N/A'}")
        print(f"Health check server: Starting server initialization...")

        # Create socket
        print(f"Health check server: Creating socket...")
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print(f"Health check server: Socket created successfully")
        
        # Set socket options
        print(f"Health check server: Setting socket options...")
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        print(f"Health check server: Socket options set successfully")

        # Bind to all interfaces
        print(f"Health check server: Attempting to bind to 0.0.0.0:{port}")
        try:
            server_socket.bind(('0.0.0.0', port))
            print(f"Health check server: Successfully bound to 0.0.0.0:{port}")
        except socket.error as bind_error:
            print(f"Health check server: Bind error - {bind_error}")
            print(f"Health check server: Bind error type: {type(bind_error).__name__}")
            if hasattr(bind_error, 'errno'):
                print(f"Health check server: Bind error number: {bind_error.errno}")
            raise bind_error

        print(f"Health check server: Starting to listen...")
        server_socket.listen(1)
        print(f"Health check server: Listening started successfully")
        
        # Set timeout (None for infinite wait, or a longer timeout)
        if timeout is None:
            server_socket.settimeout(None)  # Wait indefinitely
            print(f"Health check server: Socket timeout set to infinite wait")
        else:
            server_socket.settimeout(timeout)
            print(f"Health check server: Socket timeout set to {timeout}s")

        print(f"Health check server: Successfully started on port {port}")
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
        if hasattr(e, 'errno'):
            print(f"Health check server: Error number: {e.errno}")
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
    parser.add_argument('--timeout', type=int, default=None,
                       help='Timeout in seconds for waiting connection (None for infinite wait)')

    args = parser.parse_args()

    print(f"Health check server: Starting with args: port={args.port}, timeout={args.timeout}")
    print(f"Health check server: Main function called successfully")
    create_health_check_server(args.port, args.timeout)

if __name__ == "__main__":
    print(f"Health check server: Script started")
    main()

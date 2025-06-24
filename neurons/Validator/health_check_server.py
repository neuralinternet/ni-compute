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

        # Create socket
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('0.0.0.0', port))
        server_socket.listen(1)
        server_socket.settimeout(timeout)

        print(f"Health check server: Started on port {port}, waiting for connection (timeout: {timeout}s)...")

        # Wait for connection
        try:
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
            print(f"Health check server: Timed out after {timeout} seconds")
        finally:
            server_socket.close()
            print(f"Health check server: Socket closed")

    except Exception as e:
        print(f"Health check server: Error - {e}")
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

    create_health_check_server(args.port, args.timeout)

if __name__ == "__main__":
    main()

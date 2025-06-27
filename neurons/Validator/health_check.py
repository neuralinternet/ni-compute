#!/usr/bin/env python3
"""
Health Check Module

This module handles healthcheck independently from POG (Proof of Generation).
It runs after POG has finished to verify miner connectivity.
"""

import paramiko
import time
import bittensor as bt
import requests

def upload_health_check_script(ssh_client, health_check_script_path):
    """
    Uploads the health check script to the miner using SFTP.

    Args:
        ssh_client (paramiko.SSHClient): SSH client connected to the miner
        health_check_script_path (str): Local path of the health check script

    Returns:
        bool: True if uploaded successfully, False otherwise
    """
    try:
        sftp = ssh_client.open_sftp()
        sftp.put(health_check_script_path, "/tmp/health_check_server.py")
        sftp.chmod("/tmp/health_check_server.py", 0o755)
        sftp.close()
        return True
    except Exception as e:
        bt.logging.error(f"Error uploading health check script: {e}")
        return False

def start_health_check_server_background(ssh_client, port=27015, timeout=60):
    """
    Starts the health check server using Paramiko channels.

    Args:
        ssh_client (paramiko.SSHClient): SSH client connected to the miner
        port (int): Port for the health check server
        timeout (int): Wait time in seconds (default 60 seconds)

    Returns:
        bool: True if started successfully, False otherwise
    """
    try:
        # Use paramiko transport and channel
        transport = ssh_client.get_transport()
        channel = transport.open_session()

        # Execute the health check server command using channel
        channel.exec_command(f"python3 /tmp/health_check_server.py --port {port} --timeout {timeout}")

        # Give a small time for the server to start
        time.sleep(3)

        # Check if the channel is still active (server is running)
        if not channel.closed:
            return True
        else:
            # Collect output for debugging when channel is closed
            stdout_output = ""
            stderr_output = ""

            # Read stdout if available
            if channel.recv_ready():
                stdout_output = channel.recv(4096).decode('utf-8')

            # Read stderr if available
            if channel.recv_stderr_ready():
                stderr_output = channel.recv_stderr(4096).decode('utf-8')

            bt.logging.error(f"Health check server channel is closed")
            if stdout_output:
                bt.logging.error(f"Server stdout: {stdout_output}")
            if stderr_output:
                bt.logging.error(f"Server stderr: {stderr_output}")
            return False

    except Exception as e:
        bt.logging.error(f"Error starting health check server: {e}")
        return False

def wait_for_health_check(host, port, timeout=30, retry_interval=1):
    """
    Waits for the health check server to be available via HTTP.

    Args:
        host (str): Miner host
        port (int): Health check server port
        timeout (int): Maximum wait time in seconds
        retry_interval (int): Interval between retries in seconds

    Returns:
        bool: True if health check is successful, False otherwise
    """
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            response = requests.get(f"http://{host}:{port}", timeout=2)

            if response.status_code == 200:
                return True

        except requests.exceptions.ConnectionError as e:
            bt.logging.trace(f"Connection error to {host}:{port}: {e}")
        except requests.exceptions.Timeout as e:
            bt.logging.trace(f"Timeout error to {host}:{port}: {e}")
        except requests.exceptions.RequestException as e:
            bt.logging.trace(f"Request error to {host}:{port}: {e}")

        time.sleep(retry_interval)

    return False

def perform_health_check(axon, miner_info, config_data):
    """
    Performs health check on a miner after POG has finished.

    Args:
        axon: Axon information of the miner
        miner_info: Miner information (host, port, etc.) - always provided by POG
        config_data: Validator configuration

    Returns:
        bool: True if health check is successful, False otherwise
    """
    hotkey = axon.hotkey
    host = None
    ssh_client = None

    try:
        host = miner_info['host']

        # Connect via SSH
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh_client.connect(host, port=miner_info.get('port', 22), username=miner_info['username'], password=miner_info['password'], timeout=10)
        except Exception as ssh_error:
            bt.logging.info(f"{hotkey}: SSH connection failed during health check: {ssh_error}")
            return False

        # Health check script path
        health_check_script_path = "neurons/Validator/health_check_server.py"

        # Upload health check script
        if not upload_health_check_script(ssh_client, health_check_script_path):
            bt.logging.error(f"{hotkey}: Failed to upload health check script.")
            return False

        # Start health check server in background
        internal_health_check_port = 27015
        if not start_health_check_server_background(ssh_client, internal_health_check_port, timeout=60):
            bt.logging.error(f"{hotkey}: Failed to start health check server.")
            return False

        # Wait for health check server to be ready
        external_health_check_port = miner_info.get('fixed_external_user_port', 27015)
        health_check_timeout = 30
        health_check_retry_interval = 1

        if not wait_for_health_check(host, external_health_check_port, timeout=health_check_timeout, retry_interval=health_check_retry_interval):
            bt.logging.error(f"{hotkey}: Health check server not responding.")
            return False

        return True

    except Exception as e:
        bt.logging.info(f"❌ {hotkey}: Error during health check: {e}")
        return False

    finally:
        if ssh_client is not None:
            try:
                ssh_client.close()
            except Exception as e:
                bt.logging.trace(f"{hotkey}: Error closing SSH connection: {e}")

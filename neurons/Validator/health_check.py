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
        bt.logging.trace(f"Uploading health check script from {health_check_script_path} to /tmp/health_check_server.py")
        sftp = ssh_client.open_sftp()
        sftp.put(health_check_script_path, "/tmp/health_check_server.py")
        sftp.close()
        bt.logging.trace("Health check script uploaded successfully")
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
        bt.logging.trace(f"Starting health check server on port {port} with timeout {timeout}s")

        # Make script executable
        bt.logging.trace("Making script executable...")
        chmod_command = "chmod +x /tmp/health_check_server.py"
        stdin, stdout, stderr = ssh_client.exec_command(chmod_command)
        chmod_result = stdout.read().decode().strip()
        bt.logging.trace(f"Chmod result: {chmod_result}")

        # Use paramiko transport and channel
        bt.logging.trace("Creating Paramiko channel for health check server...")
        transport = ssh_client.get_transport()
        channel = transport.open_session()

        # Execute the health check server command using channel
        channel.exec_command(f"python3 /tmp/health_check_server.py --port {port} --timeout {timeout}")

        # Give a small time for the server to start
        bt.logging.trace("Waiting 3 seconds for server to start...")
        time.sleep(3)

        # Collect any output from the channel
        bt.logging.trace("Collecting server output from channel...")
        stdout_output = ""
        stderr_output = ""

        # Read stdout if available
        if channel.recv_ready():
            stdout_output = channel.recv(4096).decode('utf-8')
            bt.logging.trace(f"Server stdout: {stdout_output}")

        # Read stderr if available
        if channel.recv_stderr_ready():
            stderr_output = channel.recv_stderr(4096).decode('utf-8')
            bt.logging.trace(f"Server stderr: {stderr_output}")

        # Check if the channel is still active (server is running)
        if not channel.closed:
            bt.logging.trace("✅ Health check server channel is active")
        else:
            bt.logging.trace("❌ Health check server channel is closed")

        # Check if the process is running
        bt.logging.trace("Checking if health check server process is running...")
        ps_command = "ps aux | grep health_check_server | grep -v grep"
        stdin2, stdout2, stderr2 = ssh_client.exec_command(ps_command)
        process_info = stdout2.read().decode().strip()
        bt.logging.trace(f"Process info: {process_info}")

        if process_info:
            bt.logging.trace("✅ Health check server process is running")
        else:
            bt.logging.trace("❌ Health check server process is NOT running")

        # Check if the port is now listening
        bt.logging.trace(f"Checking if port {port} is now listening...")
        listen_check = f"netstat -tlnp 2>/dev/null | grep :{port} || echo 'Port not listening'"
        stdin3, stdout3, stderr3 = ssh_client.exec_command(listen_check)
        listen_info = stdout3.read().decode().strip()
        bt.logging.trace(f"Port {port} listening status: {listen_info}")

        if "Port not listening" in listen_info:
            bt.logging.trace(f"❌ Port {port} is NOT listening")
        else:
            bt.logging.trace(f"✅ Port {port} is listening")

        # Test if the server is actually responding locally
        bt.logging.trace("Testing if health check server responds locally...")
        local_test = f"timeout 5 curl -s http://localhost:{port} 2>/dev/null || echo 'Local connection failed'"
        stdin4, stdout4, stderr4 = ssh_client.exec_command(local_test)
        local_response = stdout4.read().decode().strip()
        bt.logging.trace(f"Local test response: {local_response}")

        if local_response == "Health OK":
            bt.logging.trace("✅ Health check server responds correctly locally")
        elif local_response == "Local connection failed":
            bt.logging.trace("❌ Health check server does not respond locally")
        else:
            bt.logging.trace(f"⚠️ Health check server responds with unexpected content: {local_response}")

        # Check if curl is available
        if local_response == "Local connection failed":
            bt.logging.trace("curl not available, trying with wget...")
            wget_test = f"timeout 5 wget -qO- http://localhost:{port} 2>/dev/null || echo 'Local connection failed'"
            stdin5, stdout5, stderr5 = ssh_client.exec_command(wget_test)
            wget_response = stdout5.read().decode().strip()
            bt.logging.trace(f"Wget test response: {wget_response}")

            if wget_response == "Health OK":
                bt.logging.trace("✅ Health check server responds correctly via wget")
            elif wget_response == "Local connection failed":
                bt.logging.trace("❌ Health check server does not respond via wget")
            else:
                bt.logging.trace(f"⚠️ Health check server responds with unexpected content via wget: {wget_response}")

            # If wget also fails, try with netcat
            if wget_response == "Local connection failed":
                bt.logging.trace("wget also failed, trying with netcat...")
                nc_test = f"timeout 5 bash -c 'echo -e \"GET / HTTP/1.1\\r\\nHost: localhost\\r\\n\\r\\n\" | nc localhost {port}' 2>/dev/null || echo 'Local connection failed'"
                stdin6, stdout6, stderr6 = ssh_client.exec_command(nc_test)
                nc_response = stdout6.read().decode().strip()
                bt.logging.trace(f"Netcat test response: {nc_response}")

                if "Health OK" in nc_response:
                    bt.logging.trace("✅ Health check server responds correctly via netcat")
                elif nc_response == "Local connection failed":
                    bt.logging.trace("❌ Health check server does not respond via netcat")
                else:
                    bt.logging.trace(f"⚠️ Health check server responds with unexpected content via netcat: {nc_response}")

        bt.logging.trace("Health check server execution completed")
        return True

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
    bt.logging.trace(f"Waiting for health check server on {host}:{port} (timeout: {timeout}s, retry interval: {retry_interval}s)")

    start_time = time.time()
    attempt_count = 0

    while time.time() - start_time < timeout:
        attempt_count += 1
        try:
            bt.logging.trace(f"Health check attempt {attempt_count}: trying to connect to http://{host}:{port}")
            response = requests.get(f"http://{host}:{port}", timeout=2)
            bt.logging.trace(f"Health check attempt {attempt_count}: received response status {response.status_code}")

            if response.status_code == 200:
                bt.logging.trace(f"Health check successful on {host}:{port} after {attempt_count} attempts")
                bt.logging.success(f"Health check successful on {host}:{port}")
                return True
            else:
                bt.logging.trace(f"Health check attempt {attempt_count}: unexpected status code {response.status_code}")

        except requests.exceptions.ConnectionError as e:
            bt.logging.trace(f"Health check attempt {attempt_count}: connection error - {e}")
        except requests.exceptions.Timeout as e:
            bt.logging.trace(f"Health check attempt {attempt_count}: timeout error - {e}")
        except requests.exceptions.RequestException as e:
            bt.logging.trace(f"Health check attempt {attempt_count}: request error - {e}")

        if attempt_count % 5 == 0:  # Log every 5 attempts
            elapsed = time.time() - start_time
            bt.logging.trace(f"Health check: {attempt_count} attempts made, {elapsed:.1f}s elapsed, {timeout - elapsed:.1f}s remaining")

        time.sleep(retry_interval)

    bt.logging.trace(f"Health check failed on {host}:{port} after {attempt_count} attempts and {timeout} seconds")
    bt.logging.error(f"Health check failed on {host}:{port} after {timeout} seconds")
    return False

def get_health_check_server_logs(ssh_client):
    """
    Retrieves and displays the health check server logs from /tmp/health_check.log.

    Args:
        ssh_client (paramiko.SSHClient): SSH client connected to the miner

    Returns:
        str: Log content or error message
    """
    try:
        bt.logging.trace("Reading health check server logs from /tmp/health_check.log...")

        # Read the log file content
        log_command = "cat /tmp/health_check.log 2>/dev/null || echo 'No log file found'"
        stdin, stdout, stderr = ssh_client.exec_command(log_command)
        log_content = stdout.read().decode().strip()

        if log_content and log_content != "No log file found":
            bt.logging.trace(f"Health check server logs:\n{log_content}")
            return log_content
        else:
            bt.logging.trace("No health check server logs found in /tmp/health_check.log")
            return "No log file found"

    except Exception as e:
        bt.logging.trace(f"Error reading health check server logs: {e}")
        return f"Error reading logs: {e}"

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

    bt.logging.trace(f"{hotkey}: Starting health check.")
    bt.logging.trace(f"{hotkey}: [Health Check] Step 1: Validating miner information...")

    try:
        host = miner_info['host']

        bt.logging.trace(f"{hotkey}: [Health Check] Step 2: Establishing SSH connection...")
        bt.logging.trace(f"{hotkey}: [Health Check] Connecting to {host}:{miner_info.get('port', 22)}")

        # Connect via SSH
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        bt.logging.trace(f"{hotkey}: Connecting to miner via SSH for health check.")
        try:
            ssh_client.connect(host, port=miner_info.get('port', 22), username=miner_info['username'], password=miner_info['password'], timeout=10)
            bt.logging.trace(f"{hotkey}: Connected to miner via SSH for health check.")
            bt.logging.trace(f"{hotkey}: [Health Check] SSH connection established successfully")
        except Exception as ssh_error:
            bt.logging.info(f"{hotkey}: SSH connection failed during health check: {ssh_error}")
            bt.logging.trace(f"{hotkey}: [Health Check] ERROR: SSH connection failed")
            return False

        # Health check script path
        health_check_script_path = "neurons/Validator/health_check_server.py"
        bt.logging.trace(f"{hotkey}: [Health Check] Step 3: Uploading health check script...")

        # Upload health check script
        bt.logging.trace(f"{hotkey}: Uploading health check script...")
        if not upload_health_check_script(ssh_client, health_check_script_path):
            bt.logging.error(f"{hotkey}: Failed to upload health check script.")
            bt.logging.trace(f"{hotkey}: [Health Check] ERROR: Failed to upload health check script")
            return False

        bt.logging.trace(f"{hotkey}: Health check script uploaded successfully.")
        bt.logging.trace(f"{hotkey}: [Health Check] Health check script uploaded successfully")

        # Start health check server in background
        internal_health_check_port = 27015
        bt.logging.trace(f"{hotkey}: [Health Check] Step 4: Starting health check server...")
        bt.logging.trace(f"{hotkey}: Starting health check server on internal port {internal_health_check_port}...")

        if not start_health_check_server_background(ssh_client, internal_health_check_port, timeout=60):
            bt.logging.error(f"{hotkey}: Failed to start health check server.")
            bt.logging.trace(f"{hotkey}: [Health Check] ERROR: Failed to start health check server")
            return False

        bt.logging.trace(f"{hotkey}: Health check server started in background.")
        bt.logging.trace(f"{hotkey}: [Health Check] Health check server started successfully")

        # Additional verification of server status
        bt.logging.trace(f"{hotkey}: [Health Check] Verifying server status...")

        # Check if process is still running
        ps_command = "ps aux | grep health_check_server | grep -v grep"
        stdin, stdout, stderr = ssh_client.exec_command(ps_command)
        process_info = stdout.read().decode().strip()
        if process_info:
            bt.logging.trace(f"{hotkey}: [Health Check] ✅ Server process is running")
            bt.logging.trace(f"{hotkey}: [Health Check] Process details: {process_info}")
        else:
            bt.logging.trace(f"{hotkey}: [Health Check] ❌ Server process is NOT running")

        # Check if port is listening
        listen_check = f"netstat -tlnp 2>/dev/null | grep :{internal_health_check_port} || echo 'Port not listening'"
        stdin, stdout, stderr = ssh_client.exec_command(listen_check)
        listen_info = stdout.read().decode().strip()
        if "Port not listening" not in listen_info:
            bt.logging.trace(f"{hotkey}: [Health Check] ✅ Port {internal_health_check_port} is listening")
            bt.logging.trace(f"{hotkey}: [Health Check] Port details: {listen_info}")
        else:
            bt.logging.trace(f"{hotkey}: [Health Check] ❌ Port {internal_health_check_port} is NOT listening")

        # Test local connectivity
        bt.logging.trace(f"{hotkey}: [Health Check] Testing local connectivity...")
        local_test = f"timeout 5 curl -s http://localhost:{internal_health_check_port} 2>/dev/null || echo 'Local connection failed'"
        stdin, stdout, stderr = ssh_client.exec_command(local_test)
        local_response = stdout.read().decode().strip()
        bt.logging.trace(f"{hotkey}: [Health Check] Local test response: {local_response}")

        if local_response == "Health OK":
            bt.logging.trace(f"{hotkey}: [Health Check] ✅ Local connectivity successful")
        else:
            bt.logging.trace(f"{hotkey}: [Health Check] ❌ Local connectivity failed: {local_response}")

        # Wait for health check server to be ready
        external_health_check_port = miner_info.get('fixed_external_user_port', 27015)
        bt.logging.trace(f"{hotkey}: [Health Check] Step 5: Waiting for server to be ready...")
        bt.logging.trace(f"{hotkey}: Waiting for health check server to be ready...")
        bt.logging.trace(f"{hotkey}: Validator attempting to connect to health check server on {host}:{external_health_check_port}")

        # Use default health check configuration values
        health_check_timeout = 30  # Default timeout
        health_check_retry_interval = 1  # Default retry interval

        bt.logging.trace(f"{hotkey}: [Health Check] Testing connectivity with timeout: {health_check_timeout}s, retry interval: {health_check_retry_interval}s")

        if not wait_for_health_check(host, external_health_check_port, timeout=health_check_timeout, retry_interval=health_check_retry_interval):
            bt.logging.error(f"{hotkey}: Health check server not responding.")
            bt.logging.trace(f"{hotkey}: Health check failed - validator cannot access the health check server")
            bt.logging.trace(f"{hotkey}: [Health Check] ERROR: Health check server not responding")

            # Check final status before failing
            bt.logging.trace(f"{hotkey}: [Health Check] Final status check before failure...")
            ps_command = "ps aux | grep health_check_server | grep -v grep"
            stdin, stdout, stderr = ssh_client.exec_command(ps_command)
            final_process_info = stdout.read().decode().strip()
            bt.logging.trace(f"{hotkey}: [Health Check] Final process status: {final_process_info}")

            bt.logging.trace(f"{hotkey}: [Health Check] Server output was captured from channel during startup")

            return False

        bt.logging.success(f"{hotkey}: Health check server is ready and responding.")
        bt.logging.trace(f"{hotkey}: Health check successful - validator has access to the health check server")
        bt.logging.trace(f"{hotkey}: [Health Check] SUCCESS: Health check completed successfully")

        return True

    except Exception as e:
        bt.logging.info(f"❌ {hotkey}: Error during health check: {e}")
        bt.logging.trace(f"{hotkey}: [Health Check] ERROR: Exception during health check: {e}")
        return False

    finally:
        if ssh_client is not None:
            try:
                ssh_client.close()
                bt.logging.trace(f"{hotkey}: SSH connection closed")
                bt.logging.trace(f"{hotkey}: [Health Check] SSH connection closed")
            except Exception as close_error:
                bt.logging.trace(f"{hotkey}: Error closing SSH connection: {close_error}")

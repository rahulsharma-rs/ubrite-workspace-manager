import subprocess
import os
import signal
import psutil
import json
import tempfile
import time
import logging
import socket
import shutil
import sys
import random
import glob
from pathlib import Path
from flask import current_app, request


class IDEService:
    def __init__(self):
        self._jupyter_path = None
        self.processes = {}
        # Store the token and port for each workspace
        self.tokens = {}
        self.ports = {}

    @property
    def jupyter_path(self):
        if self._jupyter_path is None:
            self._jupyter_path = current_app.config.get('JUPYTER_PATH', 'jupyter')

            # If jupyter_path is just 'jupyter', try to find the full path
            if self._jupyter_path == 'jupyter':
                # Try to find jupyter in the PATH
                jupyter_in_path = shutil.which('jupyter')
                if jupyter_in_path:
                    self._jupyter_path = jupyter_in_path
                    logging.info(f"Found jupyter at: {jupyter_in_path}")

        logging.info(f"Using jupyter path: {self._jupyter_path}")
        return self._jupyter_path

    def get_host_ip(self):
        """Get the host IP address that should be used for external access."""
        # First, try to get the host from the request
        if request:
            host = request.host.split(':')[0]
            if host != 'localhost' and host != '127.0.0.1' and host != '0.0.0.0':
                return host

        # If that doesn't work, try to get the server's IP address
        try:
            # Get the primary IP address
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Doesn't need to be reachable
            s.connect(('10.255.255.255', 1))
            ip = s.getsockname()[0]
            s.close()
            if ip != '0.0.0.0':
                return ip
        except Exception:
            pass

        # Try to get the hostname's IP
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            if ip != '0.0.0.0' and ip != '127.0.0.1':
                return ip
        except Exception:
            pass

        # Fall back to localhost if we can't determine the IP
        return 'localhost'

    def _is_port_in_use(self, port):
        """Check if a port is in use."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) == 0

    def _kill_existing_jupyter_processes(self):
        """Kill any existing JupyterLab processes that might be running."""
        try:
            # Find all python processes
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = proc.info.get('cmdline', [])
                    # Check if this is a jupyter-lab process
                    if cmdline and len(cmdline) > 1 and (
                            'jupyter-lab' in cmdline[0] or ('jupyter' in cmdline[0] and 'lab' in cmdline)):
                        logging.info(f"Found existing JupyterLab process: {proc.info['pid']}")
                        # Kill the process
                        process = psutil.Process(proc.info['pid'])
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except psutil.TimeoutExpired:
                            process.kill()
                        logging.info(f"Killed existing JupyterLab process: {proc.info['pid']}")
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
        except Exception as e:
            logging.exception(f"Error killing existing JupyterLab processes: {str(e)}")

    def launch_jupyter(self, workspace_path):
        """Launch JupyterLab for a workspace."""
        logging.info(f"Launching JupyterLab for workspace: {workspace_path}")

        # Ensure workspace_path is absolute and normalized
        workspace_path = os.path.abspath(os.path.normpath(workspace_path))
        logging.info(f"Normalized workspace path: {workspace_path}")

        # Check if workspace path exists
        if not os.path.exists(workspace_path):
            logging.error(f"Workspace path does not exist: {workspace_path}")
            return False, f"Workspace path does not exist: {workspace_path}"

        # Check if JupyterLab is installed
        jupyter_check, jupyter_message = self.check_jupyter_installation()
        if not jupyter_check:
            logging.error(f"JupyterLab is not installed: {jupyter_message}")
            return False, f"JupyterLab is not installed: {jupyter_message}"

        # Get workspace name
        workspace_name = os.path.basename(workspace_path)

        # Kill any existing JupyterLab processes to avoid conflicts
        self._kill_existing_jupyter_processes()

        # Check if env directory exists
        env_path = os.path.join(workspace_path, 'env')
        if not os.path.exists(env_path):
            logging.warning(f"Environment directory not found: {env_path}")
            logging.info("Will try to launch JupyterLab using system Python")

        # Determine if we should use the environment's jupyter or system jupyter
        jupyter_cmd = self.jupyter_path

        # Check if jupyter exists in the environment
        env_jupyter = None
        if os.path.exists(env_path):
            if os.path.exists(os.path.join(env_path, 'bin', 'jupyter')):
                env_jupyter = os.path.join(env_path, 'bin', 'jupyter')
            elif os.path.exists(os.path.join(env_path, 'Scripts', 'jupyter.exe')):
                env_jupyter = os.path.join(env_path, 'Scripts', 'jupyter.exe')

        if env_jupyter:
            jupyter_cmd = env_jupyter
            logging.info(f"Using environment's jupyter: {jupyter_cmd}")
        else:
            logging.info(f"Using system jupyter: {jupyter_cmd}")

        # Generate a random token for security
        import secrets
        token = secrets.token_hex(16)

        # Use a fixed port (8888) instead of a random port
        port = 8888

        # Check if the port is in use, and if so, try the next port
        while self._is_port_in_use(port):
            port += 1
            if port > 8900:  # Limit the search to a reasonable range
                port = 8888
                break

        # Store the token and port for this workspace
        self.tokens[workspace_name] = token
        self.ports[workspace_name] = port

        # Get the host from the request
        flask_host = None
        flask_port = None
        if request:
            try:
                flask_host = request.host.split(':')[0]
                if ':' in request.host:
                    flask_port = request.host.split(':')[1]
                logging.info(f"Using Flask host: {flask_host}")
            except Exception as e:
                logging.warning(f"Error getting Flask host: {str(e)}")

        # Build a simple command with minimal arguments
        logging.info(f"Setting JupyterLab directory to: {workspace_path}")
        cmd = [
            jupyter_cmd, 'lab',
            '--no-browser',
            f'--port={port}',
            f'--ServerApp.token={token}',
            f'--ServerApp.root_dir={workspace_path}',
            '--ip=0.0.0.0',  # Bind to all interfaces
            '--ServerApp.allow_origin=*',  # Allow cross-origin requests
            '--ServerApp.allow_remote_access=True'  # Allow remote access
        ]

        # Set up environment variables
        env = os.environ.copy()

        # Add environment's bin directory to PATH if it exists
        if os.path.exists(env_path):
            if os.path.exists(os.path.join(env_path, 'bin')):
                env['PATH'] = f"{os.path.join(env_path, 'bin')}:{env.get('PATH', '')}"
            elif os.path.exists(os.path.join(env_path, 'Scripts')):
                env['PATH'] = f"{os.path.join(env_path, 'Scripts')};{env.get('PATH', '')}"

        # Set the working directory to the workspace path
        cwd = workspace_path

        try:
            logging.info(f"Executing command: {' '.join(cmd)}")
            logging.info(f"Working directory: {cwd}")

            # Launch JupyterLab with the workspace path as the working directory
            process = subprocess.Popen(
                cmd,
                env=env,
                cwd=cwd,  # Set the working directory
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Wait a bit for JupyterLab to start
            time.sleep(5)

            # Check if process is still running
            if process.poll() is not None:
                # Process has terminated
                stdout, stderr = process.communicate()
                logging.error(f"JupyterLab process terminated with exit code {process.returncode}")
                logging.error(f"STDOUT: {stdout}")
                logging.error(f"STDERR: {stderr}")
                return False, f"JupyterLab failed to start: {stderr}"

            # Define process_key before using it
            process_key = f"jupyter_{workspace_name}"

            # Store the process
            self.processes[process_key] = process.pid

            # Create the direct URL with the token
            direct_url = f"http://localhost:{port}/lab?token={token}"
            logging.info(f"JupyterLab direct URL: {direct_url}")

            # Return the direct URL
            return True, direct_url

        except Exception as e:
            logging.exception(f"Error launching JupyterLab: {str(e)}")
            return False, str(e)

    def stop_ide(self, workspace_name, ide_type):
        """Stop a running IDE."""
        process_key = f"{ide_type}_{workspace_name}"

        if process_key in self.processes:
            try:
                pid = self.processes[process_key]
                process = psutil.Process(pid)
                process.terminate()
                try:
                    process.wait(timeout=5)
                except psutil.TimeoutExpired:
                    process.kill()
                del self.processes[process_key]
                return True, "Process terminated"
            except psutil.NoSuchProcess:
                del self.processes[process_key]
                return True, "Process already terminated"
            except Exception as e:
                logging.exception(f"Error stopping IDE process: {str(e)}")
                return False, str(e)

        return False, "Process not found"

    def check_jupyter_installation(self):
        """Check if JupyterLab is installed and available."""
        try:
            result = subprocess.run(
                [self.jupyter_path, '--version'],
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode == 0:
                version = result.stdout.strip()
                logging.info(f"Found Jupyter: {version}")

                # Check if JupyterLab is installed
                lab_result = subprocess.run(
                    [self.jupyter_path, 'lab', '--version'],
                    capture_output=True,
                    text=True,
                    check=False
                )

                if lab_result.returncode == 0:
                    lab_version = lab_result.stdout.strip()
                    logging.info(f"Found JupyterLab: {lab_version}")
                    return True, f"JupyterLab {lab_version} is available"
                else:
                    logging.warning("JupyterLab is not installed")
                    return False, "JupyterLab is not installed. Please install it with 'pip install jupyterlab'"
            else:
                logging.warning(f"Jupyter not found at {self.jupyter_path}")
                return False, f"Jupyter not found at {self.jupyter_path}"
        except Exception as e:
            logging.exception(f"Error checking Jupyter installation: {str(e)}")
            return False, str(e)

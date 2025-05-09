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
from flask import current_app, request

class IDEService:
    def __init__(self):
        self._jupyter_path = None
        self.processes = {}
    
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
        
        # Check if env directory exists
        env_path = os.path.join(workspace_path, 'env')
        if not os.path.exists(env_path):
            logging.warning(f"Environment directory not found: {env_path}")
            logging.info("Will try to launch JupyterLab using system Python")
        
        # Create a temporary file to store the token
        token_file = tempfile.NamedTemporaryFile(delete=False, suffix='.txt')
        token_file.close()
        logging.info(f"Created token file: {token_file.name}")
        
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
        
        # Get the host IP for external access
        host_ip = self.get_host_ip()
        logging.info(f"Using host IP for JupyterLab: {host_ip}")
        
        # Check if there's already a JupyterLab running for this workspace
        workspace_name = os.path.basename(workspace_path)
        process_key = f"jupyter_{workspace_name}"
        
        if process_key in self.processes:
            try:
                # Check if the process is still running
                pid = self.processes[process_key]
                process = psutil.Process(pid)
                
                # If the process is running, return the URL
                if process.is_running():
                    logging.info(f"JupyterLab is already running for workspace: {workspace_name}")
                    
                    # Get the URL with the correct host
                    if host_ip == '0.0.0.0':
                        host_ip = 'localhost'
                    
                    # We don't have the token for the existing process, so we'll need to restart it
                    logging.info(f"Stopping existing JupyterLab process for workspace: {workspace_name}")
                    process.terminate()
                    process.wait(timeout=5)
                    del self.processes[process_key]
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # Process doesn't exist or we can't access it
                if process_key in self.processes:
                    del self.processes[process_key]
            except Exception as e:
                logging.exception(f"Error checking existing JupyterLab process: {str(e)}")
        
        # Build the command - bind to all interfaces (0.0.0.0) to allow external access
        cmd = [
            jupyter_cmd, 'lab',
            '--no-browser',
            '--ip=0.0.0.0',  # Bind to all interfaces
            '--port=8888',
            '--notebook-dir', workspace_path,
            f'--ServerApp.token={token}',
            '--ServerApp.password=""'
        ]
        
        # Set up environment variables
        env = os.environ.copy()
        
        # Add environment's bin directory to PATH if it exists
        if os.path.exists(env_path):
            if os.path.exists(os.path.join(env_path, 'bin')):
                env['PATH'] = f"{os.path.join(env_path, 'bin')}:{env.get('PATH', '')}"
            elif os.path.exists(os.path.join(env_path, 'Scripts')):
                env['PATH'] = f"{os.path.join(env_path, 'Scripts')};{env.get('PATH', '')}"
        
        try:
            logging.info(f"Executing command: {' '.join(cmd)}")
            
            # Launch JupyterLab
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait a bit for JupyterLab to start
            time.sleep(2)
            
            # Check if process is still running
            if process.poll() is not None:
                # Process has terminated
                stdout, stderr = process.communicate()
                logging.error(f"JupyterLab process terminated with exit code {process.returncode}")
                logging.error(f"STDOUT: {stdout}")
                logging.error(f"STDERR: {stderr}")
                return False, f"JupyterLab failed to start: {stderr}"
            
            # Store the process
            self.processes[process_key] = process.pid
            
            # Get the URL with the correct host and token
            # Make sure we're not using 0.0.0.0 in the URL
            if host_ip == '0.0.0.0':
                host_ip = 'localhost'
            url = f"http://{host_ip}:8888/lab?token={token}"
            logging.info(f"JupyterLab URL: {url}")
            
            logging.info(f"JupyterLab started successfully. URL: {url}")
            return True, url
            
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
                process.wait(timeout=5)
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

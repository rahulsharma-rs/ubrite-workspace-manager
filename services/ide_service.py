import subprocess
import os
import logging
from flask import current_app
import json

logger = logging.getLogger(__name__)


class IDEService:
    def __init__(self):
        self.jupyter_path = self._get_jupyter_path()

    def _get_jupyter_path(self):
        """Get the Jupyter executable path."""
        # Check config file first
        config_file = os.path.join(current_app.config['UBRITE_ROOT'], '.config', 'jupyter_config.json')
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    if 'jupyter_path' in config:
                        return config['jupyter_path']
            except Exception as e:
                logger.warning(f"Could not load Jupyter config: {e}")

        # Check environment variable
        if 'JUPYTER_PATH' in current_app.config:
            return current_app.config['JUPYTER_PATH']

        # Default to system jupyter
        return 'jupyter'

    def check_jupyter_installation(self):
        """
        Check if JupyterLab is installed and available.

        Returns:
            tuple: (is_available: bool, message: str)
        """
        try:
            # Try to run jupyter --version
            result = subprocess.run(
                [self.jupyter_path, '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                version_info = result.stdout.strip()
                return True, f"JupyterLab is available. {version_info}"
            else:
                return False, f"Jupyter command failed: {result.stderr}"

        except subprocess.TimeoutExpired:
            return False, "Jupyter command timed out"
        except FileNotFoundError:
            return False, f"Jupyter not found at path: {self.jupyter_path}"
        except Exception as e:
            return False, f"Error checking Jupyter: {str(e)}"

    def launch_jupyter(self, workspace_path, port=8888):
        """
        Launch JupyterLab for a workspace.

        Args:
            workspace_path (str): Path to the workspace directory
            port (int): Port to run JupyterLab on

        Returns:
            dict: Launch result with success status and details
        """
        try:
            # Check if JupyterLab is available
            is_available, message = self.check_jupyter_installation()
            if not is_available:
                return {
                    'success': False,
                    'message': f'JupyterLab not available: {message}'
                }

            # Find an available port
            import socket
            sock = socket.socket()
            sock.bind(('', 0))
            available_port = sock.getsockname()[1]
            sock.close()

            # Launch JupyterLab
            cmd = [
                self.jupyter_path, 'lab',
                '--notebook-dir', workspace_path,
                '--port', str(available_port),
                '--no-browser',
                '--allow-root',
                '--ip', '0.0.0.0'
            ]

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=workspace_path
            )

            # Give it a moment to start
            import time
            time.sleep(2)

            if process.poll() is None:  # Process is still running
                jupyter_url = f"http://localhost:{available_port}"
                return {
                    'success': True,
                    'message': 'JupyterLab launched successfully',
                    'url': jupyter_url,
                    'port': available_port,
                    'pid': process.pid
                }
            else:
                stdout, stderr = process.communicate()
                return {
                    'success': False,
                    'message': f'JupyterLab failed to start: {stderr.decode()}'
                }

        except Exception as e:
            logger.error(f"Error launching JupyterLab: {str(e)}")
            return {
                'success': False,
                'message': f'Error launching JupyterLab: {str(e)}'
            }

    def stop_jupyter(self, pid):
        """
        Stop a JupyterLab process.

        Args:
            pid (int): Process ID of the JupyterLab instance

        Returns:
            bool: True if stopped successfully
        """
        try:
            import signal
            os.kill(pid, signal.SIGTERM)
            return True
        except Exception as e:
            logger.error(f"Error stopping JupyterLab process {pid}: {str(e)}")
            return False

    def get_running_instances(self):
        """
        Get list of running JupyterLab instances.

        Returns:
            list: List of running instances with details
        """
        try:
            result = subprocess.run(
                ['ps', 'aux'],
                capture_output=True,
                text=True,
                timeout=10
            )

            instances = []
            for line in result.stdout.split('\n'):
                if 'jupyter' in line and 'lab' in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        instances.append({
                            'pid': parts[1],
                            'command': ' '.join(parts[10:])
                        })

            return instances

        except Exception as e:
            logger.error(f"Error getting running instances: {str(e)}")
            return []

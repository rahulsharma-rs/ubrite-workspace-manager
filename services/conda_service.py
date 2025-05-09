import subprocess
import os
import json
from flask import current_app
import tempfile
import logging
import shutil


class CondaService:
    def __init__(self):
        self._conda_path = None
        self._templates_path = None

    @property
    def conda_path(self):
        if self._conda_path is None:
            # Try to get conda path from config
            config_path = current_app.config.get('CONDA_PATH', 'conda')

            # If it's just 'conda', try to find the full path
            if config_path == 'conda':
                # Try to find conda in common locations
                possible_paths = [
                    # macOS / Linux common paths
                    '/usr/local/bin/conda',
                    '/usr/bin/conda',
                    os.path.expanduser('~/miniconda3/bin/conda'),
                    os.path.expanduser('~/anaconda3/bin/conda'),
                    # Windows common paths
                    r'C:\ProgramData\Miniconda3\Scripts\conda.exe',
                    r'C:\ProgramData\Anaconda3\Scripts\conda.exe',
                    os.path.expanduser(r'~\Miniconda3\Scripts\conda.exe'),
                    os.path.expanduser(r'~\Anaconda3\Scripts\conda.exe'),
                ]

                # Also check if conda is in PATH
                conda_in_path = shutil.which('conda')
                if conda_in_path:
                    possible_paths.insert(0, conda_in_path)
                    logging.info(f"Found conda in PATH: {conda_in_path}")

                # Try each path
                for path in possible_paths:
                    if os.path.exists(path):
                        config_path = path
                        logging.info(f"Found conda at: {path}")
                        break

                # If we still couldn't find conda, log it but keep the default value
                if config_path == 'conda':
                    logging.warning("Could not find conda executable in common locations")

            self._conda_path = config_path
        return self._conda_path

    @property
    def templates_path(self):
        if self._templates_path is None:
            self._templates_path = current_app.config['ENV_TEMPLATES_PATH']
        return self._templates_path

    def is_conda_available(self):
        """Check if conda is available."""
        try:
            # Try to run conda --version
            result = subprocess.run(
                [self.conda_path, '--version'],
                capture_output=True,
                text=True,
                check=False,  # Don't raise an exception if it fails
                timeout=10  # Add a timeout to prevent hanging
            )
            if result.returncode == 0:
                logging.info(f"Conda is available: {result.stdout.strip()}")
                return True
            else:
                logging.error(f"Conda check failed with return code {result.returncode}: {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            logging.error(f"Conda check timed out after 10 seconds")
            return False
        except FileNotFoundError:
            logging.error(f"Conda executable not found at path: {self.conda_path}")
            return False
        except Exception as e:
            logging.error(f"Error checking conda availability: {str(e)}")
            return False

    def get_available_templates(self):
        """Get a list of available environment templates."""
        templates = []

        if os.path.exists(self.templates_path):
            for filename in os.listdir(self.templates_path):
                if filename.endswith('.yml') or filename.endswith('.yaml'):
                    template_name = os.path.splitext(filename)[0]
                    templates.append({
                        'name': template_name,
                        'path': os.path.join(self.templates_path, filename)
                    })

        return templates

    def create_environment(self, workspace_path, env_type):
        """Create a Conda environment for a workspace."""
        # Check if conda is available
        if not self.is_conda_available():
            error_msg = f"Conda not found at '{self.conda_path}'. Please install Conda or configure the correct path."
            logging.error(error_msg)
            return False, error_msg

        env_name = os.path.basename(workspace_path)

        if env_type == 'custom':
            # Create a basic environment
            cmd = [
                self.conda_path, 'create', '-y', '-p',
                os.path.join(workspace_path, 'env'),
                'python=3.9'
            ]
        else:
            # Use a template
            template_path = None
            for template in self.get_available_templates():
                if template['name'] == env_type:
                    template_path = template['path']
                    break

            if not template_path:
                return False, "Template not found"

            cmd = [
                self.conda_path, 'env', 'create', '-f', template_path,
                '-p', os.path.join(workspace_path, 'env')
            ]

        try:
            logging.info(f"Creating conda environment with command: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            return True, result.stdout
        except subprocess.CalledProcessError as e:
            logging.error(f"Error creating conda environment: {e.stderr}")
            return False, e.stderr
        except FileNotFoundError as e:
            error_msg = f"Conda executable not found at '{self.conda_path}'. Please install Conda or configure the correct path."
            logging.error(error_msg)
            return False, error_msg
        except Exception as e:
            logging.error(f"Unexpected error creating conda environment: {str(e)}")
            return False, str(e)

    def delete_environment(self, workspace_path):
        """Delete a Conda environment."""
        env_path = os.path.join(workspace_path, 'env')

        if not os.path.exists(env_path):
            return True, "Environment does not exist"

        # Check if conda is available
        if not self.is_conda_available():
            # If conda is not available, just remove the directory
            try:
                shutil.rmtree(env_path)
                return True, "Environment directory removed (conda not available)"
            except Exception as e:
                return False, f"Failed to remove environment directory: {str(e)}"

        cmd = [self.conda_path, 'env', 'remove', '-y', '-p', env_path]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            return True, result.stdout
        except subprocess.CalledProcessError as e:
            logging.error(f"Error removing conda environment: {e.stderr}")
            return False, e.stderr
        except Exception as e:
            logging.error(f"Unexpected error removing conda environment: {str(e)}")
            return False, str(e)

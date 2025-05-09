import os
import subprocess
import logging
import sys
import json
from flask import current_app
import shutil

class PythonEnvService:
    def __init__(self):
        self._python_path = None
    
    @property
    def python_path(self):
        if self._python_path is None:
            self._python_path = sys.executable
        return self._python_path
    
    def get_system_python_info(self):
        """Get information about the system Python."""
        try:
            # Get Python version
            version_info = sys.version_info
            version = f"{version_info.major}.{version_info.minor}.{version_info.micro}"
            
            # Get Python path
            path = sys.executable
            
            # Get site packages directory
            import site
            site_packages = site.getsitepackages()[0]
            
            return {
                'version': version,
                'path': path,
                'site_packages': site_packages,
                'type': 'system'
            }
        except Exception as e:
            logging.error(f"Error getting system Python info: {str(e)}")
            return None
    
    def detect_venv_environments(self):
        """Detect virtual environments in common locations."""
        venvs = []
        
        # Common locations for virtual environments
        locations = [
            os.path.expanduser('~/.virtualenvs'),  # virtualenvwrapper
            os.path.expanduser('~/venvs'),         # common custom location
            os.path.expanduser('~/virtualenvs'),   # common custom location
            os.path.expanduser('~/.venv'),         # common hidden location
            os.path.expanduser('~/projects'),      # project directories
        ]
        
        # Add the current working directory and parent directories
        cwd = os.getcwd()
        locations.append(cwd)
        parent = os.path.dirname(cwd)
        locations.append(parent)
        
        # Add WORKON_HOME if it exists (virtualenvwrapper)
        workon_home = os.environ.get('WORKON_HOME')
        if workon_home:
            locations.append(workon_home)
        
        # Add VIRTUAL_ENV if it exists (currently active venv)
        virtual_env = os.environ.get('VIRTUAL_ENV')
        if virtual_env:
            venvs.append(self._get_venv_info(virtual_env, 'active'))
        
        # Search for venv/bin/python or venv/Scripts/python.exe
        for location in locations:
            if os.path.exists(location):
                try:
                    for item in os.listdir(location):
                        item_path = os.path.join(location, item)
                        
                        # Check if this is a directory
                        if not os.path.isdir(item_path):
                            continue
                        
                        # Check for bin/python (Unix) or Scripts/python.exe (Windows)
                        python_path = None
                        if os.path.exists(os.path.join(item_path, 'bin', 'python')):
                            python_path = os.path.join(item_path, 'bin', 'python')
                        elif os.path.exists(os.path.join(item_path, 'Scripts', 'python.exe')):
                            python_path = os.path.join(item_path, 'Scripts', 'python.exe')
                        
                        if python_path:
                            venv_info = self._get_venv_info(item_path)
                            if venv_info:
                                venvs.append(venv_info)
                except Exception as e:
                    logging.warning(f"Error scanning directory {location}: {str(e)}")
        
        return venvs
    
    def detect_conda_environments(self):
        """Detect Conda environments."""
        conda_envs = []
        
        # Try to find conda executable
        conda_path = shutil.which('conda')
        if not conda_path:
            # Try common locations
            common_paths = [
                '/usr/local/bin/conda',
                '/usr/bin/conda',
                os.path.expanduser('~/miniconda3/bin/conda'),
                os.path.expanduser('~/anaconda3/bin/conda'),
                os.path.expanduser('~/opt/miniconda3/bin/conda'),
                os.path.expanduser('~/opt/anaconda3/bin/conda'),
                # Windows paths
                r'C:\ProgramData\Miniconda3\Scripts\conda.exe',
                r'C:\ProgramData\Anaconda3\Scripts\conda.exe',
                os.path.expanduser(r'~\Miniconda3\Scripts\conda.exe'),
                os.path.expanduser(r'~\Anaconda3\Scripts\conda.exe'),
            ]
            
            for path in common_paths:
                if os.path.exists(path):
                    conda_path = path
                    break
        
        if not conda_path:
            logging.warning("Conda not found, cannot detect Conda environments")
            return conda_envs
        
        try:
            # Run conda env list --json to get all environments
            result = subprocess.run(
                [conda_path, 'env', 'list', '--json'],
                capture_output=True,
                text=True,
                check=True
            )
            
            env_data = json.loads(result.stdout)
            
            for env_path in env_data.get('envs', []):
                # Get Python path in this environment
                python_path = None
                if os.path.exists(os.path.join(env_path, 'bin', 'python')):
                    python_path = os.path.join(env_path, 'bin', 'python')
                elif os.path.exists(os.path.join(env_path, 'python.exe')):
                    python_path = os.path.join(env_path, 'python.exe')
                
                if python_path:
                    env_name = os.path.basename(env_path)
                    if env_name == '.conda':  # Skip the base environment directory
                        env_name = 'base'
                    
                    # Get Python version
                    try:
                        version_result = subprocess.run(
                            [python_path, '--version'],
                            capture_output=True,
                            text=True,
                            check=True
                        )
                        version = version_result.stdout.strip() or version_result.stderr.strip()
                        version = version.replace('Python ', '')
                    except:
                        version = 'Unknown'
                    
                    conda_envs.append({
                        'name': env_name,
                        'path': env_path,
                        'python_path': python_path,
                        'version': version,
                        'type': 'conda'
                    })
        except Exception as e:
            logging.error(f"Error detecting Conda environments: {str(e)}")
        
        return conda_envs
    
    def get_all_environments(self):
        """Get all detected Python environments."""
        environments = []
        
        # Add system Python
        system_python = self.get_system_python_info()
        if system_python:
            environments.append(system_python)
        
        # Add virtual environments
        venvs = self.detect_venv_environments()
        environments.extend(venvs)
        
        # Add Conda environments
        conda_envs = self.detect_conda_environments()
        environments.extend(conda_envs)
        
        return environments
    
    def _get_venv_info(self, venv_path, status='inactive'):
        """Get information about a virtual environment."""
        try:
            # Determine Python path
            python_path = None
            if os.path.exists(os.path.join(venv_path, 'bin', 'python')):
                python_path = os.path.join(venv_path, 'bin', 'python')
            elif os.path.exists(os.path.join(venv_path, 'Scripts', 'python.exe')):
                python_path = os.path.join(venv_path, 'Scripts', 'python.exe')
            else:
                return None
            
            # Get Python version
            try:
                version_result = subprocess.run(
                    [python_path, '--version'],
                    capture_output=True,
                    text=True,
                    check=True
                )
                version = version_result.stdout.strip() or version_result.stderr.strip()
                version = version.replace('Python ', '')
            except:
                version = 'Unknown'
            
            # Get site packages directory
            site_packages = None
            try:
                site_result = subprocess.run(
                    [python_path, '-c', 'import site; print(site.getsitepackages()[0])'],
                    capture_output=True,
                    text=True,
                    check=True
                )
                site_packages = site_result.stdout.strip()
            except:
                # Try to guess site-packages location
                if os.path.exists(os.path.join(venv_path, 'lib')):
                    # Look for lib/pythonX.Y/site-packages
                    lib_dir = os.path.join(venv_path, 'lib')
                    for item in os.listdir(lib_dir):
                        if item.startswith('python'):
                            site_packages = os.path.join(lib_dir, item, 'site-packages')
                            if os.path.exists(site_packages):
                                break
                elif os.path.exists(os.path.join(venv_path, 'Lib', 'site-packages')):
                    # Windows style
                    site_packages = os.path.join(venv_path, 'Lib', 'site-packages')
            
            return {
                'name': os.path.basename(venv_path),
                'path': venv_path,
                'python_path': python_path,
                'version': version,
                'site_packages': site_packages,
                'status': status,
                'type': 'venv'
            }
        except Exception as e:
            logging.warning(f"Error getting venv info for {venv_path}: {str(e)}")
            return None
    
    def create_symlink_to_environment(self, env_info, workspace_path):
        """Create a symlink to an existing Python environment."""
        try:
            env_dir = os.path.join(workspace_path, 'env')
            
            # Create a symlink to the environment
            if os.path.exists(env_dir):
                if os.path.islink(env_dir):
                    os.unlink(env_dir)
                else:
                    shutil.rmtree(env_dir)
            
            os.symlink(env_info['path'], env_dir, target_is_directory=True)
            
            return True, f"Linked to existing environment: {env_info['name']}"
        except Exception as e:
            logging.error(f"Error creating symlink to environment: {str(e)}")
            return False, str(e)

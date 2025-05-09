import requests
import json
from flask import current_app
from models import Settings
from utils.encryption import decrypt_data
from extensions import db
import logging

class GitLabService:
    def __init__(self):
        self._api_url = None
        self._headers = None
    
    @property
    def api_url(self):
        if self._api_url is None:
            # Get the GitLab URL from settings if available
            settings = Settings.query.first()
            if settings:
                try:
                    if settings.gitlab_url:
                        self._api_url = settings.gitlab_url
                    else:
                        self._api_url = current_app.config['GITLAB_API_URL']
                except:
                    # If gitlab_url column doesn't exist yet
                    self._api_url = current_app.config['GITLAB_API_URL']
            else:
                self._api_url = current_app.config['GITLAB_API_URL']
        return self._api_url
    
    @property
    def headers(self):
        if self._headers is None:
            self._headers = self._get_headers()
        return self._headers
    
    def _get_headers(self):
        """Get the headers for GitLab API requests."""
        settings = Settings.query.first()
        if not settings or not settings.gitlab_pat_encrypted:
            logging.warning("GitLab PAT not configured")
            return {}
        
        try:
            token = decrypt_data(settings.gitlab_pat_encrypted, settings.encryption_key)
            return {
                'PRIVATE-TOKEN': token,
                'Content-Type': 'application/json'
            }
        except Exception as e:
            logging.error(f"Error decrypting GitLab PAT: {str(e)}")
            return {}
    
    def validate_token(self, token, api_url=None):
        """Validate a GitLab Personal Access Token."""
        headers = {
            'PRIVATE-TOKEN': token,
            'Content-Type': 'application/json'
        }
        url = api_url or self.api_url
        try:
            response = requests.get(f"{url}/user", headers=headers)
            return response.status_code == 200
        except Exception as e:
            logging.error(f"Error validating GitLab token: {str(e)}")
            return False
    
    def create_repository(self, name, visibility='private'):
        """Create a new GitLab repository."""
        data = {
            'name': name,
            'visibility': visibility,
            'initialize_with_readme': True
        }
        
        # Check if headers contain a token
        if 'PRIVATE-TOKEN' not in self.headers:
            logging.error("Cannot create GitLab repository: No PAT configured")
            return None
        
        try:
            logging.info(f"Creating GitLab repository: {name} at {self.api_url}")
            response = requests.post(
                f"{self.api_url}/projects",
                headers=self.headers,
                data=json.dumps(data)
            )
            
            if response.status_code in (201, 200):
                logging.info(f"GitLab repository created successfully: {name}")
                return response.json()
            else:
                logging.error(f"Failed to create GitLab repository: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logging.error(f"Exception creating GitLab repository: {str(e)}")
            return None
    
    def delete_repository(self, repo_id):
        """Delete a GitLab repository."""
        if not repo_id:
            logging.warning("Cannot delete GitLab repository: No repo ID provided")
            return True  # Return True to allow cleanup to continue
        
        try:
            response = requests.delete(
                f"{self.api_url}/projects/{repo_id}",
                headers=self.headers
            )
            success = response.status_code in (200, 202, 204)
            if success:
                logging.info(f"GitLab repository deleted successfully: {repo_id}")
            else:
                logging.error(f"Failed to delete GitLab repository: {response.status_code} - {response.text}")
            return success
        except Exception as e:
            logging.error(f"Exception deleting GitLab repository: {str(e)}")
            return False
    
    def get_repository_info(self, repo_id):
        """Get information about a GitLab repository."""
        try:
            response = requests.get(
                f"{self.api_url}/projects/{repo_id}",
                headers=self.headers
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logging.error(f"Failed to get GitLab repository info: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logging.error(f"Exception getting GitLab repository info: {str(e)}")
            return None
    
    def get_commits(self, repo_id, branch='main'):
        """Get commits for a repository."""
        try:
            response = requests.get(
                f"{self.api_url}/projects/{repo_id}/repository/commits?ref_name={branch}",
                headers=self.headers
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logging.error(f"Failed to get GitLab commits: {response.status_code} - {response.text}")
                return []
        except Exception as e:
            logging.error(f"Exception getting GitLab commits: {str(e)}")
            return []
    
    def test_connection(self):
        """Test the GitLab connection and return status information."""
        if 'PRIVATE-TOKEN' not in self.headers:
            return {
                'success': False,
                'message': 'GitLab PAT not configured',
                'details': 'Please configure a GitLab Personal Access Token in the settings.'
            }
        
        try:
            # Log the URL we're trying to connect to for debugging
            logging.info(f"Testing GitLab connection to: {self.api_url}")
            
            response = requests.get(f"{self.api_url}/user", headers=self.headers, timeout=10)
            
            # Log the response status and content for debugging
            logging.info(f"GitLab API response status: {response.status_code}")
            logging.info(f"GitLab API response content length: {len(response.content)}")
            
            if response.status_code == 200:
                try:
                    user_data = response.json()
                    return {
                        'success': True,
                        'message': 'Connected to GitLab successfully',
                        'details': f"Authenticated as {user_data.get('name', 'Unknown')} ({user_data.get('username', 'Unknown')})"
                    }
                except json.JSONDecodeError as e:
                    logging.error(f"JSON decode error: {str(e)}, Response content: {response.content[:100]}")
                    return {
                        'success': False,
                        'message': 'Invalid response from GitLab API',
                        'details': f"Received status code 200 but response is not valid JSON. This may indicate a network issue or proxy interference."
                    }
            else:
                # Try to get error details from response
                error_details = "No additional details available"
                try:
                    if response.content:
                        error_data = response.json()
                        if 'message' in error_data:
                            error_details = error_data['message']
                        elif 'error' in error_data:
                            error_details = error_data['error']
                except:
                    if response.content:
                        error_details = f"Raw response: {response.content[:100]}"
            
            return {
                'success': False,
                'message': f'GitLab API error: {response.status_code}',
                'details': error_details
            }
        except requests.exceptions.ConnectionError as e:
            logging.error(f"Connection error: {str(e)}")
            return {
                'success': False,
                'message': 'Connection error',
                'details': f"Could not connect to GitLab API at {self.api_url}. Please check the URL and your network connection."
            }
        except requests.exceptions.Timeout as e:
            logging.error(f"Timeout error: {str(e)}")
            return {
                'success': False,
                'message': 'Connection timeout',
                'details': f"Connection to GitLab API timed out. The server might be slow or unreachable."
            }
        except json.JSONDecodeError as e:
            logging.error(f"JSON decode error: {str(e)}")
            return {
                'success': False,
                'message': 'Invalid response format',
                'details': f"The GitLab API returned an invalid response format. This might indicate a network issue or proxy interference."
            }
        except Exception as e:
            logging.error(f"Unexpected error testing GitLab connection: {str(e)}")
            return {
                'success': False,
                'message': 'Connection error',
                'details': f"An unexpected error occurred: {str(e)}"
            }

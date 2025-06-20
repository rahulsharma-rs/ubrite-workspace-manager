import requests
import json
from datetime import datetime, timedelta
from flask import current_app
from models import Settings
from utils.encryption import decrypt_data, encrypt_data, generate_key
from extensions import db
import logging


class GitLabService:
    def __init__(self):
        self._api_url = None
        self._headers = None
        self._token_info = None

    @property
    def api_url(self):
        if self._api_url is None:
            settings = Settings.query.first()
            if settings and hasattr(settings, 'gitlab_url') and settings.gitlab_url:
                self._api_url = settings.gitlab_url
            else:
                self._api_url = current_app.config.get('GITLAB_API_URL', 'https://gitlab.com/api/v4')
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
        """
        Validate a GitLab Personal Access Token and return detailed information.

        Returns:
            dict: {
                'valid': bool,
                'user_info': dict or None,
                'token_info': dict or None,
                'scopes': list,
                'expires_at': str or None,
                'message': str,
                'error_code': str or None
            }
        """
        headers = {
            'PRIVATE-TOKEN': token,
            'Content-Type': 'application/json'
        }

        url = api_url or self.api_url
        if not url.endswith('/api/v4'):
            url = url.rstrip('/') + '/api/v4'

        result = {
            'valid': False,
            'user_info': None,
            'token_info': None,
            'scopes': [],
            'expires_at': None,
            'message': '',
            'error_code': None
        }

        try:
            # Test basic connectivity and get user info
            logging.info(f"Validating GitLab token at: {url}/user")
            user_response = requests.get(f"{url}/user", headers=headers, timeout=15)

            if user_response.status_code == 200:
                result['user_info'] = user_response.json()
                result['valid'] = True
                result['message'] = f"Token valid for user: {result['user_info'].get('name', 'Unknown')}"

                # Get token information including scopes and expiration
                try:
                    token_response = requests.get(f"{url}/personal_access_tokens/self", headers=headers, timeout=10)
                    if token_response.status_code == 200:
                        token_data = token_response.json()
                        result['token_info'] = token_data
                        result['scopes'] = token_data.get('scopes', [])
                        result['expires_at'] = token_data.get('expires_at')

                        # Check if token is expiring soon (within 30 days)
                        if result['expires_at']:
                            try:
                                expires_date = datetime.fromisoformat(result['expires_at'].replace('Z', '+00:00'))
                                days_until_expiry = (expires_date - datetime.now()).days

                                if days_until_expiry <= 0:
                                    result['valid'] = False
                                    result['message'] = "Token has expired"
                                    result['error_code'] = 'TOKEN_EXPIRED'
                                elif days_until_expiry <= 30:
                                    result['message'] += f" (expires in {days_until_expiry} days)"
                                    result['error_code'] = 'TOKEN_EXPIRING_SOON'
                            except Exception as e:
                                logging.warning(f"Could not parse expiration date: {e}")

                        # Check required scopes
                        required_scopes = ['api']
                        missing_scopes = [scope for scope in required_scopes if scope not in result['scopes']]
                        if missing_scopes:
                            result['message'] += f" Warning: Missing required scopes: {', '.join(missing_scopes)}"
                            result['error_code'] = 'INSUFFICIENT_SCOPES'

                except Exception as e:
                    logging.warning(f"Could not get token details: {e}")
                    # Token is still valid for basic operations
                    result['message'] += " (Could not retrieve token details)"

            elif user_response.status_code == 401:
                result['message'] = "Invalid token or token has expired"
                result['error_code'] = 'INVALID_TOKEN'
            elif user_response.status_code == 403:
                result['message'] = "Token does not have sufficient permissions"
                result['error_code'] = 'INSUFFICIENT_PERMISSIONS'
            elif user_response.status_code == 404:
                result['message'] = f"GitLab API not found at {url}"
                result['error_code'] = 'API_NOT_FOUND'
            else:
                result['message'] = f"Unexpected response: {user_response.status_code}"
                result['error_code'] = 'UNEXPECTED_ERROR'

        except requests.exceptions.ConnectionError:
            result['message'] = f"Could not connect to GitLab at {url}"
            result['error_code'] = 'CONNECTION_ERROR'
        except requests.exceptions.Timeout:
            result['message'] = "Connection timeout - GitLab server may be slow"
            result['error_code'] = 'TIMEOUT'
        except requests.exceptions.SSLError:
            result['message'] = "SSL certificate error - check your GitLab URL"
            result['error_code'] = 'SSL_ERROR'
        except Exception as e:
            result['message'] = f"Unexpected error: {str(e)}"
            result['error_code'] = 'UNEXPECTED_ERROR'
            logging.error(f"Unexpected error validating token: {e}")

        return result

    def check_token_status(self):
        """
        Check the status of the currently stored token.

        Returns:
            dict: Token status information
        """
        settings = Settings.query.first()
        if not settings or not settings.gitlab_pat_encrypted:
            return {
                'configured': False,
                'message': 'No GitLab token configured'
            }

        try:
            token = decrypt_data(settings.gitlab_pat_encrypted, settings.encryption_key)
            return self.validate_token(token, settings.gitlab_url)
        except Exception as e:
            return {
                'configured': True,
                'valid': False,
                'message': f'Error checking token: {str(e)}',
                'error_code': 'DECRYPTION_ERROR'
            }

    def test_connection(self):
        """Test the GitLab connection and return status information."""
        token_status = self.check_token_status()

        if not token_status.get('configured', False):
            return {
                'success': False,
                'message': 'GitLab PAT not configured',
                'details': 'Please configure a GitLab Personal Access Token in the settings.',
                'error_code': 'NO_TOKEN'
            }

        if not token_status.get('valid', False):
            return {
                'success': False,
                'message': token_status.get('message', 'Token validation failed'),
                'details': 'Please check your GitLab Personal Access Token.',
                'error_code': token_status.get('error_code', 'INVALID_TOKEN'),
                'token_info': token_status
            }

        return {
            'success': True,
            'message': token_status.get('message', 'Connected successfully'),
            'details': f"Connected as {token_status.get('user_info', {}).get('name', 'Unknown')}",
            'user_info': token_status.get('user_info'),
            'token_info': token_status.get('token_info'),
            'warning': token_status.get('error_code') in ['TOKEN_EXPIRING_SOON', 'INSUFFICIENT_SCOPES']
        }

    def create_repository(self, name, visibility='private'):
        """Create a new GitLab repository."""
        # Check token status first
        token_status = self.check_token_status()
        if not token_status.get('valid', False):
            logging.error(f"Cannot create repository: {token_status.get('message')}")
            return None

        data = {
            'name': name,
            'visibility': visibility,
            'initialize_with_readme': True
        }

        try:
            logging.info(f"Creating GitLab repository: {name} at {self.api_url}")
            response = requests.post(
                f"{self.api_url}/projects",
                headers=self.headers,
                data=json.dumps(data),
                timeout=30
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
            return True

        # Check token status first
        token_status = self.check_token_status()
        if not token_status.get('valid', False):
            logging.warning(f"Cannot delete repository: {token_status.get('message')}")
            return True  # Return True to allow cleanup to continue

        try:
            response = requests.delete(
                f"{self.api_url}/projects/{repo_id}",
                headers=self.headers,
                timeout=30
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
                headers=self.headers,
                timeout=30
            )

            if response.status_code == 200:
                return response.json()
            else:
                logging.error(f"Failed to get GitLab repository info: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logging.error(f"Exception getting GitLab repository info: {str(e)}")
            return None

    # Add these methods to maintain backward compatibility
    def get_headers_legacy(self):
        """Legacy method for getting headers - maintained for backward compatibility."""
        return self.headers

    def validate_token_legacy(self, token, api_url=None):
        """Legacy token validation that returns boolean - maintained for backward compatibility."""
        result = self.validate_token(token, api_url)
        return result.get('valid', False)

    def test_connection_legacy(self):
        """Legacy test connection method - maintained for backward compatibility."""
        result = self.test_connection()
        return {
            'success': result['success'],
            'message': result['message'],
            'details': result.get('details', '')
        }

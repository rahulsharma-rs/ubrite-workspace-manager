import requests
import json
import logging
from datetime import datetime, timedelta, timezone
from flask import current_app
from models import Settings
from utils.encryption import decrypt_data, encrypt_data, generate_key
from extensions import db


class GitLabService:
    """Service for interacting with GitLab API."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._api_url = None
        self._headers = None
        self._token_info = None
        self._gitlab_url = None
        self._token = None

    def get_analytics_service(self):
        """Get analytics service instance."""
        try:
            from services.analytics_service import AnalyticsService
            return AnalyticsService()
        except ImportError:
            self.logger.warning("AnalyticsService not available")
            return None

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
    def gitlab_url(self):
        """Get GitLab URL from settings."""
        if self._gitlab_url is None:
            settings = Settings.query.first()
            if settings and hasattr(settings, 'gitlab_url') and settings.gitlab_url:
                self._gitlab_url = settings.gitlab_url
            else:
                self._gitlab_url = None
        return self._gitlab_url

    @property
    def token(self):
        """Get decrypted GitLab token from settings."""
        if self._token is None:
            settings = Settings.query.first()
            if settings and settings.gitlab_pat_encrypted and settings.encryption_key:
                try:
                    self._token = decrypt_data(settings.gitlab_pat_encrypted, settings.encryption_key)
                except Exception as e:
                    self.logger.error(f"Error decrypting GitLab token: {str(e)}")
                    self._token = None
            else:
                self._token = None
        return self._token

    @property
    def headers(self):
        if self._headers is None:
            self._headers = self._get_headers()
        return self._headers

    @property
    def headers(self):
        """Get headers for GitLab API requests."""
        if self._headers is None and self.token:
            self._headers = {
                'Authorization': f'Bearer {self.token}',
                'Content-Type': 'application/json'
            }
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

    def validate_token(self, token, api_url=None, gitlab_url=None):
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
        try:
            # Use provided URL or fall back to configured URL
            url = gitlab_url or self.gitlab_url or api_url or self.api_url
            if not url:
                return {
                    'valid': False,
                    'message': 'GitLab URL not configured',
                    'error_code': 'NO_URL'
                }

            # Ensure URL format
            if not url.endswith('/api/v4'):
                url = url.rstrip('/') + '/api/v4'

            # Test token by getting user info
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }

            response = requests.get(f'{url}/user', headers=headers, timeout=10)

            if response.status_code == 200:
                user_data = response.json()

                # Get token info for additional details
                token_info = {}
                try:
                    token_response = requests.get(f'{url}/personal_access_tokens/self', headers=headers, timeout=10)
                    if token_response.status_code == 200:
                        token_info = token_response.json()
                except:
                    pass  # Token info is optional

                # Track analytics
                analytics = self.get_analytics_service()
                if analytics:
                    analytics.track_event('gitlab_token_validated', {
                        'user_id': user_data.get('id'),
                        'username': user_data.get('username'),
                        'scopes': token_info.get('scopes', [])
                    })

                return {
                    'valid': True,
                    'message': 'Token is valid',
                    'user_info': {
                        'id': user_data.get('id'),
                        'username': user_data.get('username'),
                        'name': user_data.get('name'),
                        'email': user_data.get('email')
                    },
                    'scopes': token_info.get('scopes', []),
                    'expires_at': token_info.get('expires_at'),
                    'created_at': token_info.get('created_at')
                }
            elif response.status_code == 401:
                return {
                    'valid': False,
                    'message': 'Invalid token or insufficient permissions',
                    'error_code': 'INVALID_TOKEN'
                }
            else:
                return {
                    'valid': False,
                    'message': f'GitLab API error: {response.status_code}',
                    'error_code': 'API_ERROR'
                }

        except requests.exceptions.Timeout:
            return {
                'valid': False,
                'message': 'Request timed out - check GitLab URL',
                'error_code': 'TIMEOUT'
            }
        except requests.exceptions.ConnectionError:
            return {
                'valid': False,
                'message': 'Cannot connect to GitLab - check URL and network',
                'error_code': 'CONNECTION_ERROR'
            }
        except Exception as e:
            self.logger.error(f"Error validating GitLab token: {str(e)}")
            return {
                'valid': False,
                'message': f'Validation error: {str(e)}',
                'error_code': 'VALIDATION_ERROR'
            }

    def check_token_status(self):
        """
        Check the status of the currently stored token.

        Returns:
            dict: Token status information
        """
        try:
            if not self.gitlab_url:
                return {
                    'configured': False,
                    'valid': False,
                    'message': 'GitLab URL not configured',
                    'error_code': 'NO_URL'
                }

            if not self.token:
                return {
                    'configured': False,
                    'valid': False,
                    'message': 'GitLab token not configured',
                    'error_code': 'NO_TOKEN'
                }

            # Validate current token
            validation_result = self.validate_token(self.token, self.gitlab_url)

            if validation_result['valid']:
                # Check expiration
                expires_at = validation_result.get('expires_at')
                if expires_at:
                    try:
                        expiry_date = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                        now = datetime.now(timezone.utc)
                        days_until_expiry = (expiry_date - now).days

                        if days_until_expiry < 0:
                            return {
                                'configured': True,
                                'valid': False,
                                'message': 'Token has expired',
                                'error_code': 'TOKEN_EXPIRED',
                                'expires_at': expires_at,
                                'days_until_expiry': days_until_expiry
                            }
                        elif days_until_expiry <= 7:
                            return {
                                'configured': True,
                                'valid': True,
                                'message': f'Token expires in {days_until_expiry} days',
                                'error_code': 'TOKEN_EXPIRING_SOON',
                                'expires_at': expires_at,
                                'days_until_expiry': days_until_expiry,
                                'user_info': validation_result.get('user_info'),
                                'scopes': validation_result.get('scopes', [])
                            }
                    except Exception as e:
                        self.logger.warning(f"Error parsing expiry date: {str(e)}")

                return {
                    'configured': True,
                    'valid': True,
                    'message': 'Token is valid and active',
                    'expires_at': expires_at,
                    'user_info': validation_result.get('user_info'),
                    'scopes': validation_result.get('scopes', [])
                }
            else:
                return {
                    'configured': True,
                    'valid': False,
                    'message': validation_result.get('message'),
                    'error_code': validation_result.get('error_code')
                }

        except Exception as e:
            self.logger.error(f"Error checking token status: {str(e)}")
            return {
                'configured': True,
                'valid': False,
                'message': f'Status check failed: {str(e)}',
                'error_code': 'STATUS_ERROR'
            }

    def test_connection(self):
        """Test the GitLab connection and return status information."""
        try:
            if not self.gitlab_url:
                return {
                    'success': False,
                    'message': 'GitLab URL not configured',
                    'error_code': 'NO_URL'
                }

            if not self.token or not self.headers:
                return {
                    'success': False,
                    'message': 'GitLab token not configured',
                    'error_code': 'NO_TOKEN'
                }

            # Test API connection
            response = requests.get(f'{self.gitlab_url}/user', headers=self.headers, timeout=10)

            if response.status_code == 200:
                user_data = response.json()

                # Track analytics
                analytics = self.get_analytics_service()
                if analytics:
                    analytics.track_event('gitlab_connection_tested', {
                        'success': True,
                        'user_id': user_data.get('id')
                    })

                return {
                    'success': True,
                    'message': f'Connected as {user_data.get("name", "Unknown")} ({user_data.get("username", "unknown")})',
                    'user_info': user_data
                }
            else:
                return {
                    'success': False,
                    'message': f'GitLab API returned status {response.status_code}',
                    'error_code': 'API_ERROR'
                }

        except requests.exceptions.Timeout:
            return {
                'success': False,
                'message': 'Connection timed out',
                'error_code': 'TIMEOUT'
            }
        except requests.exceptions.ConnectionError:
            return {
                'success': False,
                'message': 'Cannot connect to GitLab',
                'error_code': 'CONNECTION_ERROR'
            }
        except Exception as e:
            self.logger.error(f"Error testing GitLab connection: {str(e)}")
            return {
                'success': False,
                'message': f'Connection test failed: {str(e)}',
                'error_code': 'TEST_ERROR'
            }

    def create_repository(self, name, visibility='private'):
        """Create a new GitLab repository."""
        try:
            if not self.gitlab_url or not self.headers:
                self.logger.error("GitLab not configured")
                return None

            data = {
                'name': name,
                'visibility': visibility,
                'initialize_with_readme': True
            }

            response = requests.post(
                f'{self.gitlab_url}/projects',
                headers=self.headers,
                json=data,
                timeout=30
            )

            if response.status_code == 201:
                repo_data = response.json()

                # Track analytics
                analytics = self.get_analytics_service()
                if analytics:
                    analytics.track_event('gitlab_repo_created', {
                        'repo_id': repo_data.get('id'),
                        'repo_name': name,
                        'visibility': visibility
                    })

                return repo_data
            else:
                self.logger.error(f"Failed to create repository: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            self.logger.error(f"Error creating GitLab repository: {str(e)}")
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

    def get_repositories(self):
        """
        Get user's GitLab repositories.

        Returns:
            list: List of repositories or empty list if failed
        """
        try:
            if not self.gitlab_url or not self.headers:
                return []

            response = requests.get(
                f'{self.gitlab_url}/projects',
                headers=self.headers,
                params={'owned': True, 'per_page': 100},
                timeout=10
            )

            if response.status_code == 200:
                return response.json()
            else:
                self.logger.error(f"Failed to get repositories: {response.status_code}")
                return []

        except Exception as e:
            self.logger.error(f"Error getting GitLab repositories: {str(e)}")
            return []

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

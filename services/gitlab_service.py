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

    # GitLab instance configuration - EXTERNAL URLs
    DEFAULT_GITLAB_BASE_URL = 'https://gitlab.rc.uab.edu'
    DEFAULT_GITLAB_API_URL = 'https://gitlab.rc.uab.edu/api/v4'

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
        """Get GitLab API URL - always use the external GitLab instance."""
        if self._api_url is None:
            settings = Settings.query.first()
            if settings and hasattr(settings, 'gitlab_url') and settings.gitlab_url:
                self._api_url = settings.gitlab_url
                self.logger.info(f"Using configured GitLab API URL: {self._api_url}")
            else:
                # Default to UAB GitLab instance
                self._api_url = self.DEFAULT_GITLAB_API_URL
                self.logger.info(f"Using default GitLab API URL: {self._api_url}")
        return self._api_url

    @property
    def gitlab_url(self):
        """Get GitLab base URL from settings."""
        if self._gitlab_url is None:
            settings = Settings.query.first()
            if settings and hasattr(settings, 'gitlab_url') and settings.gitlab_url:
                # Remove /api/v4 to get base URL
                self._gitlab_url = settings.gitlab_url.replace('/api/v4', '')
                self.logger.info(f"Using configured GitLab base URL: {self._gitlab_url}")
            else:
                # Default to UAB GitLab instance
                self._gitlab_url = self.DEFAULT_GITLAB_BASE_URL
                self.logger.info(f"Using default GitLab base URL: {self._gitlab_url}")
        return self._gitlab_url

    @property
    def token(self):
        """Get decrypted GitLab token from settings."""
        if self._token is None:
            settings = Settings.query.first()
            if settings and settings.gitlab_pat_encrypted and settings.encryption_key:
                try:
                    self._token = decrypt_data(settings.gitlab_pat_encrypted, settings.encryption_key)
                    self.logger.info("GitLab token decrypted successfully")
                except Exception as e:
                    self.logger.error(f"Error decrypting GitLab token: {str(e)}")
                    self._token = None
            else:
                self.logger.warning("No GitLab token configured")
                self._token = None
        return self._token

    @property
    def headers(self):
        """Get headers for GitLab API requests."""
        if self._headers is None and self.token:
            self._headers = {
                'Authorization': f'Bearer {self.token}',
                'Content-Type': 'application/json'
            }
        return self._headers

    def validate_token(self, token, api_url=None, gitlab_url=None):
        """
        Validate a GitLab Personal Access Token and return detailed information.

        Args:
            token: The GitLab personal access token
            api_url: Optional API URL (deprecated, use gitlab_url)
            gitlab_url: The GitLab base URL (e.g., https://gitlab.rc.uab.edu)

        Returns:
            dict: Validation result with user info, scopes, expiration, etc.
        """
        try:
            # Determine the GitLab URL to use
            if gitlab_url:
                # Use provided GitLab URL
                base_url = gitlab_url.rstrip('/')
                if not base_url.endswith('/api/v4'):
                    api_endpoint = f"{base_url}/api/v4"
                else:
                    api_endpoint = base_url
                    base_url = base_url.replace('/api/v4', '')
            elif api_url:
                # Legacy support
                api_endpoint = api_url
                base_url = api_url.replace('/api/v4', '')
            else:
                # Use default UAB GitLab
                api_endpoint = self.DEFAULT_GITLAB_API_URL
                base_url = self.DEFAULT_GITLAB_BASE_URL

            self.logger.info(f"Validating GitLab token against: {api_endpoint}")

            # Test token by getting user info
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }

            response = requests.get(f'{api_endpoint}/user', headers=headers, timeout=10)

            if response.status_code == 200:
                user_data = response.json()

                # Get token info for additional details
                token_info = {}
                try:
                    token_response = requests.get(f'{api_endpoint}/personal_access_tokens/self', headers=headers,
                                                  timeout=10)
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
                        'gitlab_url': base_url,
                        'scopes': token_info.get('scopes', [])
                    })

                return {
                    'valid': True,
                    'message': f'Token is valid for {base_url}',
                    'gitlab_url': base_url,
                    'api_url': api_endpoint,
                    'user_info': {
                        'id': user_data.get('id'),
                        'username': user_data.get('username'),
                        'name': user_data.get('name'),
                        'email': user_data.get('email'),
                        'web_url': user_data.get('web_url')
                    },
                    'scopes': token_info.get('scopes', []),
                    'expires_at': token_info.get('expires_at'),
                    'created_at': token_info.get('created_at')
                }
            elif response.status_code == 401:
                return {
                    'valid': False,
                    'message': 'Invalid token or insufficient permissions',
                    'error_code': 'INVALID_TOKEN',
                    'gitlab_url': base_url
                }
            else:
                return {
                    'valid': False,
                    'message': f'GitLab API error: {response.status_code}',
                    'error_code': 'API_ERROR',
                    'gitlab_url': base_url
                }

        except requests.exceptions.Timeout:
            return {
                'valid': False,
                'message': 'Request timed out - check GitLab URL',
                'error_code': 'TIMEOUT',
                'gitlab_url': gitlab_url or base_url if 'base_url' in locals() else 'unknown'
            }
        except requests.exceptions.ConnectionError:
            return {
                'valid': False,
                'message': 'Cannot connect to GitLab - check URL and network',
                'error_code': 'CONNECTION_ERROR',
                'gitlab_url': gitlab_url or base_url if 'base_url' in locals() else 'unknown'
            }
        except Exception as e:
            self.logger.error(f"Error validating GitLab token: {str(e)}")
            return {
                'valid': False,
                'message': f'Validation error: {str(e)}',
                'error_code': 'VALIDATION_ERROR',
                'gitlab_url': gitlab_url or 'unknown'
            }

    def check_token_status(self):
        """
        Check the status of the currently stored token.

        Returns:
            dict: Token status information
        """
        try:
            # Always ensure we have a GitLab URL
            gitlab_url = self.gitlab_url
            if not gitlab_url:
                # Set default and save it
                settings = Settings.query.first()
                if not settings:
                    settings = Settings()
                    settings.encryption_key = generate_key()
                    db.session.add(settings)

                settings.gitlab_url = self.DEFAULT_GITLAB_API_URL
                db.session.commit()
                gitlab_url = self.DEFAULT_GITLAB_BASE_URL
                self.logger.info(f"Set default GitLab URL: {gitlab_url}")

            if not self.token:
                return {
                    'configured': False,
                    'valid': False,
                    'message': 'GitLab token not configured',
                    'error_code': 'NO_TOKEN',
                    'gitlab_url': gitlab_url
                }

            # Validate current token
            validation_result = self.validate_token(self.token, gitlab_url=gitlab_url)

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
                                'days_until_expiry': days_until_expiry,
                                'gitlab_url': gitlab_url
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
                                'scopes': validation_result.get('scopes', []),
                                'gitlab_url': gitlab_url
                            }
                    except Exception as e:
                        self.logger.warning(f"Error parsing expiry date: {str(e)}")

                return {
                    'configured': True,
                    'valid': True,
                    'message': 'Token is valid and active',
                    'expires_at': expires_at,
                    'user_info': validation_result.get('user_info'),
                    'scopes': validation_result.get('scopes', []),
                    'gitlab_url': gitlab_url
                }
            else:
                return {
                    'configured': True,
                    'valid': False,
                    'message': validation_result.get('message'),
                    'error_code': validation_result.get('error_code'),
                    'gitlab_url': gitlab_url
                }

        except Exception as e:
            self.logger.error(f"Error checking token status: {str(e)}")
            return {
                'configured': True,
                'valid': False,
                'message': f'Status check failed: {str(e)}',
                'error_code': 'STATUS_ERROR',
                'gitlab_url': self.DEFAULT_GITLAB_BASE_URL
            }

    def test_connection(self):
        """Test the GitLab connection and return status information."""
        try:
            gitlab_url = self.gitlab_url
            api_url = self.api_url

            if not self.token or not self.headers:
                return {
                    'success': False,
                    'message': 'GitLab token not configured',
                    'error_code': 'NO_TOKEN',
                    'gitlab_url': gitlab_url
                }

            # Test API connection
            self.logger.info(f"Testing GitLab connection to: {api_url}")
            response = requests.get(f'{api_url}/user', headers=self.headers, timeout=10)

            if response.status_code == 200:
                user_data = response.json()

                # Track analytics
                analytics = self.get_analytics_service()
                if analytics:
                    analytics.track_event('gitlab_connection_tested', {
                        'success': True,
                        'user_id': user_data.get('id'),
                        'gitlab_url': gitlab_url
                    })

                return {
                    'success': True,
                    'message': f'Connected to {gitlab_url} as {user_data.get("name", "Unknown")} ({user_data.get("username", "unknown")})',
                    'user_info': user_data,
                    'gitlab_url': gitlab_url,
                    'api_url': api_url
                }
            else:
                return {
                    'success': False,
                    'message': f'GitLab API returned status {response.status_code}',
                    'error_code': 'API_ERROR',
                    'gitlab_url': gitlab_url
                }

        except requests.exceptions.Timeout:
            return {
                'success': False,
                'message': f'Connection timed out to {gitlab_url}',
                'error_code': 'TIMEOUT',
                'gitlab_url': gitlab_url
            }
        except requests.exceptions.ConnectionError:
            return {
                'success': False,
                'message': f'Cannot connect to GitLab at {gitlab_url}',
                'error_code': 'CONNECTION_ERROR',
                'gitlab_url': gitlab_url
            }
        except Exception as e:
            self.logger.error(f"Error testing GitLab connection: {str(e)}")
            return {
                'success': False,
                'message': f'Connection test failed: {str(e)}',
                'error_code': 'TEST_ERROR',
                'gitlab_url': gitlab_url
            }

    def create_repository(self, name, visibility='private'):
        """Create a new GitLab repository."""
        try:
            if not self.api_url or not self.headers:
                self.logger.error("GitLab not configured")
                return None

            data = {
                'name': name,
                'visibility': visibility,
                'initialize_with_readme': True
            }

            response = requests.post(
                f'{self.api_url}/projects',
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
                        'visibility': visibility,
                        'gitlab_url': self.gitlab_url
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
            self.logger.warning("Cannot delete GitLab repository: No repo ID provided")
            return True

        # Check token status first
        token_status = self.check_token_status()
        if not token_status.get('valid', False):
            self.logger.warning(f"Cannot delete repository: {token_status.get('message')}")
            return True  # Return True to allow cleanup to continue

        try:
            response = requests.delete(
                f"{self.api_url}/projects/{repo_id}",
                headers=self.headers,
                timeout=30
            )
            success = response.status_code in (200, 202, 204)
            if success:
                self.logger.info(f"GitLab repository deleted successfully: {repo_id}")
            else:
                self.logger.error(f"Failed to delete GitLab repository: {response.status_code} - {response.text}")
            return success
        except Exception as e:
            self.logger.error(f"Exception deleting GitLab repository: {str(e)}")
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
                self.logger.error(f"Failed to get GitLab repository info: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            self.logger.error(f"Exception getting GitLab repository info: {str(e)}")
            return None

    def get_repositories(self):
        """
        Get user's GitLab repositories.

        Returns:
            list: List of repositories or empty list if failed
        """
        try:
            if not self.api_url or not self.headers:
                return []

            response = requests.get(
                f'{self.api_url}/projects',
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

    def get_clone_url(self, repo_data, use_ssh=False):
        """
        Get the clone URL for a repository.

        Args:
            repo_data: Repository data from GitLab API
            use_ssh: Whether to use SSH URL (default: False, uses HTTPS)

        Returns:
            str: Clone URL
        """
        if use_ssh:
            return repo_data.get('ssh_url_to_repo')
        else:
            # For HTTPS with token, we'll modify the URL to include the token
            https_url = repo_data.get('http_url_to_repo')
            if https_url and self.token:
                # Insert token into URL: https://oauth2:TOKEN@gitlab.rc.uab.edu/user/repo.git
                https_url = https_url.replace('https://', f'https://oauth2:{self.token}@')
            return https_url

    # Backward compatibility methods
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

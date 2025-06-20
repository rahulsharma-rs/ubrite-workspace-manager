from flask import Blueprint, request, jsonify, send_file, current_app
from models import Workspace
from utils.filesystem import log_event
import os
import logging
import mimetypes
from werkzeug.utils import secure_filename

files_bp = Blueprint('files', __name__)
logger = logging.getLogger(__name__)


def get_analytics_service():
    """Get analytics service instance."""
    try:
        from services.analytics_service import AnalyticsService
        return AnalyticsService()
    except ImportError:
        logger.warning("AnalyticsService not available")
        return None


@files_bp.route('/<int:workspace_id>/list')
def list_files(workspace_id):
    """List files in workspace directory."""
    try:
        workspace = Workspace.query.get_or_404(workspace_id)
        path = request.args.get('path', '')

        # Construct full path
        full_path = os.path.join(workspace.path, path.lstrip('/'))

        # Security check - ensure path is within workspace
        if not full_path.startswith(workspace.path):
            return jsonify({
                'success': False,
                'message': 'Access denied'
            }), 403

        if not os.path.exists(full_path):
            return jsonify({
                'success': False,
                'message': 'Path does not exist'
            }), 404

        if not os.path.isdir(full_path):
            return jsonify({
                'success': False,
                'message': 'Path is not a directory'
            }), 400

        # List directory contents
        items = []
        try:
            for item in os.listdir(full_path):
                item_path = os.path.join(full_path, item)
                is_dir = os.path.isdir(item_path)

                # Get file stats
                stat = os.stat(item_path)

                items.append({
                    'name': item,
                    'type': 'directory' if is_dir else 'file',
                    'size': stat.st_size if not is_dir else None,
                    'modified': stat.st_mtime,
                    'path': os.path.join(path, item).replace('\\', '/')
                })

            # Sort items - directories first, then files
            items.sort(key=lambda x: (x['type'] != 'directory', x['name'].lower()))

            # Track analytics
            analytics = get_analytics_service()
            if analytics:
                analytics.track_event('files_listed', {
                    'ws_id': workspace_id,
                    'path': path,
                    'item_count': len(items)
                })

            return jsonify({
                'success': True,
                'items': items,
                'current_path': path
            })

        except PermissionError:
            return jsonify({
                'success': False,
                'message': 'Permission denied'
            }), 403

    except Exception as e:
        logger.error(f"Error listing files: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@files_bp.route('/<int:workspace_id>/read')
def read_file(workspace_id):
    """Read file content."""
    try:
        workspace = Workspace.query.get_or_404(workspace_id)
        file_path = request.args.get('path', '')

        if not file_path:
            return jsonify({
                'success': False,
                'message': 'File path is required'
            }), 400

        # Construct full path
        full_path = os.path.join(workspace.path, file_path.lstrip('/'))

        # Security check - ensure path is within workspace
        if not full_path.startswith(workspace.path):
            return jsonify({
                'success': False,
                'message': 'Access denied'
            }), 403

        if not os.path.exists(full_path):
            return jsonify({
                'success': False,
                'message': 'File does not exist'
            }), 404

        if not os.path.isfile(full_path):
            return jsonify({
                'success': False,
                'message': 'Path is not a file'
            }), 400

        # Check file size (limit to 10MB for text files)
        file_size = os.path.getsize(full_path)
        if file_size > 10 * 1024 * 1024:  # 10MB
            return jsonify({
                'success': False,
                'message': 'File too large to display'
            }), 413

        # Determine if file is text
        mime_type, _ = mimetypes.guess_type(full_path)
        is_text = mime_type and mime_type.startswith('text/')

        if not is_text:
            # For binary files, return file info instead of content
            return jsonify({
                'success': True,
                'is_binary': True,
                'size': file_size,
                'mime_type': mime_type,
                'message': 'Binary file - content not displayed'
            })

        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Track analytics
            analytics = get_analytics_service()
            if analytics:
                analytics.track_event('file_read', {
                    'ws_id': workspace_id,
                    'file_path': file_path,
                    'file_size': file_size
                })

            return jsonify({
                'success': True,
                'content': content,
                'is_binary': False,
                'size': file_size,
                'mime_type': mime_type
            })

        except UnicodeDecodeError:
            return jsonify({
                'success': False,
                'message': 'File contains binary data or unsupported encoding'
            }), 400

    except Exception as e:
        logger.error(f"Error reading file: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@files_bp.route('/<int:workspace_id>/write', methods=['POST'])
def write_file(workspace_id):
    """Write content to file."""
    try:
        workspace = Workspace.query.get_or_404(workspace_id)
        data = request.json

        file_path = data.get('path', '')
        content = data.get('content', '')

        if not file_path:
            return jsonify({
                'success': False,
                'message': 'File path is required'
            }), 400

        # Construct full path
        full_path = os.path.join(workspace.path, file_path.lstrip('/'))

        # Security check - ensure path is within workspace
        if not full_path.startswith(workspace.path):
            return jsonify({
                'success': False,
                'message': 'Access denied'
            }), 403

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        # Write file
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)

        # Log the event
        log_event(workspace_id, 'file_written', {
            'file_path': file_path,
            'content_length': len(content)
        })

        # Track analytics
        analytics = get_analytics_service()
        if analytics:
            analytics.track_event('file_written', {
                'ws_id': workspace_id,
                'file_path': file_path,
                'content_length': len(content)
            })

        return jsonify({
            'success': True,
            'message': 'File saved successfully'
        })

    except Exception as e:
        logger.error(f"Error writing file: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@files_bp.route('/<int:workspace_id>/delete', methods=['POST'])
def delete_file(workspace_id):
    """Delete file or directory."""
    try:
        workspace = Workspace.query.get_or_404(workspace_id)
        data = request.json

        file_path = data.get('path', '')

        if not file_path:
            return jsonify({
                'success': False,
                'message': 'File path is required'
            }), 400

        # Construct full path
        full_path = os.path.join(workspace.path, file_path.lstrip('/'))

        # Security check - ensure path is within workspace
        if not full_path.startswith(workspace.path):
            return jsonify({
                'success': False,
                'message': 'Access denied'
            }), 403

        if not os.path.exists(full_path):
            return jsonify({
                'success': False,
                'message': 'File or directory does not exist'
            }), 404

        # Delete file or directory
        if os.path.isfile(full_path):
            os.remove(full_path)
            item_type = 'file'
        else:
            import shutil
            shutil.rmtree(full_path)
            item_type = 'directory'

        # Log the event
        log_event(workspace_id, 'file_deleted', {
            'file_path': file_path,
            'item_type': item_type
        })

        # Track analytics
        analytics = get_analytics_service()
        if analytics:
            analytics.track_event('file_deleted', {
                'ws_id': workspace_id,
                'file_path': file_path,
                'item_type': item_type
            })

        return jsonify({
            'success': True,
            'message': f'{item_type.capitalize()} deleted successfully'
        })

    except Exception as e:
        logger.error(f"Error deleting file: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@files_bp.route('/<int:workspace_id>/upload', methods=['POST'])
def upload_file(workspace_id):
    """Upload file to workspace."""
    try:
        workspace = Workspace.query.get_or_404(workspace_id)

        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'message': 'No file provided'
            }), 400

        file = request.files['file']
        upload_path = request.form.get('path', '')

        if file.filename == '':
            return jsonify({
                'success': False,
                'message': 'No file selected'
            }), 400

        # Secure filename
        filename = secure_filename(file.filename)

        # Construct full path
        full_path = os.path.join(workspace.path, upload_path.lstrip('/'), filename)

        # Security check - ensure path is within workspace
        if not full_path.startswith(workspace.path):
            return jsonify({
                'success': False,
                'message': 'Access denied'
            }), 403

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        # Save file
        file.save(full_path)

        # Get file size
        file_size = os.path.getsize(full_path)

        # Log the event
        log_event(workspace_id, 'file_uploaded', {
            'filename': filename,
            'upload_path': upload_path,
            'file_size': file_size
        })

        # Track analytics
        analytics = get_analytics_service()
        if analytics:
            analytics.track_event('file_uploaded', {
                'ws_id': workspace_id,
                'filename': filename,
                'file_size': file_size
            })

        return jsonify({
            'success': True,
            'message': 'File uploaded successfully',
            'filename': filename,
            'size': file_size
        })

    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@files_bp.route('/<int:workspace_id>/download')
def download_file(workspace_id):
    """Download file from workspace."""
    try:
        workspace = Workspace.query.get_or_404(workspace_id)
        file_path = request.args.get('path', '')

        if not file_path:
            return jsonify({
                'success': False,
                'message': 'File path is required'
            }), 400

        # Construct full path
        full_path = os.path.join(workspace.path, file_path.lstrip('/'))

        # Security check - ensure path is within workspace
        if not full_path.startswith(workspace.path):
            return jsonify({
                'success': False,
                'message': 'Access denied'
            }), 403

        if not os.path.exists(full_path):
            return jsonify({
                'success': False,
                'message': 'File does not exist'
            }), 404

        if not os.path.isfile(full_path):
            return jsonify({
                'success': False,
                'message': 'Path is not a file'
            }), 400

        # Track analytics
        analytics = get_analytics_service()
        if analytics:
            analytics.track_event('file_downloaded', {
                'ws_id': workspace_id,
                'file_path': file_path,
                'file_size': os.path.getsize(full_path)
            })

        return send_file(full_path, as_attachment=True)

    except Exception as e:
        logger.error(f"Error downloading file: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

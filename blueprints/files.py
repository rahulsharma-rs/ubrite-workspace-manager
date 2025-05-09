from flask import Blueprint, render_template, request, jsonify, current_app, send_file, abort
from models import Workspace
from extensions import db
from utils.filesystem import log_event
from services.analytics_service import AnalyticsService
import os
import shutil
import logging
import mimetypes
import json
from werkzeug.utils import secure_filename
import zipfile
import io
import tempfile

files_bp = Blueprint('files', __name__)
analytics_service = AnalyticsService()
logger = logging.getLogger(__name__)


@files_bp.route('/<int:workspace_id>/explorer')
def file_explorer(workspace_id):
    """Render the file explorer page."""
    workspace = Workspace.query.get_or_404(workspace_id)
    return render_template('files/explorer.html', workspace=workspace)


@files_bp.route('/<int:workspace_id>/list')
def list_files(workspace_id):
    """List files and directories in a workspace."""
    try:
        workspace = Workspace.query.get_or_404(workspace_id)

        # Get the path parameter, relative to the workspace root
        path = request.args.get('path', '')

        # Ensure the path is secure (doesn't go outside the workspace)
        if '..' in path:
            return jsonify({
                'success': False,
                'message': 'Invalid path'
            }), 400

        # Construct the full path
        full_path = os.path.join(workspace.path, path)

        # Check if the path exists
        if not os.path.exists(full_path):
            return jsonify({
                'success': False,
                'message': f"Path does not exist: {path}"
            }), 404

        # Get the list of files and directories
        items = []
        for item in os.listdir(full_path):
            item_path = os.path.join(full_path, item)
            item_rel_path = os.path.join(path, item) if path else item

            # Skip .git directory
            if item == '.git' and os.path.isdir(item_path):
                continue

            # Get item stats
            stats = os.stat(item_path)

            # Determine item type
            item_type = 'directory' if os.path.isdir(item_path) else 'file'

            # Get file extension and mime type for files
            extension = ''
            mime_type = ''
            if item_type == 'file':
                _, extension = os.path.splitext(item)
                mime_type, _ = mimetypes.guess_type(item_path)
                if mime_type is None:
                    mime_type = 'application/octet-stream'

            items.append({
                'name': item,
                'path': item_rel_path,
                'type': item_type,
                'size': stats.st_size,
                'modified': stats.st_mtime,
                'extension': extension.lower(),
                'mime_type': mime_type
            })

        # Sort items: directories first, then files, both alphabetically
        items.sort(key=lambda x: (x['type'] != 'directory', x['name'].lower()))

        return jsonify({
            'success': True,
            'path': path,
            'items': items
        })
    except Exception as e:
        logger.error(f"Error listing files: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"An error occurred: {str(e)}"
        }), 500


@files_bp.route('/<int:workspace_id>/file')
def get_file(workspace_id):
    """Get the contents of a file."""
    try:
        workspace = Workspace.query.get_or_404(workspace_id)

        # Get the path parameter
        path = request.args.get('path', '')

        # Ensure the path is secure
        if '..' in path:
            return jsonify({
                'success': False,
                'message': 'Invalid path'
            }), 400

        # Construct the full path
        full_path = os.path.join(workspace.path, path)

        # Check if the file exists
        if not os.path.exists(full_path):
            return jsonify({
                'success': False,
                'message': f"File does not exist: {path}"
            }), 404

        # Check if it's a directory
        if os.path.isdir(full_path):
            return jsonify({
                'success': False,
                'message': f"Path is a directory, not a file: {path}"
            }), 400

        # Get the file's mime type
        mime_type, _ = mimetypes.guess_type(full_path)

        # Check if it's a binary file
        if mime_type and (mime_type.startswith('image/') or
                          mime_type.startswith('audio/') or
                          mime_type.startswith('video/') or
                          mime_type == 'application/pdf' or
                          'octet-stream' in mime_type):
            # For binary files, return a download URL
            return jsonify({
                'success': True,
                'is_binary': True,
                'mime_type': mime_type,
                'download_url': f"/files/{workspace_id}/download?path={path}"
            })

        # For text files, read the content
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()

            return jsonify({
                'success': True,
                'is_binary': False,
                'content': content,
                'mime_type': mime_type or 'text/plain'
            })
        except UnicodeDecodeError:
            # If we can't decode as UTF-8, it's probably a binary file
            return jsonify({
                'success': True,
                'is_binary': True,
                'mime_type': 'application/octet-stream',
                'download_url': f"/files/{workspace_id}/download?path={path}"
            })
    except Exception as e:
        logger.error(f"Error getting file: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"An error occurred: {str(e)}"
        }), 500


@files_bp.route('/<int:workspace_id>/download')
def download_file(workspace_id):
    """Download a file."""
    try:
        workspace = Workspace.query.get_or_404(workspace_id)

        # Get the path parameter
        path = request.args.get('path', '')

        # Ensure the path is secure
        if '..' in path:
            abort(400)

        # Construct the full path
        full_path = os.path.join(workspace.path, path)

        # Check if the file exists
        if not os.path.exists(full_path) or os.path.isdir(full_path):
            abort(404)

        # Log the download
        log_event(workspace.id, 'file_downloaded', {
            'path': path
        })

        # Return the file
        return send_file(full_path, as_attachment=True)
    except Exception as e:
        logger.error(f"Error downloading file: {str(e)}")
        abort(500)


@files_bp.route('/<int:workspace_id>/download-folder')
def download_folder(workspace_id):
    """Download a folder as a zip file."""
    try:
        workspace = Workspace.query.get_or_404(workspace_id)

        # Get the path parameter
        path = request.args.get('path', '')

        # Ensure the path is secure
        if '..' in path:
            abort(400)

        # Construct the full path
        full_path = os.path.join(workspace.path, path)

        # Check if the directory exists
        if not os.path.exists(full_path) or not os.path.isdir(full_path):
            abort(404)

        # Create a temporary file for the zip
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_file:
            temp_path = temp_file.name

        # Create a zip file
        folder_name = os.path.basename(path) if path else workspace.name
        with zipfile.ZipFile(temp_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(full_path):
                # Skip .git directory
                if '.git' in dirs:
                    dirs.remove('.git')

                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, full_path)
                    zipf.write(file_path, arcname)

        # Log the download
        log_event(workspace.id, 'folder_downloaded', {
            'path': path
        })

        # Return the zip file
        return send_file(
            temp_path,
            as_attachment=True,
            download_name=f"{folder_name}.zip",
            mimetype='application/zip'
        )
    except Exception as e:
        logger.error(f"Error downloading folder: {str(e)}")
        abort(500)


@files_bp.route('/<int:workspace_id>/save', methods=['POST'])
def save_file(workspace_id):
    """Save a file."""
    try:
        workspace = Workspace.query.get_or_404(workspace_id)
        data = request.json

        path = data.get('path', '')
        content = data.get('content', '')

        # Ensure the path is secure
        if '..' in path:
            return jsonify({
                'success': False,
                'message': 'Invalid path'
            }), 400

        # Construct the full path
        full_path = os.path.join(workspace.path, path)

        # Create parent directories if they don't exist
        parent_dir = os.path.dirname(full_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)

        # Write the file
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)

        # Log the save
        log_event(workspace.id, 'file_saved', {
            'path': path
        })

        return jsonify({
            'success': True,
            'message': 'File saved successfully'
        })
    except Exception as e:
        logger.error(f"Error saving file: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"An error occurred: {str(e)}"
        }), 500


@files_bp.route('/<int:workspace_id>/upload', methods=['POST'])
def upload_file(workspace_id):
    """Upload a file."""
    try:
        workspace = Workspace.query.get_or_404(workspace_id)

        # Get the path parameter
        path = request.form.get('path', '')

        # Ensure the path is secure
        if '..' in path:
            return jsonify({
                'success': False,
                'message': 'Invalid path'
            }), 400

        # Check if a file was uploaded
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'message': 'No file part'
            }), 400

        file = request.files['file']

        # Check if the file has a name
        if file.filename == '':
            return jsonify({
                'success': False,
                'message': 'No selected file'
            }), 400

        # Secure the filename
        filename = secure_filename(file.filename)

        # Construct the full path
        full_dir_path = os.path.join(workspace.path, path)
        full_file_path = os.path.join(full_dir_path, filename)

        # Create parent directories if they don't exist
        os.makedirs(full_dir_path, exist_ok=True)

        # Save the file
        file.save(full_file_path)

        # Log the upload
        log_event(workspace.id, 'file_uploaded', {
            'path': os.path.join(path, filename)
        })

        return jsonify({
            'success': True,
            'message': 'File uploaded successfully',
            'path': os.path.join(path, filename)
        })
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"An error occurred: {str(e)}"
        }), 500


@files_bp.route('/<int:workspace_id>/delete', methods=['POST'])
def delete_file(workspace_id):
    """Delete a file or directory."""
    try:
        workspace = Workspace.query.get_or_404(workspace_id)
        data = request.json

        path = data.get('path', '')

        # Ensure the path is secure
        if '..' in path:
            return jsonify({
                'success': False,
                'message': 'Invalid path'
            }), 400

        # Construct the full path
        full_path = os.path.join(workspace.path, path)

        # Check if the path exists
        if not os.path.exists(full_path):
            return jsonify({
                'success': False,
                'message': f"Path does not exist: {path}"
            }), 404

        # Delete the file or directory
        if os.path.isdir(full_path):
            shutil.rmtree(full_path)
        else:
            os.remove(full_path)

        # Log the deletion
        log_event(workspace.id, 'file_deleted', {
            'path': path
        })

        return jsonify({
            'success': True,
            'message': 'Item deleted successfully'
        })
    except Exception as e:
        logger.error(f"Error deleting file: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"An error occurred: {str(e)}"
        }), 500


@files_bp.route('/<int:workspace_id>/create-folder', methods=['POST'])
def create_folder(workspace_id):
    """Create a new folder."""
    try:
        workspace = Workspace.query.get_or_404(workspace_id)
        data = request.json

        path = data.get('path', '')
        folder_name = data.get('name', '')

        # Ensure the path is secure
        if '..' in path or '..' in folder_name:
            return jsonify({
                'success': False,
                'message': 'Invalid path'
            }), 400

        # Construct the full path
        full_path = os.path.join(workspace.path, path, folder_name)

        # Check if the folder already exists
        if os.path.exists(full_path):
            return jsonify({
                'success': False,
                'message': f"Folder already exists: {folder_name}"
            }), 400

        # Create the folder
        os.makedirs(full_path, exist_ok=True)

        # Log the creation
        log_event(workspace.id, 'folder_created', {
            'path': os.path.join(path, folder_name)
        })

        return jsonify({
            'success': True,
            'message': 'Folder created successfully'
        })
    except Exception as e:
        logger.error(f"Error creating folder: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"An error occurred: {str(e)}"
        }), 500


@files_bp.route('/<int:workspace_id>/rename', methods=['POST'])
def rename_item(workspace_id):
    """Rename a file or directory."""
    try:
        workspace = Workspace.query.get_or_404(workspace_id)
        data = request.json

        path = data.get('path', '')
        new_name = data.get('new_name', '')

        # Ensure the paths are secure
        if '..' in path or '..' in new_name:
            return jsonify({
                'success': False,
                'message': 'Invalid path'
            }), 400

        # Construct the full paths
        full_path = os.path.join(workspace.path, path)
        dir_name = os.path.dirname(path)
        new_path = os.path.join(workspace.path, dir_name, new_name)

        # Check if the source exists
        if not os.path.exists(full_path):
            return jsonify({
                'success': False,
                'message': f"Path does not exist: {path}"
            }), 404

        # Check if the destination already exists
        if os.path.exists(new_path):
            return jsonify({
                'success': False,
                'message': f"Destination already exists: {new_name}"
            }), 400

        # Rename the file or directory
        os.rename(full_path, new_path)

        # Log the rename
        log_event(workspace.id, 'item_renamed', {
            'old_path': path,
            'new_path': os.path.join(dir_name, new_name)
        })

        return jsonify({
            'success': True,
            'message': 'Item renamed successfully'
        })
    except Exception as e:
        logger.error(f"Error renaming item: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"An error occurred: {str(e)}"
        }), 500

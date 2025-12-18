"""
Flask Supercomputer File Management Application - Phase 1
Main application entry point with core functionality
"""

from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session
import subprocess
import os
import pwd
import grp
import stat
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
import logging
from functools import wraps
import json

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# Configuration
class Config:
    # Base configuration - can be overridden via environment variables
    HOME_BASE = os.environ.get('HOME_BASE', '/home')
    SHARED_FOLDER_NAME = 'shared_with_me'
    DB_FOLDER_NAME = '.filemanager'
    DB_NAME = 'filemanager.db'

    # User filtering - only show users with UID in this range
    MIN_USER_UID = int(os.environ.get('MIN_USER_UID', '1000'))
    MAX_USER_UID = int(os.environ.get('MAX_USER_UID', '60000'))

    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', '/tmp/filemanager.log')

config = Config()

# Setup logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# IDENTITY RESOLUTION - Determine current Linux user
# ============================================================================

def get_current_user():
    """
    Determine the current Linux username from the request context.
    Priority order:
    1. REMOTE_USER header (set by reverse proxy with auth)
    2. X-Forwarded-User header
    3. Environment variable AUTHENTICATED_USER
    4. Fall back to process owner (for development only)
    """
    user = None

    # Try request headers first (production scenario)
    if request:
        user = request.environ.get('REMOTE_USER')
        if not user:
            user = request.headers.get('X-Forwarded-User')

    # Try environment variable
    if not user:
        user = os.environ.get('AUTHENTICATED_USER')

    # Development fallback - use process owner
    if not user:
        user = pwd.getpwuid(os.getuid()).pw_name
        logger.warning(f"Using process owner '{user}' - NOT suitable for production")

    logger.info(f"Resolved user: {user}")
    return user


def require_user(f):
    """Decorator to ensure user is identified"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            logger.error("Unable to identify user")
            return jsonify({'error': 'Unable to identify user'}), 401
        return f(user, *args, **kwargs)
    return decorated_function


# ============================================================================
# DATABASE OPERATIONS
# ============================================================================

class Database:
    """Per-user SQLite database manager"""

    @staticmethod
    def get_db_path(username):
        """Get path to user's database file"""
        user_home = os.path.join(config.HOME_BASE, username)
        db_dir = os.path.join(user_home, config.DB_FOLDER_NAME)
        os.makedirs(db_dir, mode=0o700, exist_ok=True)
        return os.path.join(db_dir, config.DB_NAME)

    @staticmethod
    def init_db(username):
        """Initialize database schema for user"""
        db_path = Database.get_db_path(username)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Shares table - tracks all sharing relationships
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS shares (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                share_type TEXT NOT NULL,  -- 'outgoing' or 'incoming'
                source_path TEXT NOT NULL,
                target_path TEXT NOT NULL,
                shared_with TEXT,
                shared_by TEXT,
                permission TEXT NOT NULL,  -- 'view' or 'edit'
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active'  -- 'active', 'revoked', 'broken'
            )
        ''')

        # Audit log - track all operations
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                action TEXT NOT NULL,
                target_path TEXT,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip_address TEXT
            )
        ''')

        # Future-ready tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()
        logger.info(f"Database initialized for user: {username}")

    @staticmethod
    def log_action(username, action, target_path=None, details=None, ip_address=None):
        """Log an action to audit trail"""
        db_path = Database.get_db_path(username)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO audit_log (username, action, target_path, details, ip_address)
            VALUES (?, ?, ?, ?, ?)
        ''', (username, action, target_path, details, ip_address))

        conn.commit()
        conn.close()
        logger.info(f"AUDIT: {username} - {action} - {target_path}")


# ============================================================================
# PATH SECURITY & VALIDATION
# ============================================================================

class PathValidator:
    """Secure path validation and resolution"""

    @staticmethod
    def get_user_home(username):
        """Get user's home directory"""
        return os.path.join(config.HOME_BASE, username)

    @staticmethod
    def get_shared_dir(username):
        """Get user's shared_with_me directory"""
        return os.path.join(PathValidator.get_user_home(username), config.SHARED_FOLDER_NAME)

    @staticmethod
    def is_safe_path(username, requested_path):
        """
        Validate that requested_path is within user's allowed scope.
        Returns (is_safe, resolved_path, path_type)
        path_type: 'home', 'shared', or None
        """
        user_home = PathValidator.get_user_home(username)
        shared_dir = PathValidator.get_shared_dir(username)

        # Resolve to absolute path
        try:
            abs_path = os.path.abspath(requested_path)
            real_path = os.path.realpath(abs_path)
        except Exception as e:
            logger.error(f"Path resolution error: {e}")
            return False, None, None

        # Check if within user's home
        if real_path.startswith(user_home + os.sep) or real_path == user_home:
            return True, real_path, 'home'

        # Check if it's a symlink in shared_with_me pointing elsewhere
        # (This is allowed - it's how sharing works)
        if abs_path.startswith(shared_dir + os.sep) or abs_path == shared_dir:
            # The symlink itself is in shared_with_me, so it's allowed
            return True, real_path, 'shared'

        logger.warning(f"Path traversal attempt by {username}: {requested_path} -> {real_path}")
        return False, None, None

    @staticmethod
    def can_user_access(username, path, mode='r'):
        """Check if user has OS-level permission to access path"""
        try:
            if mode == 'r':
                return os.access(path, os.R_OK)
            elif mode == 'w':
                return os.access(path, os.W_OK)
            elif mode == 'x':
                return os.access(path, os.X_OK)
            return False
        except Exception as e:
            logger.error(f"Permission check error: {e}")
            return False


# ============================================================================
# FILE OPERATIONS
# ============================================================================

class FileManager:
    """Core file management operations"""

    @staticmethod
    def list_directory(username, path):
        """List directory contents with metadata"""
        is_safe, real_path, path_type = PathValidator.is_safe_path(username, path)

        if not is_safe:
            raise PermissionError(f"Access denied to path: {path}")

        if not os.path.exists(real_path):
            raise FileNotFoundError(f"Path does not exist: {path}")

        if not os.path.isdir(real_path):
            raise NotADirectoryError(f"Not a directory: {path}")

        items = []
        try:
            for entry in os.scandir(real_path):
                try:
                    stat_info = entry.stat(follow_symlinks=False)
                    is_link = entry.is_symlink()

                    item = {
                        'name': entry.name,
                        'path': entry.path,
                        'is_dir': entry.is_dir(follow_symlinks=True),
                        'is_file': entry.is_file(follow_symlinks=True),
                        'is_link': is_link,
                        'size': stat_info.st_size,
                        'modified': datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
                        'permissions': oct(stat.S_IMODE(stat_info.st_mode)),
                        'readable': os.access(entry.path, os.R_OK),
                        'writable': os.access(entry.path, os.W_OK)
                    }

                    # Add link target if it's a symlink
                    if is_link:
                        try:
                            item['link_target'] = os.readlink(entry.path)
                            item['link_broken'] = not os.path.exists(entry.path)
                        except:
                            item['link_broken'] = True

                    items.append(item)
                except Exception as e:
                    logger.error(f"Error reading entry {entry.name}: {e}")
                    continue

            items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
            return items

        except PermissionError:
            raise PermissionError(f"Permission denied to list directory: {path}")

    @staticmethod
    def create_folder(username, parent_path, folder_name):
        """Create a new folder"""
        is_safe, real_parent, _ = PathValidator.is_safe_path(username, parent_path)

        if not is_safe:
            raise PermissionError("Access denied")

        new_folder = os.path.join(real_parent, folder_name)

        # Security check - ensure new path is still safe
        is_safe_new, _, _ = PathValidator.is_safe_path(username, new_folder)
        if not is_safe_new:
            raise PermissionError("Invalid folder path")

        os.makedirs(new_folder, mode=0o755, exist_ok=False)
        Database.log_action(username, 'CREATE_FOLDER', new_folder, ip_address=request.remote_addr)
        logger.info(f"Created folder: {new_folder}")
        return new_folder

    @staticmethod
    def create_file(username, parent_path, file_name, content=''):
        """Create a new file"""
        is_safe, real_parent, _ = PathValidator.is_safe_path(username, parent_path)

        if not is_safe:
            raise PermissionError("Access denied")

        new_file = os.path.join(real_parent, file_name)

        is_safe_new, _, _ = PathValidator.is_safe_path(username, new_file)
        if not is_safe_new:
            raise PermissionError("Invalid file path")

        with open(new_file, 'w') as f:
            f.write(content)

        os.chmod(new_file, 0o644)
        Database.log_action(username, 'CREATE_FILE', new_file, ip_address=request.remote_addr)
        logger.info(f"Created file: {new_file}")
        return new_file

    @staticmethod
    def rename_item(username, old_path, new_name):
        """Rename a file or folder"""
        is_safe, real_old_path, _ = PathValidator.is_safe_path(username, old_path)

        if not is_safe:
            raise PermissionError("Access denied")

        parent_dir = os.path.dirname(real_old_path)
        new_path = os.path.join(parent_dir, new_name)

        is_safe_new, _, _ = PathValidator.is_safe_path(username, new_path)
        if not is_safe_new:
            raise PermissionError("Invalid new path")

        os.rename(real_old_path, new_path)
        Database.log_action(username, 'RENAME', old_path,
                          details=json.dumps({'old': old_path, 'new': new_path}),
                          ip_address=request.remote_addr)
        logger.info(f"Renamed: {old_path} -> {new_path}")
        return new_path

    @staticmethod
    def delete_item(username, path):
        """Delete a file or folder"""
        is_safe, real_path, _ = PathValidator.is_safe_path(username, path)

        if not is_safe:
            raise PermissionError("Access denied")

        # Don't allow deleting home directory itself
        if real_path == PathValidator.get_user_home(username):
            raise PermissionError("Cannot delete home directory")

        if os.path.isdir(real_path) and not os.path.islink(real_path):
            shutil.rmtree(real_path)
        else:
            os.remove(real_path)

        Database.log_action(username, 'DELETE', path, ip_address=request.remote_addr)
        logger.info(f"Deleted: {path}")
        return True

    @staticmethod
    def move_item(username, source_path, dest_dir):
        """Move a file or folder to another directory"""
        is_safe_src, real_src, _ = PathValidator.is_safe_path(username, source_path)
        is_safe_dst, real_dst, _ = PathValidator.is_safe_path(username, dest_dir)

        if not (is_safe_src and is_safe_dst):
            raise PermissionError("Access denied")

        if not os.path.isdir(real_dst):
            raise NotADirectoryError("Destination is not a directory")

        item_name = os.path.basename(real_src)
        new_path = os.path.join(real_dst, item_name)

        is_safe_new, _, _ = PathValidator.is_safe_path(username, new_path)
        if not is_safe_new:
            raise PermissionError("Invalid destination path")

        shutil.move(real_src, new_path)
        Database.log_action(username, 'MOVE', source_path,
                          details=json.dumps({'from': source_path, 'to': new_path}),
                          ip_address=request.remote_addr)
        logger.info(f"Moved: {source_path} -> {new_path}")
        return new_path

    @staticmethod
    def search(username, root_path, query, max_depth=3, max_results=200):
        """
        Search for files/folders under root_path matching the query (case-insensitive).
        Limited by max_depth (relative to root) and max_results for safety.
        """
        is_safe, real_root, _ = PathValidator.is_safe_path(username, root_path)
        if not is_safe:
            raise PermissionError("Access denied")

        if not os.path.exists(real_root):
            raise FileNotFoundError(f"Path does not exist: {root_path}")

        query_lower = query.lower()
        results = []
        root_depth = len(Path(real_root).parts)

        for current_root, dirs, files in os.walk(real_root, followlinks=False):
            depth = len(Path(current_root).parts) - root_depth
            if depth > max_depth:
                # Prevent descending deeper
                dirs[:] = []
                continue

            # Combine dirs and files to check names
            for name in dirs + files:
                if query_lower not in name.lower():
                    continue

                full_path = os.path.join(current_root, name)

                # Ensure the path is still within allowed scope (handles symlinks in shared dir)
                is_allowed, resolved_path, _ = PathValidator.is_safe_path(username, full_path)
                if not is_allowed:
                    continue

                try:
                    stat_info = os.stat(full_path, follow_symlinks=False)
                    is_link = os.path.islink(full_path)
                    results.append({
                        'name': name,
                        'path': full_path,
                        'parent_path': current_root,
                        'is_dir': os.path.isdir(full_path),
                        'is_file': os.path.isfile(full_path),
                        'is_link': is_link,
                        'size': stat_info.st_size,
                        'modified': datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
                        'permissions': oct(stat.S_IMODE(stat_info.st_mode)),
                    })
                except Exception as e:
                    logger.error(f"Error stat-ing search result {full_path}: {e}")
                    continue

                if len(results) >= max_results:
                    return results

        return results


# ============================================================================
# SHARING SYSTEM
# ============================================================================

class ShareManager:
    """Manage file/folder sharing between users using HPC ACLs"""

    @staticmethod
    def get_system_users():
        """Get list of real system users (filtered by UID range)"""
        users = []
        for user in pwd.getpwall():
            if config.MIN_USER_UID <= user.pw_uid <= config.MAX_USER_UID:
                users.append({
                    'username': user.pw_name,
                    'uid': user.pw_uid,
                    'home': user.pw_dir,
                    'fullname': user.pw_gecos.split(',')[0] if user.pw_gecos else user.pw_name
                })
        return sorted(users, key=lambda x: x['username'])

    @staticmethod
    def create_share(owner_username, source_path, recipient_username, permission):
        """
        Share a file/folder with another user via symlink and ACLs.
        """
        # 1. Validate source path
        is_safe, real_source, _ = PathValidator.is_safe_path(owner_username, source_path)
        if not is_safe:
            raise PermissionError("Access denied to source path")

        if not os.path.exists(real_source):
            raise FileNotFoundError("Source path does not exist")

        # 2. Validate recipient exists
        try:
            pwd.getpwnam(recipient_username)
        except KeyError:
            raise ValueError(f"User {recipient_username} does not exist")

        # 3. Handle Recipient Directory - ROBUST AUTO-INIT

        # FIX: Manually build the path string.
        # DO NOT call Database.get_db_path() here because it tries to os.makedirs() and crashes.
        recipient_home = PathValidator.get_user_home(recipient_username)
        recipient_shared_dir = os.path.join(recipient_home, config.SHARED_FOLDER_NAME)
        recipient_db_dir = os.path.join(recipient_home, config.DB_FOLDER_NAME)

        # Check if we need to run the setup script
        needs_init = False

        if not os.path.exists(recipient_shared_dir):
            needs_init = True
        elif not os.path.exists(recipient_db_dir):
            needs_init = True
        elif not os.access(recipient_db_dir, os.W_OK):
            # It exists but we can't write to it
            needs_init = True

        if needs_init:
            try:
                current_app_user = pwd.getpwuid(os.getuid()).pw_name
                logger.info(f"Auto-initializing recipient {recipient_username}...")

                # Run the script to fix permissions
                subprocess.run(
                    ['sudo', '/opt/filemanager/init_user.sh', recipient_username, current_app_user],
                    check=True,
                    capture_output=True
                )
            except subprocess.CalledProcessError as e:
                # Log the stderr to see why the script failed
                logger.error(f"Failed to init recipient: {e.stderr.decode()}")
                raise PermissionError(f"Could not initialize {recipient_username}'s account.")

        # 4. Create symlink
        item_name = os.path.basename(real_source)
        link_name = f"{item_name}_from_{owner_username}"
        link_path = os.path.join(recipient_shared_dir, link_name)

        counter = 1
        while os.path.exists(link_path):
            link_name = f"{item_name}_from_{owner_username}_{counter}"
            link_path = os.path.join(recipient_shared_dir, link_name)
            counter += 1

        try:
            os.symlink(real_source, link_path)
        except PermissionError:
            raise PermissionError(f"Permission denied creating link in {recipient_shared_dir}")

        # 5. Set ACLs
        ShareManager._set_hpc_permissions(real_source, recipient_username, permission)

        # 6. Database Records
        # Owner DB
        owner_db = Database.get_db_path(owner_username)
        conn = sqlite3.connect(owner_db)
        cursor = conn.cursor()
        cursor.execute('''
                       INSERT INTO shares (share_type, source_path, target_path, shared_with, permission)
                       VALUES (?, ?, ?, ?, ?)
                       ''', ('outgoing', real_source, link_path, recipient_username, permission))
        share_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Recipient DB
        # NOW it is safe to call init_db because the sudo script has run and permissions are fixed
        Database.init_db(recipient_username)
        recipient_db = Database.get_db_path(recipient_username)
        conn = sqlite3.connect(recipient_db)
        cursor = conn.cursor()
        cursor.execute('''
                       INSERT INTO shares (share_type, source_path, target_path, shared_by, permission)
                       VALUES (?, ?, ?, ?, ?)
                       ''', ('incoming', real_source, link_path, owner_username, permission))
        conn.commit()
        conn.close()

        Database.log_action(owner_username, 'SHARE_CREATE', real_source,
                            details=json.dumps({'recipient': recipient_username, 'permission': permission}),
                            ip_address=request.remote_addr)

        logger.info(f"Share created: {owner_username} -> {recipient_username}")
        return {'share_id': share_id, 'link_path': link_path}

    @staticmethod
    def _set_hpc_permissions(path, recipient_username, permission):
        """
        Uses setfacl to grant access to the specific user.
        """
        try:
            # r-x for view (allows entering directories), rwx for edit
            perm_str = "rwx" if permission == 'edit' else "r-x"

            # 1. Grant access to the specific file/folder
            # -m: modify, u:user:permissions
            subprocess.run(['setfacl', '-R', '-m', f'u:{recipient_username}:{perm_str}', path], check=True)

            # 2. If it's a directory, set 'default' ACLs so future files are also shared
            if os.path.isdir(path):
                subprocess.run(['setfacl', '-R', '-d', '-m', f'u:{recipient_username}:{perm_str}', path], check=True)

            # 3. IMPORTANT: Grant search (+x) on the PARENT directories up to home
            # This is often needed so the user can traverse to the file.
            # (Simplified approach: Grant +x on the exact path provided)
            # Note: In strict HPC, you might need to +x the parents manually.

            logger.info(f"ACLs set on {path} for {recipient_username}")

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to set ACLs: {e}")
            # We log but don't crash, as the symlink might still work if permissions were already open

    @staticmethod
    def revoke_share(username, share_id):
        """Revoke a share by removing the symlink and scrubbing ACLs"""
        db_path = Database.get_db_path(username)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
                       SELECT *
                       FROM shares
                       WHERE id = ?
                         AND share_type = 'outgoing'
                         AND status = 'active'
                       ''', (share_id,))
        share = cursor.fetchone()

        if not share:
            conn.close()
            raise ValueError("Share not found or already revoked")
        share = dict(share)

        # 1. Remove the symlink (File operation)
        if os.path.exists(share['target_path']):
            try:
                os.remove(share['target_path'])
            except OSError as e:
                logger.error(f"Error removing symlink: {e}")

        # 2. Revoke ACL permissions (Clean up access)
        recipient = share['shared_with']
        try:
            # -x removes the specific user's entry from ACL
            subprocess.run(['setfacl', '-R', '-x', f'u:{recipient}', share['source_path']], check=False)
            if os.path.isdir(share['source_path']):
                subprocess.run(['setfacl', '-R', '-d', '-x', f'u:{recipient}', share['source_path']], check=False)
        except Exception as e:
            logger.error(f"Error revoking ACLs: {e}")

        # 3. Update DB status (Same as before)
        cursor.execute("UPDATE shares SET status = 'revoked' WHERE id = ?", (share_id,))
        conn.commit()
        conn.close()

        # Update recipient DB
        try:
            recipient_db = Database.get_db_path(recipient)
            conn = sqlite3.connect(recipient_db)
            cursor = conn.cursor()
            cursor.execute('''
                           UPDATE shares
                           SET status = 'revoked'
                           WHERE source_path = ?
                             AND shared_by = ?
                           ''', (share['source_path'], username))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error updating recipient DB: {e}")

        return True

    # Keep these helper methods as they were in your original code
    @staticmethod
    def list_outgoing_shares(username):
        return ShareManager._list_shares(username, 'outgoing')

    @staticmethod
    def list_incoming_shares(username):
        return ShareManager._list_shares(username, 'incoming')

    @staticmethod
    def _list_shares(username, share_type):
        """Helper to reduce code duplication"""
        db_path = Database.get_db_path(username)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(f'''
            SELECT * FROM shares 
            WHERE share_type = ? AND status = 'active'
            ORDER BY created_at DESC
        ''', (share_type,))
        shares = [dict(row) for row in cursor.fetchall()]
        conn.close()

        # Validation checks
        for share in shares:
            if share_type == 'outgoing':
                share['exists'] = os.path.exists(share['source_path'])
            else:
                share['link_exists'] = os.path.exists(share['target_path'])
                share['source_exists'] = os.path.exists(share['source_path'])
        return shares

# ============================================================================
# FLASK ROUTES
# ============================================================================

@app.route('/')
@require_user
def index(user):
    """Main dashboard"""

    # ---------------------------------------------------------
    # AUTOMATIC SETUP: Initialize Shared Folder
    # ---------------------------------------------------------
    user_shared_dir = PathValidator.get_shared_dir(user)

    # We check if the folder exists OR if we just want to ensure permissions are correct
    # It is safe to run this multiple times because the script handles checks,
    # but for performance, checking os.path.exists first is better.
    if not os.path.exists(user_shared_dir):
        try:
            # We assume the app is running as user 'fitsum'
            # In production, you might want to fetch this dynamically: pwd.getpwuid(os.getuid()).pw_name
            current_app_user = pwd.getpwuid(os.getuid()).pw_name

            logger.info(f"Initializing shared folder for {user}...")

            subprocess.run(
                ['sudo', '/opt/filemanager/init_user.sh', user, current_app_user],
                check=True,
                capture_output=True
            )
            logger.info(f"Successfully initialized shared folder for {user}")

        except subprocess.CalledProcessError as e:
            # Log the specific error from the script
            logger.error(f"Failed to auto-initialize user {user}: {e.stderr.decode().strip()}")
    # ---------------------------------------------------------

    Database.init_db(user)
    user_home = PathValidator.get_user_home(user)
    return render_template('index.html', username=user, home_path=user_home)


@app.route('/api/list', methods=['POST'])
@require_user
def api_list_directory(user):
    """List directory contents"""
    data = request.get_json()
    path = data.get('path', PathValidator.get_user_home(user))

    try:
        items = FileManager.list_directory(user, path)
        return jsonify({'success': True, 'items': items, 'path': path})
    except Exception as e:
        logger.error(f"List directory error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/search', methods=['POST'])
@require_user
def api_search(user):
    """Search for files/folders under a path"""
    data = request.get_json()
    path = data.get('path', PathValidator.get_user_home(user))
    query = data.get('query', '').strip()
    max_depth = int(data.get('max_depth', 3))
    max_results = int(data.get('max_results', 200))

    if not query:
        return jsonify({'success': False, 'error': 'Search query cannot be empty'}), 400

    try:
        items = FileManager.search(user, path, query, max_depth=max_depth, max_results=max_results)
        return jsonify({'success': True, 'items': items, 'path': path, 'query': query})
    except Exception as e:
        logger.error(f"Search error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/create_folder', methods=['POST'])
@require_user
def api_create_folder(user):
    """Create a new folder"""
    data = request.get_json()
    parent_path = data.get('parent_path')
    folder_name = data.get('folder_name')

    try:
        new_path = FileManager.create_folder(user, parent_path, folder_name)
        return jsonify({'success': True, 'path': new_path})
    except Exception as e:
        logger.error(f"Create folder error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/create_file', methods=['POST'])
@require_user
def api_create_file(user):
    """Create a new file"""
    data = request.get_json()
    parent_path = data.get('parent_path')
    file_name = data.get('file_name')
    content = data.get('content', '')

    try:
        new_path = FileManager.create_file(user, parent_path, file_name, content)
        return jsonify({'success': True, 'path': new_path})
    except Exception as e:
        logger.error(f"Create file error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/rename', methods=['POST'])
@require_user
def api_rename(user):
    """Rename a file or folder"""
    data = request.get_json()
    old_path = data.get('path')
    new_name = data.get('new_name')

    try:
        new_path = FileManager.rename_item(user, old_path, new_name)
        return jsonify({'success': True, 'path': new_path})
    except Exception as e:
        logger.error(f"Rename error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/delete', methods=['POST'])
@require_user
def api_delete(user):
    """Delete a file or folder"""
    data = request.get_json()
    path = data.get('path')

    try:
        FileManager.delete_item(user, path)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Delete error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/move', methods=['POST'])
@require_user
def api_move(user):
    """Move a file or folder"""
    data = request.get_json()
    source_path = data.get('source_path')
    dest_dir = data.get('dest_dir')

    try:
        new_path = FileManager.move_item(user, source_path, dest_dir)
        return jsonify({'success': True, 'path': new_path})
    except Exception as e:
        logger.error(f"Move error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/users', methods=['GET'])
@require_user
def api_list_users(user):
    """Get list of system users for sharing"""
    try:
        users = ShareManager.get_system_users()
        # Remove current user from list
        users = [u for u in users if u['username'] != user]
        return jsonify({'success': True, 'users': users})
    except Exception as e:
        logger.error(f"List users error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/share/create', methods=['POST'])
@require_user
def api_create_share(user):
    """Create a new share"""
    data = request.get_json()
    source_path = data.get('source_path')
    recipient = data.get('recipient')
    permission = data.get('permission', 'view')

    if permission not in ['view', 'edit']:
        return jsonify({'success': False, 'error': 'Invalid permission level'}), 400

    try:
        result = ShareManager.create_share(user, source_path, recipient, permission)
        return jsonify({'success': True, 'share': result})
    except Exception as e:
        logger.error(f"Create share error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/share/outgoing', methods=['GET'])
@require_user
def api_list_outgoing_shares(user):
    """List shares created by current user"""
    try:
        shares = ShareManager.list_outgoing_shares(user)
        return jsonify({'success': True, 'shares': shares})
    except Exception as e:
        logger.error(f"List outgoing shares error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/share/incoming', methods=['GET'])
@require_user
def api_list_incoming_shares(user):
    """List shares received by current user"""
    try:
        shares = ShareManager.list_incoming_shares(user)
        return jsonify({'success': True, 'shares': shares})
    except Exception as e:
        logger.error(f"List incoming shares error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/share/revoke', methods=['POST'])
@require_user
def api_revoke_share(user):
    """Revoke a share"""
    data = request.get_json()
    share_id = data.get('share_id')

    try:
        ShareManager.revoke_share(user, share_id)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Revoke share error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/audit_log', methods=['GET'])
@require_user
def api_audit_log(user):
    """Get audit log entries"""
    limit = request.args.get('limit', 100, type=int)

    try:
        db_path = Database.get_db_path(user)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM audit_log 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (limit,))

        logs = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return jsonify({'success': True, 'logs': logs})
    except Exception as e:
        logger.error(f"Audit log error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400


if __name__ == '__main__':
    # Development server - NOT for production use
    # In production, use gunicorn, uwsgi, or similar WSGI server
    app.run(host='0.0.0.0', port=5000, debug=False)

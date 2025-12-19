# HPC File Manager - Complete Deployment Guide

## Overview

This guide provides step-by-step instructions for deploying the Flask File Manager application on a High-Performance Computing (HPC) environment. The application enables secure file sharing between users using ACL-based permissions without requiring root access for routine operations.

---

## Table of Contents

1. [System Requirements](#1-system-requirements)
2. [Installation Steps](#2-installation-steps)
3. [Security Configuration](#3-security-configuration)
4. [Application Setup](#4-application-setup)
5. [Running the Application](#5-running-the-application)
6. [System Architecture](#6-system-architecture)
7. [Troubleshooting](#7-troubleshooting)
8. [Maintenance](#8-maintenance)

---

## 1. System Requirements

### Operating System
- Linux-based OS (Ubuntu 20.04+, CentOS 7+, RHEL 7+, or similar)
- Filesystem with ACL support (Lustre, GPFS, XFS, ext4)

### Software Dependencies
- **Python:** 3.8 or higher
- **Root/Sudo Access:** Required for initial setup only
- **ACL Tools:** `acl` package

### Verification Commands

Check filesystem ACL support:
```bash
mount | grep acl
```

Check Python version:
```bash
python3 --version
```

---

## 2. Installation Steps

### 2.1. Create Application Directory

```bash
# Create directory (requires sudo)
sudo mkdir -p /opt/flask-filemanager

# Set ownership to your user
sudo chown -R $USER:$USER /opt/flask-filemanager

# Navigate to directory
cd /opt/flask-filemanager
```

### 2.2. Set Up Python Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install required packages
pip install flask gunicorn
```

### 2.3. Deploy Application Files

Create the following directory structure:

```
/opt/flask-filemanager/
├── app.py              # Main application file
├── templates/
│   └── index.html      # Frontend template
├── venv/               # Virtual environment
└── filemanager.log     # Log file (auto-generated)
```

Copy your `app.py` and `templates/index.html` files to the appropriate locations.

---

## 3. Security Configuration

This is the **most critical** part of the deployment. The application uses a restricted sudo helper script to manage user directories securely.

### 3.1. Install ACL Tools

**For Debian/Ubuntu:**
```bash
sudo apt-get update
sudo apt-get install acl
```

**For RHEL/CentOS:**
```bash
sudo yum install acl
```

### 3.2. Create Helper Script Directory

```bash
sudo mkdir -p /opt/filemanager
```

### 3.3. Create Initialization Script

Create the helper script:

```bash
sudo nano /opt/filemanager/init_user.sh
```

Paste the following content:

```bash
#!/bin/bash
# Path: /opt/filemanager/init_user.sh
# Usage: ./init_user.sh <target_username> <app_running_user>

TARGET_USER=$1
APP_USER=$2
TARGET_HOME="/home/$TARGET_USER"
TARGET_DIR="$TARGET_HOME/shared_with_me"
DB_DIR="$TARGET_HOME/.filemanager"

# Validate that target user exists
if ! id "$TARGET_USER" &>/dev/null; then
    echo "Error: User $TARGET_USER does not exist."
    exit 1
fi

# 1. Grant traverse (x) permission on HOME directory
#    This allows the app to access subdirectories
setfacl -m u:"$APP_USER":x "$TARGET_HOME"

# 2. Create and configure SHARED directory
if [ ! -d "$TARGET_DIR" ]; then
    mkdir -p "$TARGET_DIR"
    chown "$TARGET_USER":"$TARGET_USER" "$TARGET_DIR"
fi

# Grant read/write/execute permissions to app user
setfacl -m u:"$APP_USER":rwx "$TARGET_DIR"
# Set default ACL for new files
setfacl -d -m u:"$APP_USER":rwx "$TARGET_DIR"

# 3. Create and configure DATABASE directory
if [ ! -d "$DB_DIR" ]; then
    mkdir -p "$DB_DIR"
    chown "$TARGET_USER":"$TARGET_USER" "$DB_DIR"
fi

# Grant read/write/execute permissions to app user
setfacl -m u:"$APP_USER":rwx "$DB_DIR"
# Set default ACL for new files
setfacl -d -m u:"$APP_USER":rwx "$DB_DIR"

echo "Success: Initialized directories for $TARGET_USER"
exit 0
```

Make the script executable:

```bash
sudo chmod +x /opt/filemanager/init_user.sh
```

### 3.4. Configure Sudo Permissions

This allows the application user to run the initialization script without a password prompt.

Edit the sudo configuration:

```bash
sudo visudo
```

Add the following line at the end of the file (replace `fitsum` with your application user):

```
fitsum ALL=(root) NOPASSWD: /opt/filemanager/init_user.sh
```

**Important:** Use the exact path and be careful with syntax. Save and exit (Ctrl+O, Enter, Ctrl+X in nano).

### 3.5. Test the Setup

Test the script as your application user:

```bash
# Test with your own username
sudo /opt/filemanager/init_user.sh $USER fitsum

# Check if directories were created
ls -la ~/ | grep -E "shared_with_me|.filemanager"

# Verify ACL permissions
getfacl ~/shared_with_me
getfacl ~/.filemanager
```

---

## 4. Application Setup

### 4.1. Environment Variables

Configure the application using environment variables. Create a configuration file:

```bash
nano /opt/flask-filemanager/.env
```

Add the following variables:

```bash
# Security - REQUIRED: Generate a strong random key
FLASK_SECRET_KEY="your-very-long-random-secret-key-here"

# File System Configuration
HOME_BASE="/home"                 # Root directory for user homes
MIN_USER_UID=1000                 # Minimum UID for visible users
MAX_USER_UID=60000                # Maximum UID for visible users

# Logging
LOG_LEVEL="INFO"                  # DEBUG, INFO, WARNING, ERROR
LOG_FILE="/tmp/filemanager.log"   # Log file location
```

**Generate a secure secret key:**

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 4.2. Load Environment Variables

Create a startup script to load environment variables:

```bash
nano /opt/flask-filemanager/start.sh
```

Add the following content:

```bash
#!/bin/bash
cd /opt/flask-filemanager
source venv/bin/activate

# Load environment variables
export FLASK_SECRET_KEY="your-secret-key-here"
export HOME_BASE="/home"
export MIN_USER_UID=1000
export MAX_USER_UID=60000

# Start application
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

Make it executable:

```bash
chmod +x /opt/flask-filemanager/start.sh
```

---

## 5. Running the Application

### 5.1. Development Mode (Testing)

For testing purposes only:

```bash
cd /opt/flask-filemanager
source venv/bin/activate
export AUTHENTICATED_USER=$USER
python app.py
```

Access at: `http://localhost:5000`

### 5.2. Production Mode with Gunicorn

**Basic startup:**

```bash
cd /opt/flask-filemanager
source venv/bin/activate
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

**Recommended production settings:**

```bash
gunicorn \
  --workers 4 \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --access-logfile /var/log/filemanager/access.log \
  --error-logfile /var/log/filemanager/error.log \
  --log-level info \
  app:app
```

### 5.3. Systemd Service (Recommended)

Create a systemd service for automatic startup and management.

Create service file:

```bash
sudo nano /etc/systemd/system/filemanager.service
```

Add the following content:

```ini
[Unit]
Description=HPC File Manager Application
After=network.target

[Service]
Type=notify
User=fitsum
Group=fitsum
WorkingDirectory=/opt/flask-filemanager
Environment="FLASK_SECRET_KEY=your-secret-key-here"
Environment="HOME_BASE=/home"
Environment="MIN_USER_UID=1000"
Environment="MAX_USER_UID=60000"
ExecStart=/opt/flask-filemanager/venv/bin/gunicorn \
  --workers 4 \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --access-logfile /var/log/filemanager/access.log \
  --error-logfile /var/log/filemanager/error.log \
  app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
# Create log directory
sudo mkdir -p /var/log/filemanager
sudo chown fitsum:fitsum /var/log/filemanager

# Reload systemd
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable filemanager

# Start service
sudo systemctl start filemanager

# Check status
sudo systemctl status filemanager
```

### 5.4. Using with Reverse Proxy (Nginx)

For production deployments, use Nginx as a reverse proxy.

Install Nginx:

```bash
sudo apt-get install nginx  # Ubuntu/Debian
sudo yum install nginx      # RHEL/CentOS
```

Create Nginx configuration:

```bash
sudo nano /etc/nginx/sites-available/filemanager
```

Add the following:

```nginx
server {
    listen 80;
    server_name your-server-name.edu;

    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # If using external authentication
        proxy_set_header X-Forwarded-User $remote_user;
    }

    location /static {
        alias /opt/flask-filemanager/static;
        expires 30d;
    }
}
```

Enable and start:

```bash
sudo ln -s /etc/nginx/sites-available/filemanager /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## 6. System Architecture

### 6.1. How Sharing Works

When User A shares a file with User B:

1. **Validation:** Application verifies User B exists and source file is accessible
2. **Auto-initialization:** If needed, runs `init_user.sh` to set up User B's directories
3. **Symlink Creation:** Creates a symbolic link in `~/shared_with_me/` pointing to the source file
4. **ACL Permissions:** Uses `setfacl` to grant User B read or read-write access to the source file
5. **Database Recording:** Records the share in both users' SQLite databases

### 6.2. Directory Structure

Each user has:

```
/home/username/
├── shared_with_me/        # Contains symlinks to shared files
├── .filemanager/          # Application database
│   └── filemanager.db     # SQLite database
└── [user files]           # Regular user files
```

### 6.3. Security Model

- **Path Validation:** All paths are validated to prevent directory traversal
- **ACL-Based Access:** Linux ACLs control actual file access
- **Sudo Restriction:** Only specific initialization script can be run via sudo
- **User Isolation:** Each user can only access their own files and explicitly shared items

---

## 7. Troubleshooting

### Common Issues

#### Issue: "Permission denied" when creating share

**Solution:**
```bash
# Check if ACLs are supported
mount | grep acl

# Verify init script permissions
ls -l /opt/filemanager/init_user.sh

# Check sudo configuration
sudo -l | grep init_user.sh

# Test manually
sudo /opt/filemanager/init_user.sh testuser fitsum
```

#### Issue: Application can't access user directories

**Solution:**
```bash
# Check application user permissions
getfacl /home/targetuser/shared_with_me
getfacl /home/targetuser/.filemanager

# Re-run initialization
sudo /opt/filemanager/init_user.sh targetuser fitsum
```

#### Issue: Broken symlinks in shared_with_me

**Cause:** Original file was moved or deleted

**Solution:**
- Original owner should revoke the share
- Or manually remove the broken symlink:
```bash
rm ~/shared_with_me/broken_link_name
```

#### Issue: Database permission errors

**Solution:**
```bash
# Fix database directory permissions
sudo /opt/filemanager/init_user.sh $USER fitsum

# Verify permissions
ls -la ~/.filemanager/
```

### Debug Mode

Enable detailed logging:

```bash
export LOG_LEVEL="DEBUG"
tail -f /tmp/filemanager.log
```

---

## 8. Maintenance

### 8.1. Regular Maintenance Tasks

**Check application status:**
```bash
sudo systemctl status filemanager
```

**View logs:**
```bash
tail -f /var/log/filemanager/access.log
tail -f /var/log/filemanager/error.log
tail -f /tmp/filemanager.log
```

**Restart application:**
```bash
sudo systemctl restart filemanager
```

### 8.2. Updating the Application

```bash
# Stop service
sudo systemctl stop filemanager

# Backup current version
cd /opt
sudo tar -czf flask-filemanager-backup-$(date +%Y%m%d).tar.gz flask-filemanager/

# Update code
cd /opt/flask-filemanager
# Copy new files...

# Restart service
sudo systemctl start filemanager
```

### 8.3. Database Maintenance

User databases are stored in `~/.filemanager/filemanager.db`

**Backup a user's database:**
```bash
sqlite3 ~/.filemanager/filemanager.db .dump > backup.sql
```

**Clean up revoked shares:**
```bash
sqlite3 ~/.filemanager/filemanager.db "DELETE FROM shares WHERE status='revoked' AND created_at < date('now', '-30 days');"
```

### 8.4. Monitoring

**Check disk usage:**
```bash
du -sh /opt/flask-filemanager
```

**Monitor active connections:**
```bash
sudo netstat -tulpn | grep 8000
```

**Check resource usage:**
```bash
ps aux | grep gunicorn
```

---

## 9. Security Considerations

### Best Practices

1. **Secret Key:** Never commit `FLASK_SECRET_KEY` to version control
2. **HTTPS:** Always use HTTPS in production (configure via Nginx)
3. **Firewall:** Restrict access to port 8000
4. **Updates:** Keep Python packages updated
5. **Audit Logs:** Regularly review audit logs for suspicious activity
6. **User Training:** Educate users about secure file sharing practices

### Hardening Recommendations

```bash
# Restrict application directory permissions
sudo chmod 750 /opt/flask-filemanager

# Ensure init script can only be run via sudo
sudo chmod 700 /opt/filemanager/init_user.sh

# Set secure permissions on log files
sudo chmod 640 /var/log/filemanager/*.log
```

---

## 10. Support and Additional Resources

### Key Files Reference

| File | Location | Purpose |
|------|----------|---------|
| Main Application | `/opt/flask-filemanager/app.py` | Core application logic |
| Frontend | `/opt/flask-filemanager/templates/index.html` | User interface |
| Init Script | `/opt/filemanager/init_user.sh` | User directory setup |
| Service File | `/etc/systemd/system/filemanager.service` | Systemd service |
| Nginx Config | `/etc/nginx/sites-available/filemanager` | Reverse proxy |
| Application Log | `/tmp/filemanager.log` | Application logs |
| Access Log | `/var/log/filemanager/access.log` | HTTP access logs |

### Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_SECRET_KEY` | - | **Required.** Session encryption key |
| `HOME_BASE` | `/home` | Base directory for user homes |
| `MIN_USER_UID` | `1000` | Minimum UID for user visibility |
| `MAX_USER_UID` | `60000` | Maximum UID for user visibility |
| `LOG_LEVEL` | `INFO` | Logging verbosity level |
| `LOG_FILE` | `/tmp/filemanager.log` | Log file location |
| `AUTHENTICATED_USER` | - | Username (for development) |

---

## Quick Start Checklist

- [ ] Install ACL tools
- [ ] Create application directory at `/opt/flask-filemanager`
- [ ] Set up Python virtual environment
- [ ] Deploy application files
- [ ] Create init script at `/opt/filemanager/init_user.sh`
- [ ] Configure sudo permissions in visudo
- [ ] Test init script
- [ ] Generate Flask secret key
- [ ] Configure environment variables
- [ ] Create systemd service file
- [ ] Start and enable service
- [ ] Configure Nginx reverse proxy (optional)
- [ ] Test file operations and sharing
- [ ] Set up log rotation

---

**Document Version:** 1.0  
**Last Updated:** December 2024  
**Tested On:** Ubuntu 22.04, CentOS 8

For questions or issues, please refer to the application logs and troubleshooting section.
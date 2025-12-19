# HPC File Manager - Installation Guide

A secure file sharing application for HPC environments using ACL-based permissions.

---

## Quick Overview

This guide will help you:
1. Clone the repository
2. Set up the application
3. Configure the secure sharing system
4. Run it locally for testing

---

## Prerequisites

- **Operating System:** Linux (Ubuntu 20.04+, CentOS 7+, RHEL 7+)
- **Python:** 3.8 or higher
- **Filesystem:** Must support ACLs (check with `mount | grep acl`)
- **Root Access:** Required only for initial security setup

---

## Installation Steps

### Step 1: Clone the Repository

```bash
# Clone the repository
git clone https://github.com/rahulsharma-rs/ubrite-workspace-manager.git

# Navigate to the project
cd ubrite-workspace-manager

# Checkout the stable version
git checkout stable-v1

# Navigate to the application directory
cd new-app
```

You should now see:
```
new-app/
├── app.py
├── readme.md
├── requirements.txt
└── templates/
    └── index.html
```

### Step 2: Set Up Python Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

---

## Security Configuration (One-Time Setup)

This section sets up the secure sharing system. **You need sudo/root access for this part only.**

### Step 1: Install ACL Tools

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install acl
```

**RHEL/CentOS:**
```bash
sudo yum install acl
```

### Step 2: Create Helper Script

Create the directory:
```bash
sudo mkdir -p /opt/filemanager
```

Create the initialization script:
```bash
sudo nano /opt/filemanager/init_user.sh
```

Paste this content:
```bash
#!/bin/bash
# User initialization script for file sharing

TARGET_USER=$1
APP_USER=$2
TARGET_HOME="/home/$TARGET_USER"
TARGET_DIR="$TARGET_HOME/shared_with_me"
DB_DIR="$TARGET_HOME/.filemanager"

# Validate user exists
if ! id "$TARGET_USER" &>/dev/null; then
    echo "Error: User $TARGET_USER does not exist."
    exit 1
fi

# Grant traverse permission on home directory
setfacl -m u:"$APP_USER":x "$TARGET_HOME"

# Setup shared directory
if [ ! -d "$TARGET_DIR" ]; then
    mkdir -p "$TARGET_DIR"
    chown "$TARGET_USER":"$TARGET_USER" "$TARGET_DIR"
fi
setfacl -m u:"$APP_USER":rwx "$TARGET_DIR"
setfacl -d -m u:"$APP_USER":rwx "$TARGET_DIR"

# Setup database directory
if [ ! -d "$DB_DIR" ]; then
    mkdir -p "$DB_DIR"
    chown "$TARGET_USER":"$TARGET_USER" "$DB_DIR"
fi
setfacl -m u:"$APP_USER":rwx "$DB_DIR"
setfacl -d -m u:"$APP_USER":rwx "$DB_DIR"

echo "Success: Initialized directories for $TARGET_USER"
exit 0
```

Make it executable:
```bash
sudo chmod +x /opt/filemanager/init_user.sh
```

### Step 3: Configure Sudo Permissions

Edit sudo configuration:
```bash
sudo visudo
```

Add this line at the end (replace `fitsum` with your username):
```
fitsum ALL=(root) NOPASSWD: /opt/filemanager/init_user.sh
```

Save and exit (Ctrl+O, Enter, Ctrl+X).

### Step 4: Test the Setup

```bash
# Test with your username
sudo /opt/filemanager/init_user.sh $USER fitsum

# Verify directories were created
ls -la ~/ | grep -E "shared_with_me|.filemanager"

# Check permissions
getfacl ~/shared_with_me
```

You should see output showing ACL permissions for the `fitsum` user.

---

## Configuration

### Generate Secret Key

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Copy the generated key for the next step.

### Set Environment Variables

```bash
# Set your secret key (use the one you just generated)
export FLASK_SECRET_KEY="your-generated-secret-key-here"

# Set other configuration (optional)
export HOME_BASE="/home"
export MIN_USER_UID=1000
export MAX_USER_UID=60000
export LOG_LEVEL="INFO"
```

**Optional:** Create a `.env` file in the `new-app` directory to persist these settings:
```bash
nano .env
```

Add:
```bash
FLASK_SECRET_KEY=your-generated-secret-key-here
HOME_BASE=/home
MIN_USER_UID=1000
MAX_USER_UID=60000
LOG_LEVEL=INFO
```

---

## Running the Application

### Development Mode (Local Testing)

```bash
# Make sure you're in the new-app directory
cd ~/PycharmProjects/ubrite-workspace-manager/new-app

# Activate virtual environment
source venv/bin/activate

# Set your username (for development)
export AUTHENTICATED_USER=$USER

# Run the application
python app.py
```

The application will start on `http://localhost:5000`

Open your browser and navigate to:
```
http://localhost:5000
```

### Testing with Gunicorn (Optional)

For a more production-like test:

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Run with gunicorn
gunicorn -w 2 -b 0.0.0.0:8000 app:app
```

Access at: `http://localhost:8000`

---

## How It Works

### Sharing Files Between Users

1. **User A** shares a file with **User B**
2. Application automatically initializes User B's directories (if needed)
3. Creates a symbolic link in User B's `~/shared_with_me/` folder
4. Sets ACL permissions so User B can access the file
5. Records the share in both users' databases

### Directory Structure

After setup, each user will have:
```
/home/username/
├── shared_with_me/        # Symlinks to files shared with you
├── .filemanager/          # Application database
│   └── filemanager.db     # SQLite database
└── [your files]           # Your regular files
```

---

## Troubleshooting

### "Permission denied" errors

```bash
# Check ACL support
mount | grep acl

# Verify init script permissions
ls -l /opt/filemanager/init_user.sh

# Check sudo configuration
sudo -l | grep init_user.sh

# Re-run initialization
sudo /opt/filemanager/init_user.sh $USER fitsum
```

### Can't access shared directories

```bash
# Check ACL permissions
getfacl /home/targetuser/shared_with_me

# Re-run initialization for the user
sudo /opt/filemanager/init_user.sh targetuser fitsum
```

### Database errors

```bash
# Fix database directory permissions
sudo /opt/filemanager/init_user.sh $USER fitsum

# Verify
ls -la ~/.filemanager/
```

### Enable debug logging

```bash
export LOG_LEVEL="DEBUG"
tail -f /tmp/filemanager.log
```

---

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_SECRET_KEY` | - | **Required.** Session encryption key |
| `HOME_BASE` | `/home` | Base directory for user homes |
| `MIN_USER_UID` | `1000` | Minimum UID for visible users |
| `MAX_USER_UID` | `60000` | Maximum UID for visible users |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `LOG_FILE` | `/tmp/filemanager.log` | Log file location |
| `AUTHENTICATED_USER` | - | Username (for development testing) |

---

## Security Notes

- The init script can only be run via sudo and is restricted to specific operations
- All file paths are validated to prevent directory traversal attacks
- ACLs control actual file system access
- Each user's database is isolated
- Audit logs track all file operations

---

## Quick Start Checklist

- [ ] Clone repository and checkout `stable-v1` branch
- [ ] Navigate to `new-app` directory
- [ ] Create and activate Python virtual environment
- [ ] Install dependencies from `requirements.txt`
- [ ] Install ACL tools (`acl` package)
- [ ] Create `/opt/filemanager/init_user.sh` script
- [ ] Configure sudo permissions in visudo
- [ ] Test the init script
- [ ] Generate and set `FLASK_SECRET_KEY`
- [ ] Set `AUTHENTICATED_USER` environment variable
- [ ] Run `python app.py` and test at `http://localhost:5000`

---

**Need Help?**
- Check application logs: `tail -f /tmp/filemanager.log`
- Enable debug mode: `export LOG_LEVEL="DEBUG"`
- Verify ACL permissions: `getfacl ~/shared_with_me`

**Version:** 1.0  
**Last Updated:** December 2024
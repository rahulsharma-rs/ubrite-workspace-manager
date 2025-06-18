# UBRITE Project Workspace Manager

A comprehensive Flask-based web application designed for researchers and developers to create, manage, and work with project workspaces. The application provides integrated support for Conda environments, GitLab repositories, JupyterLab, VS Code Web, and comprehensive file management capabilities.

## 🚀 Features

### Core Functionality
- **One-Click Workspace Creation**: Create complete project workspaces with a single click
- **Integrated GitLab Repository Management**: Automatic repository creation and Git operations
- **Environment Management**: Support for Conda environments and existing Python environments
- **In-Browser IDEs**: Launch JupyterLab and VS Code Web directly from the interface
- **File Explorer**: Full-featured file browser with upload, download, and editing capabilities
- **Real-Time Updates**: WebSocket-based real-time notifications and updates
- **Audit Logging**: Immutable audit trail with CSV export functionality
- **Analytics**: Built-in analytics service for usage tracking

### Environment Templates
The application comes with pre-configured Conda environment templates for various research domains:

- **data-science**: General data science packages (numpy, pandas, matplotlib, scikit-learn, jupyter)
- **web-dev**: Web development packages (Flask, SQLAlchemy, requests, etc.)
- **deep-learning**: Deep learning frameworks (PyTorch, TensorFlow, transformers, CUDA support)
- **bioinformatics**: Bioinformatics tools (Biopython, BLAST, samtools, bedtools)
- **nlp**: Natural Language Processing (NLTK, spaCy, transformers, gensim)
- **computer-vision**: Computer Vision libraries (OpenCV, torchvision, detectron2, PIL)
- **geospatial**: Geospatial analysis tools (GeoPandas, GDAL, rasterio, folium)
- **scientific-computing**: Scientific computing (FEniCS, PETSc, Numba, scipy)
- **statistics**: Statistical analysis (statsmodels, PyMC3, R integration, seaborn)

### File Management
- **File Explorer Interface**: Browse, create, edit, and delete files and folders
- **Upload/Download**: Support for single files and bulk folder downloads as ZIP
- **Text Editor**: Built-in editor for code and text files
- **Binary File Support**: Proper handling of images, PDFs, and other binary files
- **Git Integration**: Real-time Git status and operations within the file explorer

## 📋 Prerequisites

### System Requirements
- Python 3.8 or higher
- Git (for repository operations)
- Conda/Miniconda (optional, for environment management)
- JupyterLab (optional, for notebook functionality)

### Operating System Support
- Linux (recommended)
- macOS
- Windows (with some limitations)

## 🛠 Installation

### 1. Clone the Repository
\`\`\`bash
git clone https://github.com/yourusername/ubrite-workspace-manager.git
cd ubrite-workspace-manager
\`\`\`

### 2. Create and Activate Virtual Environment
\`\`\`bash
python -m venv venv

# On Linux/macOS
source venv/bin/activate

# On Windows
venv\\Scripts\\activate
\`\`\`

### 3. Install Dependencies
\`\`\`bash
pip install -r requirements.txt
\`\`\`

### 4. Configure Environment Variables (Optional)
Create a \`.env\` file in the project root:
\`\`\`bash
# Flask Configuration
FLASK_APP=app.py
FLASK_ENV=development
SECRET_KEY=your-secret-key-here

# GitLab Configuration
GITLAB_API_URL=https://your-gitlab-instance.com/api/v4

# Tool Paths (if not in PATH)
CONDA_PATH=/path/to/conda
JUPYTER_PATH=/path/to/jupyter
VSCODE_PATH=/path/to/code-server

# Custom Directory Paths (optional)
UBRITE_ROOT=/custom/path/to/ubrite
DB_ROOT=/custom/path/to/db
TEMP_ROOT=/custom/path/to/temp
\`\`\`

### 5. Initialize the Application
\`\`\`bash
python app.py
\`\`\`

The application will automatically:
- Create necessary directories
- Initialize the database
- Run any required migrations
- Start the web server

## 🔧 Configuration

### Directory Structure
By default, the application creates the following directory structure under \`/data/user/\<username\>/ondemand/dev/rc_workspace\`:

\`\`\`
/data/user/<username>/ondemand/dev/rc_workspace/
├── UBRITE/                 # Main workspace directory
│   ├── workspace1/         # Individual workspaces
│   ├── workspace2/
│   └── .config/           # Configuration files
├── DB/                    # Database files
├── UBRITE_TEMP/          # Temporary files
│   ├── logs/             # Application logs
│   ├── cache/            # Cache files
│   └── uploads/          # File uploads
├── dev.db                # Development database
└── ubrite.db            # Production database
\`\`\`

### GitLab Integration Setup
1. Navigate to your GitLab instance
2. Go to User Settings → Access Tokens
3. Create a new Personal Access Token with \`api\` scope
4. Configure the token in the application settings page

### Conda Integration
The application automatically detects Conda installations in common locations:
- \`/usr/local/bin/conda\`
- \`~/miniconda3/bin/conda\`
- \`~/anaconda3/bin/conda\`
- Windows: \`C:\\ProgramData\\Miniconda3\\Scripts\\conda.exe\`

## 🚀 Usage

### Creating a Workspace
1. Navigate to the main dashboard
2. Click "Create New Workspace"
3. Fill in the workspace details:
   - **Name**: Unique workspace identifier
   - **Environment Type**: Choose from available templates or use existing Python environment
   - **Git Visibility**: Public or private repository
   - **Skip Conda**: Option to skip environment creation
4. Click "Create Workspace"

### Managing Files
1. From the workspace detail page, click "File Explorer"
2. Use the file browser to:
   - Navigate directories
   - Create new files and folders
   - Upload files (drag & drop supported)
   - Download files or entire folders as ZIP
   - Edit text files in the built-in editor
   - Delete files and folders

### Launching IDEs
From either the workspace detail page or file explorer:
- **JupyterLab**: Click "Launch JupyterLab" to start a notebook server
- **VS Code Web**: Click "Launch VS Code" for a full IDE experience

### Git Operations
Use the Git panel to:
- View repository status
- See recent commits
- Access GitLab repository directly
- Monitor real-time Git changes

### Audit and Analytics
- View detailed audit logs for each workspace
- Export audit logs as CSV files
- Monitor usage analytics (if enabled)

## 🔌 API Endpoints

### Workspaces
- \`GET /workspaces/\` - List all workspaces
- \`POST /workspaces/create\` - Create new workspace
- \`GET /workspaces/<id>\` - Get workspace details
- \`POST /workspaces/<id>/delete\` - Delete workspace
- \`GET /workspaces/<id>/audit-log\` - Get audit log

### Files
- \`GET /files/<workspace_id>/list\` - List files in directory
- \`GET /files/<workspace_id>/file\` - Get file content
- \`POST /files/<workspace_id>/save\` - Save file
- \`POST /files/<workspace_id>/upload\` - Upload file
- \`POST /files/<workspace_id>/delete\` - Delete file/folder

### IDE
- \`GET /ide/<workspace_id>/launch/<ide_type>\` - Launch IDE
- \`GET /ide/<workspace_id>/stop/<ide_type>\` - Stop IDE

### Git
- \`GET /git/<workspace_id>/status\` - Get Git status
- \`GET /git/<workspace_id>/commits\` - Get recent commits

## 🐛 Troubleshooting

### Common Issues

#### Conda Not Found
**Error**: "Conda not found" or environment creation fails
**Solution**: 
- Ensure Conda is installed and in PATH
- Set \`CONDA_PATH\` environment variable to the full path
- Check \`/workspaces/check-conda\` endpoint for status

#### JupyterLab Won't Start
**Error**: JupyterLab fails to launch or doesn't open workspace directory
**Solution**:
- Ensure JupyterLab is installed: \`pip install jupyterlab\`
- Check if the workspace environment has ipykernel: \`pip install ipykernel\`
- Verify workspace directory permissions

#### GitLab Connection Issues
**Error**: "Failed to create GitLab repository"
**Solution**:
- Verify GitLab URL is correct
- Check Personal Access Token has \`api\` scope
- Test connection at \`/git/test-connection\`

#### Permission Denied Errors
**Error**: Cannot create directories or files
**Solution**:
- Check directory permissions for \`/data/user/<username>/ondemand/dev/rc_workspace\`
- Ensure the application user has write permissions
- Verify disk space availability

### Logging
Application logs are stored in \`TEMP_ROOT/logs/app.log\`. Check this file for detailed error information.

## 🔒 Security Considerations

- Personal Access Tokens are encrypted before storage
- File operations are restricted to workspace directories
- Path traversal attacks are prevented with input validation
- All user inputs are sanitized and validated

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: \`git checkout -b feature-name\`
3. Make your changes and add tests
4. Commit your changes: \`git commit -am 'Add feature'\`
5. Push to the branch: \`git push origin feature-name\`
6. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
- Create an issue on GitHub
- Check the troubleshooting section above
- Review application logs for error details

## 🔄 Version History

### v1.0.0
- Initial release with core workspace management
- GitLab integration
- Conda environment support
- JupyterLab integration
- File explorer functionality
- Audit logging system

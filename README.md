# UBRITE Project Workspace Manager

A Flask application that helps researchers create and manage project workspaces with integrated Conda environments, GitLab repositories, and in-browser IDEs.

## Features

- Create workspaces with a single click
- Integrated GitLab repository creation
- Conda environment management
- One-click JupyterLab and VS Code Web launch
- Git panel with real-time updates
- Immutable audit log with CSV export

## Available Environment Templates

The following Conda environment templates are available:

- **data-science**: General data science packages (numpy, pandas, matplotlib, scikit-learn)
- **web-dev**: Web development packages (Flask, SQLAlchemy, etc.)
- **deep-learning**: Deep learning frameworks and tools (PyTorch, TensorFlow, transformers)
- **bioinformatics**: Bioinformatics tools and libraries (Biopython, BLAST, samtools)
- **nlp**: Natural Language Processing libraries (NLTK, spaCy, transformers)
- **computer-vision**: Computer Vision libraries (OpenCV, torchvision, detectron2)
- **geospatial**: Geospatial analysis tools (GeoPandas, GDAL, rasterio)
- **scientific-computing**: Scientific computing and simulation (FEniCS, PETSc, Numba)
- **statistics**: Statistical analysis packages (statsmodels, PyMC3, R integration)

## Installation

1. Clone the repository:
\`\`\`bash
git clone https://github.com/yourusername/ubrite-workspace-manager.git
cd ubrite-workspace-manager
\`\`\`

2. Create a virtual environment:
\`\`\`bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
\`\`\`

3. Install dependencies:
\`\`\`bash
pip install -r requirements.txt
\`\`\`

4. Set up environment variables:
\`\`\`bash
export FLASK_APP=app.py
export FLASK_ENV=development
\`\`\`

5. Run the application:
\`\`\`bash
flask run
\`\`\`

## Configuration

The application can be configured using environment variables or by modifying the `config.py` file.

## Usage

1. Open the application in your browser at `http://localhost:5000`
2. Configure your GitLab Personal Access Token
3. Create a new workspace
4. Use the Git panel to manage your code
5. Launch JupyterLab or VS Code Web to start coding

## License

MIT

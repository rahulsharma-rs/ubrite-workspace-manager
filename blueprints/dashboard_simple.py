from flask import Blueprint, render_template, jsonify

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
def index():
    """Simple dashboard home page."""
    try:
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>UBRITE Workspace Manager</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; }
                .container { max-width: 800px; margin: 0 auto; }
                .status { padding: 20px; background: #f0f8ff; border-radius: 5px; margin: 20px 0; }
                .success { background: #d4edda; color: #155724; }
                .info { background: #d1ecf1; color: #0c5460; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🚀 UBRITE Workspace Manager</h1>
                <div class="status success">
                    <h3>✅ Application Status: Running</h3>
                    <p>The UBRITE Workspace Manager is successfully running!</p>
                </div>

                <div class="status info">
                    <h3>📋 Available Actions</h3>
                    <ul>
                        <li><a href="/health">Health Check</a></li>
                        <li><a href="/status">Application Status</a></li>
                        <li><a href="/debug/routes">View All Routes</a></li>
                        <li><a href="/debug/info">Debug Information</a></li>
                        <li><a href="/test">Test Route</a></li>
                    </ul>
                </div>

                <div class="status">
                    <h3>🔧 Next Steps</h3>
                    <p>The basic application is working. You can now:</p>
                    <ol>
                        <li>Configure your GitLab integration</li>
                        <li>Set up your Git user information</li>
                        <li>Create your first workspace</li>
                    </ol>
                </div>
            </div>
        </body>
        </html>
        """
    except Exception as e:
        return jsonify({'error': f'Dashboard error: {str(e)}'}), 500


@dashboard_bp.route('/simple-test')
def simple_test():
    """Simple test endpoint."""
    return jsonify({
        'message': 'Dashboard blueprint is working!',
        'blueprint': 'dashboard',
        'route': '/simple-test'
    })

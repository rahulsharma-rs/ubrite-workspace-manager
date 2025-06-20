# -*- coding: utf-8 -*-
import os, sys

# —————————————————————————————————————————————————
# 1) figure out where everything lives
# —————————————————————————————————————————————————

user      = os.environ.get('USER', '')
base_dir  = '/data/user/{user}/ondemand/dev/rc_workspace'.format(user=user)
venv_dir  = os.path.join(base_dir, 'venv')
app_dir   = os.path.join(base_dir, 'ubrite-workspace-manager')

# —————————————————————————————————————————————————
# 2) activate the venv in the env
# —————————————————————————————————————————————————
os.environ['VIRTUAL_ENV'] = venv_dir
os.environ['PATH']        = os.path.join(venv_dir, 'bin') + ':' + os.environ.get('PATH', '')
if 'PYTHONHOME' in os.environ:
    del os.environ['PYTHONHOME']

# —————————————————————————————————————————————————
# 3) re-exec under the venv’s python3 if we’re not already
# —————————————————————————————————————————————————
python3_bin = os.path.join(venv_dir, 'bin', 'python3')
if sys.executable != python3_bin:
    os.execl(python3_bin, python3_bin, *sys.argv)

# —————————————————————————————————————————————————
# 4) insert the venv’s site-packages on sys.path
# —————————————————————————————————————————————————
ver = str(sys.version_info[0]) + '.' + str(sys.version_info[1])
site_packages = os.path.join(venv_dir, 'lib', 'python' + ver, 'site-packages')
if os.path.isdir(site_packages):
    sys.path.insert(0, site_packages)

# —————————————————————————————————————————————————
# 5) insert *your* app folder so `import app` works
# —————————————————————————————————————————————————
sys.path.insert(0, app_dir)

# —————————————————————————————————————————————————
# 6) import & expose your Flask app
# —————————————————————————————————————————————————
from app import create_app, socketio

# Create your Flask app
app = create_app()

# Wrap it with the python-socketio WSGI adapter
from socketio import WSGIApp
application = WSGIApp(socketio.server, app)

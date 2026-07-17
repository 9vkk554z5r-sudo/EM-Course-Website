import sys, os
sys.stdout.reconfigure(encoding='utf-8')
os.chdir(r'C:\Users\hp\Documents\Codex\2026-06-24\agent-agent-python-1-2-9\electron-microscopy-course')
sys.path.insert(0, os.getcwd())
from app import app, init_db
init_db()
with open('server_started.log', 'w') as log:
    sys.stdout = log
    sys.stderr = log
    print('Starting server on port 5002...')
    app.run(host='0.0.0.0', port=5002, debug=False, use_reloader=False)

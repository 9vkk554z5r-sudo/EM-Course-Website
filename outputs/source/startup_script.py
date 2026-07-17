# Startup script for Electron Microscopy Course Website
import sys, os
sys.stdout.reconfigure(encoding="utf-8")
os.chdir(r"C:\Users\hp\Documents\Codex\2026-06-24\agent-agent-python-1-2-9\electron-microscopy-course")
sys.path.insert(0, os.getcwd())

with open("server_started.log", "w", encoding="utf-8") as log:
    sys.stdout = log
    sys.stderr = log
    
    from app import app as flask_app, init_db
    init_db()
    
    print("Starting server on http://127.0.0.1:5000")
    flask_app.run(host="0.0.0.0", port=5001, debug=True, use_reloader=False)

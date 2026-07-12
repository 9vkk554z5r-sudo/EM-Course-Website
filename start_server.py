
import sys, os
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
os.chdir("C:/Users/hp/Documents/Codex/2026-06-24/agent-agent-python-1-2-9/electron-microscopy-course")
sys.path.insert(0, os.getcwd())
with open(os.path.join(os.getcwd(), "server.log"), "w", encoding="utf-8") as log:
    sys.stdout = log
    sys.stderr = log
    from app import app, init_db
    init_db()
    print("Starting server on 0.0.0.0:5001")
    print("Local: http://127.0.0.1:5001")
    print("LAN: http://10.20.234.36:5001")
    app.run(host="0.0.0.0", port=5001, debug=False, use_reloader=False)

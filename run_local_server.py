# -*- coding: utf-8 -*-
import sys
from app import app, init_db, setup_scheduler

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

if __name__ == "__main__":
    init_db()
    try:
        setup_scheduler(app)
    except Exception as exc:
        print(f"Scheduler not started: {exc}", flush=True)
    print("生命科学课程助手", flush=True)
    print("Local: http://127.0.0.1:5001", flush=True)
    app.run(host="0.0.0.0", port=5001, debug=False, use_reloader=False)
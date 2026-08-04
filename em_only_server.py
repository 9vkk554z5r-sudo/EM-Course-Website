import os
import sys

os.environ["EM_ONLY_SITE"] = "1"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
os.chdir(BASE_DIR)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from app import app, init_db


if __name__ == "__main__":
    init_db()
    print("EM-only course server")
    print("Local: http://127.0.0.1:5002")
    print("LAN: http://0.0.0.0:5002")
    app.run(host="0.0.0.0", port=5002, debug=False, use_reloader=False)

# -*- coding: utf-8 -*-
import os
import sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.getcwd())
log = open('server-lsca-preview.log', 'a', encoding='utf-8', buffering=1)
sys.stdout = log
sys.stderr = log

from app import app, init_db, setup_scheduler

if __name__ == '__main__':
    init_db()
    setup_scheduler(app)
    print('生命科学课程助手 preview: http://127.0.0.1:5001', flush=True)
    app.run(host='0.0.0.0', port=5001, debug=False, use_reloader=False)

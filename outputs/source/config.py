# -*- coding: utf-8 -*-
import os

BASEDIR = os.path.abspath(os.path.dirname(__file__))

SECRET_KEY = os.environ.get('SECRET_KEY', 'em-course-secret-key-change-in-production')
SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASEDIR, 'course.db')
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Email configuration (configure with real SMTP in production)
MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.qq.com')
MAIL_PORT = int(os.environ.get('MAIL_PORT', 465))
MAIL_USE_SSL = True
MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', '')

# Literature API config (placeholder for real agent endpoint)
LITERATURE_API_URL = os.environ.get('LITERATURE_API_URL', 'http://localhost:5001/api/literature')
AGENT_API_KEY = os.environ.get('AGENT_API_KEY', 'demo-key')


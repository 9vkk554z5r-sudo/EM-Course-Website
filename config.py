# -*- coding: utf-8 -*-
import os
from dotenv import load_dotenv


BASEDIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASEDIR, ".env"))

SECRET_KEY = os.environ.get("SECRET_KEY", "em-course-secret-key-change-in-production")
SQLALCHEMY_DATABASE_URI = os.environ.get(
    "DATABASE_URL", "sqlite:///" + os.path.join(BASEDIR, "course.db")
)
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Email configuration
MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.qq.com")
MAIL_PORT = int(os.environ.get("MAIL_PORT", 465))
MAIL_USE_SSL = True
MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "")

# Standalone LLM API configuration. The same fields may be configured by an
# administrator in the website. Environment variables take precedence.
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "custom")
LLM_API_ENDPOINT = os.environ.get("LLM_API_ENDPOINT", "")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "")
LLM_DEPLOYMENT = os.environ.get("LLM_DEPLOYMENT", "")
LLM_API_STYLE = os.environ.get("LLM_API_STYLE", "auto")

# Supplying an email places OpenAlex requests in its polite pool.
OPENALEX_EMAIL = os.environ.get("OPENALEX_EMAIL", "")

# Scheduled tasks
WEEKLY_LITERATURE_HOUR = 9
WEEKLY_LITERATURE_MINUTE = 0
WEEKLY_LITERATURE_DAY = 0  # Monday

# Optional proxy settings for school/corporate networks.
HTTP_PROXY = os.environ.get("HTTP_PROXY", "")
HTTPS_PROXY = os.environ.get("HTTPS_PROXY", "")

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

# ========================================
# Agent API 配置说明
# ========================================
# 要与你的学校Agent搭建平台联动，按以下步骤:
#
# 1. 设置 Agent API 端点地址
#    LITERATURE_API_URL = "https://your-agent-platform.com/api/literature"
#
# 2. 设置 Agent API 密钥
#    AGENT_API_KEY = "your-api-key-here"
#
# 3. 设置邮件SMTP（用于每周一9:00推送文献）
#    MAIL_USERNAME = "your@email.com"
#    MAIL_PASSWORD = "smtp-password-or-auth-code"
#    MAIL_SERVER = "smtp.qq.com"      # QQ邮箱
#    MAIL_DEFAULT_SENDER = "your@email.com"
#
# 4. Agent API 期望的请求格式 (POST JSON):
#    {
#        "topic": "cryo-EM",
#        "keywords": "single-particle, high-resolution",
#        "limit": 10
#    }
#
# 5. Agent API 期望的响应格式:
#    {
#        "results": [
#            {
#                "title": "Paper Title",
#                "authors": "Author1, Author2",
#                "journal": "Nature",
#                "year": 2025,
#                "doi": "10.1038/example",
#                "abstract": "...",
#                "url": "https://doi.org/...",
#                "citation_count": 100
#            }
#        ]
#    }
#
# 如果未配置 Agent API，系统将使用内置的模拟数据运行。
# ========================================


# Scheduled tasks
WEEKLY_LITERATURE_HOUR = 9
WEEKLY_LITERATURE_MINUTE = 0
WEEKLY_LITERATURE_DAY = 0  # Monday

# Proxy settings (for school/corporate networks blocking external APIs)
# Set these if you cannot connect to OpenAI/DeepSeek directly
HTTP_PROXY = os.environ.get('HTTP_PROXY', '')
HTTPS_PROXY = os.environ.get('HTTPS_PROXY', '')

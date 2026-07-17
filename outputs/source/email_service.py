# -*- coding: utf-8 -*-
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from config import MAIL_SERVER, MAIL_PORT, MAIL_USE_SSL, MAIL_USERNAME, MAIL_PASSWORD, MAIL_DEFAULT_SENDER


def send_email(to_addr, subject, html_content):
    """Send an HTML email."""
    if not MAIL_USERNAME or not MAIL_PASSWORD:
        print(f"[Email] SMTP not configured — would send to {to_addr}: {subject}")
        return False

    msg = MIMEMultipart("alternative")
    msg["From"] = MAIL_DEFAULT_SENDER or MAIL_USERNAME
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        if MAIL_USE_SSL:
            server = smtplib.SMTP_SSL(MAIL_SERVER, MAIL_PORT)
        else:
            server = smtplib.SMTP(MAIL_SERVER, MAIL_PORT)
            server.starttls()
        server.login(MAIL_USERNAME, MAIL_PASSWORD)
        server.sendmail(MAIL_USERNAME, [to_addr], msg.as_string())
        server.quit()
        print(f"[Email] Sent to {to_addr}")
        return True
    except Exception as e:
        print(f"[Email] Failed to send to {to_addr}: {e}")
        return False


def send_weekly_literature():
    """Send weekly literature digest to all users with active subscriptions."""
    from app import create_app
    from models import db, User, LiteratureSubscription, LiteratureItem

    app = create_app()
    with app.app_context():
        users = User.query.all()
        for user in users:
            subs = LiteratureSubscription.query.filter_by(user_id=user.id, active=True).all()
            if not subs:
                continue

            items_html = ""
            for sub in subs:
                papers = LiteratureItem.query.filter_by(topic=sub.topic).order_by(
                    LiteratureItem.fetched_at.desc()
                ).limit(5).all()
                if papers:
                    items_html += f'<h3 style="color:#3b82f6;margin-top:20px;">{sub.topic}</h3>'
                    for p in papers:
                        items_html += f'''
                        <div style="margin:10px 0;padding:12px;background:#f9fafb;border-radius:8px;">
                            <a href="{p.url}" style="color:#1d4ed8;font-weight:600;text-decoration:none;">{p.title}</a>
                            <p style="color:#6b7280;margin:4px 0 0;">{p.authors} — {p.journal} ({p.year})</p>
                        </div>
                        '''

            if not items_html:
                continue

            html = f"""
            <!DOCTYPE html>
            <html><head><meta charset="utf-8"></head>
            <body style="font-family:'Segoe UI',Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
                <div style="background:linear-gradient(135deg,#1e3a5f,#3b82f6);color:white;padding:30px 20px;border-radius:12px;text-align:center;">
                    <h1 style="margin:0;font-size:24px;">电子显微学前沿文献周报</h1>
                    <p style="margin:8px 0 0;opacity:0.9;">{datetime.now().strftime('%Y年%m月%d日')}</p>
                </div>
                <div style="padding:20px 0;">
                    <p>亲爱的 <strong>{user.name}</strong> 同学，</p>
                    <p>以下是您订阅的最新文献推送：</p>
                    {items_html}
                </div>
                <div style="border-top:1px solid #e5e7eb;padding:15px 0;color:#9ca3af;font-size:12px;text-align:center;">
                    <p>本邮件由电子显微学前沿课程Agent自动生成 | 退订请登录网站设置</p>
                </div>
            </body></html>
            """

            send_email(
                to_addr=user.email,
                subject=f"电子显微学前沿文献周报 — {datetime.now().strftime('%Y-%m-%d')}",
                html_content=html,
            )

    print(f"[Email] Weekly literature digest sent at {datetime.now(timezone.utc)}")
    return True


def send_test_email(to_addr):
    """Send a test email to verify configuration."""
    html = """
    <html><body style="font-family:Arial,sans-serif;">
        <h2>电子显微学课程邮件测试</h2>
        <p>邮件服务配置成功！</p>
        <p>您将在每周一上午9:00收到最新的文献推送。</p>
    </body></html>
    """
    return send_email(to_addr, "电子显微学课程 — 邮件测试", html)

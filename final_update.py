# -*- coding: utf-8 -*-
import os
W = r"C:\Users\hp\Documents\Codex\2026-06-24\agent-agent-python-1-2-9\electron-microscopy-course"

# Create i18n.js
with open(os.path.join(W, "static", "js", "i18n.js"), "w", encoding="utf-8") as f:
    f.write("// i18n client\nconsole.log('i18n loaded');")

# Create quiz template (Skill 6)
with open(os.path.join(W, "templates", "study_quiz.html"), "w", encoding="utf-8") as f:
    f.write("{% extends 'base.html' %}{% block title %}Quiz{% endblock %}{% block content %}<h1>Quiz</h1>{% endblock %}")

# Create admin quiz page
with open(os.path.join(W, "templates", "admin_quizzes.html"), "w", encoding="utf-8") as f:
    f.write("{% extends 'admin_base.html' %}{% block title %}Quiz Admin{% endblock %}{% block admin_content %}<h1>Quiz Admin</h1>{% endblock %}")

print("Core files created")

# -*- coding: utf-8 -*-
import os
import sys
from datetime import datetime, date, timezone

from flask import (
    Flask, render_template, redirect, url_for, request,
    flash, jsonify, abort, session as flask_session
)
from flask_login import (
    LoginManager, login_user, logout_user, login_required, current_user
)
from apscheduler.schedulers.background import BackgroundScheduler

from config import SECRET_KEY, SQLALCHEMY_DATABASE_URI, SQLALCHEMY_TRACK_MODIFICATIONS
from config import WEEKLY_LITERATURE_HOUR, WEEKLY_LITERATURE_MINUTE
from models import db, User, LiteratureSubscription, LiteratureItem, CitationLink, KnowledgePoint, DailyCheckin, ProtocolVideo, UploadedLiterature, AttendanceReward, Quiz, QuizAttempt, ProtocolCollection, PresentationTemplate, AgentLog, ApiKey, LiteraturePlanet, PlanetPaper, ChatHistory, LiteratureCategory, BookmarkedLiterature, UserStudyPlan
from knowledge_points import DIFFICULTY_LABELS, DIFFICULTY_COLORS
import json
import re
import datetime as dt_module
from functools import wraps
from werkzeug.utils import secure_filename



def call_llm(api_key, provider, prompt, system="You are an EM expert."):
    import requests as req, os as _os
    # Auto-detect proxy from environment variables
    _proxies = {}
    _hp = _os.environ.get("HTTP_PROXY", "") or _os.environ.get("http_proxy", "")
    _hs = _os.environ.get("HTTPS_PROXY", "") or _os.environ.get("https_proxy", "")
    if _hp: _proxies["http"] = _hp
    if _hs: _proxies["https"] = _hs
    if provider == "deepseek":
        url = "https://api.deepseek.com/v1/chat/completions"
        model = "deepseek-chat"
    else:
        url = "https://api.openai.com/v1/chat/completions"
        model = "gpt-3.5-turbo"
    try:
        resp = req.post(url, headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}], "max_tokens": 600}, timeout=60, proxies=_proxies if _proxies else None)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        else:
            return "API Error (" + str(resp.status_code) + "): " + resp.text[:300]
    except Exception as e:
        return "Request Error: " + str(e)


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = SECRET_KEY
    app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = SQLALCHEMY_TRACK_MODIFICATIONS
    return app


app = create_app()
db.init_app(app)

PLATFORM_NAME = "生命科学课程助手"
COURSE_REGISTRY = {
    "electron-microscopy": {
        "slug": "electron-microscopy",
        "name": "冷冻电子显微学",
        "name_en": "Cryo-Electron Microscopy",
        "label": "Electron Microscopy",
        "description": "聚焦冷冻电镜、冷冻电镜断层成像与体积电镜，连接结构解析、样品制备和文献追踪",
        "description_en": "Focuses on cryo-EM, cryo-electron tomography and volume EM, connecting structure determination, sample preparation and literature tracking",
        "status": "open",
        "accent": "Cryo-EM / Cryo-ET / vEM",
        "galaxy_keywords": ["Cryo-EM", "Cryo-ET", "vEM"],
        "galaxy_keywords_en": ["Cryo-EM", "Cryo-ET", "vEM"],
    },
    "structural-biology": {
        "slug": "structural-biology",
        "name": "结构生物学",
        "name_en": "Structural Biology",
        "label": "Structural Biology",
        "description": "围绕蛋白质、复合物与分子机器的结构解析，组织方法、文献与科研问题",
        "description_en": "Organizes methods, literature and research questions around proteins, complexes and molecular machines",
        "status": "soon",
        "accent": "Structure / Function / Binding",
        "galaxy_keywords": ["蛋白质结构解析", "分子机器", "构效关系"],
        "galaxy_keywords_en": ["Protein Structure", "Molecular Machines", "Structure-Activity"],
    },
    "cell-biology": {
        "slug": "cell-biology",
        "name": "细胞生物学",
        "name_en": "Cell Biology",
        "label": "Cell Biology",
        "description": "关注细胞结构、信号通路、细胞器与动态过程，辅助课程学习和实验设计",
        "description_en": "Explores cellular structures, signaling pathways, organelles and dynamic processes for learning and experiment design",
        "status": "soon",
        "accent": "Imaging / Signaling / Organelles",
        "galaxy_keywords": ["细胞器动态", "信号通路", "细胞成像"],
        "galaxy_keywords_en": ["Organelle Dynamics", "Signaling Pathways", "Cell Imaging"],
    },
    "bioinformatics": {
        "slug": "bioinformatics",
        "name": "生物信息学",
        "name_en": "Bioinformatics",
        "label": "Bioinformatics",
        "description": "面向序列、组学与结构数据分析，整理工具链、数据集和分析流程",
        "description_en": "Structures toolchains, datasets and analysis workflows for sequences, omics and structural data",
        "status": "soon",
        "accent": "Omics / Sequence / Pipeline",
        "galaxy_keywords": ["序列分析", "组学数据", "结构预测"],
        "galaxy_keywords_en": ["Sequence Analysis", "Omics Data", "Structure Prediction"],
    },
    "neuroscience": {
        "slug": "neuroscience",
        "name": "神经科学",
        "name_en": "Neuroscience",
        "label": "Neuroscience",
        "description": "围绕神经环路、突触机制与疾病模型，连接课程知识和研究文献",
        "description_en": "Connects course knowledge and research literature around neural circuits, synaptic mechanisms and disease models",
        "status": "soon",
        "accent": "Circuit / Imaging / Cognition",
        "galaxy_keywords": ["神经环路", "突触机制", "疾病模型"],
        "galaxy_keywords_en": ["Neural Circuits", "Synaptic Mechanisms", "Disease Models"],
    },
}


def _selected_course():
    slug = (
        request.args.get("course")
        or flask_session.get("selected_course")
        or "electron-microscopy"
    )
    return COURSE_REGISTRY.get(slug, COURSE_REGISTRY["electron-microscopy"])


@app.context_processor
def inject_platform_context():
    return {
        "platform_name": PLATFORM_NAME,
        "course_registry": COURSE_REGISTRY,
        "selected_course": _selected_course(),
    }

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = '请先登录'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.route('/')
def index():
    return render_template("platform_home.html")


@app.route('/courses')
def courses():
    return render_template("course_select.html", courses=COURSE_REGISTRY)


@app.route('/course/<slug>')
def course_entry(slug):
    course = COURSE_REGISTRY.get(slug)
    if not course:
        abort(404)
    if course["status"] != "open":
        flash(f"{course['name']} 星系即将开放", "info")
        return redirect(url_for("courses"))
    flask_session["selected_course"] = slug
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login", course=slug, next=url_for("dashboard")))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(request.args.get("next") or url_for('dashboard'))
    course_slug = request.args.get("course") or flask_session.get("selected_course") or "electron-microscopy"
    course = COURSE_REGISTRY.get(course_slug, COURSE_REGISTRY["electron-microscopy"])
    flask_session["selected_course"] = course["slug"]
    if request.method == 'POST':
        course_slug = request.form.get("course") or course["slug"]
        course = COURSE_REGISTRY.get(course_slug, COURSE_REGISTRY["electron-microscopy"])
        flask_session["selected_course"] = course["slug"]
        identifier = request.form.get('identifier', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter(
            db.or_(
                User.student_id == identifier,
                User.email == identifier,
                User.phone == identifier,
            )
        ).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            flash('登录成功！欢迎回来', 'success')
            return redirect(request.form.get("next") or request.args.get("next") or url_for('dashboard'))
        flash('账号或密码错误', 'error')
    return render_template('login.html', course=course, next_url=request.args.get("next") or url_for("dashboard"))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    course = _selected_course()
    if request.method == 'POST':
        student_id = request.form.get('student_id', '').strip()
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        if not all([student_id, name, password]) or not (email or phone):
            flash('请填写所有必填字段', 'error')
            return render_template('register.html', course=course)

        if password != confirm:
            flash('两次输入的密码不一致', 'error')
            return render_template('register.html', course=course)

        if len(password) < 6:
            flash('密码长度至少6位', 'error')
            return render_template('register.html', course=course)

        if User.query.filter_by(student_id=student_id).first():
            flash('该学号已被注册', 'error')
            return render_template('register.html', course=course)

        if email and User.query.filter_by(email=email).first():
            flash('该邮箱已被注册', 'error')
            return render_template('register.html', course=course)

        if phone and User.query.filter_by(phone=phone).first():
            flash('该手机号已被注册', 'error')
            return render_template('register.html', course=course)

        user = User(student_id=student_id, name=name, email=email, phone=phone or None)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('注册成功！请登录', 'success')
        return redirect(url_for('login', course=course["slug"]))

    return render_template('register.html', course=course)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('已退出登录', 'info')
    return redirect(url_for('index'))


@app.route('/dashboard')
@login_required
def dashboard():
    today = date.today()
    today_checkin = DailyCheckin.query.filter_by(
        user_id=current_user.id, date=today
    ).first()

    subscription_count = LiteratureSubscription.query.filter_by(
        user_id=current_user.id, active=True
    ).count()
    active_subscriptions = LiteratureSubscription.query.filter_by(
        user_id=current_user.id, active=True
    ).order_by(LiteratureSubscription.created_at.desc()).limit(4).all()
    total_checkins = DailyCheckin.query.filter_by(user_id=current_user.id).count()
    streak = _calc_streak(current_user.id)

    recent_papers = LiteratureItem.query.order_by(
        LiteratureItem.fetched_at.desc()
    ).limit(5).all()

    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    import datetime as dt
    today_dt = date.today()
    monday = today_dt - dt.timedelta(days=today_dt.weekday())
    week_data = []
    for i in range(7):
        d = monday + dt.timedelta(days=i)
        count = DailyCheckin.query.filter_by(
            user_id=current_user.id, date=d
        ).count()
        week_data.append(count)

    total_trees = AttendanceReward.query.filter_by(user_id=current_user.id).count()
    weekly_trees = AttendanceReward.query.filter_by(user_id=current_user.id, period="weekly").count()

    # Sample literature for nebula
    from literature_agent import SAMPLE_LITERATURE
    sample_literature = []
    for topic, papers in SAMPLE_LITERATURE.items():
        for p in papers:
            p_copy = dict(p)
            p_copy["topic"] = topic
            sample_literature.append(p_copy)

    # Knowledge points for forest
    all_kps = KnowledgePoint.query.all()

    # User protocols
    user_protocols_list = ProtocolCollection.query.filter_by(user_id=current_user.id).all()
    bookmark_count = BookmarkedLiterature.query.filter_by(user_id=current_user.id).count()
    protocol_count = ProtocolCollection.query.filter_by(user_id=current_user.id).count()
    primary_topic = active_subscriptions[0].topic if active_subscriptions else "cryo-EM / single particle analysis"

    return render_template(
        "dashboard.html",
        today_checkin=today_checkin,
        subscription_count=subscription_count,
        total_checkins=total_checkins,
        streak=streak,
        recent_papers=recent_papers,
        weekdays=weekdays,
        week_data=week_data,
        trees=total_trees,
        weekly_forest=weekly_trees,
        sample_literature=sample_literature,
        all_kps=all_kps,
        user_protocols=user_protocols_list,
        active_subscriptions=active_subscriptions,
        bookmark_count=bookmark_count,
        protocol_count=protocol_count,
        primary_topic=primary_topic,
    )


def _calc_streak(user_id):
    import datetime as dt
    today = date.today()
    streak = 0
    current = today
    while True:
        checkin = DailyCheckin.query.filter_by(
            user_id=user_id, date=current
        ).first()
        if checkin:
            streak += 1
            current -= dt.timedelta(days=1)
        else:
            break
    return streak


@app.route("/literature")
@login_required
def literature():
    page = request.args.get("page", 1, type=int)
    per_page = 20
    pagination = LiteratureItem.query.order_by(
        LiteratureItem.fetched_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    return render_template("literature.html", pagination=pagination)


@app.route("/literature/subscribe", methods=["POST"])
@login_required
def subscribe():
    topic = request.form.get("topic", "").strip()
    keywords = request.form.get("keywords", "").strip()
    if not topic:
        flash("请输入订阅主题", "error")
        return redirect(url_for("literature"))

    existing = LiteratureSubscription.query.filter_by(
        user_id=current_user.id, topic=topic
    ).first()
    if existing:
        existing.active = True
    else:
        sub = LiteratureSubscription(
            user_id=current_user.id, topic=topic, keywords=keywords
        )
        db.session.add(sub)
    db.session.commit()
    flash(f"已订阅：{topic}", "success")
    return redirect(url_for("literature"))


@app.route("/literature/unsubscribe/<int:sub_id>")
@login_required
def unsubscribe(sub_id):
    sub = LiteratureSubscription.query.get_or_404(sub_id)
    if sub.user_id != current_user.id:
        abort(403)
    sub.active = False
    db.session.commit()
    flash("已取消订阅", "info")
    return redirect(url_for("literature"))


@app.route("/literature/refresh")
@login_required
def refresh_literature():
    from literature_agent import fetch_literature_for_topic
    subs = LiteratureSubscription.query.filter_by(
        user_id=current_user.id, active=True
    ).all()
    count = 0
    for sub in subs:
        results = fetch_literature_for_topic(sub.topic, sub.keywords)
        for paper in results:
            existing = LiteratureItem.query.filter_by(
                doi=paper.get("doi")
            ).first()
            if not existing and paper.get("doi"):
                item = LiteratureItem(
                    title=paper.get("title", ""),
                    authors=paper.get("authors", ""),
                    journal=paper.get("journal", ""),
                    year=paper.get("year"),
                    doi=paper.get("doi", ""),
                    abstract=paper.get("abstract", ""),
                    url=paper.get("url", ""),
                    topic=sub.topic,
                    citation_count=paper.get("citation_count", 0),
                )
                db.session.add(item)
                count += 1
        db.session.commit()
    flash(f"已刷新文献 {count} 篇", "success")
    return redirect(url_for("literature"))


@app.route("/my-subscriptions")
@login_required
def my_subscriptions():
    subs = LiteratureSubscription.query.filter_by(
        user_id=current_user.id
    ).order_by(LiteratureSubscription.created_at.desc()).all()
    return render_template("my_subscriptions.html", subs=subs)


@app.route("/nebula")
@login_required
def nebula():
    return render_template("nebula.html")


@app.route("/api/nebula-data")
@login_required
def nebula_data():
    items = LiteratureItem.query.all()
    if not items:
        return jsonify({"nodes": [], "edges": []})

    from literature_agent import generate_citation_graph
    data = generate_citation_graph(items)
    return jsonify(data)


@app.route("/api/literature-graph")
@login_required
def literature_graph():
    query = request.args.get("q", "").strip() or "cryo-EM"
    return jsonify(_build_literature_graph(current_user.id, query))


def _build_literature_graph(user_id, query):
    nodes = {}
    edges = []

    def add_node(node):
        nodes[node["id"]] = node

    def add_edge(source, target, relation, weight=0.5):
        if source in nodes and target in nodes:
            edges.append({
                "from": source,
                "to": target,
                "relation": relation,
                "weight": weight,
            })

    seed_id = "topic:" + re.sub(r"[^a-zA-Z0-9_-]+", "-", query.lower()).strip("-")
    add_node({
        "id": seed_id,
        "type": "Topic",
        "label": query,
        "title": query,
        "year": "",
        "authors": "",
        "keywords": [query],
        "abstract": "当前文献探索的中心研究主题。",
        "relevance": 1.0,
        "citation_count": 0,
        "bookmarked": False,
        "read": False,
        "url": "",
        "source": "seed",
    })

    bookmarks = BookmarkedLiterature.query.filter_by(user_id=user_id).order_by(BookmarkedLiterature.added_at.desc()).limit(16).all()
    literature_items = LiteratureItem.query.order_by(LiteratureItem.citation_count.desc()).limit(18).all()
    planet_papers = PlanetPaper.query.join(LiteraturePlanet).filter(LiteraturePlanet.user_id == user_id).limit(14).all()
    protocols = ProtocolCollection.query.filter_by(user_id=user_id).order_by(ProtocolCollection.created_at.desc()).limit(6).all()

    paper_sources = []
    for item in literature_items:
        paper_sources.append(("lit", item.id, item.title, item.authors, item.journal, item.year, item.abstract, item.topic, item.citation_count, item.url, item.doi, False))
    for item in planet_papers:
        topic = item.planet.topic or item.planet.name if item.planet else ""
        paper_sources.append(("planet", item.id, item.title, item.authors, item.journal, item.year, item.abstract, topic, 0, item.url, item.doi, False))
    for item in bookmarks:
        paper_sources.append(("bookmark", item.id, item.title, item.authors, item.journal, item.year, item.abstract, item.source, item.citation_count, item.url, item.doi, True))

    seen_titles = set()
    author_counts = {}
    keyword_counts = {}
    paper_ids = []
    for source, item_id, title, authors, journal, year, abstract, topic, citations, url, doi, bookmarked in paper_sources:
        if not title or title.lower() in seen_titles:
            continue
        seen_titles.add(title.lower())
        node_id = f"paper:{source}:{item_id}"
        keywords = _graph_keywords(topic, title, abstract)
        add_node({
            "id": node_id,
            "type": "Paper",
            "label": title[:42] + ("..." if len(title) > 42 else ""),
            "title": title,
            "year": year or "",
            "authors": authors or "",
            "journal": journal or "",
            "keywords": keywords,
            "abstract": abstract[:360] if abstract else "暂无摘要。可从 DOI、标题或收藏记录继续补充。",
            "relevance": _graph_relevance(query, title, topic, citations),
            "citation_count": citations or 0,
            "bookmarked": bookmarked,
            "read": False,
            "url": url or "",
            "doi": doi or "",
            "source": source,
        })
        paper_ids.append(node_id)
        add_edge(seed_id, node_id, "similar_work", 0.55 + min((citations or 0) / 300, 0.35))

        for author in _split_authors(authors)[:2]:
            author_counts[author] = author_counts.get(author, 0) + 1
        for kw in keywords[:3]:
            keyword_counts[kw] = keyword_counts.get(kw, 0) + 1

    for kw, count in sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        kw_id = "keyword:" + re.sub(r"[^a-zA-Z0-9_-]+", "-", kw.lower()).strip("-")
        add_node({
            "id": kw_id,
            "type": "Keyword",
            "label": kw,
            "title": kw,
            "year": "",
            "authors": "",
            "keywords": [kw],
            "abstract": f"在当前图谱中与 {count} 篇文献相关。",
            "relevance": min(0.95, 0.45 + count * 0.12),
            "citation_count": count,
            "bookmarked": False,
            "read": False,
            "url": "",
            "source": "keyword",
        })
        add_edge(seed_id, kw_id, "shared_keyword", 0.45 + count * 0.08)

    for author, count in sorted(author_counts.items(), key=lambda x: x[1], reverse=True)[:7]:
        author_id = "author:" + re.sub(r"[^a-zA-Z0-9_-]+", "-", author.lower()).strip("-")
        add_node({
            "id": author_id,
            "type": "Author",
            "label": author,
            "title": author,
            "year": "",
            "authors": author,
            "keywords": ["research team"],
            "abstract": f"当前图谱中出现 {count} 次的作者或研究团队。",
            "relevance": min(0.9, 0.4 + count * 0.15),
            "citation_count": count,
            "bookmarked": False,
            "read": False,
            "url": "",
            "source": "author",
        })
        add_edge(seed_id, author_id, "same_author", 0.4 + count * 0.08)

    for protocol in protocols:
        protocol_id = f"protocol:{protocol.id}"
        add_node({
            "id": protocol_id,
            "type": "Protocol",
            "label": protocol.name[:32],
            "title": protocol.name,
            "year": protocol.created_at.year if protocol.created_at else "",
            "authors": "",
            "keywords": ["protocol", "method"],
            "abstract": protocol.methods_summary[:360] if protocol.methods_summary else protocol.paper_title or "个人实验流程收藏。",
            "relevance": 0.72,
            "citation_count": 0,
            "bookmarked": True,
            "read": False,
            "url": url_for("agent_methods"),
            "source": "protocol",
        })
        add_edge(seed_id, protocol_id, "method_dependency", 0.7)

    if len(nodes) <= 1:
        return _sample_literature_graph(query)

    keyword_nodes = [n for n in nodes.values() if n["type"] == "Keyword"]
    author_nodes = [n for n in nodes.values() if n["type"] == "Author"]
    for paper_id in paper_ids:
        paper = nodes[paper_id]
        for kw in paper["keywords"][:3]:
            kw_id = "keyword:" + re.sub(r"[^a-zA-Z0-9_-]+", "-", kw.lower()).strip("-")
            add_edge(paper_id, kw_id, "shared_keyword", 0.35)
        for author in _split_authors(paper.get("authors", ""))[:2]:
            author_id = "author:" + re.sub(r"[^a-zA-Z0-9_-]+", "-", author.lower()).strip("-")
            add_edge(paper_id, author_id, "same_author", 0.35)

    if len(paper_ids) >= 2:
        for i in range(min(len(paper_ids) - 1, 8)):
            add_edge(paper_ids[i], paper_ids[i + 1], "similar_work", 0.32)

    return {
        "seed": nodes[seed_id],
        "nodes": list(nodes.values())[:42],
        "edges": edges[:90],
        "meta": {
            "query": query,
            "source": "database",
            "node_count": len(nodes),
            "edge_count": len(edges),
        },
    }


def _split_authors(authors):
    if not authors:
        return []
    parts = re.split(r",|;| and |、|，", authors)
    return [p.strip() for p in parts if p.strip()][:6]


def _graph_keywords(topic, title="", abstract=""):
    seeds = []
    if topic:
        seeds.extend(re.split(r",|;|/|、|，", topic))
    text = f"{title} {abstract}".lower()
    vocab = [
        "cryo-EM", "single particle analysis", "electron tomography",
        "sample preparation", "image processing", "classification",
        "resolution", "reconstruction", "protein complex", "membrane protein",
        "focused refinement", "micrograph", "dose weighting", "CLEM",
        "subtomogram averaging",
    ]
    for term in vocab:
        if term.lower() in text:
            seeds.append(term)
    clean = []
    for item in seeds:
        item = item.strip()
        if item and item.lower() not in [x.lower() for x in clean]:
            clean.append(item)
    return clean[:6] or ["electron microscopy"]


def _graph_relevance(query, title, topic, citations):
    score = 0.48
    q = query.lower()
    if q and q in (title or "").lower():
        score += 0.24
    if q and q in (topic or "").lower():
        score += 0.18
    score += min((citations or 0) / 500, 0.18)
    return round(min(score, 0.98), 2)


def _sample_literature_graph(query):
    seed = {
        "id": "topic:cryo-em",
        "type": "Topic",
        "label": query or "cryo-EM",
        "title": query or "cryo-EM",
        "year": "",
        "authors": "",
        "keywords": ["cryo-EM", "structure determination"],
        "abstract": "示例图谱：以冷冻电镜单颗粒分析为中心组织论文、作者、关键词和方法。",
        "relevance": 1,
        "citation_count": 0,
        "bookmarked": False,
        "read": False,
        "url": "",
        "source": "sample",
    }
    nodes = [seed]
    samples = [
        ("paper:1", "Paper", "RELION: implementation of Bayesian single-particle reconstruction", 2012, "Scheres SHW", ["single particle analysis", "reconstruction", "classification"], 1850, 0.96),
        ("paper:2", "Paper", "CryoSPARC: algorithms for rapid unsupervised cryo-EM structure determination", 2017, "Punjani A, Rubinstein JL", ["ab initio reconstruction", "heterogeneity", "GPU"], 1400, 0.93),
        ("paper:3", "Paper", "Motion correction and dose weighting for electron cryo-microscopy", 2013, "Li X, Mooney P", ["micrograph", "motion correction", "dose weighting"], 980, 0.86),
        ("paper:4", "Paper", "Atomic resolution cryo-EM structure determination of protein complexes", 2020, "Nakane T, Kotecha A", ["resolution", "protein complex", "refinement"], 720, 0.84),
        ("keyword:spa", "Keyword", "single particle analysis", "", "", ["cryo-EM", "classification"], 8, 0.9),
        ("keyword:heterogeneity", "Keyword", "conformational heterogeneity", "", "", ["3D variability", "classification"], 6, 0.76),
        ("author:scheres", "Author", "Scheres Lab", "", "Scheres SHW", ["RELION", "Bayesian refinement"], 5, 0.82),
        ("author:punjani", "Author", "Punjani / Rubinstein", "", "Punjani A", ["CryoSPARC", "algorithms"], 4, 0.78),
        ("method:refinement", "Method", "Bayesian refinement", "", "", ["refinement", "alignment"], 0, 0.8),
        ("method:motion", "Method", "Motion correction", "", "", ["micrograph", "beam-induced motion"], 0, 0.74),
        ("protocol:vitrification", "Protocol", "Vitrification and grid screening", "", "", ["sample preparation", "grid"], 0, 0.66),
        ("dataset:empiar", "Dataset", "EMPIAR benchmark datasets", "", "", ["dataset", "validation"], 0, 0.58),
    ]
    for sid, typ, title, year, authors, keywords, citations, relevance in samples:
        nodes.append({
            "id": sid,
            "type": typ,
            "label": title[:40] + ("..." if len(title) > 40 else ""),
            "title": title,
            "year": year,
            "authors": authors,
            "journal": "",
            "keywords": keywords,
            "abstract": "示例节点，用于展示真实文献知识图谱的数据结构和交互。接入真实 DOI / OpenAlex 数据后可替换。",
            "relevance": relevance,
            "citation_count": citations,
            "bookmarked": sid in ("paper:2", "protocol:vitrification"),
            "read": False,
            "url": "",
            "doi": "",
            "source": "sample",
        })
    edges = [
        ("topic:cryo-em", "paper:1", "similar_work", 0.9),
        ("topic:cryo-em", "paper:2", "similar_work", 0.9),
        ("topic:cryo-em", "paper:3", "similar_work", 0.75),
        ("topic:cryo-em", "keyword:spa", "shared_keyword", 0.85),
        ("paper:1", "author:scheres", "same_author", 0.8),
        ("paper:2", "author:punjani", "same_author", 0.76),
        ("paper:1", "method:refinement", "method_dependency", 0.78),
        ("paper:3", "method:motion", "method_dependency", 0.72),
        ("paper:1", "keyword:spa", "shared_keyword", 0.7),
        ("paper:2", "keyword:heterogeneity", "shared_keyword", 0.68),
        ("paper:4", "paper:1", "cited_by", 0.55),
        ("protocol:vitrification", "dataset:empiar", "similar_work", 0.38),
    ]
    return {
        "seed": seed,
        "nodes": nodes,
        "edges": [{"from": a, "to": b, "relation": r, "weight": w} for a, b, r, w in edges],
        "meta": {"query": query or "cryo-EM", "source": "sample", "node_count": len(nodes), "edge_count": len(edges)},
    }


@app.route("/study")
@login_required
def study():
    difficulty = request.args.get("difficulty", "beginner")
    today = date.today()

    existing = DailyCheckin.query.filter_by(
        user_id=current_user.id, date=today
    ).first()

    from knowledge_points import KNOWLEDGE_POINTS, get_points_by_difficulty
    import random

    points = get_points_by_difficulty(difficulty)
    if not points:
        points = KNOWLEDGE_POINTS

    if existing and existing.difficulty == difficulty:
        today_point = existing.knowledge_point
    else:
        today_point = random.choice(points)

    import datetime as dt
    today_dt = date.today()
    monday = today_dt - dt.timedelta(days=today_dt.weekday())
    week_checkins = DailyCheckin.query.filter(
        DailyCheckin.user_id == current_user.id,
        DailyCheckin.date >= monday,
        DailyCheckin.date <= today_dt,
    ).all()
    week_days = set(c.date.isoformat() for c in week_checkins)

    week_labels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    week_dates = [(monday + dt.timedelta(days=i)).isoformat() for i in range(7)]

    if hasattr(today_point, "id"):
        point_id = today_point.id
    else:
        point_id = today_point.get("id", 0)

    quizzes = Quiz.query.filter_by(knowledge_point_id=point_id).all()

    return render_template(
        "study.html",
        point=today_point,
        point_id=point_id,
        difficulty=difficulty,
        existing=existing,
        today=today,
        quizzes=quizzes,
        streak=_calc_streak(current_user.id),
        total_checkins=DailyCheckin.query.filter_by(user_id=current_user.id).count(),
        difficulties=DIFFICULTY_LABELS,
        difficulty_colors=DIFFICULTY_COLORS,
        week_days=week_days,
        week_labels=week_labels,
        week_dates=week_dates,
    )


@app.route("/study/checkin", methods=["POST"])
@login_required
def do_checkin():
    point_id = request.form.get("point_id", type=int)
    difficulty = request.form.get("difficulty", "beginner")
    today = date.today()

    point = db.session.get(KnowledgePoint, point_id)
    if not point:
        point = KnowledgePoint(
            title=request.form.get("point_title", ""),
            content=request.form.get("point_content", ""),
            difficulty=difficulty,
        )
        db.session.add(point)
        db.session.flush()
        point_id = point.id

    existing = DailyCheckin.query.filter_by(
        user_id=current_user.id, date=today
    ).first()
    if existing:
        flash("今天已经完成打卡", "info")
        return redirect(url_for("study", difficulty=difficulty))

    score = {
        "beginner": 10,
        "intermediate": 20,
        "advanced": 30,
    }.get(difficulty, 10)

    checkin = DailyCheckin(
        user_id=current_user.id,
        knowledge_point_id=point_id,
        difficulty=difficulty,
        score=score,
        date=today,
    )
    db.session.add(checkin)
    db.session.commit()

    flash(f"打卡完成 获得 {score} 分", "success")
    return redirect(url_for("study", difficulty=difficulty))



@app.route("/admin")
@login_required
@admin_required
def admin_dashboard():
    total_users = User.query.count()
    total_checkins = DailyCheckin.query.count()
    total_literature = LiteratureItem.query.count()
    total_videos = ProtocolVideo.query.count()
    total_knowledge = KnowledgePoint.query.count()
    return render_template("admin_dashboard.html",
        total_users=total_users, total_checkins=total_checkins,
        total_literature=total_literature, total_videos=total_videos,
        total_knowledge=total_knowledge)


@app.route("/admin/knowledge")
@login_required
@admin_required
def admin_knowledge():
    points = KnowledgePoint.query.order_by(KnowledgePoint.created_at.desc()).all()
    from knowledge_points import DIFFICULTY_LABELS
    return render_template("admin_knowledge.html", points=points, difficulties=DIFFICULTY_LABELS)


@app.route("/admin/knowledge/add", methods=["POST"])
@login_required
@admin_required
def admin_add_knowledge():
    kp = KnowledgePoint(
        title=request.form.get("title", ""),
        content=request.form.get("content", ""),
        difficulty=request.form.get("difficulty", "beginner"),
        category=request.form.get("category", "general"),
        source="admin",
    )
    db.session.add(kp)
    db.session.commit()
    flash("知识点已添加", "success")
    return redirect(url_for("admin_knowledge"))


@app.route("/admin/knowledge/edit/<int:kp_id>", methods=["POST"])
@login_required
@admin_required
def admin_edit_knowledge(kp_id):
    kp = db.session.get(KnowledgePoint, kp_id)
    if not kp:
        abort(404)
    kp.title = request.form.get("title", kp.title)
    kp.content = request.form.get("content", kp.content)
    kp.difficulty = request.form.get("difficulty", kp.difficulty)
    kp.category = request.form.get("category", kp.category)
    kp.updated_at = dt_module.datetime.now(timezone.utc)
    db.session.commit()
    flash("知识点已更新", "success")
    return redirect(url_for("admin_knowledge"))


@app.route("/admin/knowledge/delete/<int:kp_id>")
@login_required
@admin_required
def admin_delete_knowledge(kp_id):
    kp = db.session.get(KnowledgePoint, kp_id)
    if kp:
        db.session.delete(kp)
        db.session.commit()
        flash("知识点已删除", "info")
    return redirect(url_for("admin_knowledge"))


@app.route("/admin/videos")
@login_required
@admin_required
def admin_videos():
    videos = ProtocolVideo.query.order_by(ProtocolVideo.uploaded_at.desc()).all()
    return render_template("admin_videos.html", videos=videos)


@app.route("/admin/videos/upload", methods=["POST"])
@login_required
@admin_required
def admin_upload_video():
    video = ProtocolVideo(
        title=request.form.get("title", ""),
        description=request.form.get("description", ""),
        category=request.form.get("category", "general"),
        video_url=request.form.get("video_url", ""),
        difficulty=request.form.get("difficulty", "intermediate"),
        duration_minutes=request.form.get("duration", 0, type=int),
        uploaded_by=current_user.id,
    )
    if "video_file" in request.files:
        f = request.files["video_file"]
        if f and f.filename:
            import uuid
            ext = f.filename.rsplit(".", 1)[-1] if "." in f.filename else "mp4"
            fname = f"video_{uuid.uuid4().hex[:12]}.{ext}"
            save_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "uploads", "videos")
            os.makedirs(save_dir, exist_ok=True)
            f.save(os.path.join(save_dir, fname))
            video.video_path = f"static/uploads/videos/{fname}"
    db.session.add(video)
    db.session.commit()
    flash("视频已保存", "success")
    return redirect(url_for("admin_videos"))


@app.route("/admin/videos/delete/<int:vid>")
@login_required
@admin_required
def admin_delete_video(vid):
    video = db.session.get(ProtocolVideo, vid)
    if video:
        db.session.delete(video)
        db.session.commit()
        flash("已取消订阅", "info")
    return redirect(url_for("admin_videos"))


@app.route("/admin/users")
@login_required
@admin_required
def admin_users():
    users = User.query.order_by(User.registered_at.desc()).all()
    return render_template("admin_users.html", users=users)


@app.route("/admin/users/set-admin/<int:uid>")
@login_required
@admin_required
def admin_set_admin(uid):
    user = db.session.get(User, uid)
    if user and user.id != current_user.id:
        user.is_admin = not user.is_admin
        db.session.commit()
        flash(f"已更新 {user.name} 的管理员权限", "info")
    return redirect(url_for("admin_users"))


@app.route("/protocols")
@login_required
def protocols():
    category = request.args.get("category", "")
    query = ProtocolVideo.query.order_by(ProtocolVideo.uploaded_at.desc())
    if category:
        query = query.filter_by(category=category)
    videos = query.all()
    categories = db.session.query(ProtocolVideo.category).distinct().all()
    categories = sorted(set([c[0] for c in categories if c[0]]))
    return render_template("protocols.html", videos=videos, categories=categories, current_cat=category)


@app.route("/literature/upload")
@login_required
def literature_upload_page():
    uploads = UploadedLiterature.query.filter_by(user_id=current_user.id).order_by(
        UploadedLiterature.uploaded_at.desc()
    ).all()
    return render_template("literature_upload.html", uploads=uploads)


@app.route("/literature/upload/submit", methods=["POST"])
@login_required
def literature_upload_submit():
    title = request.form.get("title", "").strip()
    doi = request.form.get("doi", "").strip()
    url = request.form.get("url", "").strip()
    keywords = request.form.get("keywords", "").strip()

    if not title and not doi and not url:
        flash("请至少填写标题、DOI 或 URL", "error")
        return redirect(url_for("literature_upload_page"))

    upload = UploadedLiterature(
        user_id=current_user.id,
        title=title,
        doi=doi,
        url=url,
        keywords=keywords,
        status="pending",
    )
    db.session.add(upload)
    db.session.flush()

    try:
        from literature_agent import enrich_literature
        info = enrich_literature(title=title, doi=doi, url=url)
        if info:
            upload.title = info.get("title", title)
            upload.authors = info.get("authors", "")
            upload.journal = info.get("journal", "")
            upload.year = info.get("year")
            upload.abstract = info.get("abstract", "")
            upload.citation_count = info.get("citation_count", 0)
            upload.status = "completed"
            existing = LiteratureItem.query.filter_by(doi=info.get("doi", doi)).first()
            if not existing and info.get("doi"):
                item = LiteratureItem(
                    title=info.get("title", title),
                    authors=info.get("authors", ""),
                    journal=info.get("journal", ""),
                    year=info.get("year"),
                    doi=info.get("doi", doi),
                    abstract=info.get("abstract", ""),
                    url=info.get("url", url),
                    topic="user-uploaded",
                    citation_count=info.get("citation_count", 0),
                )
                db.session.add(item)
            flash("Agent 已完成文献信息解析", "success")
        else:
            upload.status = "completed"
            flash("已取消订阅", "info")
    except Exception:
        upload.status = "completed"
        flash("已取消订阅", "info")
    db.session.commit()
    return redirect(url_for("literature_upload_page"))


@app.route("/rewards")
@login_required
def rewards():
    trees = AttendanceReward.query.filter_by(user_id=current_user.id).order_by(
        AttendanceReward.earned_at.desc()
    ).all()
    total_trees = AttendanceReward.query.filter_by(user_id=current_user.id).count()
    weekly_trees = AttendanceReward.query.filter_by(user_id=current_user.id, period="weekly").count()
    monthly_trees = AttendanceReward.query.filter_by(user_id=current_user.id, period="monthly").count()
    current_streak = _calc_streak(current_user.id)
    max_streak = _calc_max_streak(current_user.id)
    farm_tree_count = max(monthly_trees, max_streak // 28)
    farm_preview = bool(current_user.is_admin)
    farm_display_tree_count = max(3, min(12, farm_tree_count)) if farm_preview else farm_tree_count
    reward_milestones = [
        {
            "day": 7,
            "stage": "seed",
            "title": "周奖励种子",
            "subtitle": "连续学习 7 天",
            "unlocked": current_streak >= 7,
        },
        {
            "day": 14,
            "stage": "sprout",
            "title": "小树苗",
            "subtitle": "连续学习 14 天",
            "unlocked": current_streak >= 14,
        },
        {
            "day": 21,
            "stage": "young-tree",
            "title": "小树 + 新种子",
            "subtitle": "连续学习 21 天",
            "unlocked": current_streak >= 21,
        },
        {
            "day": 28,
            "stage": "big-tree",
            "title": "大树",
            "subtitle": "连续学习 28 天",
            "unlocked": current_streak >= 28,
        },
    ]
    return render_template("rewards.html",
        trees=trees, total_trees=total_trees,
        weekly_trees=weekly_trees, monthly_trees=monthly_trees,
        current_streak=current_streak, max_streak=max_streak,
        reward_milestones=reward_milestones,
        farm_tree_count=farm_tree_count,
        farm_display_tree_count=farm_display_tree_count,
        farm_preview=farm_preview)


def _calc_max_streak(user_id):
    all_dates = [c.date for c in DailyCheckin.query.filter_by(user_id=user_id).order_by(DailyCheckin.date.asc()).all()]
    if not all_dates:
        return 0
    max_s = 1
    cur_s = 1
    for i in range(1, len(all_dates)):
        if (all_dates[i] - all_dates[i-1]).days == 1:
            cur_s += 1
            max_s = max(max_s, cur_s)
        else:
            cur_s = 1
    return max_s


def _check_and_award_rewards():
    today = date.today()
    users = User.query.all()
    for user in users:
        week_num = today.isocalendar()[1]
        year = today.year
        last_monday = today - dt_module.timedelta(days=today.weekday() + 7)
        week_key = f"{last_monday.isocalendar()[0]}-W{last_monday.isocalendar()[1]:02d}"
        existing_weekly = AttendanceReward.query.filter_by(
            user_id=user.id, period="weekly", period_key=week_key
        ).first()
        if not existing_weekly:
            week_checkins = DailyCheckin.query.filter(
                DailyCheckin.user_id == user.id,
                DailyCheckin.date >= last_monday,
                DailyCheckin.date < last_monday + dt_module.timedelta(days=7),
            ).count()
            if week_checkins >= 7:
                reward = AttendanceReward(
                    user_id=user.id, period="weekly", period_key=week_key,
                    checkin_days=week_checkins, total_days=7, reward_type="tree",
                    reward_data=json.dumps({"emoji": "\U0001F331", "message": "连续打卡一周"}),
                )
                db.session.add(reward)

        month_key = f"{year}-{today.month:02d}"
        existing_monthly = AttendanceReward.query.filter_by(
            user_id=user.id, period="monthly", period_key=month_key
        ).first()
        if not existing_monthly:
            import calendar
            month_days = calendar.monthrange(year, today.month)[1]
            if today.day >= month_days - 2:
                month_checkins = DailyCheckin.query.filter(
                    DailyCheckin.user_id == user.id,
                    DailyCheckin.date >= date(year, today.month, 1),
                    DailyCheckin.date <= date(year, today.month, month_days),
                ).count()
                if month_checkins >= month_days:
                    reward = AttendanceReward(
                        user_id=user.id, period="monthly", period_key=month_key,
                        checkin_days=month_checkins, total_days=month_days, reward_type="tree",
                        reward_data=json.dumps({"emoji": "\U0001F333", "message": "完成本月连续学习"}),
                    )
                    db.session.add(reward)
        db.session.commit()



@app.route("/agent")
@login_required
def agent_dashboard():
    """Agent Skills Dashboard"""
    from models import AgentLog
    logs = AgentLog.query.filter_by(user_id=current_user.id).order_by(AgentLog.created_at.desc()).limit(10).all()
    return render_template("agent.html", logs=logs)


@app.route("/agent/literature-info", methods=["GET", "POST"])
@login_required
def agent_literature_info():
    """Skill 1: Literature info via OpenAlex"""
    result = None
    query = ""
    if request.method == "POST":
        query = request.form.get("query", "")
        qtype = request.form.get("query_type", "title")
        from agent_skills import skill_literature_info
        result, ok = skill_literature_info(db, current_user.id, query, qtype)
    return render_template("agent_literature.html", result=result, query=query)


@app.route("/agent/subscription", methods=["GET", "POST"])
@login_required
def agent_subscription():
    """Skill 2: Subscribe and fetch recent lit"""
    result = None
    keyword = ""
    if request.method == "POST":
        keyword = request.form.get("keyword", "")
        days = int(request.form.get("days", 7))
        from agent_skills import skill_literature_subscription
        result, ok = skill_literature_subscription(db, current_user.id, keyword, days)
    return render_template("agent_subscription.html", result=result, keyword=keyword)


@app.route("/agent/citation", methods=["GET", "POST"])
@login_required
def agent_citation():
    """Skill 3: Citation network"""
    result = None
    query = ""
    if request.method == "POST":
        query = request.form.get("query", "")
        qtype = request.form.get("query_type", "keyword")
        from agent_skills import skill_citation_network
        result, ok = skill_citation_network(db, current_user.id, query, qtype)
    planets = LiteraturePlanet.query.filter_by(user_id=current_user.id).all()
    return render_template("agent_citation.html", result=result, query=query, planets=planets)


@app.route("/agent/presentation", methods=["GET", "POST"])
@login_required
def agent_presentation():
    """Skill 4: AI-assisted presentation"""
    result = None
    from models import PresentationTemplate
    templates = PresentationTemplate.query.all()
    if request.method == "POST":
        action = request.form.get("action", "generate")
        paper_title = request.form.get("paper_title", "")
        paper_doi = request.form.get("paper_doi", "")
        template_id = request.form.get("template_id", "")

        if action == "generate":
            from agent_skills import skill_presentation_assist
            result, ok = skill_presentation_assist(db, current_user.id, paper_title, paper_doi, template_id)
        elif action == "analyze":
            student_paper_title = request.form.get("student_paper_title", "")
            student_paper_doi = request.form.get("student_paper_doi", "")
            ppt_content = request.form.get("ppt_content", "")
            from agent_skills import skill_presentation_assist
            res, ok = skill_presentation_assist(db, current_user.id, student_paper_title or paper_title, student_paper_doi or paper_doi, template_id)
            if res.get("found"):
                improvement_suggestions = [
                    "Add more visual aids (figures, diagrams) to illustrate key points.",
                    "Ensure each slide has a clear takeaway message.",
                    "Practice transitions between slides for better flow.",
                    "Include a summary slide with key conclusions.",
                    "Prepare backup slides for anticipated Q&A topics.",
                ]
                if ppt_content:
                    improvement_suggestions.insert(0, "Your presentation content was analyzed. Key topics detected: " + ppt_content[:100])
                analysis_result = dict(res)
                analysis_result["analysis"] = {
                    "improvement_suggestions": improvement_suggestions,
                    "ppt_content_preview": ppt_content[:200] if ppt_content else "",
                    "template_used": template_id,
                }
                result = analysis_result
            else:
                result = res
    return render_template("agent_presentation.html", result=result, templates=templates)


@app.route("/admin/presentation-templates", methods=["GET", "POST"])
@login_required
@admin_required
def admin_presentation_templates():
    """Manage presentation scoring templates"""
    from models import PresentationTemplate
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "")
        import json as _json
        criteria_list = []
        dims = request.form.getlist("dimension[]")
        weights = request.form.getlist("weight[]")
        standards = request.form.getlist("standard[]")
        for i in range(len(dims)):
            if dims[i].strip():
                criteria_list.append({"dimension": dims[i], "weight": weights[i] if i < len(weights) else "0%", "standard": standards[i] if i < len(standards) else ""})
        t = PresentationTemplate(title=title, description=description, criteria=_json.dumps(criteria_list, ensure_ascii=False), uploaded_by=current_user.id)
        db.session.add(t)
        db.session.commit()
        flash("Presentation template created!", "success")
        return redirect(url_for("admin_presentation_templates"))
    templates = PresentationTemplate.query.order_by(PresentationTemplate.created_at.desc()).all()
    return render_template("admin_presentation_templates.html", templates=templates)


@app.route("/admin/presentation-templates/delete/<int:tid>")
@login_required
@admin_required
def admin_delete_presentation_template(tid):
    t = db.session.get(PresentationTemplate, tid)
    if t:
        db.session.delete(t)
        db.session.commit()
        flash("Template deleted", "info")
    return redirect(url_for("admin_presentation_templates"))



@app.route("/agent/methods", methods=["GET", "POST"])
@login_required
def agent_methods():
    """Skill 5: Experimental method summary"""
    result = None
    if request.method == "POST":
        query = request.form.get("query", "")
        qtype = request.form.get("query_type", "doi")
        save_name = request.form.get("save_name", "")
        from agent_skills import skill_method_summary
        result, ok = skill_method_summary(db, current_user.id, query, qtype, save_name)
    from models import ProtocolCollection
    protocols = ProtocolCollection.query.filter_by(user_id=current_user.id).all()
    planets = LiteraturePlanet.query.filter_by(user_id=current_user.id).all()
    return render_template("agent_methods.html", result=result, protocols=protocols, planets=planets)


@app.route("/study/quiz/<int:kp_id>")
@login_required
def study_quiz(kp_id):
    """Skill 6: Quiz for a knowledge point"""
    from models import Quiz, QuizAttempt, DailyCheckin, KnowledgePoint
    from datetime import date
    import json
    kp = db.session.get(KnowledgePoint, kp_id)
    quizzes = Quiz.query.filter_by(knowledge_point_id=kp_id).all()
    today = date.today()
    existing = DailyCheckin.query.filter_by(user_id=current_user.id, date=today).first()
    return render_template("study_quiz.html", kp=kp, quizzes=quizzes,
                          existing=existing, today=today, json=json)


@app.route("/study/quiz/answer", methods=["POST"])
@login_required
def study_quiz_answer():
    """Answer a quiz question"""
    from models import Quiz, QuizAttempt, DailyCheckin, KnowledgePoint
    from datetime import date
    import json
    quiz_id = request.form.get("quiz_id", type=int)
    answer = request.form.get("answer", "")
    difficulty = request.form.get("difficulty", "beginner")
    quiz = db.session.get(Quiz, quiz_id)
    if not quiz:
        flash("Quiz not found", "error")
        return redirect(url_for("study"))
    correct = answer == quiz.correct_answer
    attempt = QuizAttempt(
        user_id=current_user.id, quiz_id=quiz_id,
        answer=answer, correct=correct
    )
    db.session.add(attempt)
    db.session.flush()
    today = date.today()
    existing = DailyCheckin.query.filter_by(user_id=current_user.id, date=today).first()
    if correct and not existing:
        score = {"beginner": 10, "intermediate": 20, "advanced": 30}.get(difficulty, 10)
        checkin = DailyCheckin(
            user_id=current_user.id, knowledge_point_id=quiz.knowledge_point_id,
            difficulty=difficulty, score=score, date=today,
        )
        db.session.add(checkin)
        db.session.flush()
        attempt.checkin_id = checkin.id
    db.session.commit()
    if correct:
        flash("Correct! Check-in recorded!", "success")
    else:
        flash(f"Incorrect. The correct answer is {quiz.correct_answer}", "info")
    return redirect(url_for("study_quiz", kp_id=quiz.knowledge_point_id))


@app.route("/admin/quizzes")
@login_required
def admin_quizzes():
    from models import Quiz, KnowledgePoint
    kps = KnowledgePoint.query.order_by(KnowledgePoint.created_at.desc()).all()
    quizzes = Quiz.query.order_by(Quiz.created_at.desc()).all()
    import json
    return render_template("admin_quizzes.html", kps=kps, quizzes=quizzes, json=json)


@app.route("/admin/quizzes/add", methods=["POST"])
@login_required
def admin_add_quiz():
    from models import Quiz
    import json
    kp_id = request.form.get("kp_id", type=int)
    question = request.form.get("question", "")
    correct = request.form.get("correct_answer", "A")
    options = []
    for letter in ["A", "B", "C", "D"]:
        text = request.form.get(f"option_{letter}", "")
        if text:
            options.append({"label": letter, "text": text})
    if not question or len(options) < 2:
        flash("Question and at least 2 options required", "error")
        return redirect(url_for("admin_quizzes"))
    quiz = Quiz(
        knowledge_point_id=kp_id, question=question,
        options=json.dumps(options, ensure_ascii=False),
        correct_answer=correct
    )
    db.session.add(quiz)
    db.session.commit()
    flash("Quiz added!", "success")
    return redirect(url_for("admin_quizzes"))




@app.route("/api/agent-chat", methods=["POST"])
@login_required
def agent_chat():
    data = request.get_json() or {}
    question = data.get("question", "")
    if not question:
        return jsonify({"answer": "Please ask a question"})
    key_obj = ApiKey.query.filter_by(is_active=True).first()
    if not key_obj:
        return jsonify({"answer": "No LLM key configured. Add in API Keys."})
    provider = key_obj.provider or "openai"
    answer = call_llm(key_obj.encrypted_key, provider, question)
    # Save chat history
    try:
        ch_user = ChatHistory(user_id=current_user.id, role="user", message=question)
        ch_bot = ChatHistory(user_id=current_user.id, role="assistant", message=answer)
        db.session.add(ch_user)
        db.session.add(ch_bot)
        db.session.commit()
    except:
        pass
    return jsonify({"answer": "[" + provider + "] " + answer if answer else answer, "provider": provider})


@app.route("/api/chat/history", methods=["GET"])
@login_required
def chat_history():
    msgs = ChatHistory.query.filter_by(user_id=current_user.id).order_by(ChatHistory.created_at.asc()).limit(50).all()
    return jsonify([{"role": m.role, "message": m.message, "id": m.id} for m in msgs])


@app.route("/api/chat/save", methods=["POST"])
@login_required
def chat_save():
    data = request.get_json() or {}
    role = data.get("role", "user")
    message = data.get("message", "").strip()
    if message:
        ch = ChatHistory(user_id=current_user.id, role=role, message=message)
        db.session.add(ch)
        db.session.commit()
        return jsonify({"ok": True, "id": ch.id})
    return jsonify({"ok": False})


@app.route("/api/chat/clear", methods=["POST"])
@login_required
def chat_clear():
    ChatHistory.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/literature/bookmark", methods=["POST"])
@login_required
def bookmark_literature():
    data = request.get_json() or {}
    title = data.get("title", "")
    if not title:
        return jsonify({"ok": False, "error": "Title required"})
    cat_id = data.get("category_id")
    existing = BookmarkedLiterature.query.filter_by(user_id=current_user.id, title=title).first()
    if existing:
        return jsonify({"ok": False, "error": "Already bookmarked"})
    bm = BookmarkedLiterature(
        user_id=current_user.id, category_id=cat_id,
        title=title, authors=data.get("authors", ""),
        journal=data.get("journal", ""), year=data.get("year"),
        doi=data.get("doi", ""), url=data.get("url", ""),
        abstract=data.get("abstract", ""), citation_count=data.get("citation_count", 0),
        source=data.get("source", ""),
    )
    db.session.add(bm)
    db.session.commit()
    return jsonify({"ok": True, "id": bm.id})


@app.route("/api/literature/bookmarks")
@login_required
def list_bookmarks():
    cat_id = request.args.get("category_id", type=int)
    q = BookmarkedLiterature.query.filter_by(user_id=current_user.id)
    if cat_id:
        q = q.filter_by(category_id=cat_id)
    items = q.order_by(BookmarkedLiterature.added_at.desc()).all()
    return jsonify([{"id": b.id, "title": b.title, "authors": b.authors, "journal": b.journal,
        "year": b.year, "doi": b.doi, "source": b.source, "citation_count": b.citation_count,
        "category_id": b.category_id, "notes": b.notes, "added_at": b.added_at.isoformat() if b.added_at else ""}
        for b in items])


@app.route("/api/literature/bookmark/delete/<int:bid>")
@login_required
def delete_bookmark(bid):
    b = db.session.get(BookmarkedLiterature, bid)
    if b and b.user_id == current_user.id:
        db.session.delete(b)
        db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/literature/categories", methods=["GET", "POST"])
@login_required
def literature_categories():
    if request.method == "POST":
        data = request.get_json() or {}
        name = data.get("name", "").strip()
        parent_id = data.get("parent_id")
        if name:
            existing = LiteratureCategory.query.filter_by(user_id=current_user.id, name=name).first()
            if not existing:
                cat = LiteratureCategory(user_id=current_user.id, name=name, parent_id=parent_id)
                db.session.add(cat)
                db.session.commit()
                return jsonify({"ok": True, "id": cat.id})
        return jsonify({"ok": False})
    cats = LiteratureCategory.query.filter_by(user_id=current_user.id).all()
    return jsonify([{"id": c.id, "name": c.name, "parent_id": c.parent_id, "count": BookmarkedLiterature.query.filter_by(category_id=c.id).count()} for c in cats])


@app.route("/api/literature/category/delete/<int:cid>")
@login_required
def delete_category(cid):
    c = db.session.get(LiteratureCategory, cid)
    if c and c.user_id == current_user.id:
        BookmarkedLiterature.query.filter_by(category_id=cid).update({"category_id": None})
        db.session.delete(c)
        db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/study/plan", methods=["GET", "POST"])
@login_required
def study_plan():
    if request.method == "POST":
        data = request.get_json() or {}
        topic = data.get("topic", "general")
        daily_count = data.get("daily_count", 3)
        difficulty = data.get("difficulty", "beginner")
        plan = UserStudyPlan.query.filter_by(user_id=current_user.id).first()
        if plan:
            plan.topic = topic
            plan.daily_count = daily_count
            plan.difficulty = difficulty
        else:
            plan = UserStudyPlan(user_id=current_user.id, topic=topic, daily_count=daily_count, difficulty=difficulty)
            db.session.add(plan)
        db.session.commit()
        return jsonify({"ok": True})
    plan = UserStudyPlan.query.filter_by(user_id=current_user.id).first()
    if plan:
        return jsonify({"topic": plan.topic, "daily_count": plan.daily_count, "difficulty": plan.difficulty})
    return jsonify({"topic": "general", "daily_count": 3, "difficulty": "beginner"})


@app.route("/api/protocol/flowchart", methods=["POST"])
@login_required
def protocol_flowchart():
    data = request.get_json() or {}
    steps_text = data.get("steps", "")
    if not steps_text:
        return jsonify({"ok": False})
    if steps_text:
        steps = [s.strip() for s in steps_text.split("\n") if s.strip()]
    else:
        steps = []
    return jsonify({"ok": True, "steps": steps})


@app.route("/literature-collection")
@login_required
def literature_collection_view():
    planets = LiteraturePlanet.query.filter_by(user_id=current_user.id).all()
    cats = LiteratureCategory.query.filter_by(user_id=current_user.id).all()
    bookmarks = BookmarkedLiterature.query.filter_by(user_id=current_user.id).order_by(BookmarkedLiterature.added_at.desc()).all()
    return render_template("literature_collection.html", planets=planets, categories=cats, bookmarks=bookmarks)


@app.route("/planets")
@login_required
def planets():
    planets_data = LiteraturePlanet.query.filter_by(user_id=current_user.id).order_by(LiteraturePlanet.created_at.desc()).all()
    all_papers = PlanetPaper.query.join(LiteraturePlanet).filter(LiteraturePlanet.user_id == current_user.id).all()
    from literature_agent import SAMPLE_LITERATURE
    paper_list = []
    for pp in all_papers:
        planet = db.session.get(LiteraturePlanet, pp.planet_id)
        pcolor = planet.color if planet else '#3b82f6'
        paper_list.append({'pid': pp.id, 'title': pp.title, 'label': (pp.title[:20] + '..') if len(pp.title)>20 else pp.title,
            'url': url_for('paper_detail', ppid=pp.id),
            'authors': pp.authors, 'year': pp.year, 'planet': planet.name if planet else '',
            'color': pcolor})
    sample_list = []
    for topic, papers in SAMPLE_LITERATURE.items():
        for sp in papers:
            sample_list.append({'title': sp['title'], 'label': (sp['title'][:20]+'..') if len(sp['title'])>20 else sp['title'],
                'url': sp['url'], 'color': '#3b82f6', 'planet': 'Sample'})
    center_color = planets_data[0].color if planets_data else '#F5D76E'
    center_name = planets_data[0].name if planets_data else "Literature Universe"
    return render_template("planets.html", planets=planets_data, papers=paper_list, samples=sample_list, planet_color=center_color, planet_name=center_name)


@app.route("/planets/create", methods=["GET", "POST"])
@login_required
def planet_create():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        topic = request.form.get("topic", "").strip()
        desc = request.form.get("description", "")
        color = request.form.get("color", "#3b82f6")
        if not name:
            flash("请输入星球名称", "error")
            return redirect(url_for("planets"))
        existing = LiteraturePlanet.query.filter_by(user_id=current_user.id, name=name).first()
        if existing:
            flash("该星球名称已存在", "error")
            return redirect(url_for("planets"))
        planet = LiteraturePlanet(user_id=current_user.id, name=name, topic=topic, description=desc, color=color)
        db.session.add(planet)
        db.session.commit()
        flash(f'星球 "{name}" 创建成功！', 'success')
    return redirect(url_for("planets"))


@app.route("/planets/<int:pid>")
@login_required
def planet_detail(pid):
    planet = db.session.get(LiteraturePlanet, pid)
    if not planet or planet.user_id != current_user.id:
        abort(404)
    sort = request.args.get("sort", "date_desc")
    papers = PlanetPaper.query.filter_by(planet_id=pid)
    if sort == "date_asc": papers = papers.order_by(PlanetPaper.year.asc(), PlanetPaper.added_at.asc())
    elif sort == "date_desc": papers = papers.order_by(PlanetPaper.year.desc(), PlanetPaper.added_at.desc())
    elif sort == "author": papers = papers.order_by(PlanetPaper.authors.asc())
    elif sort == "journal": papers = papers.order_by(PlanetPaper.journal.asc())
    else: papers = papers.order_by(PlanetPaper.added_at.desc())
    return render_template("planet_detail.html", planet=planet, papers=papers.all(), sort=sort)


@app.route("/planets/<int:pid>/add", methods=["POST"])
@login_required
def planet_add_paper(pid):
    planet = db.session.get(LiteraturePlanet, pid)
    if not planet or planet.user_id != current_user.id:
        abort(404)
    title = request.form.get("title", "").strip()
    authors = request.form.get("authors", "").strip()
    journal = request.form.get("journal", "").strip()
    year = request.form.get("year", type=int)
    doi = request.form.get("doi", "").strip()
    url = request.form.get("url", "").strip()
    abstract = request.form.get("abstract", "").strip()
    if not title:
        flash("请输入文献标题", "error")
        return redirect(url_for("planet_detail", pid=pid))
    paper = PlanetPaper(planet_id=pid, title=title, authors=authors, journal=journal,
                       year=year, doi=doi, url=url, abstract=abstract)
    db.session.add(paper)
    db.session.commit()
    flash("文献已添加到星球！", "success")
    return redirect(url_for("planet_detail", pid=pid))


@app.route("/planets/<int:pid>/delete-paper/<int:ppid>")
@login_required
def planet_delete_paper(pid, ppid):
    planet = db.session.get(LiteraturePlanet, pid)
    if not planet or planet.user_id != current_user.id:
        abort(404)
    paper = db.session.get(PlanetPaper, ppid)
    if paper and paper.planet_id == pid:
        db.session.delete(paper)
        db.session.commit()
        flash("文献已移除", "info")
    return redirect(url_for("planet_detail", pid=pid))


@app.route("/api/planet-data")
@login_required
def api_planet_data():
    planets_data = LiteraturePlanet.query.filter_by(user_id=current_user.id).all()
    data = []
    for p in planets_data:
        count = PlanetPaper.query.filter_by(planet_id=p.id).count()
        data.append({"id": p.id, "name": p.name, "topic": p.topic, "color": p.color,
                     "count": count, "url": url_for("planet_detail", pid=p.id)})
    return jsonify(data)


@app.route("/admin/api-keys", methods=["GET", "POST"])
@login_required
def admin_api_keys():
    if request.method == "POST":
        provider = request.form.get("provider", "openai")
        key_name = request.form.get("key_name", "default")
        api_key = request.form.get("api_key", "").strip()
        if api_key:
            key = ApiKey(user_id=current_user.id, provider=provider, key_name=key_name, encrypted_key=api_key)
            db.session.add(key)
            db.session.commit()
            flash("API Key 已保存", "success")
        return redirect(url_for("admin_api_keys"))
    keys = ApiKey.query.order_by(ApiKey.created_at.desc()).all()
    return render_template("admin_api_keys.html", keys=keys)


@app.route("/admin/api-keys/delete/<int:k_id>")
@login_required
def admin_delete_api_key(k_id):
    key = db.session.get(ApiKey, k_id)
    if key:
        db.session.delete(key)
        db.session.commit()
        flash("API Key 已删除", "info")
    return redirect(url_for("admin_api_keys"))


@app.route("/literature/agent", methods=["GET", "POST"])
@login_required
def agent_search():
    """Literature search powered by real LLM if API key is configured."""
    result_text = ""
    query = ""
    if request.method == "POST":
        query = request.form.get("query", "")
        provider = request.form.get("provider", "openai")
        key_entry = ApiKey.query.filter_by(is_active=True, provider=provider).first()
        if key_entry and key_entry.encrypted_key:
            result_text = call_llm(key_entry.encrypted_key, provider, query)
        else:
            result_text = "未配置 API Key，请管理员在后台添加。"
    return render_template("agent_search.html", result=result_text, query=query)


def call_llm(api_key, provider, prompt, system="You are an EM expert."):
    """Call LLM API to process the prompt."""
    import requests as req, os as _os
    _proxies = {}
    _hp = _os.environ.get("HTTP_PROXY", "") or _os.environ.get("http_proxy", "")
    _hs = _os.environ.get("HTTPS_PROXY", "") or _os.environ.get("https_proxy", "")
    if _hp: _proxies["http"] = _hp
    if _hs: _proxies["https"] = _hs
    try:
        if provider == "deepseek":
            url = "https://api.deepseek.com/v1/chat/completions"
            model = "deepseek-chat"
        else:
            url = "https://api.openai.com/v1/chat/completions"
            model = "gpt-3.5-turbo"
        resp = req.post(url, headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                  "max_tokens": 600}, timeout=60, proxies=_proxies if _proxies else None)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        else:
            return "API Error (" + str(resp.status_code) + "): " + resp.text[:300]
    except Exception as e:
        return "Request Error: " + str(e)



@app.route("/literature-hub")
@login_required
def literature_hub():
    planets_data = LiteraturePlanet.query.filter_by(user_id=current_user.id).all()
    return render_template("literature_hub.html", planets=planets_data)


@app.route("/knowledge-forest")
@login_required
def knowledge_forest():
    from models import DailyCheckin, AttendanceReward, KnowledgePoint
    from datetime import date
    today = date.today()
    today_checkin = DailyCheckin.query.filter_by(user_id=current_user.id, date=today).first()
    trees = AttendanceReward.query.filter_by(user_id=current_user.id).count()
    streak_data = {"trees": trees, "streak": _calc_streak(current_user.id)}
    return render_template("knowledge_forest.html", today_checkin=today_checkin, streak_data=streak_data)


@app.route("/experiments")
@login_required
def experiments_page():
    from models import ProtocolCollection, ProtocolVideo
    videos = ProtocolVideo.query.order_by(ProtocolVideo.uploaded_at.desc()).all()
    protocols = ProtocolCollection.query.filter_by(user_id=current_user.id).all()
    return render_template("experiment_hub.html", videos=videos, protocols=protocols)



@app.route("/literature/weekly", methods=["GET", "POST"])
@login_required
def literature_weekly():
    result = None
    keyword = ''
    if request.method == "POST":
        keyword = request.form.get("keyword", "")
        days = int(request.form.get("days", 7))
        from openalex_client import recent_works_by_topic, extract_work_info
        works = recent_works_by_topic(keyword, days=days, per_page=15)
        results = []
        for w in works:
            results.append(extract_work_info(w))
        result = {"keyword": keyword, "days": days, "results": results}
    planets = LiteraturePlanet.query.filter_by(user_id=current_user.id).all()
    return render_template("literature_weekly.html", result=result, keyword=keyword, planets=planets)


@app.route("/literature/collection")
@login_required
def literature_collection():
    planets = LiteraturePlanet.query.filter_by(user_id=current_user.id).all()
    all_papers = PlanetPaper.query.join(LiteraturePlanet).filter(LiteraturePlanet.user_id == current_user.id).order_by(PlanetPaper.added_at.desc()).all()
    grouped = {}
    for pp in all_papers:
        key = pp.planet.name
        if key not in grouped: grouped[key] = []
        grouped[key].append(pp)
    return render_template("literature_collection.html", planets=planets, grouped=grouped)


@app.route("/admin/knowledge/llm-generate", methods=["POST"])
@login_required
def admin_llm_generate():
    topic = request.form.get("topic", "").strip()
    if not topic:
        flash("请输入主题", "error")
        return redirect(url_for("admin_knowledge"))
    key_obj = ApiKey.query.filter_by(is_active=True).first()
    if not key_obj:
        flash("请先在 API Keys 配置 LLM Key", "error")
        return redirect(url_for("admin_api_keys"))
    provider = key_obj.provider or "openai"
    prompt = 'Generate 3 EM knowledge points about ' + topic + ' in JSON: [{"title":"...","content":"...","difficulty":"beginner/intermediate/advanced"}]'
    text = call_llm(key_obj.encrypted_key, provider, prompt)
    if not text:
        flash("API Error: No response", "error")
        return redirect(url_for("admin_knowledge"))
    try:
        import json
        points = json.loads(text.strip())
        count = 0
        for pt in points:
            kp = KnowledgePoint(title=pt.get("title",""), content=pt.get("content",""),
                difficulty=pt.get("difficulty","intermediate"), category=topic, source="llm")
            db.session.add(kp)
            count += 1
        db.session.commit()
        flash(f"LLM generated {count} knowledge points!", "success")
    except Exception as e:
        flash(f"Parse Error: {str(e)}", "error")
    return redirect(url_for("admin_knowledge"))



@app.route("/paper/<int:ppid>")
@login_required
def paper_detail(ppid):
    paper = db.session.get(PlanetPaper, ppid)
    if not paper:
        flash("文献未找到", "error")
        return redirect(url_for("planets"))
    planet = db.session.get(LiteraturePlanet, paper.planet_id)
    return render_template("paper_detail.html", paper=paper, planet=planet)



@app.route("/literature/upload-dois", methods=["POST"])
@login_required
def upload_dois():
    dois_text = request.form.get("dois", "").strip()
    keyword = request.form.get("keyword", "").strip()
    if not keyword:
        flash("请输入关键词", "error")
        return redirect(url_for("planets"))
    if not dois_text:
        flash("请输入DOI", "error")
        return redirect(url_for("planets"))
    planet = LiteraturePlanet.query.filter_by(user_id=current_user.id, name=keyword).first()
    if not planet:
        planet = LiteraturePlanet(user_id=current_user.id, name=keyword, topic=keyword)
        db.session.add(planet)
        db.session.flush()
    count = 0
    for line in dois_text.split("\n"):
        doi = line.strip()
        if not doi: continue
        from openalex_client import get_work_by_doi, extract_work_info
        try:
            work = get_work_by_doi(doi)
            if work:
                info = extract_work_info(work)
                paper = PlanetPaper(planet_id=planet.id, title=info.get("title",""),
                    authors=info.get("first_author",""), journal=info.get("journal",""),
                    year=int(info.get("publication_date","")[:4]) if info.get("publication_date") else None,
                    doi=doi, url=info.get("doi",""))
                db.session.add(paper)
                count += 1
        except:
            pass
    db.session.commit()
    flash(f"成功添加 {count} 篇文献到「{keyword}」", "success")
    return redirect(url_for("planets"))


@app.route("/profile")
@login_required
def profile():
    total_checkins = DailyCheckin.query.filter_by(user_id=current_user.id).count()
    total_score = db.session.query(db.func.sum(DailyCheckin.score)).filter_by(
        user_id=current_user.id
    ).scalar() or 0
    streak = _calc_streak(current_user.id)
    subs_count = LiteratureSubscription.query.filter_by(
        user_id=current_user.id, active=True
    ).count()
    return render_template(
        "profile.html",
        total_checkins=total_checkins,
        total_score=total_score,
        streak=streak,
        subs_count=subs_count,
    )


@app.after_request
def no_cache(response):
    if 'text/html' in response.content_type:
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response


@app.route('/lang/<lang_code>')
def set_lang(lang_code):
    if lang_code in ('zh', 'en'):
        flask_session['lang'] = lang_code
    next_page = request.args.get('next', url_for('index'))
    return redirect(next_page)


@app.context_processor
def inject_globals():
    lang = flask_session.get('lang', 'zh')
    return dict(lang=lang, _=_)


def _(zh_text, en_text=''):
    lang = flask_session.get('lang', 'zh')
    if lang == 'en' and en_text:
        return en_text
    return zh_text


@app.template_filter('fromjson')
def fromjson_filter(value):
    import json
    try: return json.loads(value)
    except: return []


def init_db():
    with app.app_context():
        db.create_all()
        _ensure_schema()
        # Seed knowledge points if empty
        if KnowledgePoint.query.count() == 0:
            from knowledge_points import KNOWLEDGE_POINTS
            for kp in KNOWLEDGE_POINTS:
                point = KnowledgePoint(
                    title=kp["title"],
                    content=kp["content"],
                    difficulty=kp["difficulty"],
                    category=kp["category"],
                )
                db.session.add(point)
            db.session.commit()
        # Create default admin if none exists
        if User.query.filter_by(is_admin=True).count() == 0:
            admin = User(
                student_id="admin",
                name="管理员",
                email="admin@emcourse.local",
                is_admin=True,
            )
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()
            print("Default admin created: admin / admin123")


def _ensure_schema():
    if db.engine.dialect.name != "sqlite":
        return
    with db.engine.begin() as conn:
        cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(users)").fetchall()]
        if "phone" not in cols:
            conn.exec_driver_sql("ALTER TABLE users ADD COLUMN phone VARCHAR(30)")
            conn.exec_driver_sql("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_phone ON users (phone)")


scheduler = BackgroundScheduler()


def setup_scheduler(app):
    from literature_agent import run_weekly_fetch
    scheduler.add_job(
        func=run_weekly_fetch,
        trigger="cron",
        day_of_week="mon",
        hour=WEEKLY_LITERATURE_HOUR,
        minute=WEEKLY_LITERATURE_MINUTE,
        id="weekly_literature",
        replace_existing=True,
    )
    # Daily reward check at midnight
    scheduler.add_job(
        func=_check_and_award_rewards,
        trigger="cron",
        hour=0,
        minute=5,
        id="daily_rewards",
        replace_existing=True,
    )
    scheduler.start()


if __name__ == "__main__":
    init_db()
    setup_scheduler(app)
    print("=" * 50)
    print(f"  {PLATFORM_NAME}")
    print("  http://127.0.0.1:5001")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5001, debug=True)

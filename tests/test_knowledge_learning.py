import os
import tempfile
import unittest

from flask import Flask, jsonify
from flask_login import LoginManager, login_required

from knowledge_study_v2 import build_custom_study_context, knowledge_study_bp
from learning_models import DailyLearningQueueEntry, DailyLearningSession
from models import (
    DailyCheckin,
    KnowledgePoint,
    User,
    UserKnowledgeItem,
    UserKnowledgeLibrary,
    db,
)


class KnowledgeLearningFlowTests(unittest.TestCase):
    def setUp(self):
        handle, self.database_path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        self.app = Flask(__name__)
        self.app.config.update(
            SECRET_KEY="test-secret",
            SQLALCHEMY_DATABASE_URI=f"sqlite:///{self.database_path}",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TESTING=True,
        )
        db.init_app(self.app)
        login_manager = LoginManager(self.app)

        @login_manager.user_loader
        def load_user(user_id):
            return db.session.get(User, int(user_id))

        @self.app.route("/study")
        @login_required
        def study():
            context = build_custom_study_context({
                "slug": "electron-microscopy",
                "name": "冷冻电子显微学",
            })
            return jsonify({
                "session_id": context["session"].id,
                "library_id": context["session"].library_id,
                "target": context["session"].base_target,
            })

        self.app.register_blueprint(knowledge_study_bp)
        with self.app.app_context():
            db.create_all()
            user = User(student_id="student", name="Test", email="test@example.com")
            user.set_password("password")
            db.session.add(user)
            db.session.add_all([
                KnowledgePoint(title="课程知识一", content="课程标准内容一。", difficulty="beginner", category="course"),
                KnowledgePoint(title="课程知识二", content="课程标准内容二。", difficulty="advanced", category="course"),
            ])
            db.session.flush()
            library = UserKnowledgeLibrary(
                user_id=user.id,
                name="我的测试知识库",
                daily_new_count=2,
                study_mode="mixed",
                difficulty_filter="all",
                is_active=True,
            )
            db.session.add(library)
            db.session.flush()
            db.session.add_all([
                UserKnowledgeItem(
                    library_id=library.id,
                    title="基础题",
                    content="冷冻电镜通过低温保存样品结构。",
                    difficulty="beginner",
                    position=1,
                ),
                UserKnowledgeItem(
                    library_id=library.id,
                    title="中级题",
                    content="CTF 描述电子显微镜的对比度传递特性。",
                    difficulty="intermediate",
                    position=2,
                ),
                UserKnowledgeItem(
                    library_id=library.id,
                    title="进阶题",
                    content="贝叶斯精修利用概率模型估计三维结构参数。",
                    difficulty="advanced",
                    position=3,
                ),
            ])
            db.session.commit()
            self.user_id = user.id
            self.library_id = library.id
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.user_id)
            session["_fresh"] = True

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        os.remove(self.database_path)

    def _current_entry_id(self):
        with self.app.app_context():
            entry = DailyLearningQueueEntry.query.filter_by(state="pending").order_by(
                DailyLearningQueueEntry.queue_order.asc()
            ).first()
            return entry.id

    def test_selected_library_answer_gate_checkin_and_advanced_learning(self):
        response = self.client.get("/study")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["library_id"], self.library_id)
        self.assertEqual(payload["target"], 2)

        session_id = payload["session_id"]
        self.assertEqual(self.client.post("/api/study/session/start", json={"session_id": session_id}).status_code, 200)

        for submitted_answer in ("低温保存样品结构", "CTF 对比度传递"):
            entry_id = self._current_entry_id()
            blocked = self.client.post("/api/study/review", json={"entry_id": entry_id, "rating": "good"})
            self.assertEqual(blocked.status_code, 409)
            answer = self.client.post("/api/study/answer", json={"entry_id": entry_id, "answer": submitted_answer})
            self.assertEqual(answer.status_code, 200)
            self.assertIn("score", answer.get_json())
            review = self.client.post("/api/study/review", json={"entry_id": entry_id, "rating": "good"})
            self.assertEqual(review.status_code, 200)

        with self.app.app_context():
            session = db.session.get(DailyLearningSession, session_id)
            self.assertEqual(session.status, "completed")
            self.assertEqual(DailyCheckin.query.filter_by(user_id=self.user_id).count(), 1)

        advanced = self.client.post(
            "/api/study/continue",
            json={"session_id": session_id, "mode": "advanced", "count": 5},
        )
        self.assertEqual(advanced.status_code, 200)
        self.assertEqual(advanced.get_json()["added"], 1)
        with self.app.app_context():
            entry = DailyLearningQueueEntry.query.filter_by(state="pending").first()
            self.assertEqual(entry.task.item.difficulty, "advanced")

    def test_plan_settings_rebuild_an_unstarted_daily_session(self):
        first = self.client.get("/study").get_json()
        self.assertEqual(first["target"], 2)
        response = self.client.post(
            f"/study/library/{self.library_id}/settings",
            data={
                "daily_count": "1",
                "study_mode": "advanced",
                "difficulty_filter": "all",
                "content_filter": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            session = DailyLearningSession.query.one()
            self.assertEqual(session.requested_target, 1)
            self.assertEqual(session.base_target, 1)
            self.assertEqual(session.study_mode, "advanced")
            entry = DailyLearningQueueEntry.query.one()
            self.assertEqual(entry.task.item.difficulty, "advanced")


if __name__ == "__main__":
    unittest.main()

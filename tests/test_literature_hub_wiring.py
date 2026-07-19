import unittest
from pathlib import Path
from unittest.mock import patch

from flask_login import login_user

from app import app, nebula, nebula_data
from models import User


ROOT = Path(__file__).resolve().parents[1]


class LiteratureHubWiringTests(unittest.TestCase):
    def test_generate_button_is_wired_to_openalex_api(self):
        script = (ROOT / "static" / "js" / "literature_graph.js").read_text(encoding="utf-8")
        template = (ROOT / "templates" / "literature_hub.html").read_text(encoding="utf-8")

        self.assertIn("/api/nebula-data?q=", script)
        self.assertIn("searchOpenAlex(query)", script)
        self.assertIn("setSearchLoading(false)", script)
        self.assertIn('data-idle-text="生成星云"', template)
        self.assertIn('<option value="author">作者姓名</option>', template)
        self.assertIn('<option value="title">论文标题</option>', template)
        self.assertIn('<option value="journal">期刊 / 会议</option>', template)
        self.assertIn('data-example-query="quantum computing"', template)
        self.assertIn('<option value="45">45 篇 · 快速</option>', template)
        self.assertIn('<option value="100" selected>100 篇 · 推荐</option>', template)
        self.assertIn('<option value="200">200 篇 · 大型图谱</option>', template)
        self.assertIn("&limit=", script)

    def test_literature_pages_are_merged_into_force_graph_workspace(self):
        script = (ROOT / "static" / "js" / "literature_graph.js").read_text(encoding="utf-8")
        template = (ROOT / "templates" / "literature_hub.html").read_text(encoding="utf-8")

        self.assertIn("vis-network@9.1.6", template)
        self.assertIn("unified-nebula-layout", template)
        self.assertIn("data-node-detail", template)
        self.assertIn("data-hub-list", template)
        self.assertNotIn("进入动态星云", template)
        self.assertIn("new vis.Network", script)
        self.assertIn("showNodeDetail", script)
        self.assertIn("openAlexUrl", script)

        user = User(id=998, student_id="merged-user", name="Merged", email="merged@example.com")
        with app.test_request_context("/nebula"):
            login_user(user)
            response = nebula()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/literature-hub"))

    @patch("literature_agent.sync_citation_network")
    def test_nebula_api_returns_synced_openalex_graph(self, sync_network):
        sync_network.return_value = (
            {"nodes": [{"id": "W1", "title": "Test paper"}], "edges": [], "source": "OpenAlex"},
            {"created_nodes": 1, "created_edges": 0},
        )
        user = User(id=999, student_id="test-user", name="Test", email="test@example.com")

        with app.test_request_context("/api/nebula-data?q=cryo-EM&type=keyword&limit=100"):
            login_user(user)
            response = nebula_data()
            payload = response.get_json()

        self.assertEqual(payload["source"], "OpenAlex")
        self.assertEqual(payload["query"], "cryo-EM")
        self.assertEqual(payload["limit"], 100)
        self.assertEqual(payload["sync"]["created_nodes"], 1)
        sync_network.assert_called_once_with("cryo-EM", query_type="keyword", topic="cryo-EM", max_nodes=100)

    def test_nebula_api_rejects_unsupported_graph_size(self):
        user = User(id=997, student_id="limit-user", name="Limit", email="limit@example.com")
        with app.test_request_context("/api/nebula-data?q=physics&type=keyword&limit=99"):
            login_user(user)
            response, status = nebula_data()

        self.assertEqual(status, 400)
        self.assertIn("45、100 或 200", response.get_json()["error"])


if __name__ == "__main__":
    unittest.main()

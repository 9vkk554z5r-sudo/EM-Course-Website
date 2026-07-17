import unittest
from unittest.mock import Mock, patch

from llm_client import LLMConfig, call_llm


class LLMClientTests(unittest.TestCase):
    @patch("llm_client.requests.post")
    def test_chat_completions_response_is_normalized(self, post):
        response = Mock(ok=True)
        response.json.return_value = {"choices": [{"message": {"content": "connected"}}]}
        post.return_value = response
        config = LLMConfig("secret", "https://example.test/v1/chat/completions", "model-x")

        self.assertEqual(call_llm(config, "hello"), "connected")
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "model-x")
        self.assertEqual(payload["messages"][-1]["content"], "hello")

    @patch("llm_client.requests.post")
    def test_start_gateway_fallback(self, post):
        invalid = Mock(ok=False, status_code=422, text="schema mismatch")
        valid = Mock(ok=True)
        valid.json.return_value = {"data": {"answer": "gateway connected"}}
        post.side_effect = [invalid, valid]
        config = LLMConfig(
            "secret", "https://example.test/api/v1/start", "GPT-5.5",
            deployment="east-US-2-gpt-5.5", api_style="auto",
        )

        self.assertEqual(call_llm(config, "hello"), "gateway connected")
        self.assertEqual(post.call_count, 2)
        self.assertIn("prompt", post.call_args.kwargs["json"])


if __name__ == "__main__":
    unittest.main()


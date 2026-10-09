import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import requests

from inference.agent.runtime_state import Frame, write_runtime_state
from inference.agent.tool_agent import ToolAgent, _resolve_request_log_path


class ResponseLoggingTests(unittest.TestCase):
    def run_response(self, response, *, provider="vllm", logging=True):
        agent = ToolAgent(model="logging-test", base_url="http://localhost:1/v1",
                          provider=provider, save_request_logs=logging)
        agent._tool_steps = 1
        agent._build_user_message = lambda prompt, frame: {"role": "user", "content": prompt}
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state.json"
            write_runtime_state(state, current_frame=Frame(((0, 0), (0, 0)), 0, 1), history=[])
            with patch("inference.agent.tool_agent.requests.post", side_effect=response if isinstance(response, Exception) else None,
                       return_value=response) as post:
                agent.analyze(state, 0, valid_actions=["UP"], analysis_step=1)
                agent.analyze(state, 0, valid_actions=["UP"], analysis_step=2)
            self.sent_payloads = [call.kwargs["json"] for call in post.call_args_list]
            log = _resolve_request_log_path(state)
            return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []

    def response(self, body, status=200, *, text=False):
        response = requests.Response()
        response.status_code = status
        response.encoding = "utf-8"
        response._content = (body if text else json.dumps(body, ensure_ascii=False)).encode()
        return response

    def assert_pairs(self, records):
        requests_by_id = {r["request_id"]: r for r in records if r["event"] == "request"}
        self.assertEqual(len(requests_by_id), 2)
        for record in records:
            self.assertIn(record["request_id"], requests_by_id)
            self.assertEqual(record["analysis_step"], requests_by_id[record["request_id"]]["analysis_step"])
            self.assertGreater(record["timestamp_unix"], 0)
            if record["event"] != "request":
                self.assertGreaterEqual(record["latency_seconds"], 0)

    def test_complete_response_preserves_reasoning_and_extra_fields(self):
        body = {"id": "original-id", "model": "actual-model", "vendor": {"extra": [1, 2]},
                "choices": [{"index": 0, "finish_reason": "length", "message": {
                    "role": "assistant", "content": "  输出\n", "reasoning_content": "  think\n\n" * 5000}},
                    {"index": 1, "message": {"content": "other choice"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30,
                          "completion_tokens_details": {"reasoning_tokens": 15}}}
        records = self.run_response(self.response(body))
        self.assert_pairs(records)
        for record in records:
            if record["event"] == "response":
                self.assertEqual(record["response"], body)
                self.assertEqual(record["usage"], body["usage"])
                self.assertEqual(record["http_status"], 200)
                self.assertEqual(record["finish_reason"], "length")
        self.assertEqual([r["event"] for r in records], ["request", "response"] * 2)

    def test_strata_history_keeps_original_reasoning_content(self):
        raw = "  original thinking\n\nwith whitespace  "
        body = {"choices": [{"finish_reason": "stop", "message": {
            "role": "assistant", "content": None, "reasoning_content": raw}}]}
        self.run_response(self.response(body))
        assistant = next(m for m in self.sent_payloads[1]["messages"] if m["role"] == "assistant")
        self.assertEqual(assistant["reasoning_content"], raw)
        self.assertNotIn("reasoning", assistant)

    def test_tool_arguments_are_preserved_before_normalization(self):
        body = {"choices": [{"finish_reason": "tool_calls", "message": {"role": "assistant",
                "tool_calls": [{"id": "call", "type": "function", "function": {
                    "name": "python", "arguments": "{ malformed original argument"}}]}}]}
        records = self.run_response(self.response(body))
        self.assertEqual(next(r for r in records if r["event"] == "response")["response"], body)

    def test_http_rejection_is_saved_before_error(self):
        body = {"error": {"message": "rejected", "code": "invalid_request"}}
        records = self.run_response(self.response(body, 400), provider="deepseek")
        self.assert_pairs(records)
        self.assertEqual([r["event"] for r in records], ["request", "response", "error"] * 2)
        self.assertEqual(records[1]["response"], body)
        self.assertEqual(records[1]["http_status"], 400)

    def test_non_json_body_is_saved_without_truncation(self):
        raw = "upstream failure\n" * 1000
        records = self.run_response(self.response(raw, 502, text=True))
        self.assert_pairs(records)
        self.assertEqual(records[1]["response_text"], raw)
        self.assertIsNone(records[1]["response"])

    def test_missing_choices_is_saved(self):
        body = {"unexpected": "payload"}
        records = self.run_response(self.response(body))
        self.assertEqual([r["event"] for r in records], ["request", "response", "error"] * 2)
        self.assertEqual(records[1]["response"], body)

    def test_network_error_has_one_error_per_request(self):
        records = self.run_response(requests.Timeout("timed out"))
        self.assert_pairs(records)
        self.assertEqual([r["event"] for r in records], ["request", "error"] * 2)

    def test_disabled_logging_creates_no_records(self):
        self.assertEqual(self.run_response(self.response({"choices": []}), logging=False), [])


if __name__ == "__main__":
    unittest.main()

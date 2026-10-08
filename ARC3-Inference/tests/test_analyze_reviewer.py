import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from inference.agent.analyze_reviewer import AnalyzeReviewer, add_review_feedback
from inference.agent.runtime_state import Frame, write_runtime_state
from inference.agent.tool_agent import (
    AnalyzerTurnResult, ToolAgent, _ChatCompletionResult, _ToolDispatchResult,
)


class ReviewerTests(unittest.TestCase):
    def test_warn_then_stop_identical_checks(self):
        reviewer = AnalyzeReviewer()
        reviewer.begin_state("board")
        outcomes = [reviewer.observe("python", {"code": "print(1)"}, "1") for _ in range(5)]
        self.assertEqual([r.outcome if r else None for r in outcomes],
                         [None, None, "warn", None, "stop"])

    def test_alternating_checks_also_stop(self):
        reviewer = AnalyzeReviewer()
        results = [reviewer.observe("python", {"code": f"print({i % 2})"}, str(i % 2))
                   for i in range(9)]
        self.assertEqual(results[-1].outcome, "stop")

    def test_new_results_and_new_checks_are_allowed(self):
        reviewer = AnalyzeReviewer()
        for i in range(40):
            self.assertIsNone(reviewer.observe("python", {"code": "print(value)"}, str(i)))
            self.assertIsNone(reviewer.observe("python", {"code": f"print({i})"}, "same"))

    def test_comments_do_not_evade_repetition_detection(self):
        reviewer = AnalyzeReviewer()
        decisions = [reviewer.observe("python", {"code": f"# comment {i}\nprint(1)"}, "1")
                     for i in range(3)]
        self.assertEqual(decisions[-1].outcome, "warn")

    def test_action_and_observation_change_reset_counts(self):
        reviewer = AnalyzeReviewer()
        reviewer.begin_state("first")
        for _ in range(2):
            reviewer.observe("python", {"code": "print(1)"}, "1")
        reviewer.begin_state("first")
        self.assertEqual(reviewer.observe("python", {"code": "print(1)"}, "1").outcome, "warn")
        reviewer.begin_state("second")
        self.assertIsNone(reviewer.observe("python", {"code": "print(1)"}, "1"))
        reviewer.observe("python", {"code": "action(['UP'])"}, "ok", step_executed=True)
        self.assertIsNone(reviewer.observe("python", {"code": "print(1)"}, "1"))

    def test_window_and_disabled_mode(self):
        reviewer = AnalyzeReviewer()
        reviewer.observe("python", {"code": "print(1)"}, "1")
        for i in range(20):
            reviewer.observe("python", {"code": f"print({i + 10})"}, str(i))
        self.assertIsNone(reviewer.observe("python", {"code": "print(1)"}, "1"))
        reviewer = AnalyzeReviewer(enabled=False)
        for _ in range(20):
            self.assertIsNone(reviewer.observe("python", {"code": "print(1)"}, "1"))

    def test_feedback_preserves_original_result(self):
        reviewer = AnalyzeReviewer()
        decision = None
        for _ in range(3):
            decision = reviewer.observe("python", {"code": "print(1)"}, "1")
        original = {"returncode": 0, "stdout": "1"}
        payload = json.loads(add_review_feedback(json.dumps(original), decision))
        self.assertEqual(payload["stdout"], "1")
        self.assertIn("Reviewer:", payload["reviewer_feedback"])
        self.assertNotIn("reviewer_feedback", original)


class AnalyzerIntegrationTests(unittest.TestCase):
    def make_agent(self):
        agent = ToolAgent(model="reviewer-test", base_url="http://localhost:1/v1", provider="vllm")
        agent._tool_steps = 2
        agent._reviewer = AnalyzeReviewer()
        agent._build_user_message = lambda prompt, frame: {"role": "user", "content": prompt}
        agent._dispatch_tool = Mock(return_value=_ToolDispatchResult(
            json.dumps({"returncode": 0, "stdout": "same result"})))
        self.requests = []

        def completion(messages, **kwargs):
            self.requests.append(copy.deepcopy(messages))
            return _ChatCompletionResult(message={"role": "assistant", "tool_calls": [{
                "id": f"call-{len(self.requests)}", "type": "function", "function": {
                    "name": "python", "arguments": json.dumps({"code": "print(1)"})}}]},
                finish_reason="tool_calls")
        agent._chat_completion = completion
        return agent

    def test_stop_and_feedback_survive_analyze_boundaries(self):
        agent = self.make_agent()
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state.json"
            write_runtime_state(state, current_frame=Frame(((0, 0), (0, 0)), 0, 1), history=[])
            results = [agent.analyze(state, 0, valid_actions=["UP"], analysis_step=i)
                       for i in range(1, 4)]
        self.assertTrue(all(r is not None for r in results))
        self.assertIsNone(results[0].reviewer_stop_reason)
        self.assertIsNone(results[1].reviewer_stop_reason)
        self.assertIn("Repeated analysis stopped", results[2].reviewer_stop_reason)
        self.assertEqual(len(self.requests), 5)
        fourth_request = self.requests[3]
        self.assertTrue(any("reviewer_feedback" in str(m.get("content"))
                            for m in fourth_request if m["role"] == "tool"))
        self.assertTrue(any(m["role"] == "user" for m in fourth_request))

    def test_agent_can_act_after_warning(self):
        agent = self.make_agent()
        agent._dispatch_tool.side_effect = [
            _ToolDispatchResult("same result"), _ToolDispatchResult("same result"),
            _ToolDispatchResult("same result"), _ToolDispatchResult("action executed", step_executed=True),
            _ToolDispatchResult("same result"), _ToolDispatchResult("same result"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state.json"
            write_runtime_state(state, current_frame=Frame(((0,),), 0, 1), history=[])
            first = agent.analyze(state, 0, valid_actions=["UP"])
            second = agent.analyze(state, 0, valid_actions=["UP"])
            third = agent.analyze(state, 1, valid_actions=["UP"])
        self.assertFalse(first.step_executed)
        self.assertTrue(second.step_executed)
        self.assertIsNone(third.reviewer_stop_reason)

    def test_solver_finishes_game_when_reviewer_stops(self):
        from inference.framework.solver import _HarnessGameSession
        run = SimpleNamespace(solver_analysis_html=None, final_score=None,
                              solver_note=None, state="playing")
        session = _HarnessGameSession.__new__(_HarnessGameSession)
        session.game = SimpleNamespace(game_run=run)
        session.analysis_html_relpath = "analysis.html"
        session.analyzer = Mock()
        session.analyzer.total_tokens = 0
        session.analyzer.generated_tokens = 0
        session.analyzer.analyze.return_value = AnalyzerTurnResult(
            step_executed=False, reviewer_stop_reason="repeated check")
        session.analysis_step = 0
        for method in ["seed_initial_history", "write_runtime_state", "_append_initial_viewer_event",
                       "write_viewer_payload", "_finish_if_needed", "_write_analysis_html"]:
            setattr(session, method, Mock())
        session.should_stop = Mock(side_effect=[False, True])
        session._read_transcript_bytes = Mock(return_value=b"")
        session._transcript_delta_since = Mock(return_value="")
        session.request_timeout_seconds = Mock(return_value=1)
        session.step_env = Mock()
        with tempfile.TemporaryDirectory() as directory:
            session.state_path = Path(directory) / "state.json"
            session.transcript_path = Path(directory) / "transcript.txt"
            with patch("inference.framework.solver._is_engine_game_over", return_value=False), \
                 patch("inference.framework.solver._engine_action_names", return_value=["UP"]), \
                 patch.object(_HarnessGameSession, "action_count", new_callable=property,
                              fget=lambda self: 0):
                session.play()
        self.assertEqual(run.solver_note, "reviewer: repeated check")
        session.analyzer.analyze.assert_called_once()
        session._finish_if_needed.assert_called_once()


if __name__ == "__main__":
    unittest.main()

"""Detect repeated analysis with unchanged observations and tool feedback."""
from __future__ import annotations

import ast
from collections import Counter, deque
from dataclasses import dataclass
import hashlib
import json
from typing import Any


@dataclass(frozen=True)
class ReviewDecision:
    outcome: str
    fingerprint: str
    repeats: int
    message: str


class AnalyzeReviewer:
    """A bounded, deterministic guard; it does not assess semantic usefulness."""

    def __init__(self, *, enabled: bool = True, warn_repeats: int = 3,
                 stop_repeats: int = 5, window: int = 12) -> None:
        self.enabled = enabled
        self.warn_repeats = max(2, warn_repeats)
        self.stop_repeats = max(self.warn_repeats + 1, stop_repeats)
        self.window = max(self.stop_repeats, window)
        self.reset()

    def reset(self) -> None:
        self._state: Any = None
        self._recent: deque[str] = deque(maxlen=self.window)
        self._warned: set[str] = set()

    def begin_state(self, state: Any) -> None:
        if state != self._state:
            self.reset()
            self._state = state

    @staticmethod
    def _fingerprint(name: str, arguments: dict[str, Any], output: str) -> str:
        arguments = dict(arguments)
        if name == "python" and isinstance(arguments.get("code"), str):
            try:
                arguments["code"] = ast.dump(ast.parse(arguments["code"]))
            except SyntaxError:
                arguments["code"] = arguments["code"].strip()
        try:
            feedback = json.loads(output)
        except (ValueError, TypeError):
            feedback = output.strip()
        payload = json.dumps([name, arguments, feedback], sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode()).hexdigest()

    def observe(self, name: str, arguments: dict[str, Any], output: str,
                *, step_executed: bool = False) -> ReviewDecision | None:
        if step_executed:
            self.reset()
            return None
        if not self.enabled:
            return None
        fingerprint = self._fingerprint(name, arguments, output)
        self._recent.append(fingerprint)
        counts = Counter(self._recent)
        self._warned.intersection_update(counts)
        repeats = counts[fingerprint]
        if repeats >= self.stop_repeats:
            return ReviewDecision("stop", fingerprint, repeats,
                f"Repeated analysis stopped: identical input and feedback occurred {repeats} "
                f"times in the last {len(self._recent)} checks without an environment action.")
        if repeats >= self.warn_repeats and fingerprint not in self._warned:
            self._warned.add(fingerprint)
            return ReviewDecision("warn", fingerprint, repeats,
                f"Reviewer: this identical check and feedback occurred {repeats} times "
                "without an environment action. Repeating it yields no new evidence. "
                "Change the hypothesis or inspection, or select a justified valid action. "
                "Do not repeat this check unless the observation or expected result changes. "
                f"At {self.stop_repeats} repetitions in the recent window, this game will stop.")
        return None


def add_review_feedback(output: str, decision: ReviewDecision) -> str:
    """Attach feedback to the tool message, preserving the user observation."""
    try:
        payload = json.loads(output)
    except (ValueError, TypeError):
        payload = None
    if isinstance(payload, dict):
        payload["reviewer_feedback"] = decision.message
        return json.dumps(payload, ensure_ascii=False)
    return output + "\n\n" + decision.message

# Local development changes

Fork of https://github.com/Tufalabs/duck-harness, based on commit
`7652836056c59e044f093e3c13ed7438c814169e`. Original authorship and history are preserved.

## Context retention

Budget trimming retains the latest user observation (including images) and the latest
complete assistant/tool exchange. Older exchanges are removed as groups. The persistent
30-assistant-turn cap restores the preceding user anchor instead of emptying the history.
If the smallest complete exchange exceeds the estimated budget, retain it so the server
can report an explicit context error rather than sending a system-only request.

## DeepSeek experimental backend

Set `LOCAL_ANALYZER_PROVIDER=deepseek` and supply the model, API URL and key through the
existing local-analyzer environment variables. Thinking uses DeepSeek's `thinking`
parameter. Preserve `reasoning_content` verbatim for tool history, without duplicating it
in `reasoning`. Non-retryable request failures stop the analyzer attempt.

Cloud API inference is for local experiments. Kaggle evaluation must use a local model
backend with packaged sources, weights and offline dependencies.

## Validation

From `ARC3-Inference`, with Python 3.12.12 and the runtime dependencies installed:

```sh
python -m unittest discover -s tests -p test_duck_context.py -v
python -m unittest discover -s tests -p test_deepseek_adapter.py -v
```

Nine regression tests pass. The parent workspace also verified LS20 and VC33 using a
local mock Chat Completions server, images and Python tool execution. This is interface
validation; the context fix has not yet been evaluated in a fresh live model run.
## Analysis reviewer

The deterministic reviewer tracks tool inputs and feedback across `analyze()` calls
while the observation and action count remain unchanged. Python code is compared by
AST, ignoring formatting and comments. It also detects identical assistant replies
that never call a tool. It performs no additional model inference.

Within the last 12 checks, the third occurrence of an identical input/result pair
adds corrective feedback to the tool response. The fifth occurrence ends the game
normally (`gave_up`) with a `reviewer:` solver note, allowing other games to continue.
An executed environment action or changed observation resets the repetition history.
Alternating two repeated checks is detected; new checks or changed results are allowed.
Review decisions and thresholds are included in the analyzer transcript.

| Environment variable | Default |
| --- | --- |
| `LOCAL_ANALYZER_REVIEWER_ENABLED` | `true` |
| `LOCAL_ANALYZER_REVIEWER_WARN_REPEATS` | `3` |
| `LOCAL_ANALYZER_REVIEWER_STOP_REPEATS` | `5` |
| `LOCAL_ANALYZER_REVIEWER_WINDOW` | `12` |

The stop threshold is at least one greater than the warning threshold, and the window
is at least as large as the stop threshold. This detects exact repeated behavior,
not all semantically redundant reasoning. Identical truncated output can hide changes;
thresholds may need tuning for a model/game. The guard does not force arbitrary actions
and does not stop novel analysis simply because no action has occurred yet.

Stopping reports generated tokens since the last environment action in the game's
`final_generated_tokens`, so non-action analysis is included in benchmark token totals.

Run all 21 regression tests with `python -m unittest discover -s tests -v`.
The parent workspace verified two complete mock games: each warns and finishes after
five repeated checks, including across analysis boundaries. Offline replay detects the
observed G50T, LS20 and LP85 loops. Replay does not simulate how a live model would
respond to the corrective feedback.

Real Strata acceptance of commit `92704b3` passed on four games, including an LP85
warning and stop followed by normal VC33 execution. See
[validation/reviewer](validation/reviewer/README.md) for results and reproduction details.

## Complete response logging

With `--save-request-logs`, each HTTP response is recorded before status checks,
message normalization or tool dispatch. `event=response` now contains the complete
parsed JSON in `response`, including every choice, original `reasoning_content`,
content, tool arguments, usage and provider extensions. Non-JSON bodies are preserved
in `response_text`. No response text limit is applied by the logger.

Each attempt has a unique `request_id` shared by its request, response and error
records, plus timestamps, HTTP status and elapsed request time. HTTP failures,
invalid responses and network errors are recorded; existing fields remain compatible.
No authorization headers are logged. Earlier logs cannot recover discarded responses.
The model's output/context limits still apply independently of log preservation.

All 28 regression tests passed locally and on the experiment machine. Validate new
logs with `python tools/validate_response_logs.py /path/to/requests.jsonl --require-reasoning`.

Real Strata thinking acceptance also passed: four complete HTTP responses and one
paired timeout. See [validation/response-logging](validation/response-logging/README.md).

## Thinking continuity and unrestricted output

Strata/Qwen history now receives original `reasoning_content` instead of the ignored
`reasoning` field. The analyzer default `LOCAL_ANALYZER_MAX_OUTPUT=0` omits
`max_tokens`; Strata then permits generation up to remaining context capacity.
The acceptance runner now also defaults to 0, with `--max-output` for an explicit cap.
`--thinking` selects Qwen's recommended temperature 1.0, top_p 0.95 and top_k 20.
Time budgets, context capacity and the tool-result length limit remain independent.
All 30 regression tests passed locally and on the experiment machine.

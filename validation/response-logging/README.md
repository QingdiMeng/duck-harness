# Response logging acceptance

Validated on 2026-10-09 on the experiment machine, reusing the loaded Strata
`qwen3.8-flash-next-coder-iq1_m` service. A short LP85 native harness run enabled
thinking and request logging, with a one-minute game budget and 1024 output tokens.

All five requests had unique IDs and terminal records: four HTTP 200 responses and
one read timeout when the remaining game budget was about ten seconds. Every response
preserved the complete returned JSON, usage, finish reason and original reasoning.
Reasoning lengths were 48, 2705, 2768 and 2639 characters. One response contained a
tool call; three had `finish_reason=length` from the smoke test's model output cap.
The logger does not remove that model cap or manufacture missing responses on timeout.

All 28 regression tests passed on Mac and the experiment host. Seven new tests cover
long reasoning and provider extensions, original malformed tool arguments, HTTP
rejection, non-JSON bodies, missing choices, network errors and disabled logging.

The field/pairing report is [strata-thinking-20261009.json](strata-thinking-20261009.json).
Full logs remain at `/home/xiaoxiaohu/agc/runs/duck-response-logging-thinking-20261009`.
No DeepSeek cloud requests were made. This validates logging, not game-solving quality.

```sh
python tools/validate_response_logs.py /path/to/requests.jsonl --require-reasoning
```

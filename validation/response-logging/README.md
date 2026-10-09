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

## Unlimited-output thinking retest

After restoring `reasoning_content` in Strata/Qwen history, a second LP85 smoke run
used `LOCAL_ANALYZER_MAX_OUTPUT=0` (no max_tokens), thinking enabled, temperature 1.0,
top_p 0.95 and top_k 20. Strata permits generation up to the remaining 32K context.
The run had a one-action cap, a three-minute game budget and a 180-second timeout.

Both responses finished with tool_calls: 177 and 2994 generated tokens, taking about
3.1 and 43.9 seconds. The second request carried the previous original reasoning
verbatim. The agent executed one mouse action at row 44, column 25; no HTTP errors
occurred. The run ended normally at the action cap with zero levels completed.
All 30 regression tests passed on both machines. This validates unrestricted output,
thinking history continuity and action execution, not improved solving performance.

Report: [strata-unlimited-20261009.json](strata-unlimited-20261009.json).
Full logs: `/home/xiaoxiaohu/agc/runs/duck-thinking-unlimited-20261009`.

## Four-game solving validation

A fresh real-model run of commit `1d4a74d` tested LP85, G50T, LS20 and VC33 serially
with thinking enabled, no max_tokens cap, temperature 1.0, top_p 0.95 and top_k 20.
Each game had a 30-action cap and ten-minute active-time budget. The total test took
2050.67 seconds (34.18 minutes), including local SDK scoring. Both processes exited 0.

| Game | Completed levels | Actions | Stop cause | Generated tokens |
| --- | ---: | ---: | --- | ---: |
| LP85 | 1 / 8 | 30 | Action cap | 26609 |
| G50T | 0 / 7 | 17 | Time budget | 37002 |
| LS20 | 0 / 7 | 9 | Time budget | 35644 |
| VC33 | 1 / 7 | 30 | Action cap | 23953 |

All 94 requests returned normally with `finish_reason=tool_calls`; no HTTP errors or
length finishes occurred. Maximum single-request input plus output was 30080 tokens,
below the 32768 server context. The largest completion was 5993 tokens. Generation
across requests totaled 123208 tokens, which is not a single context length.
No exact-repetition reviewer warnings/stops occurred. G50T and LS20 nevertheless
spent substantial time inspecting state without acting: semantic redundancy and slow
rule discovery remain outside the exact-pair reviewer mechanism.

The run completed two levels and zero full games. Saved action events were rescored
with the official local SDK, yielding 0.8038194444; this is a local reconstruction,
not a Kaggle evaluation score. The native harness score is zero because baseline
metadata is unavailable in simulation mode; use the separate SDK report.

This is one stochastic trajectory per game under limited action/time budgets, not
proof of hidden-set performance or improved solving compared to prior runs. The older
non-thinking run had different time and output limits, so there is no controlled
comparison. Earlier compaction is also not implemented: budget trimming deletes
older exchanges, while optional world-model notes are extracted only from assistant
content. Thinking history continuity does not provide automatic semantic compression.

Reports: [solving](strata-solving-1d4a74d.json) and
[token/stop diagnostics](strata-solving-diagnostics-1d4a74d.json).
Full logs remain at `/home/xiaoxiaohu/agc/runs/duck-thinking-solving-20261009`.

```sh
python tools/validate_solving.py --root /home/xiaoxiaohu/agc \
  --output /home/xiaoxiaohu/agc/runs/new-solving-validation --commit "$(git rev-parse HEAD)"
```

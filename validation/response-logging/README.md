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

## Medium versus low effort

The experiment machine tested commit `92a7f08` with explicit medium and low effort,
serially on the same loaded Strata service. Both used seed 42, temperature 1.0,
top_p 0.95, top_k 20, thinking enabled, no output cap, 32K context, and the same
LP85/G50T/LS20/VC33 order with 30 actions and ten minutes per game. Transport tests
verified the effort in the actual HTTP payload; all 34 regression tests passed on
both hosts. Every request-log event recorded the configured effort.

| Metric | Medium | Low |
| --- | ---: | ---: |
| Levels completed | 2 | 3 |
| Full games won | 0 | 0 |
| Actions executed | 75 | 114 |
| Wallclock minutes, including scoring | 34.21 | 31.64 |
| Generated tokens | 122029 | 109479 |
| Requests / responses | 110 / 110 | 136 / 136 |
| Mean generated tokens per response | 1109.35 | 804.99 |
| Total HTTP response latency seconds | 2039.87 | 1854.83 |
| HTTP errors / length finishes | 0 / 0 | 0 / 0 |
| Local reconstructed SDK score | 0.8294753086 | 1.6463805206 |

| Game | Medium levels / actions | Low levels / actions |
| --- | --- | --- |
| LP85 | 1 / 18 | 1 / 30 |
| G50T | 0 / 8 | 0 / 30 |
| LS20 | 0 / 19 | 1 / 24 |
| VC33 | 1 / 30 | 1 / 30 |

In this pair, low used 10.28% fewer generated tokens and 7.51% less wallclock time,
while completing LS20's first level, which medium did not complete. Mean output per
request fell by about 27.4%, but request count increased by 23.6%, limiting the overall
savings. Low completed LP85's first level in six actions versus medium's fifteen;
both completed VC33's first level in eighteen actions. Neither effort solved a full
game. Shorter effort did not force short replies: medium had a 7018-token response.

This is one trajectory per effort, not a statistical performance claim. Seed 42 makes
the settings reproducible but does not establish confidence or generalization. The
historical xhigh run had no fixed seed and is only a reference. Scores are local SDK
reconstructions, not Kaggle evaluation scores. No default effort was changed.

Reports: [comparison](effort-comparison-92a7f08.json),
[medium](strata-medium-92a7f08.json), [low](strata-low-92a7f08.json).
Full logs remain in `/home/xiaoxiaohu/agc/runs/duck-effort-comparison-20261009/{medium,low}`.
On the prepared experiment host, reproduce via `scripts/compare_duck_effort.py`; the
same orchestration is saved as `tools/compare_reasoning_effort.py`. The orchestrator
expects the solving runner at the host's `scripts/validate_duck_solving.py` path.

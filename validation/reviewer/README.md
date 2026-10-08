# Reviewer acceptance

Validated on the experiment machine on 2026-10-09 (Asia/Shanghai), using Strata and
`qwen3.8-flash-next-coder-iq1_m`, with images enabled, thinking disabled, temperature 0,
32K context and 1024 output tokens. The model service was already loaded. Games ran
serially with a 30-action cap and a 3-minute active-time budget per game.

The tested code is commit `92704b390e75b3a4b63d82d3a8b129bc572ea375`.
The implementation files on the experiment host match the local fork by SHA-256.
All 21 regression tests passed on both machines. Two mock games separately verified
that warnings reach subsequent model requests, counters survive analysis boundaries,
games finish normally, and five non-action completions are counted in final token totals.

The final real-model acceptance passed all eight checks, with 114 requests,
zero requests missing a user observation, and 602.5 seconds total wallclock.

| Game | Actions | Levels completed | Reviewer outcome |
| --- | ---: | ---: | --- |
| G50T | 30 | 0 | No repeated pair threshold reached; normal action cap |
| LS20 | 16 | 0 | No repeated pair threshold reached; time budget |
| LP85 | 14 | 1 | Warn at 3 repeats, stop at 5 repeats; next game continued |
| VC33 | 30 | 1 | No repeated pair threshold reached; normal action cap |

LP85's 1177 generated tokens after its last action were preserved in
`final_generated_tokens`. An earlier acceptance of the same reviewer core also
observed G50T stopping a persistent loop and LS20 acting after corrective feedback.
Trajectories differed between runs; these are mechanism checks, not a controlled
claim of improved solving score.

The machine-readable report is [strata-acceptance-92704b3.json](strata-acceptance-92704b3.json).
The full logs remain on the experiment machine at
`~/agc/runs/duck-reviewer-strata-acceptance-final-20261009`.

To reproduce with an already-loaded Strata service:

```sh
python tools/accept_analyze_reviewer.py \
  --root /home/xiaoxiaohu/agc \
  --source /path/to/duck-harness/ARC3-Inference \
  --output /home/xiaoxiaohu/agc/runs/new-reviewer-acceptance \
  --commit "$(git rev-parse HEAD)"
```

This tests four public games. The rule reviewer does not detect every semantically
redundant rewrite and does not guarantee score improvement or hidden-set performance.

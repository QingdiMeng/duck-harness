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
There is no added cross-analysis no-action limit.

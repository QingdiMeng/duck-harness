"""Accept the reviewer on public games using an already-loaded Strata service."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    source = (args.source or root / "external/Duck-official/ARC3-Inference").resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    games = ["g50t", "ls20", "lp85", "vc33"]
    env = os.environ.copy()
    env.update(
        PYTHONPATH=os.pathsep.join([str(source), str(source.parent / "tufa-arc-agi-framework/src")]),
        LOCAL_ANALYZER_PROVIDER="vllm",
        LOCAL_ANALYZER_BASE_URL="http://127.0.0.1:8081/v1",
        LOCAL_ANALYZER_MODEL_ID="qwen3.8-flash-next-coder-iq1_m",
        LOCAL_ANALYZER_ENABLE_THINKING="false", LOCAL_ANALYZER_MAX_OUTPUT="1024",
        LOCAL_ANALYZER_CONTEXT_WINDOW="32768", LOCAL_ANALYZER_TOOL_STEPS="12",
        LOCAL_ANALYZER_TEMPERATURE="0", LOCAL_ANALYZER_TOP_P="1", LOCAL_ANALYZER_TOP_K="0",
        LOCAL_ANALYZER_REVIEWER_ENABLED="true", LOCAL_ANALYZER_REVIEWER_WARN_REPEATS="3",
        LOCAL_ANALYZER_REVIEWER_STOP_REPEATS="5", LOCAL_ANALYZER_REVIEWER_WINDOW="12",
        MULTIMODAL_CONTEXT="current_grid", MULTIMODAL_UPSCALE="8", ONLY_RESET_LEVELS="true",
        NO_PROXY="127.0.0.1,localhost", no_proxy="127.0.0.1,localhost",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open("http://127.0.0.1:8081/health", timeout=10) as response:
        health = json.load(response)
    if not health.get("loaded"):
        raise RuntimeError("Strata is not loaded")
    config = {"commit": args.commit, "health": health, "games": games,
              "max_actions": 30, "per_game_minutes": 3, "reviewer": {"warn": 3, "stop": 5, "window": 12}}
    (output / "acceptance-config.json").write_text(json.dumps(config, indent=2) + "\n")
    command = [sys.executable, "-u", "-m", "inference.framework.run", "--game", ",".join(games),
               "--environments-dir", str(root / "environment_files"), "--model", "local",
               "--simulate-competition-arcade", "--n-passes", "1", "--concurrent-jobs", "1",
               "--max-actions", "30", "--max-runtime-minutes", "3",
               "--max-experiment-runtime-minutes", "30", "--timeout", "120",
               "--save-request-logs", "--experiment-dir", str(output)]
    (output / "launch-command.json").write_text(json.dumps(command, indent=2) + "\n")
    started = time.monotonic()
    with (output / "stdout.log").open("w") as log:
        result = subprocess.run(command, cwd=root, env=env, stdout=log,
                                stderr=subprocess.STDOUT, timeout=30 * 60 + 120)
    with (output / "scoring.log").open("w") as log:
        scoring = subprocess.run([sys.executable, str(root / "scripts/score_duck_local.py"),
                                  str(output), "--environments-dir", str(root / "environment_files")],
                                 cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=120)
    benchmark = json.loads((output / "benchmark.json").read_text())
    game_reports = []
    for run in benchmark["game_runs"]:
        counts = Counter()
        decisions = []
        events_path = next((output / "artifacts").glob(run["game_id"] + "*_events.jsonl"))
        for line in events_path.open():
            event = json.loads(line)
            if event.get("type") != "analysis":
                continue
            counts[event.get("action_num")] += 1
            sections = re.split(r"(?m)^\[(.+?)\]\s*$", event.get("transcript", ""))
            for label, body in zip(sections[1::2], sections[2::2]):
                if label == "ANALYZE REVIEWER":
                    decision = json.loads(body.strip())
                    decision.update(analysis_step=event.get("analysis_step"), action_count=event.get("action_num"))
                    decisions.append(decision)
        game_reports.append({"game": run["game_id"], "state": run["state"],
                             "actions": len(run["history"]), "levels": run["levels_completed"],
                             "generated_tokens": sum(h.get("generated_tokens", 0) for h in run["history"])
                                                 + run.get("final_generated_tokens", 0),
                             "final_generated_tokens": run.get("final_generated_tokens", 0),
                             "wallclock_seconds": run.get("final_wallclock_seconds", 0),
                             "note": run.get("solver_note"), "reviewer_decisions": decisions,
                             "max_analyses_at_one_action_count": max(counts.values(), default=0)})
    requests = []
    for line in (output / "requests.jsonl").open():
        record = json.loads(line)
        if record.get("event") == "request":
            requests.append(record)
    missing_user = sum(not any(m.get("role") == "user" for m in r["messages"]) for r in requests)
    decisions = [d for g in game_reports for d in g["reviewer_decisions"]]
    stops = [d for d in decisions if d["outcome"] == "stop"]
    criteria = {
        "harness_exited_cleanly": result.returncode == 0,
        "sdk_scoring_succeeded": scoring.returncode == 0,
        "all_four_games_finished_without_crash": len(game_reports) == 4 and all(
            g["state"] in {"gave_up", "won"} for g in game_reports),
        "observations_retained": missing_user == 0,
        "reviewer_warning_observed": any(d["outcome"] == "warn" for d in decisions),
        "persistent_loop_stopped": bool(stops),
        "stopped_games_have_reviewer_note": all(
            str(g["note"]).startswith("reviewer:") for g in game_reports
            if any(d["outcome"] == "stop" for d in g["reviewer_decisions"])),
        "normal_control_still_acts": any(g["game"].startswith("vc33") and g["actions"] > 0
                                        for g in game_reports),
    }
    report = {"passed": all(criteria.values()), "criteria": criteria, "commit": args.commit,
              "wallclock_seconds": round(time.monotonic() - started, 2),
              "requests": len(requests), "requests_without_user": missing_user, "games": game_reports,
              "limitations": ["Four public games only; no claim about hidden-set score.",
                              "Rule reviewer detects repeated inputs/results, not all semantic redundancy."]}
    (output / "acceptance-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2), flush=True)
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

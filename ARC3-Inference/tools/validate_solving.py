"""Measure real public-game solving with the current Duck/Strata configuration."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    source = root / 'external/Duck-official/ARC3-Inference'
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    env.update(PYTHONPATH=os.pathsep.join([str(source), str(source.parent / 'tufa-arc-agi-framework/src')]),
               LOCAL_ANALYZER_PROVIDER='vllm', LOCAL_ANALYZER_BASE_URL='http://127.0.0.1:8081/v1',
               LOCAL_ANALYZER_MODEL_ID='qwen3.8-flash-next-coder-iq1_m',
               LOCAL_ANALYZER_ENABLE_THINKING='true', LOCAL_ANALYZER_MAX_OUTPUT='0',
               LOCAL_ANALYZER_CONTEXT_WINDOW='32768', LOCAL_ANALYZER_TOOL_STEPS='12',
               LOCAL_ANALYZER_TIMEOUT='0', LOCAL_ANALYZER_YIELD_SECONDS='0',
               LOCAL_ANALYZER_TEMPERATURE='1.0', LOCAL_ANALYZER_TOP_P='0.95', LOCAL_ANALYZER_TOP_K='20',
               LOCAL_ANALYZER_REVIEWER_ENABLED='true', LOCAL_ANALYZER_REVIEWER_WARN_REPEATS='3',
               LOCAL_ANALYZER_REVIEWER_STOP_REPEATS='5', LOCAL_ANALYZER_REVIEWER_WINDOW='12',
               MULTIMODAL_CONTEXT='current_grid', MULTIMODAL_UPSCALE='8', ONLY_RESET_LEVELS='true',
               NO_PROXY='127.0.0.1,localhost', no_proxy='127.0.0.1,localhost')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open('http://127.0.0.1:8081/health', timeout=10) as response:
        health = json.load(response)
    if not health.get('loaded'):
        raise RuntimeError('Strata not loaded')
    games = ['lp85', 'g50t', 'ls20', 'vc33']
    config = {'commit': args.commit, 'health': health, 'games': games, 'max_actions': 30,
              'per_game_minutes': 10, 'total_minutes': 45, 'request_timeout_seconds': 600,
              'thinking': True, 'max_output': 0, 'temperature': 1.0, 'top_p': 0.95, 'top_k': 20,
              'context': 32768, 'code_sha256': hashlib.sha256((source / 'inference/agent/tool_agent.py').read_bytes()).hexdigest(),
              'limitations': ['One stochastic trajectory per game, four public games only.',
                              'No controlled comparison; the older 3-minute non-thinking run used different budgets.']}
    (output / 'solving-config.json').write_text(json.dumps(config, indent=2)+'\n')
    command = [sys.executable, '-u', '-m', 'inference.framework.run', '--game', ','.join(games),
               '--environments-dir', str(root / 'environment_files'), '--model', 'local',
               '--simulate-competition-arcade', '--n-passes', '1', '--concurrent-jobs', '1',
               '--max-actions', '30', '--max-runtime-minutes', '10',
               '--max-experiment-runtime-minutes', '45', '--timeout', '600',
               '--save-request-logs', '--experiment-dir', str(output)]
    (output / 'launch-command.json').write_text(json.dumps(command, indent=2)+'\n')
    started = time.monotonic()
    with (output / 'stdout.log').open('w') as log:
        run = subprocess.run(command, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=46*60)
    with (output / 'scoring.log').open('w') as log:
        scoring = subprocess.run([sys.executable, str(root / 'scripts/score_duck_local.py'), str(output),
                                  '--environments-dir', str(root / 'environment_files')], cwd=root, env=env,
                                 stdout=log, stderr=subprocess.STDOUT, timeout=120)
    benchmark = json.loads((output / 'benchmark.json').read_text())
    request_count = response_count = errors = generated = length_finishes = 0
    for line in (output / 'requests.jsonl').open():
        record = json.loads(line)
        event = record.get('event')
        request_count += event == 'request'
        response_count += event == 'response'
        errors += event == 'error'
        if event == 'response':
            generated += (record.get('usage') or {}).get('completion_tokens', 0)
            length_finishes += record.get('finish_reason') == 'length'
    report = {'config': config, 'harness_exit_code': run.returncode, 'sdk_scoring_exit_code': scoring.returncode,
              'wallclock_seconds': round(time.monotonic()-started, 2), 'requests': request_count,
              'responses': response_count, 'errors': errors, 'generated_tokens_from_responses': generated,
              'length_finishes': length_finishes, 'games': []}
    for g in benchmark['game_runs']:
        report['games'].append({'game': g['game_id'], 'state': g['state'], 'levels_completed': g['levels_completed'],
                                'total_levels': g['number_of_levels'], 'actions': len(g['history']),
                                'actions_per_level': g.get('actions_per_level'), 'solver_note': g.get('solver_note'),
                                'generated_tokens': sum(h.get('generated_tokens', 0) for h in g['history'])
                                                    + g.get('final_generated_tokens', 0)})
    score = output / 'sdk-local-score.json'
    if score.exists():
        report['sdk_score'] = json.loads(score.read_text())
    report['total_levels_completed'] = sum(g['levels_completed'] for g in report['games'])
    report['games_won'] = sum(g['state'] == 'won' for g in report['games'])
    (output / 'solving-report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()

"""Run medium and low serially with identical public-game budgets and sampling seed."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    reports = []
    started = time.monotonic()
    for effort in ['medium', 'low']:
        target = output / effort
        command = [sys.executable, '-u', str(root / 'scripts/validate_duck_solving.py'),
                   '--root', str(root), '--output', str(target), '--commit', args.commit,
                   '--effort', effort, '--seed', '42']
        print(f'Starting {effort}: {target}', flush=True)
        with (output / (effort + '-launcher.log')).open('w') as log:
            process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=48*60)
        if process.returncode != 0:
            raise RuntimeError(f'{effort} validation runner failed: {process.returncode}')
        report = json.loads((target / 'solving-report.json').read_text())
        responses = []
        with (target / 'requests.jsonl').open() as log:
            for line in log:
                record = json.loads(line)
                assert record.get('reasoning_effort') == effort, 'Effort missing from request log'
                if record.get('event') == 'response':
                    responses.append(record)
        request_seconds = sum(r['latency_seconds'] for r in responses)
        summary = {'effort': effort, 'seed': 42, 'levels_completed': report['total_levels_completed'],
                   'games_won': report['games_won'], 'actions': sum(g['actions'] for g in report['games']),
                   'generated_tokens': report['generated_tokens_from_responses'], 'requests': report['requests'],
                   'errors': report['errors'], 'length_finishes': report['length_finishes'],
                   'wallclock_seconds': report['wallclock_seconds'],
                   'model_request_seconds': round(request_seconds, 2),
                   'mean_tokens_per_response': round(report['generated_tokens_from_responses']/len(responses), 2),
                   'games': report['games'], 'sdk_score': report['sdk_score']['scorecard']['score']}
        reports.append(summary)
        (output / 'comparison.json').write_text(json.dumps({'complete': False, 'runs': reports}, indent=2)+'\n')
        print(json.dumps(summary, indent=2), flush=True)
    comparison = {'complete': True, 'wallclock_seconds': round(time.monotonic()-started, 2),
                  'runs': reports, 'limitations': ['One trajectory per effort with seed 42; not a statistical performance claim.',
                                                 'Historical xhigh run used no fixed seed and is only a reference.',
                                                 'SDK scores are local reconstructions, not Kaggle evaluation scores.']}
    (output / 'comparison.json').write_text(json.dumps(comparison, indent=2)+'\n')
    print(json.dumps(comparison, indent=2), flush=True)


if __name__ == '__main__':
    main()

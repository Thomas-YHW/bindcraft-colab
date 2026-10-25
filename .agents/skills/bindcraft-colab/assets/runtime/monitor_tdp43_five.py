"""Collect authoritative worker progress and optional result snapshots locally."""
import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys
import os
import time

ROOT = Path(__file__).resolve().parents[1]
BATCH = os.environ.get('TDP43_BATCH', 'ten')
STATE = ROOT / f'results/tdp43-{BATCH}'
CLI = [sys.executable, '-m', 'colab_cli.cli']
parser = argparse.ArgumentParser()
parser.add_argument('--snapshots', action='store_true')
args = parser.parse_args()
reports = []
unique = {}
released_path = STATE / 'released.json'
released = json.loads(released_path.read_text()) if released_path.exists() else []
for worker in range(1, 6):
    session = f'tdp43-{BATCH}-w{worker}'
    folder = STATE / f'w{worker}'
    folder.mkdir(parents=True, exist_ok=True)
    try:
        if worker not in released:
            subprocess.run([*CLI, 'exec', '-s', session, '-f', str(ROOT / 'scripts/probe_tdp43_multi.py'),
                            '--timeout', '120'], check=True, stdout=subprocess.DEVNULL, timeout=180)
            subprocess.run([*CLI, 'download', '-s', session, '/content/progress.json', str(folder / 'progress.json')],
                           check=True, stdout=subprocess.DEVNULL, timeout=90)
        report = json.loads((folder / 'progress.json').read_text())
        if worker not in released and (args.snapshots or report.get('accepted')):
            subprocess.run([*CLI, 'download', '-s', session, '/content/tdp43_snapshot.zip', str(folder / 'snapshot.zip')],
                           check=True, stdout=subprocess.DEVNULL, timeout=180)
        for row in report.get('accepted', []):
            sequences = [(key, value) for key, value in row.items() if key.startswith('Binder_Sequence')]
            if not sequences:
                raise ValueError('Accepted row lacks binder sequence; unique-count audit required.')
            sequence = sequences[0][1]
            unique.setdefault(sequence, {'worker': worker, **row})
        report['observed_at'] = time.time()
        reports.append(report)
        print(json.dumps({'worker': worker, 'state': report.get('state'), 'process_state': report.get('process_state'),
                          'trajectories': report.get('completed_trajectories'), 'accepted': len(report.get('accepted', [])),
                          'gpu': report.get('gpu'), 'log_tail': report.get('log_tail', '')[-1000:]}), flush=True)
    except Exception as error:
        previous = folder / 'progress.json'
        prior = json.loads(previous.read_text()) if previous.exists() else {'worker': worker}
        for row in prior.get('accepted', []):
            sequences = [value for key, value in row.items() if key.startswith('Binder_Sequence')]
            if sequences:
                unique.setdefault(sequences[0], {'worker': worker, **row})
        prior.update(observation_error=str(error), observation_failed_at=time.time())
        reports.append(prior)
        print(f'Worker {worker} observation failed: {error}', flush=True)
excluded_path = STATE / 'exclude_sequences.json'
excluded = set(json.loads(excluded_path.read_text())) if excluded_path.exists() else set()
unique = {sequence: row for sequence, row in unique.items() if sequence not in excluded}
aggregate = {'observed_at': time.time(), 'unique_passing_count': len(unique), 'unique_designs': list(unique.values()), 'workers': reports}
(STATE / 'progress.json').write_text(json.dumps(aggregate, indent=2))
if unique:
    fields = list(dict.fromkeys(key for row in unique.values() for key in row))
    with (STATE / 'passing_designs.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(unique.values())
print('UNIQUE PASSING DESIGNS:', len(unique), flush=True)

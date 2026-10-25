"""Keep collecting checkpoints until ten unique passing sequences are present.

Runs locally in a hidden process; does not claim final success or upload to
Drive. Final chat-side verification and connected Drive upload remain required.
"""
import csv
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BATCH = os.environ.get('TDP43_BATCH', 'ten')
TARGET_COUNT = int(os.environ.get('TDP43_TARGET_COUNT', '2'))
GOAL_COUNT = TARGET_COUNT * 5
STATE = ROOT / f'results/tdp43-{BATCH}'
lock = (STATE / 'supervisor.lock').open('a+b')
lock.seek(0)
lock.write(b'0')
lock.flush()
lock.seek(0)
if os.name == 'nt':
    import msvcrt
    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
else:
    import fcntl
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
released_path = STATE / 'released.json'


def heartbeat(**extra):
    record = {'pid': os.getpid(), 'updated_at': time.time(), **extra}
    (STATE / 'supervisor.json').write_text(json.dumps(record, indent=2))


while True:
    try:
        heartbeat(state='monitoring')
        subprocess.run([sys.executable, str(ROOT / 'scripts/monitor_tdp43_five.py'), '--snapshots'],
                       cwd=ROOT, timeout=1800, check=True)
        aggregate = json.loads((STATE / 'progress.json').read_text())
        released = json.loads(released_path.read_text()) if released_path.exists() else []
        recovery_path = STATE / 'recoveries.json'
        recoveries = json.loads(recovery_path.read_text()) if recovery_path.exists() else {}
        for worker in aggregate['workers']:
            index = worker['worker']
            if (index not in released and worker.get('state') == 'failed'
                    and worker.get('process_state') in ('Z', 'missing')
                    and not worker.get('observation_error')
                    and recoveries.get(str(index), 0) < 3):
                # The remote resume script rechecks terminal state before launch.
                snapshot = STATE / f'w{index}/snapshot.zip'
                with zipfile.ZipFile(snapshot) as archive:
                    if archive.testzip() is not None:
                        raise RuntimeError('Cannot recover from a corrupted checkpoint')
                recovery = subprocess.run([sys.executable, '-m', 'colab_cli.cli', 'exec',
                    '-s', f'tdp43-{BATCH}-w{index}', '-f', str(ROOT / 'scripts/resume_tdp43_multi.py'),
                    '--timeout', '120'], timeout=180)
                if recovery.returncode == 0:
                    recoveries[str(index)] = recoveries.get(str(index), 0) + 1
                    recovery_path.write_text(json.dumps(recoveries))
                continue
            if index in released or worker.get('state') != 'finished':
                continue
            # Verify the final downloaded snapshot contains the accepted table.
            snapshot = STATE / f'w{index}/snapshot.zip'
            with zipfile.ZipFile(snapshot) as archive:
                if archive.testzip() is not None:
                    raise RuntimeError(f'Worker {index} checkpoint corruption')
                table = '3_Ranked/!_Ranked.csv'
                rows = list(csv.DictReader(io.StringIO(archive.read(table).decode()))) if table in archive.namelist() else []
                if len(rows) != len(worker.get('accepted', [])):
                    raise RuntimeError(f'Worker {index} accepted table incomplete')
            result = subprocess.run([sys.executable, '-m', 'colab_cli.cli', 'stop', '-s', f'tdp43-{BATCH}-w{index}'], timeout=90)
            if result.returncode == 0:
                released.append(index)
                released_path.write_text(json.dumps(released))
        count = aggregate['unique_passing_count']
        if count >= GOAL_COUNT:
            heartbeat(state='passing_goal_ready_for_drive_verification', unique_passing_count=count)
            print(f'{count} unique passing designs ready for final Drive transfer.', flush=True)
            break
        if len(released) == 5:
            heartbeat(state='finished_below_unique_goal', unique_passing_count=count)
            print('All workers finished; requested unique count has not been achieved.', flush=True)
            break
        heartbeat(state='waiting', unique_passing_count=count,
                  attention_workers=[r['worker'] for r in aggregate['workers'] if r.get('state') == 'failed'])
        time.sleep(180)
    except Exception:
        traceback.print_exc()
        heartbeat(state='retrying_observation', error=traceback.format_exc())
        time.sleep(60)

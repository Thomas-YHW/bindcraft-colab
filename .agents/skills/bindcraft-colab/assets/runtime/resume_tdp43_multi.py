"""Resume only a terminal, failed worker; retain all campaign outputs."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

root = Path('/content/tdp43_campaign')
status = json.loads((root / 'worker_status.json').read_text())
record = json.loads(Path('/content/tdp43_multi_pid.json').read_text())
proc = Path(f"/proc/{record['pid']}/stat")
process_state = proc.read_text().split()[2] if proc.exists() else 'missing'
if status['state'] != 'failed' or process_state not in ('Z', 'missing'):
    raise RuntimeError('Resume requires authoritative evidence the old worker is terminal and failed.')
history = root / 'previous_failures'
history.mkdir(exist_ok=True)
stamp = str(int(time.time()))
shutil.copy2(root / 'worker_status.json', history / f'{stamp}.json')
shutil.copy2('/content/tdp43_worker.log', history / f'{stamp}.log')
env = os.environ.copy()
env['TDP43_WORKER'] = str(status['worker'])
config = json.loads((root / 'campaign.json').read_text())
env['TDP43_BATCH'] = config['campaign_name'].removeprefix('tdp43_').rsplit('_w', 1)[0]
env['TDP43_TARGET_COUNT'] = str(config['number_of_final_designs'])
env['TDP43_SEED_BASE'] = str(config['campaign_seed'] - status['worker'])
with open('/content/tdp43_worker.log', 'w') as log:
    process = subprocess.Popen([sys.executable, '-u', '/content/tdp43_multi_worker.py'],
                               stdout=log, stderr=subprocess.STDOUT, start_new_session=True, env=env)
Path('/content/tdp43_multi_pid.json').write_text(json.dumps({'pid': process.pid, 'worker': status['worker']}))
print('Resumed worker', status['worker'], 'PID', process.pid)

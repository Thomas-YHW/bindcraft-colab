import json
import os
from pathlib import Path
import subprocess
import sys

pid_file = Path('/content/tdp43_multi_pid.json')
if pid_file.exists():
    raise RuntimeError('Worker already submitted; inspect before restarting.')
with open('/content/tdp43_worker.log', 'w') as log:
    process = subprocess.Popen([sys.executable, '-u', '/content/tdp43_multi_worker.py'],
                               stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
pid_file.write_text(json.dumps({'pid': process.pid, 'worker': int(os.environ['TDP43_WORKER'])}))
print(pid_file.read_text())

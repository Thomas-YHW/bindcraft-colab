import csv
import json
from pathlib import Path
import subprocess
import zipfile

root = Path('/content/tdp43_campaign')
pid_path = Path('/content/tdp43_multi_pid.json')
report = json.loads(pid_path.read_text()) if pid_path.exists() else {'state': 'not_submitted'}
stat = Path(f"/proc/{report.get('pid', 0)}/stat")
report['process_state'] = stat.read_text().split()[2] if stat.exists() else 'missing'
status = root / 'worker_status.json'
if status.exists():
    report.update(json.loads(status.read_text()))
ranked = root / '3_Ranked/!_Ranked.csv'
rows = list(csv.DictReader(ranked.open())) if ranked.exists() else []
report['accepted'] = rows
trajectory = root / '1_Trajectories/!_Trajectories.csv'
report['completed_trajectories'] = len(list(csv.DictReader(trajectory.open()))) if trajectory.exists() else 0
log = Path('/content/tdp43_worker.log')
report['log_tail'] = log.read_text(errors='replace')[-1800:] if log.exists() else ''
report['gpu'] = subprocess.check_output(['nvidia-smi', '--query-gpu=name,utilization.gpu,memory.used', '--format=csv,noheader'], text=True).strip()
Path('/content/progress.json').write_text(json.dumps(report, indent=2))
# Snapshot campaign artifacts, excluding disposable compiled GPU graphs.
with zipfile.ZipFile('/content/tdp43_snapshot.zip', 'w', compression=zipfile.ZIP_DEFLATED) as archive:
    for path in root.rglob('*'):
        if path.is_file() and 'compile_cache' not in path.parts:
            archive.write(path, path.relative_to(root))
    if log.exists():
        archive.write(log, 'live_worker.log')
print(json.dumps(report, indent=2))

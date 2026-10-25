"""Independent Colab worker: continue until two designs pass unchanged filters."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import traceback
import time

WORKER = int(os.environ['TDP43_WORKER'])
BATCH = os.environ.get('TDP43_BATCH', 'ten')
TARGET_COUNT = int(os.environ.get('TDP43_TARGET_COUNT', '2'))
SEED_BASE = int(os.environ.get('TDP43_SEED_BASE', '2026102200'))
ROOT = Path('/content/BindCraft2')
OUTPUT = Path('/content/tdp43_campaign')
REVISION = 'b6fb3ae15ab6a702f1156cffc11bcc3323c2fd06'
OUTPUT.mkdir(exist_ok=True)
status = {'worker': WORKER, 'state': 'installing', 'started': time.time(), 'revision': REVISION}


def save_status():
    (OUTPUT / 'worker_status.json').write_text(json.dumps(status, indent=2))


def run(*args, **kwargs):
    print('+', ' '.join(args), flush=True)
    subprocess.run(args, check=True, **kwargs)


try:
    save_status()
    config = {
        'targets': [{'name': 'TDP43_IDR_274_414', 'target_path': '/content/tdp43_idr_274_414.fasta'}],
        'modality': 'binder', 'campaign_name': f'tdp43_{BATCH}_w{WORKER}',
        'campaign_seed': SEED_BASE + WORKER,
        'binder_lengths': [60, 100], 'crop_fasta_sequence': [20, 30],
        'validation_crop_flank': 5, 'number_of_final_designs': TARGET_COUNT,
        'desperation': False, 'project_folder': str(OUTPUT),
        'save_design_sequences': True, 'save_failed_refolds': True,
        'save_failed_trajectories': True,
    }
    requested = Path('/content/requested_campaign.json')
    if requested.exists():
        config = json.loads(requested.read_text(encoding='utf-8'))
        config['project_folder'] = str(OUTPUT)
    (OUTPUT / 'campaign.json').write_text(json.dumps(config, indent=2))
    inputs = [Path(target['target_path']) for target in config.get('targets', [])]
    inputs.append(Path('/content/provenance.json'))
    for source in inputs:
        shutil.copy2(source, OUTPUT / source.name)
    run('nvidia-smi')
    if not ROOT.exists():
        run('git', 'clone', 'https://github.com/PacesaLab/BindCraft2.git', str(ROOT))
    run('git', 'checkout', '--detach', REVISION, cwd=ROOT)
    env = os.environ.copy()
    env.pop('VIRTUAL_ENV', None)
    env.pop('CONDA_PREFIX', None)
    env['MPLBACKEND'] = 'Agg'
    run('bash', 'install.sh', cwd=ROOT, env=env)
    status['state'] = 'designing'
    save_status()
    run(str(ROOT / '.venv/bin/bindcraft'), 'design', str(OUTPUT / 'campaign.json'), cwd=ROOT, env=env)
    status['state'] = 'finished'
except BaseException as error:
    status.update(state='failed', error=str(error), traceback=traceback.format_exc())
    traceback.print_exc()
finally:
    status['ended'] = time.time()
    save_status()
    log = Path('/content/tdp43_worker.log')
    if log.exists():
        shutil.copy2(log, OUTPUT / 'worker.log')

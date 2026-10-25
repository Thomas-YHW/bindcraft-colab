"""Prepare and operate an isolated, five-worker BindCraft2 Colab campaign."""
import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import zipfile

SKILL = Path(__file__).resolve().parents[1]
CLI = [sys.executable, '-m', 'colab_cli.cli']


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, value):
    path.write_text(json.dumps(value, indent=2), encoding='utf-8')


def cli(*args, timeout=180):
    subprocess.run([*CLI, *map(str, args)], check=True, timeout=timeout)


def prepare(a, p):
    if p.exists() and any(p.iterdir()):
        raise ValueError('Preparation requires a new or empty directory; existing runs are not overwritten.')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,23}', a.name):
        raise ValueError('Use a lowercase alphanumeric batch name with optional hyphens, at most 24 characters.')
    if a.accepted <= 0 or a.accepted % 5:
        raise ValueError('This five-worker profile requires a positive goal divisible by five.')
    if a.max_trajectories is not None and a.max_trajectories <= 0:
        raise ValueError('Attempt budget must be positive.')
    source = Path(a.target_file).resolve() if a.target_file else SKILL / 'assets/tdp43_idr_274_414.fasta'
    fasta = source.suffix.lower() in {'.fasta', '.fa', '.faa'}
    if not source.is_file() or source.suffix.lower() not in {'.fasta', '.fa', '.faa', '.pdb', '.cif', '.mmcif'}:
        raise ValueError('Provide an existing FASTA, PDB or mmCIF target.')
    if not fasta and not a.chains:
        raise ValueError('Specify --chains for structured inputs.')
    overrides = read(Path(a.settings)) if a.settings else {}
    reserved = {'targets', 'target', 'project_folder', 'campaign_name', 'campaign_seed', 'number_of_final_designs', 'max_trajectories'}
    if reserved & overrides.keys():
        raise ValueError('Use preparation arguments for identity, target, quota, seed and budget.')
    excluded = read(Path(a.exclude)) if a.exclude else []
    if not isinstance(excluded, list) or any(not isinstance(s, str) for s in excluded):
        raise ValueError('Exclusions must be a JSON list of binder sequences.')
    gpus = a.gpus.split(',')
    if len(gpus) != 5 or any(g not in {'T4', 'L4', 'G4', 'A100', 'H100'} for g in gpus):
        raise ValueError('Supply five supported GPU names.')
    for folder in ['scripts', 'inputs', 'campaigns', f'results/tdp43-{a.name}']:
        (p / folder).mkdir(parents=True, exist_ok=True)
    for path in (SKILL / 'assets/runtime').glob('*.py'):
        shutil.copy2(path, p / 'scripts' / path.name)
    inp = p / 'inputs' / ('target_input' + source.suffix.lower())
    shutil.copy2(source, inp)
    target = {'name': a.target_name or ('TDP43_IDR_274_414' if not a.target_file else source.stem),
              'target_path': '/content/' + inp.name}
    if a.chains:
        target['chains'] = a.chains
    provenance = {'original_file': str(source), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
    if not a.target_file:
        provenance.update(accession='Q13148', residues=[274, 414], input_to_uniprot_offset=273,
                          source='https://rest.uniprot.org/uniprotkb/Q13148.fasta')
    write(p / 'inputs/provenance.json', provenance)
    write(p / f'results/tdp43-{a.name}/exclude_sequences.json', excluded)
    seed = a.seed_base if a.seed_base is not None else int(time.time()) % 2000000000
    workers = []
    for i, gpu in enumerate(gpus, 1):
        c = {'targets': [target], 'modality': 'binder', 'binder_lengths': [60, 100],
             'validation_crop_flank': 5, 'desperation': False, 'save_design_sequences': True,
             'save_failed_refolds': True, 'save_failed_trajectories': True, **overrides,
             'campaign_name': f'tdp43_{a.name}_w{i}', 'campaign_seed': seed+i,
             'number_of_final_designs': a.accepted//5, 'project_folder': '/content/tdp43_campaign'}
        if fasta:
            c.setdefault('crop_fasta_sequence', [20, 30])
        if not a.unbounded:
            c['max_trajectories'] = a.max_trajectories or 100
        write(p / f'campaigns/w{i}.json', c)
        workers.append({'worker': i, 'session': f'tdp43-{a.name}-w{i}', 'gpu': gpu})
    manifest = {'batch': a.name, 'accepted_goal': a.accepted, 'per_worker': a.accepted//5,
                'input_file': str(inp.relative_to(p)), 'seed_base': seed,
                'prepared_at': time.time(), 'workers': workers}
    write(p / 'campaign_manifest.json', manifest)
    print(json.dumps(manifest, indent=2))


def fetch(p, m):
    state = p / f"results/tdp43-{m['batch']}"
    dest = state / 'accepted'
    dest.mkdir(exist_ok=True)
    unique, excluded = {}, set(read(state / 'exclude_sequences.json'))
    for worker in m['workers']:
        snapshot = state / f"w{worker['worker']}/snapshot.zip"
        if not snapshot.exists():
            continue
        with zipfile.ZipFile(snapshot) as z:
            if z.testzip() is not None:
                raise ValueError('Corrupted snapshot: ' + str(snapshot))
            table = '3_Ranked/!_Ranked.csv'
            rows = list(csv.DictReader(io.StringIO(z.read(table).decode()))) if table in z.namelist() else []
            for row in rows:
                seq, name = row['Binder_Sequence'], row['design']
                if seq in unique or seq in excluded:
                    continue
                if Path(name).name != name or '/' in name or '\\' in name:
                    raise ValueError('Invalid design filename')
                (dest / f'{name}.cif').write_bytes(z.read(f'3_Ranked/{name}.cif'))
                unique[seq] = {'worker': worker['worker'], **row}
    rows = sorted(unique.values(), key=lambda r: float(r['i_pDAE']), reverse=True)
    if rows:
        fields = list(dict.fromkeys(k for row in rows for k in row))
        with (dest / 'passing_designs.csv').open('w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    (dest / 'passing_designs.fasta').write_text(''.join(f">{r['design']}\n{r['Binder_Sequence']}\n" for r in rows), encoding='utf-8')
    audit = {'unique_passing_count': len(rows), 'goal': m['accepted_goal'],
             'structures_verified': True, 'independent_refolding_performed': False}
    write(dest / 'audit.json', audit)
    output = p / f"{m['batch']}-results.zip"
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for path in state.rglob('*'):
            if path.is_file() and path.suffix in {'.zip', '.json', '.cif', '.csv', '.fasta'}:
                z.write(path, path.relative_to(state))
        z.write(p / 'campaign_manifest.json', 'campaign_manifest.json')
    print(json.dumps(audit), output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'launch', 'status', 'fetch', 'watch', 'resume', 'stop'])
    parser.add_argument('--project', required=True)
    parser.add_argument('--name', default='campaign')
    parser.add_argument('--accepted', type=int, default=10)
    for name in ['target-file', 'target-name', 'chains', 'settings', 'exclude']:
        parser.add_argument('--' + name)
    parser.add_argument('--gpus', default='T4,T4,T4,L4,L4')
    parser.add_argument('--seed-base', type=int)
    budget = parser.add_mutually_exclusive_group()
    budget.add_argument('--max-trajectories', type=int)
    budget.add_argument('--unbounded', action='store_true')
    parser.add_argument('--worker', type=int, choices=range(1, 6))
    a = parser.parse_args()
    p = Path(a.project).resolve()
    if a.action == 'prepare':
        prepare(a, p)
        return
    m = read(p / 'campaign_manifest.json')
    env = {**os.environ, 'TDP43_BATCH': m['batch'], 'TDP43_TARGET_COUNT': str(m['per_worker'])}
    if a.action == 'launch':
        for w in m['workers']:
            if w.get('submitted') or w.get('submission_unknown'):
                print('Already submitted or requires inspection:', w['session'])
                continue
            session = w['session']
            try:
                cli('new', '-s', session, '--gpu', w['gpu'], timeout=240)
                cli('status', '-s', session)
                w['allocated'] = True
                for local, remote in [('scripts/tdp43_multi_worker.py', '/content/tdp43_multi_worker.py'),
                                      (m['input_file'], '/content/' + Path(m['input_file']).name),
                                      ('inputs/provenance.json', '/content/provenance.json'),
                                      (f"campaigns/w{w['worker']}.json", '/content/requested_campaign.json')]:
                    cli('upload', '-s', session, p / local, remote)
                w['submission_unknown'] = True
                write(p / 'campaign_manifest.json', m)
                cli('exec', '-s', session, '-f', p / 'scripts/start_tdp43_multi.py',
                    '--env', f"TDP43_WORKER={w['worker']}", '--env', f"TDP43_BATCH={m['batch']}",
                    '--env', f"TDP43_TARGET_COUNT={m['per_worker']}", '--timeout', '120')
                w.update(submitted=True, submission_unknown=False)
            except Exception as error:
                w['error'] = str(error)
                if w.get('allocated') and not w.get('submission_unknown'):
                    cli('stop', '-s', session)
            finally:
                write(p / 'campaign_manifest.json', m)
    elif a.action in {'status', 'fetch', 'watch'}:
        script = 'supervise_tdp43_five.py' if a.action == 'watch' else 'monitor_tdp43_five.py'
        subprocess.run([sys.executable, str(p / 'scripts' / script), *([] if a.action == 'watch' else ['--snapshots'])],
                       cwd=p, env=env, check=True)
        if a.action == 'fetch':
            fetch(p, m)
    elif a.action == 'resume':
        if a.worker is None:
            parser.error('resume requires --worker')
        cli('exec', '-s', m['workers'][a.worker-1]['session'], '-f', p / 'scripts/resume_tdp43_multi.py', '--timeout', '120')
    elif a.action == 'stop':
        for w in ([m['workers'][a.worker-1]] if a.worker else m['workers']):
            cli('stop', '-s', w['session'])


if __name__ == '__main__':
    main()

# BindCraft Colab Operator

Run reproducible BindCraft2 binder-design campaigns on five Google Colab GPUs,
monitor and recover workers, and fetch accepted sequences and predicted complexes.
Includes a reusable Codex skill and a source-recorded human TDP-43 IDR example.

Each user runs on their own Colab account. This repository distributes an operator
workflow; it is not a hosted protein-design service. BindCraft2 is downloaded at a
pinned revision on the remote VMs. See [NOTICE](NOTICE.md) for its separate license.

## Requirements

- Python 3.12 or newer on Windows or Linux.
- Git and a Google Colab account with suitable GPU availability/compute units.
- About 20 GB of disk on each remote runtime for dependencies and weights.
- A local computer that stays running for background supervision.

The controller uses only Python's standard library plus the Colab CLI. CUDA and
the protein-design dependencies are installed remotely, not on your computer.

## Install

```sh
git clone https://github.com/Thomas-YHW/bindcraft-colab.git
cd bindcraft-colab
python -m venv .venv
```

Activate the environment on Windows PowerShell:

```powershell
.venv/Scripts/Activate.ps1
```

Or on Linux:

```sh
source .venv/bin/activate
```

Then install the tested CLI version and authenticate interactively:

```sh
python -m pip install -r requirements.txt
python -m colab_cli.cli sessions
```

Complete the Google sign-in flow in your own browser/terminal. Credentials stay
with your local Colab CLI. No credentials, campaign results or model weights are
distributed in this repository.

## Prepare a campaign locally

```sh
python pipeline.py prepare --project runs/tdp43-demo --name tdp43-demo --accepted 10 --max-trajectories 100
```

This creates five worker JSON files, requesting two accepted designs per worker.
It does not allocate GPUs. Review `runs/tdp43-demo/campaign_manifest.json` and
`runs/tdp43-demo/campaigns/w*.json` before launching.

The included example uses canonical human TDP-43 (UniProt Q13148) residues
274–414, sampled as 20–30-residue FASTA windows. Binders are 60–100 residues.
Desperation mode is disabled to keep acceptance thresholds fixed.

For a custom structured target:

```sh
python pipeline.py prepare --project runs/custom --name custom --accepted 10 --target-file /path/to/target.pdb --target-name my_target --chains A
```

For a custom sequence/IDR, provide a `.fasta` target file instead. `--settings`
accepts a JSON file for explicit BindCraft setting overrides. This five-worker
profile requires an accepted count divisible by five. For additional designs,
use `--exclude previous_sequences.json` with a JSON list of prior binder sequences.

An explicitly desired campaign without an attempt cap can be prepared with:

```sh
python pipeline.py prepare --project runs/tdp43-50 --name tdp43-50 --accepted 50 --unbounded
```

That goal may take substantial compute and is not a guarantee of convergence.
Do not launch it until you intend to incur those charges. The default GPU plan is
`T4,T4,T4,L4,L4`; change it with `--gpus` if supported by your account.

## Launch and monitor

```sh
python pipeline.py launch --project runs/tdp43-demo
python pipeline.py status --project runs/tdp43-demo
python pipeline.py watch --project runs/tdp43-demo
```

Launch allocates billable runtimes. Workers install the pinned upstream package,
download model weights, and run the native design CLI concurrently. The watcher
downloads snapshots, counts unique accepted sequences, performs up to three guarded
recoveries of confirmed failed processes, and releases finished workers after
verifying their local checkpoints. It does not automatically replace a lost VM.

`watch` stays in the foreground. For background operation, use your normal process
supervisor; on Windows launch a hidden `Start-Process`, or on Linux use `nohup`.
Only one watcher should operate on a campaign. Keep the computer running.

Check `supervisor.json`, logs and native ranked records under
`runs/<project>/results/tdp43-<batch>/`. A timeout is not proof that a worker died.
If a launch records `submission_unknown`, inspect that runtime before resubmitting.

## Fetch, resume and stop

```sh
python pipeline.py fetch --project runs/tdp43-demo
python pipeline.py resume --project runs/tdp43-demo --worker 3
python pipeline.py stop --project runs/tdp43-demo
```

Fetch produces `<batch>-results.zip`, CSV/FASTA files and accepted mmCIF structures.
It verifies saved acceptance records and matching structures; it does not run a
new independent AlphaFold validation. Resume is guarded and refuses a live worker.
Stop can target one worker with `--worker N` or all workers in that manifest.

Drive delivery is agent-managed: use the connected Google Drive tools to upload
the fetched ZIP, then verify the returned metadata/link. The local watcher saves
local checkpoints; it does not silently upload to Drive or mount your Drive.

## Use as a Codex skill

The repository includes `.agents/skills/bindcraft-colab/`. When working in this
repository, invoke:

> $bindcraft-colab Prepare a five-runtime TDP-43 campaign for 50 additional passing designs, then launch and monitor it using my authorized compute budget.

The skill includes target provenance, validation semantics, authentication and
recovery guidance. It does not itself grant permission to spend compute. You can
also copy that folder into your personal Codex skills directory to reuse it elsewhere.

## Validation and tests

See [the pinned validation algorithm](.agents/skills/bindcraft-colab/references/validation.md).
Passing confidence/geometry filters does not establish experimental binding,
affinity or specificity. IDR complexes contain predicted co-folded fragments,
not the entire full-length protein.

Run the offline controller checks without credentials or GPUs:

```sh
python -m unittest discover -s tests -v
```

The tests cover preparation, identity/quotas, overwrite protection, structured-input
handling, deduplication, prior-sequence exclusion and result packaging. Remote GPU
execution depends on the user's Colab account and is not performed by CI.

Upstream: https://github.com/PacesaLab/BindCraft2

Pinned revision: `b6fb3ae15ab6a702f1156cffc11bcc3323c2fd06`.

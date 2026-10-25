# Operating the packaged workflow

## Prepare without spending compute

Run helpers with a Python that can import `colab_cli`; in the original environment
this is `python`, not the Windows Store `python` alias.

```powershell
python <skill>/scripts/campaign.py prepare --project runs/example --name example --accepted 50 --max-trajectories 100
```

The output directory must be new or empty. Preparation copies portable runtime
helpers, target input and provenance, and writes `campaign_manifest.json` plus
five worker JSON files. It does not authenticate, allocate, launch or modify the
established project's live campaigns. A custom `--target-file` can be FASTA,
PDB or mmCIF; structured inputs require `--chains`. Use `--settings <JSON>` for
explicit BindCraft overrides such as binder modality, length and properties.
Default FASTA crops are 20–30 residues; use `crop_fasta_sequence=false` in
settings to co-fold the supplied sequence without sampling windows.

Specify `--exclude <JSON>` with a list of previous binder sequences when
requesting additional designs. The five-worker profile divides the accepted
count equally, so the count must be divisible by five. Other worker counts or
uneven allocations require adapting the controller explicitly. Distinct seeds
are generated and recorded. Default per-worker attempt cap is 100; an approved
open-ended task can be prepared with `--unbounded`. Budget exhaustion is an
incomplete design goal, not a failure of the result-transfer workflow.

Review all five JSON files and the manifest. In particular, confirm target,
chain selections, modality, expected accepted count, attempts and filters.
Pin the revision/checkpoints; do not silently update upstream during a run.

## Authenticate and launch

Inspect installed CLI help, `colab sessions`, and `colab usage` before allocation.
For login, run `colab sessions` interactively in the user's own terminal or a
persisted PTY with user participation. OAuth needs consent; never bundle or
print cached tokens. CLI authentication is different from VM-side `colab auth`.
Do not use an interactive REPL, console or Drive mount from a noninteractive
agent loop. A Google OAuth error is not proof the account lacks GPU access.

```powershell
python <skill>/scripts/campaign.py launch --project <prepared-dir>
```

Launch is the billable action and needs task authorization. Each worker installs
on Linux, downloads about 5.3 GB of AlphaFold weights, then runs the official
`bindcraft design` CLI. Allow roughly 20 GB of remote disk. All five workers
overlap, but launch and installation are not a synchronized design-step barrier.
T4/T4/T4/L4/L4 worked for this account; entitlement and capacity must be rechecked.

If submission times out, the manifest records `submission_unknown`; revalidate the
existing runtime PID before resetting that flag. Do not blindly run launch twice.
Allocation refusal, CLI failures and a new runtime are distinct states. A skill
installation or a previous account balance is not ongoing approval for new jobs.

## Observe and supervise

`status` fetches reports and snapshots; `watch` repeats this and runs until the
native workers finish or their unique accepted goal is reached. Start `watch`
as a hidden local process on Windows when sustained supervision is requested:

```powershell
Start-Process -FilePath python -ArgumentList '<skill>/scripts/campaign.py','watch','--project','<prepared-dir>' -WindowStyle Hidden -RedirectStandardOutput '<prepared-dir>/watch.log' -RedirectStandardError '<prepared-dir>/watch.err.log'
```

Quote paths containing spaces with a tested argv representation. The machine must
remain on and connected. `supervisor.json` is a heartbeat; verify the actual PID
and current Colab assignment when it is stale. A file alone is not a live job.
The watcher uses a single-instance lock, retains checkpointed accepted rows on
observation failure and does not recreate workers just because a request times out.
It stops a completed bounded worker even if that worker did not reach its quota,
and records `finished_below_unique_goal` rather than claiming success.

## Recover

Use `resume --worker N` only after the previous remote worker is terminal and
failed. The remote script checks status and `/proc` again, archives failed logs,
and reuses campaign output and settings. The watcher allows at most three such
technical recoveries. A killed process may be a memory problem; diagnose the
actual logs, memory and compiled shapes before repeating resource failures.

If the VM is gone, a local checkpoint is not a running session. Allocate a new
authorized runtime, upload its snapshot, inspect ZIP entries before extracting
within `/content/tdp43_campaign`, restore inputs/config, and resume using the native
campaign settings. Preserve the campaign identity and distinguish recovery from
a new seed/batch. Never discard accepted candidates to make a restart easy.

Known environment fixes:

- Set `MPLBACKEND=Agg` in the separate BindCraft subprocess. Colab's inherited
  notebook backend is not installed in its venv.
- Remove inherited `VIRTUAL_ENV` and `CONDA_PREFIX` before the official installer.
- Invoke CLI with `python -m colab_cli.cli` on Windows, not a launcher executable
  whose Python child can survive timeout termination.
- When stopping a local monitor, identify its exact PID/command first. Never
  stop remote design processes to fix a local observation connection.

## Fetch, validate and save

`fetch` refreshes native snapshots, checks ZIP integrity and accepted-structure
presence, deduplicates sequences, writes CSV/FASTA/audit files and packages a ZIP.
It reads acceptance records; it does not run a new AlphaFold validation. Scores
are usually rounded in tables. Read `validation.md` before interpreting cutoffs.

Save through the available Google Drive connector, using its skill and supported
file-reference argument. Verify metadata/size after upload and expose actual
returned links. Upload a new version of an existing checkpoint only after grounding
its file ID. The local watcher is not wired to the connector; do not promise
unattended Drive uploads. The Colab OAuth application's Drive API returned 403
for this project, while connected Drive uploads worked. Do not enable a quota
project, change API settings or extract connector credentials to work around it.

Snapshots exclude compiled GPU caches. Do not distribute OAuth/session caches,
refresh tokens, account balances, or model weights with the skill or result ZIP.
Release completed runtimes after their output is verified locally; a failed
download warrants preserving the runtime for recovery and reporting its name.

Source: https://github.com/PacesaLab/BindCraft2
Pinned revision: b6fb3ae15ab6a702f1156cffc11bcc3323c2fd06

---
name: bindcraft-colab
description: Run and manage BindCraft2 protein binder design campaigns on Google Colab GPUs, including the TDP-43 IDR project, parallel workers, validation, recovery, result fetching, and Drive delivery. Use for actual binder-design workflows, not generic protein questions or unrelated notebooks.
---

# BindCraft Colab

Act as campaign operator: prepare inputs, launch authorized compute, monitor real
processes, recover checkpoints, verify accepted candidates and deliver results.
The skill supplies the workflow; the calling agent and Colab CLI execute it.

## Select context

- Established project: read [project-context.md](references/project-context.md).
  Inspect current manifests, logs and assignments. Historical counts are not live state.
- New campaign: read [operations.md](references/operations.md) and use
  `scripts/campaign.py`. The portable profile has five workers with equal quotas;
  accepted-design counts must be divisible by five. Adapt other layouts explicitly.
- Acceptance decisions: read [validation.md](references/validation.md). Its
  thresholds describe this binder/IDR profile, not every BindCraft modality.

## Operating invariants

1. Ground the target sequence/structure, chains or IDR range, modality, accepted
   count and GPU plan. Reuse known inputs and record provenance for new targets.
2. Prepare a reviewable campaign before seeking missing authorization. Packaging
   this skill does not authorize new billable jobs. Honor existing session approval;
   historical project approval is not blanket approval for future tasks. If automatic
   review rejects an operation, report its reason and obtain the required approval;
   do not bypass it through another launcher.
3. Check `colab sessions` and `colab usage`. Use supported GPU names, distinct
   runtime names and separate output folders. Capacity fallback is not permission
   to circumvent account quotas. Use distinct seeds and preserve fixed filters.
4. Submission, live execution and acceptance are different states. Inspect process
   state, job status, logs, ranked records and downloaded structures. Observation
   timeout is not termination. Resume only a confirmed terminal failed worker;
   preserve logs and outputs. Limit automatic technical recovery to three attempts
   per worker, then investigate instead of repeatedly recreating failed compute.
5. Count unique binder sequences in native accepted records; exclude previous
   batches for additional designs. Verify each accepted complex exists. Rounded
   CSV checks do not reproduce independent refolding. Keep desperation disabled
   for this fixed-filter project; never lower cutoffs to manufacture passes.
6. Fetch checkpoints before releasing completed workers. Preserve local artifacts,
   use connected Drive tools for requested delivery, and verify metadata readback.
   The local supervisor cannot call chat connector tools and does not auto-upload.
   Never bundle tokens, credentials, account session stores, or model weights.
7. Report accepted/goal count, worker states, actual artifact links and remaining
   work. Completion requires the requested unique count and verified delivery;
   confidence is not experimentally established binding or measured affinity.

## Helpers

Use an activated Python environment containing `google-colab-cli`. Invoke the
module directly to avoid Windows executable
wrappers orphaning child clients when an observation times out.

```text
python <skill>/scripts/campaign.py prepare --project <new-empty-dir> --name <batch> --accepted 50
python <skill>/scripts/campaign.py launch --project <dir>
python <skill>/scripts/campaign.py status --project <dir>
python <skill>/scripts/campaign.py fetch --project <dir>
python <skill>/scripts/campaign.py watch --project <dir>
python <skill>/scripts/campaign.py resume --project <dir> --worker 3
python <skill>/scripts/campaign.py stop --project <dir>
```

Preparation is local. Launch spends compute. Default input is bundled TDP-43 IDR;
use `--target-file`, `--target-name`, structured-input `--chains`, and `--settings`
for other targets. Review generated JSON before launch. Default attempt budget is
100 per worker; `--max-trajectories` changes it and `--unbounded` explicitly removes
it from the prepared campaign, without granting external authorization.

Visualize actual saved coordinates, identify binder chains by sequence, and label
predicted target fragments correctly. The established visualization code and
outputs are mapped in the project reference.

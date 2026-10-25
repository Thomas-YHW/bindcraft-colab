# Portable project profile

This public distribution contains a reusable controller and skill, not a copy of
an account's running campaigns. Inspect the selected project's manifest and live
Colab assignments rather than assuming any runtime names or design counts.

Default example: human TDP-43/TARDBP, UniProt Q13148, residues 274–414 (141 aa).
Input coordinate +273 maps to the canonical sequence. The bundled FASTA is
source-recorded by the preparation helper. Source:
https://rest.uniprot.org/uniprotkb/Q13148.fasta

The binder profile samples 20–30-residue target windows, adds up to five flanking
residues per side during validation, and designs 60–100-residue binders. It keeps
desperation disabled. Validation uses separate model_1_ptm/model_2_ptm weights,
three recycles, and the pinned filter implementation in validation.md.

New isolated projects are prepared through `scripts/campaign.py`; see operations.md.
The repository's `pipeline.py` is a convenience entry point. Files under `runs/`
and generated outputs should remain untracked. Existing campaign adoption requires
grounding its actual inputs, identity, source revision, snapshots and permissions.

No account credentials, past compute approvals, private Drive IDs, experimental
results or live session records are provided by this skill. Each user authenticates
with their own Colab account and authorizes their intended compute usage.

# BindCraft2 validation algorithm for this TDP-43 campaign

This describes the actual pinned campaign, not a universal set of cutoffs for
every BindCraft modality. Revision: b6fb3ae15ab6a702f1156cffc11bcc3323c2fd06.
Thresholds and model selections were checked against campaign_metadata.json
inside the saved worker snapshots and against the pinned source code.

## Pipeline

1. Supply the canonical TDP-43 IDR 274–414 as FASTA. Each trajectory samples a
   20–30-residue target window and co-folds it with a 60–100-residue binder.
2. Optimize with the design ensemble model_1_multimer_v3 through
   model_5_multimer_v3. Stop failing trajectories at stage gates below.
3. For a successful hallucination, generate up to ten ProteinMPNN redesign
   candidates using the negative/v_48_020 weights. This campaign preserves the
   interface during redesign (redesign_interface=false).
4. Restore up to five target residues on each side of the sampled window for
   validation. Independently predict the complex and the binder-alone state
   using model_1_ptm and model_2_ptm, with three validation recycles.
5. Require each model to pass the configured confidence checks. Evaluate the
   full filter set on the ensemble prediction. Any mandatory missing metric or
   failed threshold rejects the candidate.
6. Rank accepted candidates by descending i_pDAE. Up to three passing redesigns
   may terminate candidate testing early; retain the best one per trajectory.
   For the combined campaign, deduplicate accepted candidates by binder sequence.

## Early design gates

| Stage | Binder pLDDT minimum | i_pTM minimum |
| --- | --- | --- |
| screen | 0.60 | none |
| refine | 0.60 | none |
| anneal | 0.65 | 0.50 |
| harden | 0.65 | 0.50 |
| mutate | 0.60 | 0.50 |
| final | 0.70 | 0.70 |

These are computational screening gates before final redesigned-sequence
validation. A trajectory passing them is not yet an accepted final design.

## Final mandatory checks

| Metric | Pass rule | Meaning |
| --- | --- | --- |
| pLDDT | >= 0.70 | Mean bound-binder confidence |
| Unbound_Binder_pLDDT | >= 0.70 | Binder-alone fold confidence |
| Target_pLDDT | >= 0.60 | Confidence of the co-folded target fragment |
| pTM | >= 0.55 | Complex geometry confidence |
| i_pTM | >= 0.70 | Interface confidence |
| i_pAE | <= 0.35 | Mean interface PAE / 31 Angstrom; about 10.85 Angstrom |
| Interface_Residues | >= 7 | Binder residues with any atom within 4 Angstrom of target |
| Backbone_Clashes | = 0 | Interchain CA atom pairs at <= 2.5 Angstrom |
| Binder_RMSD | <= 3.5 Angstrom | Aligned binder CA RMSD between bound and binder-alone predictions |

The per-model confidence checks apply to pLDDT, Unbound_Binder_pLDDT,
Target_pLDDT, pTM and i_pTM. Other full-filter checks are evaluated on the
ensemble prediction: prediction metrics are averaged across models, while its
representative atomic coordinates come from the first evaluated model. This
is not a requirement that every geometry filter passes independently in both
model structures. Validation can terminate early when failure is already
unavoidable.

## Pseudocode

```python
for hallucination in design_trajectories:
    if fails_any_enabled_design_stage_gate(hallucination):
        continue

    accepted = []
    for sequence in distinct_mpnn_redesigns(hallucination, maximum=10):
        states = complex_with_restored_target_flanks_and_binder_alone(sequence)
        model_predictions = {}
        failed = []

        for model in ["model_1_ptm", "model_2_ptm"]:
            prediction = alphafold_predict(states, model=model, recycles=3)
            model_predictions[model] = prediction
            failed += failed_confidence_filters(prediction)
            if failed:
                break
            if full_filter_success_is_already_unreachable(model_predictions):
                break

        ensemble = mean_prediction_metrics_with_first_model_coordinates(model_predictions)
        failed += failed_full_filters(ensemble)  # AND of all mandatory rules

        # Each enabled metric: missing mandatory => fail;
        # higher=True => measured >= threshold; otherwise measured <= threshold.
        # NaN comparisons do not pass.
        if not failed:
            accepted.append(sequence_with_metrics_and_structure(sequence, ensemble))
            if len(accepted) >= 3:
                break

    keep_best(accepted, count=1, descending_metric="i_pDAE")
```

## Interpretation and additional checks

- i_pDAE is a distance-masked interface-confidence ranking score, with an
  8-Angstrom contact cutoff by default. This campaign has no minimum i_pDAE gate.
- All_Atom_Clashes, surface hydrophobicity, mass, charge, cysteines and other
  descriptors are recorded but do not have restrictive acceptance thresholds
  in this campaign. Backbone_Clashes=0 does not establish all-atom clash freedom.
- Target_Crop_Length is recorded; this campaign has no positive minimum-length
  acceptance gate beyond constructing the sampled window and validation flanks.
- Desperation mode is disabled. Acceptance cutoffs are not automatically lowered.
- Use unrounded model measurements for exact boundary decisions. A CSV value
  printed as 0.70 may be slightly below or above the 0.70 threshold. A table-only
  check cannot reproduce the complete refolding and per-model validation.
- These scores do not establish affinity, specificity, expression, or biological
  accessibility. For an IDR, assess the predicted pose in full-length TDP-43
  context and test binding experimentally; fragment co-folding does not validate
  recognition of every physiological TDP-43 conformational state.

## Sources

- Lab overview: https://www.pacesalab.com/bindcraft
- Pinned filters and comparison rules:
  https://github.com/PacesaLab/BindCraft2/blob/b6fb3ae15ab6a702f1156cffc11bcc3323c2fd06/bindcraft/filters.py
- Pinned redesign and ensemble validation:
  https://github.com/PacesaLab/BindCraft2/blob/b6fb3ae15ab6a702f1156cffc11bcc3323c2fd06/bindcraft/MPNN_stage.py
- Pinned metric definitions:
  https://github.com/PacesaLab/BindCraft2/blob/b6fb3ae15ab6a702f1156cffc11bcc3323c2fd06/docs/source/outputs.md
- Local authoritative run settings: campaign_metadata.json inside each
  results/tdp43-ten/w*/snapshot.zip.

This document explains the algorithm; it does not claim a new independent
AlphaFold validation run has been executed.

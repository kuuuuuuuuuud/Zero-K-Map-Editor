# TPL-canyon_network-1 handoff

## Delivery

- Template: `canyon_network` / Canyon Network.
- Files: `atlasforge/templates/canyon_network.py`, `tests/test_template_canyon_network.py`, this handoff, a patch against Core `e283112`, and the preview, thumbnail, contact sheet and quick report.
- Source was developed in local snapshot `571d63c`, reconciled from Core `397122d`. Read-only inspection confirmed Core `main` and `origin/main` are at `e283112`; the template pipeline, design, terrain, checks and workflow files used here are unchanged between `397122d` and `e283112`.
- Baseline hashes: both Python files are new in `e283112`, so no prior file hashes exist. `docs/TEMPLATE_BACKLOG.md` is a workspace-only file absent from Core `e283112`; its status row is updated locally and is not part of the Core patch.
- Registry import, final registration and watermark ID remain for the core integration owner.

## Design

Seeded long ravines divide the map into parallel fronts. Deliberate, seeded cross-links connect neighbouring routes. The `branching`, `parallel` and `fan` forms change the main corridor geometry; the canyon width, main-canyon count and cross-link count are adjustable. Standard starts, resources and tank-ramp carving come from the private wildlands pipeline.

## Verification performed

- `pytest tests/test_template_canyon_network.py -q` in an isolated Core `e283112` scratch snapshot with this template overlaid: **5 passed**.
- `python -m tools.template_workflow check canyon_network --level quick` in the same Core `e283112` scratch snapshot: **PASS**, default seed 1; all five movement classes reach the enemy and all 38 metal spots are tank-reachable.
- Preview inspected at 1024 px. The map reads as a canyon network and the seed changes its shape. Ramps and route convergence around the centre need focused QA review.
- No full suite, parameter matrix, seed 1–10 run, archive export or Zero-K in-game test was performed.

## QA request

Run the full default seed set and safe parameter matrix on the current Core snapshot. Check tank, bot, spider, amphibian and hover connectivity across route and form variants; confirm that seed changes visibly alter the network; inspect the central convergence and ramp transitions; then report any gameplay or visual failures. Keep the expensive suite and matrix on QA as assigned.

## Integration notes

- Required integration base: current Core `e283112` or newer, as specified in SCU-14. The patch and focused test were checked against an isolated `e283112` snapshot; QA should run the full matrix on current Core.
- Core integration still needs to add the import and registry entry and assign the final watermark ID.
- No shared core modules were modified.

## Suggested ROADMAP.md row

`canyon_network` — Add a seeded branching canyon network with parallel routes and controlled cross-canyon links; verify movement-class reachability and seed variation.

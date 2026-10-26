# Chicken Mesa template handoff

## Design

`chicken_mesa` adds a co-op defence layout around one irregular, raised central mesa. Multiple long ramps approach from the surrounding lowlands, and the team can retreat to a shared central position. Metal expansion and geothermal vents are outside the mesa. The seed changes the summit outline, ramp bearings and lowland relief. The template has no custom Mex, Geo, wind, tree, rock, wreck or erosion controls.

## Scope and integration

- New source: `atlasforge/templates/chicken_mesa.py`
- New focused tests: `tests/test_template_chicken_mesa.py`
- Ownership recorded under this workspace's `docs/TEMPLATE_BACKLOG.md` (SCU-13; not part of the Core patch)
- No registry, watermark or shared-core changes. Lead must add the import and registry entry and allocate the final watermark ID.
- Patch targets Core `c9cf17f` (with requested `e283112` as an ancestor). The template's required shared interfaces have no changes between Core `397122d` and `c9cf17f`.

## Baseline hashes

Baseline at Core `c9cf17f`:

| Path | SHA-256 |
|---|---|
| `atlasforge/templates/__init__.py` | See `BASELINE_HASHES.txt` in the delivery package |
| `atlasforge/templates/chicken_mesa.py` | Absent |
| `tests/test_template_chicken_mesa.py` | Absent |

## Verification

- Focused tests: `pytest -q -p no:cacheprovider tests/test_template_chicken_mesa.py` — **3 passed**.
- Workflow quick check: `python -m tools.template_workflow check --level quick --mode coop --out <dir> chicken_mesa` — **PASS**, default seed 1; deterministic generation and preview creation included.
- Preview inspected at 1024 px. The mesa has visible surface relief, three distinct broad ramp approaches, and resources outside its rim.
- No full seed 1–10, advanced-parameter matrix, archive build or game test was run.

## QA request

Please run the full cooperative validation for seeds 1–10 and every advanced parameter boundary. Check that ground units reach all starts and exterior metal through the intended ramp network, that resources remain reachable and clear of ramp footprints, and that ramp approaches stay usable at the smallest supported map size and highest mesa setting. Review the included preview/contact sheet and export/build one default map if the checks pass. Report any failing configuration and retain the generated report with the task.

## Open integration items

1. Register the template and assign its permanent watermark ID in the Core workspace.
2. Run QA's requested full matrix, then the Core release and game checks.

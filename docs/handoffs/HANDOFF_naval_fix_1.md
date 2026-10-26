# TPL-naval-fix-1: smooth naval shore joins

## Result

Naval island components are combined with a polynomial smooth-min (320 elmos) before one plateau evaluation, including reflected geometry. Shore tops use round_=96 and feet toe=48. This removes intersecting independently built flanks and avoids introducing a new contact at the mirror axis.

Open Sea, Archipelago and Straits use a broad deep-water-only filter (640 elmos), protecting all heights >= -20 and all port discs of radius 500. Coastal Front uses broad prefiltered shore noise and a 1024-elmo shelf blend. Atoll uses its combined ring/home shape without a broad sea-floor filter, preserving lagoon entrances; its entrance and bypass cuts now also use round_=96 / toe=48.

The latest Core mex distribution, minimum gap max(300, 0.06*W), sea/land fallback and min(count, 6) acceptance remain unchanged. The six opening spots are now explicitly fixed for the general resource control.

## Base and ownership

Base: CORE-20261022-1930 (main 7c66ad73c1643de1d601601abd673f764736cf4e), plus CORE-20261022-2000-ffa.tgz. The changed naval files are identical in both published bases. Registry, watermark, checks, terrain and all other shared core sources are excluded. No locks or edits were made in atlas-map-forge.

## Validation

Full source-suite regression: 319 passed, 3 deselected in 951.27s (0:15:51); local HTTP app tests: 3 passed.
Regression revision: naval-fix-before-cut-polish (bd883fb), before the final two-line Atoll entrance/bypass rounding. Final Atoll is rechecked separately: 29 tests passed (all its existing tests, ten join/route/economy seeds and both general-resource combinations), and its complete parameter matrix was rerun. Every other source file is unchanged from the full regression.
Targeted join/economy suite: 62 passed before that final Atoll polish; its 12 Atoll-specific cases are included in the 29 final checks. The synthetic hard-V regression fails the metric by >20x, demonstrating that the criterion detects an actual crease.

| Template | Matrix cases | Max seam ratio | Max flank ratio | Design timings |
|---|---|---|---|---|
| open_sea | 74 | 0.257 | 0.183 | [{'size': 12, 'seconds': 0.244}, {'size': 20, 'seconds': 0.735}] |
| archipelago | 78 | 0.092 | 0.495 | [{'size': 12, 'seconds': 0.473}, {'size': 20, 'seconds': 1.468}] |
| straits | 78 | 1.311 | 0.491 | [{'size': 12, 'seconds': 0.403}, {'size': 20, 'seconds': 1.041}] |
| coastal_front | 74 | 1.252 | N/A: no above-seabed flank intersection | [{'size': 12, 'seconds': 0.492}, {'size': 20, 'seconds': 1.324}] |
| atoll | 78 | 0.070 | 0.673 | [{'size': 12, 'seconds': 0.368}, {'size': 20, 'seconds': 1.167}] |

Total: 382 cases. All default seeds 1-10 and tested safe settings are playable. Advanced-only gameplay failures remain inspectable and are listed in each exact report.

Metric: mean absolute one-sample second height difference across the join, divided by its mean at offsets 40, 44, 48, 52, 56 and 60 cells on both sides. Only submerged triples (< -30) outside building/resource pads count, with at least six valid reference triples per join sample. Contact lines come from the unsmoothed component geometry, excluding intersections already below the original sea floor. Coastal Front has a mainland and a separate submerged shelf, with no above-seabed intersection at defaults: this is explicitly N/A, never a fabricated passing ratio.

See acceptance-final.json for all 50 seed checks, sample counts and exact statistics. General controls test mex_count 6/20 and geos 0/3 for all five templates; every opening spot remains protected.

## Visual review

Seed 1 and 2 previews and native 1:1 crop sheets inspected for all five templates. Each crop pixel is one height sample (8 elmos), with height shading independent of the normal minimap shader. Crops show the mirror axis, a flank contact (or the mainland/shelf gap), and an upper beach. The Atoll cuts were further rounded after the first visual review; final crops and final checks are included.
No map has been loaded or played in Zero-K. The atoll still has deliberately straight entrance geometry; its intersecting slope profiles are smoothly blended rather than converted into a different atoll layout.

## Existing parameters

No player controls or safe/advanced ranges were changed. The only new options are private finish() arguments smooth_bottom / bottom_scale, not UI settings. Existing English info texts, modes/tags/players and general resource controls are retained.

## Integration

Apply the selected patch after checking base hashes; reconcile independently changed files. Run python -m pytest tests (explicit tests directory avoids collecting unpacked historical delivery sources under out). No registry entry or watermark ID is needed for a fix to existing templates.
Four matrix reports predate only the final Atoll-only polish; their own template and shared-helper contents remain unchanged. The Atoll matrix is from the final source. Do not rewrite their original global fingerprints to conceal that chronology. The per-file base/final hashes in the manifest and the final 50-seed geometry acceptance record identify the delivered code.

## Reproduction

python -m pytest tests/test_naval_layout_quality.py tests/test_template_atoll.py
python -m tools.template_workflow check open_sea archipelago straits coastal_front atoll --level full
python out/TPL-naval-fix-1-current/review.py

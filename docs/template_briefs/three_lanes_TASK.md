# Develop Three Lanes

Read docs/TEMPLATE_GUIDE.md and docs/TEMPLATE_WORKFLOW.md first.
Read docs/template_briefs/three_lanes.json and fill in its concept, difference from the base,
players, routes and economy before changing geometry. The copied chokepoint template is only a
working starting point, not a new design. Implement a distinct layout and add tests for its rules.
Keep all player-facing text and code comments English. Preserve existing unrelated changes.
Do not change core modules as part of template production; record wishes in the brief.
Do not delegate or start other chats unless the user explicitly requests it.

Use python -m tools.template_workflow check three_lanes --level quick while iterating.
Then run --level full, inspect every image in the contact sheet and at least one enlarged preview,
and set visual_review=true in the brief only after inspection. Run
python -m tools.template_workflow integrate three_lanes, then finish with check three_lanes --level release.
The release level builds a real archive and runs the complete test suite. Fix failures; never
weaken tests or classify a failed advanced crash as success. Gameplay failures in advanced mode
are allowed and must be reported. Do not edit the registry until the integration checklist passes.
Deliver HANDOFF_three_lanes.md, the check report, contact sheet, preview, thumbnail and build result.
Report honestly whether the map was loaded and played in Zero-K.

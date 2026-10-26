# Develop Open Dunes

Read docs/TEMPLATE_GUIDE.md and docs/TEMPLATE_WORKFLOW.md first.
Read docs/template_briefs/open_dunes.json and fill in its concept, difference from the base,
players, routes and economy before changing geometry. The copied skirmish template is only a
working starting point, not a new design. Implement a distinct layout and add tests for its rules.
Keep all player-facing text and code comments English. Preserve existing unrelated changes.
Do not change core modules as part of template production; record wishes in the brief.
Do not delegate or start other chats unless the user explicitly requests it.

Use python -m tools.template_workflow check open_dunes --level quick while iterating.
Then run --level full, inspect every image in the contact sheet and at least one enlarged preview,
and set visual_review=true only after inspection. The Core owner alone registers templates and assigns final watermark IDs. Never run integrate or edit registry/watermark modules in this workspace. Deliver a selected patch, English parameter explanations, check reports, timing, previews, thumbnail and tests through forge-exchange. State honestly whether the map was loaded or played in Zero-K.

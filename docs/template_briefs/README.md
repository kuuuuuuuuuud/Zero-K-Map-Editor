# Design briefs

`python -m tools.template_workflow new <id> --title "English title" --base <template>` creates a
JSON brief and a matching `_TASK.md` for a developer or AI assistant.

Fill in the concept, difference from the base, player count, routes and economy before coding.
Keep one gameplay idea per template; put simple variants into parameters. `visual_review` and
`in_game_tested` record real human/agent inspection, never assumed approval. List known weaknesses
and core wishes honestly.

Use `../TEMPLATE_WORKFLOW.md` for the complete process and `../TEMPLATE_GUIDE.md` for engine rules.
Generated reports go to `out/template_workflow/<id>/` and do not belong in this folder.

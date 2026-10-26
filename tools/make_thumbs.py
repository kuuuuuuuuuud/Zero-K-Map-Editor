"""Render the template gallery pictures for the app (atlasforge/app/web/thumbs/<id>.jpg).
Run after changing a template: python tools/make_thumbs.py [template_id ...]
Without arguments all templates are rendered; with ids only those (others stay byte-identical).
Optional --out DIR writes elsewhere (e.g. to compare against the committed pictures)."""
import os
import sys

from atlasforge import forge
from atlasforge.templates import all_templates

args = sys.argv[1:]
OUT = os.path.join(os.path.dirname(__file__), "..", "atlasforge", "app", "web", "thumbs")
if "--out" in args:
    i = args.index("--out")
    OUT = args[i + 1]
    del args[i:i + 2]
os.makedirs(OUT, exist_ok=True)
for t in all_templates():
    if args and t.id not in args:
        continue
    d = forge.make(t.id, {}, seed=7, log=lambda *a: None)
    forge.preview(d, size=720).resize((320, 320)).convert("RGB").save(os.path.join(OUT, t.id + ".jpg"), quality=86)
    print(t.id)

"""Regression SCU-57: renderParams must grab the seed row before clearing #params."""
from pathlib import Path

APP_JS = Path(__file__).resolve().parents[1] / "atlasforge" / "app" / "web" / "app.js"


def test_render_params_grabs_seed_row_before_clearing():
    src = APP_JS.read_text(encoding="utf-8")
    body = src[src.index("function renderParams()"):src.index("function paramField(")]
    assert body.index('$("seed").closest') < body.index('box.innerHTML = ""')

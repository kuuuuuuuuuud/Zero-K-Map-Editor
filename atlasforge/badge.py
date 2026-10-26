"""Map browser badge: a tab at the bottom centre of the minimap embedded in the SMF.
Only the map browser and zero-k.info show it; in game the clean minimap (smf.minimaptex) is used."""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "InterDisplay-Black.otf")

STYLES = {
    # text, tab colour, inner colour, text colour, (optional) glow colour
    "forge": dict(text="FORGE", tab=(255, 112, 26, 255), inner=(22, 18, 18, 255), ink=(255, 150, 48, 255),
                  glow=(255, 90, 10)),
}


def _font(size):
    try:
        return ImageFont.truetype(FONT, size)
    except OSError:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", int(size * 0.93))


def draw_badge(img, style="forge"):
    """img: (H, W, 3) uint8 minimap -> copy with the badge. style: a key of STYLES."""
    st = STYLES[style]
    base = Image.fromarray(np.ascontiguousarray(img)).convert("RGBA")
    S = 2048                                  # supersampling
    lay = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    cx, w, h = S / 2, 820, 200
    d.polygon([(cx - w / 2 - 70, S), (cx - w / 2, S - h), (cx + w / 2, S - h), (cx + w / 2 + 70, S)], fill=st["tab"])
    d.polygon([(cx - w / 2 - 44, S), (cx - w / 2 + 16, S - h + 22), (cx + w / 2 - 16, S - h + 22),
               (cx + w / 2 + 44, S)], fill=st["inner"])
    f = _font(150)
    txt, sp = st["text"], 30
    ws = [d.textlength(c, font=f) for c in txt]
    x0 = cx - (sum(ws) + sp * (len(txt) - 1)) / 2
    if st.get("glow"):                        # ember glow behind the letters
        gl = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        gd = ImageDraw.Draw(gl)
        x = x0
        for c, cw in zip(txt, ws):
            gd.text((x, S - h / 2 + 18), c, font=f, fill=st["glow"] + (255,), anchor="lm")
            x += cw + sp
        gl = gl.filter(ImageFilter.GaussianBlur(18))
        lay.alpha_composite(gl)
        d = ImageDraw.Draw(lay)
    x = x0
    for c, cw in zip(txt, ws):
        d.text((x, S - h / 2 + 18), c, font=f, fill=st["ink"], anchor="lm")
        x += cw + sp
    lay = lay.resize(base.size, Image.LANCZOS)
    a = lay.split()[3].filter(ImageFilter.GaussianBlur(10))          # soft shadow
    sh = Image.new("RGBA", base.size, (0, 0, 0, 0))
    sh.putalpha(a.point(lambda v: int(v * 0.75)))
    base.alpha_composite(sh, (0, 6))
    base.alpha_composite(lay)
    return np.asarray(base.convert("RGB"))

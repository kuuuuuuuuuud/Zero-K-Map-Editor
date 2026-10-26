"""DeepInfra text-to-image backend for Atlas Map Forge.

``DeepInfraGenerator`` converts a text prompt into a ``(heightmap, texture)``
pair that the build pipeline can consume directly:

* ``generate_image(prompt, width, height)`` -> a single RGB ``PIL.Image``.
* ``generate_terrain(prompt, size=(16, 8))``   -> ``(hm, tex)`` where ``hm`` is
  a ``float32`` elmos heightmap of shape ``(nz+1, nx+1)`` and ``tex`` is an RGB
  image of shape ``(nx*8, nz*8)`` (matching ``TEX_PER_SQ``).

The real backend uses DeepInfra's OpenAI-compatible image endpoint::

    POST https://api.deepinfra.com/v1/openai/images/generations
    {"model": ..., "prompt": ..., "size": "1024x1024", "n": 1,
     "response_format": "b64_json"}

which returns ``{"data": [{"b64_json": "<base64>"}]}``.  A ``url`` field and
the DeepInfra native ``images``/``output`` payloads are also tolerated.

Environment variables (see ``.env.example``):

* ``DEEPINFRA_API_KEY``      required for real calls.
* ``DEEPINFRA_IMAGE_MODEL``  model id, default ``stabilityai/sdxl-turbo``.
* ``USE_STUB``               ``"1"`` -> deterministic offline synthetic images.
* ``AI_SEED``                seed for the stub generator (default 1).
"""

import base64
import io
import logging
import os

import numpy as np
import requests
from dotenv import load_dotenv
from PIL import Image, ImageFilter

from .. import TEX_PER_SQ

logger = logging.getLogger("atlasforge.ai")

DEFAULT_MODEL = "stabilityai/sdxl-turbo"
API_URL = "https://api.deepinfra.com/v1/openai/images/generations"

HEIGHTMAP_PROMPT = (
    "{prompt}, grayscale topographic heightmap, top-down orthographic view, "
    "black is low elevation, white is high elevation, no text, no labels, no border"
)
TEXTURE_PROMPT = (
    "{prompt}, top-down orthographic satellite terrain, natural colors, "
    "real-time strategy game map, no text, no icons, no grid, no border"
)


class DeepInfraError(RuntimeError):
    """Raised when a DeepInfra call cannot be completed."""


class DeepInfraGenerator:
    """Generate ``(heightmap, texture)`` from a text prompt.

    Parameters
    ----------
    api_key : str | None
        Overrides ``DEEPINFRA_API_KEY``.
    model : str | None
        Overrides ``DEEPINFRA_IMAGE_MODEL``.
    timeout : float
        HTTP timeout in seconds.
    log : callable | None
        Optional message sink, matching the upstream ``log`` convention.
    """

    def __init__(self, api_key=None, model=None, timeout=120.0, log=None):
        load_dotenv()  # no-op if .env is absent; searches upward from CWD
        self.api_key = (api_key or os.environ.get("DEEPINFRA_API_KEY", "")).strip()
        self.model = (
            (model or os.environ.get("DEEPINFRA_IMAGE_MODEL", "")).strip()
            or DEFAULT_MODEL
        )
        self.timeout = timeout
        self._log = log or (lambda msg: logger.info(msg))
        self.stub = os.environ.get("USE_STUB", "0") == "1"
        self.seed = int(os.environ.get("AI_SEED", "1"))
        if self.stub:
            self._log(f"DeepInfraGenerator: STUB mode enabled (offline, seed={self.seed})")

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #
    def generate_image(self, prompt, width=1024, height=1024):
        """Return a single RGB image (``width`` x ``height``) for ``prompt``."""
        if self.stub:
            return self._stub_image(prompt, int(width), int(height))
        self._require_key()
        return self._api_image(prompt, int(width), int(height))

    def generate_terrain(
        self,
        prompt,
        size=(16, 8),
        gen_width=1024,
        gen_height=1024,
        min_height=-30.0,
        max_height=170.0,
        percentile_lo=2,
        percentile_hi=98,
    ):
        """Generate a ``(heightmap, texture)`` pair for a map of ``size`` units.

        ``size`` is ``(width, height)`` in Spring map units (1 unit == 512 elmos
        == 64 heightmap squares).  Upstream requires even sizes (``nx % 128 ==
        0``); odd sizes are rejected here.

        Returns
        -------
        hm : np.ndarray (float32, shape (nz+1, nx+1))
            Heights in elmos; water level is 0.
        tex : PIL.Image (RGB, size (nx*TEX_PER_SQ, nz*TEX_PER_SQ))
            Top-down texture, upscaled to the map's texel grid.
        """
        sx, sz = int(size[0]), int(size[1])
        if sx % 2 or sz % 2:
            raise ValueError(f"map size must be even, got {sx}x{sz} (e.g. use 16x8)")
        nx, nz = sx * 64, sz * 64

        hm_img = self.generate_image(
            HEIGHTMAP_PROMPT.format(prompt=prompt), gen_width, gen_height
        )
        tex_img = self.generate_image(
            TEXTURE_PROMPT.format(prompt=prompt), gen_width, gen_height
        )

        hm = self._heightmap_from_image(
            hm_img, nz, nx, min_height, max_height, percentile_lo, percentile_hi
        )
        tex = tex_img.convert("RGB").resize(
            (nx * TEX_PER_SQ, nz * TEX_PER_SQ), Image.LANCZOS
        )
        self._log(f"DeepInfra terrain ready: {nx}x{nz} squares, texture {tex.size}")
        return hm, tex

    # ------------------------------------------------------------------ #
    # real backend
    # ------------------------------------------------------------------ #
    def _require_key(self):
        if not self.api_key:
            raise DeepInfraError(
                "DEEPINFRA_API_KEY is not set. Copy .env.example to .env and add "
                "your DeepInfra key, or set USE_STUB=1 for offline testing."
            )

    def _api_image(self, prompt, width, height):
        payload = {
            "model": self.model,
            "prompt": prompt,
            "size": f"{width}x{height}",
            "n": 1,
            "response_format": "b64_json",
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        self._log(f"DeepInfra image request: model={self.model} size={payload['size']}")
        try:
            resp = requests.post(API_URL, headers=headers, json=payload, timeout=self.timeout)
        except requests.RequestException as exc:
            raise DeepInfraError(f"DeepInfra request failed: {exc}") from exc
        if resp.status_code != 200:
            raise DeepInfraError(f"DeepInfra HTTP {resp.status_code}: {resp.text[:400]}")
        image = self._extract_image(resp.json())
        if image is None:
            raise DeepInfraError("DeepInfra returned no usable image data")
        return image

    @staticmethod
    def _extract_image(data):
        """Pull the first decodable image out of a DeepInfra JSON response."""
        items = data.get("data") or []
        if isinstance(items, dict):
            items = [items]
        for item in items:
            b64 = item.get("b64_json")
            if b64:
                return Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
            url = item.get("url")
            if url:
                resp = requests.get(url, timeout=120)
                resp.raise_for_status()
                return Image.open(io.BytesIO(resp.content)).convert("RGB")
        for field in ("images", "output"):
            for entry in data.get(field) or []:
                if isinstance(entry, str):
                    try:
                        return Image.open(io.BytesIO(base64.b64decode(entry))).convert("RGB")
                    except Exception:  # noqa: BLE001
                        continue
        return None

    @staticmethod
    def _heightmap_from_image(img, nz, nx, min_height, max_height, lo, hi):
        gray = np.asarray(img.convert("L"), dtype=np.float32) / 255.0
        lo_v = float(np.percentile(gray, lo))
        hi_v = float(np.percentile(gray, hi))
        span = max(hi_v - lo_v, 1e-6)
        norm = np.clip((gray - lo_v) / span, 0.0, 1.0).astype(np.float32)
        resized = Image.fromarray(norm, mode="F").resize((nx + 1, nz + 1), Image.BILINEAR)
        hm = min_height + np.asarray(resized, dtype=np.float32) * (max_height - min_height)
        return hm.astype(np.float32)

    # ------------------------------------------------------------------ #
    # offline stub backend (deterministic, no network / no key)
    # ------------------------------------------------------------------ #
    def _stub_image(self, prompt, width, height):
        field = self._stub_field(width, height)
        text = prompt.lower()
        if "heightmap" in text or "grayscale" in text:
            arr = (field * 255.0).astype(np.uint8)
            return Image.fromarray(arr, mode="L").convert("RGB")
        r = (0.30 + 0.50 * field) * 255.0
        g = (0.52 + 0.25 * (1.0 - field)) * 255.0
        b = (0.30 + 0.15 * field) * 255.0
        rgb = np.stack([r, g, b], axis=-1).astype(np.uint8)
        return Image.fromarray(rgb, mode="RGB")

    def _stub_field(self, width, height):
        rng = np.random.default_rng(self.seed)
        yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
        field = np.zeros((height, width), dtype=np.float32)
        for _ in range(3):
            field += np.sin(xx / width * 6.28318 * rng.uniform(1.0, 4.0) + rng.uniform(0, 6.28))
            field += np.sin(yy / height * 6.28318 * rng.uniform(1.0, 4.0) + rng.uniform(0, 6.28))
        field += 0.6 * np.sin((xx + yy) / max(1, width + height) * 6.28318 * 2.0)
        field -= field.min()
        field /= max(field.max(), 1e-6)
        img = Image.fromarray((field * 255.0).astype(np.uint8), mode="L")
        img = img.filter(ImageFilter.GaussianBlur(radius=max(1.0, min(width, height) / 48.0)))
        return np.asarray(img, dtype=np.float32) / 255.0
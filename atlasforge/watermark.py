"""Hidden watermark in the heightmap of every map built with Atlas Map Forge.

Two layers, both far below anything visible or relevant for gameplay:

1. Pattern (robust): a keyed +-1 pattern over the whole heightmap, amplitude about 0.04 elmos. Found by
   correlation even after the map was re-packed, renamed, re-textured, given a new mapinfo, or the
   heightmap was lightly edited, re-quantised or slightly smoothed.
2. Payload (exact): the lowest bit of a keyed quarter of all height samples carries a short record
   (tool version, template, seed, build date, build id), each bit repeated hundreds of times. Survives
   everything that keeps the 16-bit heights (re-packing, renaming, new texture or mapinfo).

    from atlasforge import watermark
    watermark.verify("Forge_Iron_Wall_v1.sdz")   # -> {"forge": True, "confidence": ..., "payload": {...}}

Note: Atlas Map Forge is open source, so someone who studies this file can remove or fake the mark.
It reliably tells Forge maps apart from other maps, it is not a proof against deliberate forgery.
"""
import datetime
import hashlib
import io
import os
import struct
import zipfile
import zlib

import numpy as np
from scipy import ndimage

KEY = b"Atlas Map Forge / heightmap watermark / v1"
MAGIC = b"AMF1"
TEMPLATE_CODES = {"procedural": 0, "skirmish": 1, "chokepoint": 2, "river": 3, "arena": 4, "volcano": 5,
                  "chicken": 6, "open_sea": 7, "archipelago": 8, "straits": 9, "three_lanes": 10,
                  "coastal_front": 11, "atoll": 12, "ffa_ring": 13, "asteroid": 14, "highlands": 15,
                  "watershed": 16, "dune_sea": 17, "open_dunes": 18, "twin_plateaus": 19, "lake_district": 20,
                  "river_delta": 21, "fjord_coast": 22,
                  "chicken_mesa": 23, "canyon_network": 24, "mountain_spine": 25}
EPOCH = datetime.date(2026, 1, 1)
PAYLOAD_LEN = 4 + 3 + 1 + 4 + 2 + 4 + 4          # magic, version, template, seed, day, build id, crc32
PATTERN_ELMOS = 0.04                              # amplitude of the robust layer
PAYLOAD_SHARE = 0.25                              # share of samples that carry the payload bits
Z_FORGE = 8.0                                     # pattern correlation above this = Forge map


def _rng(shape, tag):
    seed = int.from_bytes(hashlib.sha256(KEY + tag + struct.pack("<2i", *shape)).digest()[:8], "little")
    return np.random.default_rng(seed)


def _pattern(shape):
    return _rng(shape, b"pattern").integers(0, 2, size=shape, dtype=np.int8) * 2 - 1


def _slots(shape):
    """Positions and key bits of the payload samples: (flat indices [nbits, reps], key bits)."""
    n = shape[0] * shape[1]
    nbits = PAYLOAD_LEN * 8
    reps = max(1, int(n * PAYLOAD_SHARE) // nbits)
    r = _rng(shape, b"payload")
    idx = r.permutation(n)[: nbits * reps].reshape(nbits, reps)
    key = r.integers(0, 2, size=(nbits, reps), dtype=np.uint16)
    return idx, key


def _pack(version, template, seed, day, build_id):
    v = [int(x) for x in (version.split(".") + ["0", "0", "0"])[:3]]
    body = (MAGIC + bytes(v) + bytes([TEMPLATE_CODES.get(template or "", 255)])
            + struct.pack("<IHI", seed & 0xFFFFFFFF, day & 0xFFFF, build_id & 0xFFFFFFFF))
    return body + struct.pack("<I", zlib.crc32(body))


def _unpack(raw):
    if len(raw) != PAYLOAD_LEN or raw[:4] != MAGIC:
        return None
    body, crc = raw[:-4], struct.unpack("<I", raw[-4:])[0]
    if zlib.crc32(body) != crc:
        return None
    names = {v: k for k, v in TEMPLATE_CODES.items()}
    seed, day, build_id = struct.unpack("<IHI", body[8:18])
    return dict(tool_version=".".join(str(b) for b in body[4:7]), template=names.get(body[7], "unknown"),
                seed=seed, built=str(EPOCH + datetime.timedelta(days=day)), build_id=f"{build_id:08x}")


def embed(hm16, hmin, hmax, version, template=None, seed=0, build_id=None, today=None):
    """Return a watermarked copy of the uint16 heightmap (as written into the SMF)."""
    h = hm16.astype(np.int32)
    unit = (hmax - hmin) / 65535.0
    amp = max(1, int(round(PATTERN_ELMOS / unit)))
    h = np.clip(h + amp * _pattern(h.shape), 0, 65535)
    day = ((today or datetime.date.today()) - EPOCH).days
    if build_id is None:
        build_id = int.from_bytes(os.urandom(4), "little")
    bits = np.unpackbits(np.frombuffer(_pack(version, template, seed, day, build_id), np.uint8))[:, None]
    idx, key = _slots(h.shape)
    flat = h.reshape(-1)
    want = (bits ^ key).astype(np.int32)
    v = flat[idx]
    flat[idx] = (v & ~1) | want
    return flat.reshape(hm16.shape).astype(np.uint16)


def detect(hm16):
    """Look for both layers in a uint16 heightmap. -> dict(forge, confidence, pattern_z, payload_match, payload)"""
    h = hm16.astype(np.float64)
    resid = h - ndimage.uniform_filter(h, 3)
    p = _pattern(h.shape).astype(np.float64)
    resid -= resid.mean()
    z = float((resid * p).sum() / (resid.std() * np.sqrt(resid.size) + 1e-9))
    idx, key = _slots(h.shape)
    lsb = (hm16.reshape(-1)[idx] & 1).astype(np.uint16) ^ key
    votes = lsb.mean(axis=1)
    bits = (votes > 0.5).astype(np.uint8)
    agree = float(np.where(bits[:, None] == 1, lsb, 1 - lsb).mean())
    payload = _unpack(np.packbits(bits).tobytes())
    forge = z > Z_FORGE or payload is not None
    if payload is not None and z > Z_FORGE:
        conf = "certain"
    elif forge:
        conf = "high"
    else:
        conf = "none"
    return dict(forge=forge, confidence=conf, pattern_z=round(z, 1), payload_match=round(agree, 4), payload=payload)


def read_heights(sdz_or_smf):
    """uint16 heightmap of a map archive (.sdz) or .smf file."""
    low = str(sdz_or_smf).lower()
    if low.endswith(".smf"):
        with open(sdz_or_smf, "rb") as f:
            data = f.read()
    elif low.endswith(".sd7"):                       # 7-Zip map archive
        try:
            import py7zr
        except ImportError:
            raise ValueError(".sd7 maps need the py7zr package (pip install py7zr)") from None
        import tempfile
        with py7zr.SevenZipFile(sdz_or_smf) as z:
            smf = [n for n in z.getnames() if n.lower().endswith(".smf")]
            if not smf:
                raise ValueError("no .smf file in the archive")
        with tempfile.TemporaryDirectory() as tmp, py7zr.SevenZipFile(sdz_or_smf) as z:
            z.extract(path=tmp, targets=smf[:1])
            with open(os.path.join(tmp, smf[0]), "rb") as f:
                data = f.read()
    else:
        with zipfile.ZipFile(sdz_or_smf) as z:
            smf = [n for n in z.namelist() if n.lower().endswith(".smf")]
            if not smf:
                raise ValueError("no .smf file in the archive")
            data = z.read(smf[0])
    hdr = struct.unpack("<16s7i2f7i", data[:80])
    if not hdr[0].startswith(b"spring map file"):
        raise ValueError("not a Spring map file")
    nx, nz, hm_ptr = hdr[3], hdr[4], hdr[10]
    n = (nx + 1) * (nz + 1)
    return np.frombuffer(data, "<u2", count=n, offset=hm_ptr).reshape(nz + 1, nx + 1)


def verify(path):
    """Check a map file (.sdz, .sd7 unpacked to .smf, or .smf). -> detect() result plus the file name."""
    res = detect(read_heights(path))
    res["file"] = os.path.basename(str(path))
    return res


def describe(res):
    """Plain-English summary of a verify() result."""
    if not res["forge"]:
        return f"{res['file']}: no Atlas Map Forge watermark found."
    lines = [f"{res['file']}: made with Atlas Map Forge (confidence: {res['confidence']}, "
             f"pattern score {res['pattern_z']})."]
    p = res["payload"]
    if p:
        lines.append(f"  tool {p['tool_version']}, template {p['template']}, seed {p['seed']}, built {p['built']}, "
                     f"build id {p['build_id']}")
    else:
        lines.append("  The detailed record is damaged (heightmap was edited), the pattern is still there.")
    return "\n".join(lines)


def _selftest():
    rng = np.random.default_rng(1)
    hm = (ndimage.gaussian_filter(rng.normal(size=(513, 513)), 6) * 4e5 + 30000).clip(0, 65535).astype(np.uint16)
    w = embed(hm, -50, 900, "0.4.0", "river", 77, build_id=0xABCDEF01)
    return detect(hm), detect(w)


if __name__ == "__main__":
    print(_selftest())

"""Install a built map into Zero-K: find the game folder, copy the .sdz into maps/ and add the lobby
(Chobby) minimap and thumbnail so the map shows a picture in the map list.

Note: Zero-K's map list only shows local maps when "Only show featured maps" is switched off in the
lobby settings."""
import glob
import io
import os
import re
import shutil
import struct
import sys
import zipfile

import numpy as np
from PIL import Image


# ----------------------------------------------------------------------------- game folder
def _steam_roots():
    roots = []
    if sys.platform.startswith("win"):
        for env in ("PROGRAMFILES(X86)", "PROGRAMFILES"):
            base = os.environ.get(env)
            if base:
                roots.append(os.path.join(base, "Steam"))
    else:
        roots += [os.path.expanduser("~/.steam/steam"), os.path.expanduser("~/.local/share/Steam"),
                  os.path.expanduser("~/Library/Application Support/Steam")]
    libs = []
    for r in roots:
        if os.path.isdir(r):
            libs.append(r)
            vdf = os.path.join(r, "steamapps", "libraryfolders.vdf")
            if os.path.exists(vdf):
                with open(vdf, encoding="utf8", errors="replace") as f:
                    for m in re.finditer(r'"path"\s+"([^"]+)"', f.read()):
                        libs.append(m.group(1).replace("\\\\", "\\"))
    return libs


def find_zerok():
    """Candidate Zero-K data folders (containing a maps/ folder or the engine), best first."""
    cands = [os.path.join(lib, "steamapps", "common", "Zero-K") for lib in _steam_roots()]
    if sys.platform.startswith("win"):
        docs = os.path.join(os.path.expanduser("~"), "Documents")
        cands += [os.path.join(docs, "My Games", "Zero-K"), os.path.join(docs, "Zero-K"),
                  os.path.join(os.environ.get("LOCALAPPDATA", ""), "Zero-K")]
    else:
        cands += [os.path.expanduser("~/.spring"), os.path.expanduser("~/Zero-K")]
    seen, out = set(), []
    for c in cands:
        c = os.path.normpath(c)
        if c in seen or not os.path.isdir(c):
            continue
        seen.add(c)
        if os.path.isdir(os.path.join(c, "maps")) or os.path.isdir(os.path.join(c, "engine")):
            out.append(c)
    return out


# ----------------------------------------------------------------------------- lobby pictures
def dxt1_decode(data, w, h):
    b = np.frombuffer(data, np.uint8, count=(w // 4) * (h // 4) * 8).reshape(h // 4, w // 4, 8)
    c0 = b[..., 0].astype(np.uint32) | (b[..., 1].astype(np.uint32) << 8)
    c1 = b[..., 2].astype(np.uint32) | (b[..., 3].astype(np.uint32) << 8)

    def rgb(c):
        r = ((c >> 11) & 31) * 255 // 31
        g = ((c >> 5) & 63) * 255 // 63
        bl = (c & 31) * 255 // 31
        return np.stack([r, g, bl], -1).astype(np.float32)
    p0, p1 = rgb(c0), rgb(c1)
    four = (c0 > c1)[..., None]
    p2 = np.where(four, (2 * p0 + p1) / 3, (p0 + p1) / 2)
    p3 = np.where(four, (p0 + 2 * p1) / 3, 0)
    pal = np.stack([p0, p1, p2, p3], -2)
    idx = b[..., 4:8].astype(np.uint32)
    bits = idx[..., 0] | (idx[..., 1] << 8) | (idx[..., 2] << 16) | (idx[..., 3] << 24)
    sh = np.arange(16, dtype=np.uint32) * 2
    ix = (bits[..., None] >> sh) & 3
    px = np.take_along_axis(pal, ix[..., None].astype(np.int64).repeat(3, -1), axis=-2)
    px = px.reshape(h // 4, w // 4, 4, 4, 3).transpose(0, 2, 1, 3, 4).reshape(h, w, 3)
    return np.clip(px, 0, 255).astype(np.uint8)


def lobby_name(name):
    """File name Chobby uses for override images."""
    return re.sub(r"[^a-zA-Z0-9\-\(\)\.]", "_", name)


def read_map(sdz):
    """-> (map name, 1024x1024 minimap RGB from the SMF)"""
    with zipfile.ZipFile(sdz) as z:
        mi = z.read("mapinfo.lua").decode("utf8", "replace")
        name = re.search(r'\bname\s*=\s*"([^"]+)"', mi).group(1)
        smf = [n for n in z.namelist() if n.lower().endswith(".smf")][0]
        d = z.read(smf)
    h = struct.unpack("<16s7i2f7i", d[:80])
    mini_ptr = h[13]
    return name, dxt1_decode(d[mini_ptr:mini_ptr + 524288], 1024, 1024)


def install(sdz, zerok_dir, lobby_images=True, log=print):
    """Copy the map into <zerok_dir>/maps and write the Chobby minimap override + thumbnail."""
    maps = os.path.join(zerok_dir, "maps")
    os.makedirs(maps, exist_ok=True)
    dst = os.path.join(maps, os.path.basename(sdz))
    shutil.copyfile(sdz, dst)
    log(f"  installed {dst}")
    if lobby_images:
        name, mini = read_map(sdz)
        base = os.path.join(zerok_dir, "LuaMenu", "configs", "gameConfig", "zk")
        ov, th = os.path.join(base, "minimapOverride"), os.path.join(base, "minimapThumbnail")
        os.makedirs(ov, exist_ok=True); os.makedirs(th, exist_ok=True)
        img = Image.fromarray(mini)
        img.save(os.path.join(ov, lobby_name(name) + ".jpg"), quality=90)
        img.resize((64, 64), Image.LANCZOS).convert("RGBA").save(os.path.join(th, lobby_name(name) + ".png"))
        log("  lobby minimap and thumbnail written")
    return dst


# ----------------------------------------------------------------------------- versions
def existing_versions(cfg, title, folders):
    """Version numbers of this map that already exist as .sdz in the given folders (e.g. Zero-K/maps,
    the output folder). Two different files with the same map name cause download conflicts in Zero-K,
    so a changed map needs a new version number."""
    stem = cfg.map_name(title, 0).rsplit(" v", 1)[0].replace(" ", "_")   # "Forge_Iron_Wall"
    pat = re.compile(re.escape(stem) + r"_v(\d+)\.sdz$", re.IGNORECASE)
    found = set()
    for f in folders:
        if f and os.path.isdir(f):
            for n in os.listdir(f):
                m = pat.match(n)
                if m:
                    found.add(int(m.group(1)))
    return sorted(found)

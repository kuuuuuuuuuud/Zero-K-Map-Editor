"""Procedural 3D models for map features: rocks and crystals, written as Spring .s3o models with
their textures and feature definitions, so every map carries its own decoration (no downloads).

    files, kinds = feature_pack(biome, rng)   # {archive path: bytes}, {kind: FeatureKind}
"""
import struct
from dataclasses import dataclass

import numpy as np

from .formats import png_bytes
from .noise import periodic_noise


@dataclass
class FeatureKind:
    name: str            # feature def name (unique per map)
    metal: float         # reclaim metal
    radius: float        # footprint radius in elmos (for spacing)
    blocking: bool
    family: str          # "rock" or "crystal"


# ----------------------------------------------------------------------------- s3o writer
def s3o_bytes(verts, normals, uvs, tris, tex1, tex2, piece="base"):
    """Single-piece Spring S3O model. verts/normals (N, 3) in elmos (y up), uvs (N, 2), tris (M, 3)."""
    verts = np.asarray(verts, np.float32); normals = np.asarray(normals, np.float32)
    uvs = np.asarray(uvs, np.float32); tris = np.asarray(tris, np.int32)
    lo, hi = verts.min(0), verts.max(0)
    mid = (lo + hi) / 2
    radius = float(np.linalg.norm(verts - mid, axis=1).max())
    height = float(hi[1])
    hdr_fmt = "<12si5f4i"                                 # magic, version, radius, height, mid xyz, 4 offsets
    piece_fmt = "<10i3f"
    hdr_size = struct.calcsize(hdr_fmt)
    piece_off = hdr_size
    piece_size = struct.calcsize(piece_fmt)
    name_off = piece_off + piece_size
    name_b = piece.encode() + b"\0"
    vert_off = name_off + len(name_b)
    vdata = np.concatenate([verts, normals, uvs], 1).astype("<f4").tobytes()
    idx_off = vert_off + len(vdata)
    idata = tris.astype("<i4").tobytes()
    tex1_off = idx_off + len(idata)
    t1 = tex1.encode() + b"\0"
    tex2_off = tex1_off + len(t1)
    t2 = tex2.encode() + b"\0"
    header = struct.pack(hdr_fmt, b"Spring unit\0", 0, radius, height, float(mid[0]), float(mid[1]), float(mid[2]),
                         piece_off, 0, tex1_off, tex2_off)
    pc = struct.pack(piece_fmt, name_off, 0, 0, len(verts), vert_off, 0, 0, tris.size, idx_off, 0, 0.0, 0.0, 0.0)
    return header + pc + name_b + vdata + idata + t1 + t2


def read_s3o(data):
    """Minimal reader (tests): -> (radius, height, verts, tris, tex1, tex2)."""
    magic, ver, radius, height, mx, my, mz, root, coll, t1, t2 = struct.unpack_from("<12si5f4i", data, 0)
    assert magic == b"Spring unit\0" and ver == 0
    (name, nch, ch, nv, vo, vt, pt, nidx, io, cd, *_off) = struct.unpack_from("<10i3f", data, root)
    v = np.frombuffer(data, "<f4", nv * 8, vo).reshape(nv, 8)
    idx = np.frombuffer(data, "<i4", nidx, io).reshape(-1, 3)
    cstr = lambda o: data[o:data.index(b"\0", o)].decode()
    return radius, height, v[:, :3], idx, cstr(t1), cstr(t2)


# ----------------------------------------------------------------------------- meshes
def _icosphere(subdiv):
    t = (1 + 5 ** 0.5) / 2
    v = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
         (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    f = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6),
         (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10),
         (8, 6, 7), (9, 8, 1)]
    verts = [np.array(p, float) / np.linalg.norm(p) for p in v]
    for _ in range(subdiv):
        cache, nf = {}, []

        def mid(a, b):
            k = (min(a, b), max(a, b))
            if k not in cache:
                m = verts[a] + verts[b]
                verts.append(m / np.linalg.norm(m))
                cache[k] = len(verts) - 1
            return cache[k]
        for a, b, c in f:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            nf += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        f = nf
    return np.array(verts), np.array(f)


def _orient_outward(v, f, center):
    """Wind every triangle so (b - a) x (c - a) points away from `center` (the S3O/Recoil convention:
    counter-clockwise seen from outside, normal = cross product)."""
    fn = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    out = ((v[f].mean(1) - center) * fn).sum(1) < 0
    f = f.copy()
    f[out] = f[out][:, ::-1]
    return f


def _vertex_normals(v, f):
    n = np.zeros_like(v)
    fn = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    for k in range(3):
        np.add.at(n, f[:, k], fn)
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)


def rock_mesh(rng, size, flat=0.55):
    """Lumpy boulder: displaced icosphere, flattened, sunk a little into the ground. size: radius (elmos)."""
    v, f = _icosphere(3)
    d = np.zeros(len(v))
    for k in range(5):                                             # broad lobes and dents
        c = rng.normal(size=3); c /= np.linalg.norm(c)
        d += rng.uniform(-0.18, 0.28) * np.exp(-((v @ c - 1) ** 2) / rng.uniform(0.3, 0.8))
    for k in range(int(rng.integers(3, 6))):                        # flat split faces like broken stone
        c = rng.normal(size=3); c[1] = abs(c[1]) * 0.6; c /= np.linalg.norm(c)
        cut = rng.uniform(0.5, 0.8)
        over = np.clip(v @ c - cut, 0, None)
        d -= over * 1.0
    for k in range(6):                                             # fine relief, smooth (no crumpling)
        c = rng.normal(size=3); c /= np.linalg.norm(c)
        d += 0.025 * np.sin((v @ c) * rng.uniform(6, 11) + rng.uniform(0, 6.3))
    p = v * (1 + d)[:, None]
    p *= np.array([rng.uniform(0.9, 1.3), flat * rng.uniform(0.8, 1.2), rng.uniform(0.8, 1.15)]) * size
    th = rng.uniform(0, 2 * np.pi)
    rot = np.array([[np.cos(th), 0, -np.sin(th)], [0, 1, 0], [np.sin(th), 0, np.cos(th)]])
    p = p @ rot.T
    p[:, 1] -= p[:, 1].min() + 0.18 * size                         # sunk into the ground
    uv = np.stack([0.5 + np.arctan2(p[:, 2], p[:, 0]) / (2 * np.pi), 0.5 + p[:, 1] / (3 * size)], 1)
    f = _orient_outward(p, f, p.mean(0))
    return p, _vertex_normals(p, f), uv, f


def crystal_mesh(rng, size):
    """Cluster of 4-7 hexagonal crystal prisms with pointed tips."""
    vs, fs, uvs = [], [], []
    for k in range(rng.integers(4, 8)):
        r = size * rng.uniform(0.18, 0.32)
        L = size * rng.uniform(0.9, 2.2) * (1.0 if k else 1.3)
        tilt = rng.normal(0, 0.35, 2) if k else np.zeros(2)
        base = np.array([rng.uniform(-0.5, 0.5) * size if k else 0, -0.15 * size, rng.uniform(-0.5, 0.5) * size if k else 0])
        axis = np.array([tilt[0], 1.0, tilt[1]]); axis /= np.linalg.norm(axis)
        a1 = np.cross(axis, [0, 0, 1.0]); a1 /= np.linalg.norm(a1); a2 = np.cross(axis, a1)
        ring = [base + r * (np.cos(t) * a1 + np.sin(t) * a2) for t in np.linspace(0, 2 * np.pi, 7)[:-1]]
        top = [p + axis * L for p in ring]
        tip = base + axis * (L + r * 1.6)
        o = sum(len(x) for x in vs)
        pts = np.array(ring + top + [tip])
        faces = []
        for i in range(6):
            j = (i + 1) % 6
            faces += [(i, 6 + i, j), (j, 6 + i, 6 + j), (6 + i, 12, 6 + j)]
        faces = _orient_outward(pts, np.array(faces), pts.mean(0))
        vs.append(pts); fs += [tuple(x + o) for x in faces]
        uvs.append(np.stack([np.r_[np.linspace(0, 1, 6), np.linspace(0, 1, 6), 0.5],
                             np.r_[np.zeros(6), np.full(6, 0.8), np.ones(1)]], 1))
    v = np.concatenate(vs); f = np.array(fs)
    # flat shading looks crystalline: split vertices per face
    fv = v[f].reshape(-1, 3)
    fuv = np.concatenate(uvs)[f].reshape(-1, 2)
    ff = np.arange(len(fv)).reshape(-1, 3)
    fn = np.cross(fv[ff[:, 1]] - fv[ff[:, 0]], fv[ff[:, 2]] - fv[ff[:, 0]])
    fn /= np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-9)
    return fv, np.repeat(fn, 3, axis=0), fuv, ff


# ----------------------------------------------------------------------------- textures
def rock_textures(rng, rock, cliff):
    """tex1 (colour, no team colour) and tex2 (no glow, a little shine, opaque) as PNG bytes."""
    n1 = periodic_noise(256, rng, 0.9); n2 = periodic_noise(256, rng, 0.4)
    yy = np.arange(256)[:, None] / 256.0
    strata = 0.5 + 0.5 * np.sin(yy * 40 + n1 * 1.5)
    col = np.array(rock, np.float32) * (1 - 0.35 * strata[..., None]) + np.array(cliff, np.float32) * 0.35 * strata[..., None]
    col *= (1 + 0.18 * n1 + 0.12 * n2)[..., None]
    lichen = np.clip((n1 - 0.9) * 1.5, 0, 1)[..., None] * 0.35
    col = col * (1 - lichen) + np.array([96, 108, 70], np.float32) * lichen
    t1 = np.dstack([np.clip(col, 0, 255), np.zeros((256, 256))]).astype(np.uint8)
    t2 = np.dstack([np.zeros((256, 256)), np.full((256, 256), 30), np.zeros((256, 256)),
                    np.full((256, 256), 255)]).astype(np.uint8)
    return png_bytes(t1), png_bytes(t2)


def crystal_textures(rng, color):
    n1 = periodic_noise(128, rng, 0.6)
    vv = np.linspace(0, 1, 128)[:, None]
    base = np.array(color, np.float32)
    col = base * (0.55 + 0.45 * vv)[..., None] * (1 + 0.15 * n1)[..., None]
    t1 = np.dstack([np.clip(col, 0, 255), np.zeros((128, 128))]).astype(np.uint8)
    glow = np.clip(120 + 120 * vv + 30 * n1, 0, 255)                # self-illumination, brightest at the tips
    t2 = np.dstack([glow, np.full((128, 128), 160), np.zeros((128, 128)), np.full((128, 128), 255)]).astype(np.uint8)
    return png_bytes(t1), png_bytes(t2)


CRYSTAL_COLORS = {"alien": (90, 230, 200), "moon": (150, 170, 255), "volcanic": (255, 120, 40),
                  "ashland": (255, 110, 30), "arctic": (140, 210, 255)}


def _feature_def(name, obj, metal, foot, blocking, desc, height):
    return (f'\t{name} = {{\n\t\tdescription = "{desc}",\n\t\tobject = "{obj}",\n\t\tfootprintX = {foot},\n'
            f'\t\tfootprintZ = {foot},\n\t\tblocking = {"true" if blocking else "false"},\n\t\tmetal = {metal:.0f},\n'
            f'\t\tenergy = 0,\n\t\treclaimable = true,\n\t\treclaimTime = {max(20, metal * 2):.0f},\n'
            f'\t\tdamage = {metal * 20 + 300:.0f},\n\t\tupright = true,\n\t\theight = {height:.0f},\n'
            f'\t\tautoreclaimable = true,\n\t\tflammable = false,\n\t}},\n')


def feature_pack(biome_name, biome, rng, crystals=None):
    """Models, textures and feature defs for rocks (and crystals for alien-like biomes).
    Returns ({archive path: bytes}, {kind name: FeatureKind})."""
    files, kinds, defs = {}, {}, []
    t1, t2 = rock_textures(rng, biome["rock"], biome["cliff"])
    files["unittextures/forge_rock1.png"], files["unittextures/forge_rock2.png"] = t1, t2
    for k, (size, metal, foot, blocking, label) in enumerate([(14, 5, 1, False, "Pebbles"), (26, 12, 2, False, "Stone"),
                                                               (42, 25, 3, True, "Boulder"), (64, 45, 4, True, "Big boulder")]):
        for var in range(2):
            name = f"forge_rock_{k}{var}"
            v, n, uv, f = rock_mesh(rng, size, flat=rng.uniform(0.45, 0.7))
            files[f"objects3d/{name}.s3o"] = s3o_bytes(v, n, uv, f, "forge_rock1.png", "forge_rock2.png")
            defs.append(_feature_def(name, f"{name}.s3o", metal, foot, blocking, label, v[:, 1].max()))
            kinds[name] = FeatureKind(name, metal, size * 1.2, blocking, "rock")
    use_crystals = crystals if crystals is not None else biome_name in ("alien", "moon")
    if use_crystals:
        ct1, ct2 = crystal_textures(rng, CRYSTAL_COLORS.get(biome_name, (120, 220, 255)))
        files["unittextures/forge_crystal1.png"], files["unittextures/forge_crystal2.png"] = ct1, ct2
        for k, (size, metal) in enumerate([(22, 15), (34, 30), (50, 60)]):
            name = f"forge_crystal_{k}"
            v, n, uv, f = crystal_mesh(rng, size)
            files[f"objects3d/{name}.s3o"] = s3o_bytes(v, n, uv, f, "forge_crystal1.png", "forge_crystal2.png")
            defs.append(_feature_def(name, f"{name}.s3o", metal, 2 + k // 2, k > 0, "Crystal", v[:, 1].max()))
            kinds[name] = FeatureKind(name, metal, size * 1.1, k > 0, "crystal")
    files["features/forge_rocks.lua"] = ("-- Atlas Map Forge: rocks and crystals of this map (reclaimable metal).\n"
                                         "return {\n" + "".join(defs) + "}\n").encode()
    return files, kinds

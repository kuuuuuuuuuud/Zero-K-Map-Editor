"""Engine file formats: DXT1/DDS, SMT tiles, SMF, PNG/BMP and the Lua config files of a Zero-K map."""
import io
import struct

import numpy as np
from PIL import Image
import etcpak

from . import SQ, TEX_PER_SQ, TILE


# ----------------------------------------------------------------------------- images
def png_bytes(arr):
    b = io.BytesIO()
    Image.fromarray(arr).save(b, format="PNG", optimize=False, compress_level=6)
    return b.getvalue()


def bmp_bytes(arr):
    b = io.BytesIO()
    Image.fromarray(arr).save(b, format="BMP")
    return b.getvalue()


def dxt1_blocks(rgb):
    """rgb (H, W, 3) uint8 -> blocks (H/4, W/4, 8) uint8."""
    h, w, _ = rgb.shape
    rgba = np.empty((h, w, 4), np.uint8)
    rgba[..., :3] = rgb
    rgba[..., 3] = 255
    b = etcpak.compress_bc1(rgba.tobytes(), w, h)
    return np.frombuffer(b, np.uint8).reshape(h // 4, w // 4, 8)


def downsample2(img):
    f = img.astype(np.float32)
    f = (f[0::2, 0::2] + f[1::2, 0::2] + f[0::2, 1::2] + f[1::2, 1::2]) * 0.25
    return np.clip(f + 0.5, 0, 255).astype(np.uint8)


def dds_bytes(rgb, fmt="DXT1"):
    """rgb/rgba uint8 -> DDS (DXT1 or DXT5) with a COMPLETE mip chain down to 1x1.
    Recoil uploads embedded mips without checks; a chain that stops before 1x1 leaves the GL texture
    incomplete and it renders black.
    Note: Recoil flips DDS files vertically when loading (CBitmap::Load). Callers must pass the image
    upside down (img[::-1]) if the orientation matters in game."""
    h, w = rgb.shape[:2]
    levels = []
    img = rgb
    while True:
        hh, ww = img.shape[:2]
        rgba = img if img.shape[2] == 4 else np.dstack([img, np.full((hh, ww), 255, np.uint8)])
        hc, wc = -(-hh // 4) * 4, -(-ww // 4) * 4   # pad to block size (NPOT mips such as 10x10, 2x2, 1x1)
        if (hc, wc) != (hh, ww):
            rgba = np.pad(rgba, ((0, hc - hh), (0, wc - ww), (0, 0)), mode="edge")
        comp = etcpak.compress_bc1 if fmt == "DXT1" else etcpak.compress_bc3
        levels.append(comp(np.ascontiguousarray(rgba).tobytes(), wc, hc))
        if hh == 1 and ww == 1:
            break
        f = img.astype(np.float32)
        if hh >= 2:                                   # odd sizes: drop the last row/column (floor)
            f = f[:hh // 2 * 2]
            f = (f[0::2] + f[1::2]) * 0.5
        if ww >= 2:
            f = f[:, :ww // 2 * 2]
            f = (f[:, 0::2] + f[:, 1::2]) * 0.5
        img = np.clip(f + 0.5, 0, 255).astype(np.uint8)
    blk = 8 if fmt == "DXT1" else 16
    hdr = struct.pack("<4sIIIIIII44x", b"DDS ", 124, 0x1 | 0x2 | 0x4 | 0x1000 | 0x20000 | 0x80000, h, w,
                      (w // 4) * (h // 4) * blk, 0, len(levels))
    pf = struct.pack("<II4sIIIII", 32, 0x4, fmt.encode(), 0, 0, 0, 0, 0)
    caps = struct.pack("<IIIII", 0x1000 | 0x400000 | 0x8, 0, 0, 0, 0)
    out = hdr + pf + caps
    assert len(out) == 128
    return out + b"".join(levels)


def tiles_from_strip(rgb):
    """Texture strip (Hs, W, 3), Hs and W multiples of 32 -> (ntiles, 680) SMT tile data with 4 mip levels."""
    Hs, W, _ = rgb.shape
    nty, ntx = Hs // TILE, W // TILE
    parts = []
    img = rgb
    for lvl in range(4):
        bl = dxt1_blocks(img)
        b = (TILE >> lvl) // 4
        bl = bl.reshape(nty, b, ntx, b, 8).transpose(0, 2, 1, 3, 4).reshape(nty * ntx, b * b * 8)
        parts.append(bl)
        img = downsample2(img)
    return np.concatenate(parts, 1)


def minimap_dxt(rgb1024):
    """SMF minimap: 1024x1024 DXT1 with mips down to 4x4 (699048 bytes)."""
    out = []
    img = rgb1024
    size = 1024
    while size >= 4:
        out.append(dxt1_blocks(img).tobytes())
        img = downsample2(img)
        size //= 2
    return b"".join(out)


def smt_header(ntiles):
    return struct.pack("<16s4i", b"spring tilefile\0", 1, ntiles, TILE, 1)


# ----------------------------------------------------------------------------- SMF
def write_smf(path, nx, nz, hmin, hmax, hm16, typemap, minimap, metalmap, tilefile, ntiles, features, mapid,
              grass=None):
    """features: [(type name, x, y, z, rotation, size)]; grass: optional uint8 grid (nz/4, nx/4), > 0 = grass
    (stored as the MEH_Vegetation extra header the engine reads in CSMFMapFile::ReadGrassMap)."""
    feat_types = sorted(set(f[0] for f in features))
    ftype_idx = {t: k for k, t in enumerate(feat_types)}
    n_extra = 1 if grass is not None else 0
    hdr_size = 80 + 12 * n_extra
    hm_ptr = hdr_size
    type_ptr = hm_ptr + hm16.nbytes
    mini_ptr = type_ptr + typemap.nbytes
    metal_ptr = mini_ptr + len(minimap)
    feat_ptr = metal_ptr + metalmap.nbytes
    feat = io.BytesIO()
    feat.write(struct.pack("<2i", len(feat_types), len(features)))
    for t in feat_types:
        feat.write(t.encode() + b"\0")
    for (t, x, y, z, rot, size) in features:
        feat.write(struct.pack("<i5f", ftype_idx[t], x, y, z, rot, size))
    feat = feat.getvalue()
    tile_ptr = feat_ptr + len(feat)
    tilesec = io.BytesIO()
    tilesec.write(struct.pack("<2i", 1, ntiles))
    tilesec.write(struct.pack("<i", ntiles) + tilefile.encode() + b"\0")
    idx = np.arange((nx // 4) * (nz // 4), dtype=np.int32)
    tilesec.write(idx.tobytes())
    tiles = tilesec.getvalue()
    header = struct.pack("<16s7i2f7i", b"spring map file\0", 1, mapid, nx, nz, SQ, TEX_PER_SQ, TILE,
                         float(hmin), float(hmax), hm_ptr, type_ptr, tile_ptr, mini_ptr, metal_ptr,
                         feat_ptr, n_extra)
    if grass is not None:
        g = np.ascontiguousarray(grass, np.uint8)
        assert g.shape == (nz // 4, nx // 4), g.shape
        header += struct.pack("<3i", 12, 1, tile_ptr + len(tiles))
    assert len(header) == hdr_size
    with open(path, "wb") as f:
        f.write(header)
        f.write(hm16.tobytes()); f.write(typemap.tobytes()); f.write(minimap)
        f.write(metalmap.tobytes()); f.write(feat); f.write(tiles)
        if grass is not None:
            f.write(g.tobytes())


# ----------------------------------------------------------------------------- Lua files
def lua_tuple(t):
    return "{" + ", ".join(f"{v:.3f}" for v in t) + "}"


def lua_string(s):
    """Quote a string for Lua (double quotes)."""
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'


def mapinfo_lua(name, desc, author, hmin, hmax, smtname, starts, biome, water_h, smfname, minimap_tex=None,
                emission_tex=None, tool="Atlas Map Forge", sky_box=None, grass_shading=None):
    """mapinfo.lua. minimap_tex: separate in-game minimap without badge (unitsync and zero-k.info always
    read the minimap embedded in the SMF, which carries the badge)."""
    minimap_line = f'\n    minimaptex   = "{minimap_tex}",' if minimap_tex else ""
    emis_line = f'\n    lightEmissionTex = "{emission_tex}",' if emission_tex else ""
    if grass_shading:
        emis_line += f'\n    grassShadingTex = "{grass_shading}",'
    sky_line = f'\n    skybox       = "{sky_box}",' if sky_box else ""
    sd = biome.get("sundir", (-0.4, 0.75, -0.5))
    # a water plane (planecolor) also tints the lower half of the sky box: not on void maps, where the
    # space below the edge must show the sky (Recoil CubeMapFS / MapInfo hasWaterPlane)
    plane_line = "" if biome.get("void") else f"    planecolor     = {lua_tuple(biome['water_min'])},"
    void_type = ""
    if biome.get("void"):        # space below the water line: nothing can move there (typemap 255)
        void_type = """
    [255] = {
      name = "Void",
      hardness = 1000.0,
      receivetracks = false,
      movespeeds = { tank = 0.0, kbot = 0.0, hover = 0.0, ship = 0.0 },
    },"""
    g = biome.get("grass") or {}
    grass_block = ""
    if grass_shading and g:
        grass_block = f"""
  grass = {{
    bladeWaveScale   = {g.get("wave", 1.0)},
    bladeWidth       = {g.get("width", 0.7)},
    bladeHeight      = {g.get("height", 4.5)},
    bladeAngle       = {g.get("angle", 1.0)},
    maxStrawsPerTurf = {int(g.get("straws", 150))},
    bladeColor       = {lua_tuple(g.get("color", (0.3, 0.45, 0.15)))},
  }},
"""
    b = biome
    teams = "\n".join(
        f"    [{k}] = {{ startpos = {{ x = {int(x)}, z = {int(z)} }} }}," for k, (x, z) in enumerate(starts))
    return f'''-- generated by {tool}
local mapinfo = {{
  name        = {lua_string(name)},
  shortname   = {lua_string(name)},
  description = {lua_string(desc)},
  author      = {lua_string(author)},
  version     = "",
  modtype     = 3,
  mapfile     = "maps/{smfname}",
  replace     = {{}},

  maphardness     = 400,
  notdeformable   = false,
  gravity         = {int(b.get("gravity", 120))},
  tidalstrength   = {int(b.get("tidal", 12))},
  maxmetal        = 3.0,
  extractorradius = 80.0,
  voidwater       = {"true" if b.get("void") else "false"},
  voidground      = false,
  autoshowmetal   = false,

  smf = {{
    minheight    = {hmin:.1f},
    maxheight    = {hmax:.1f},
    smtfilename0 = "{smtname}",{minimap_line}
  }},

  resources = {{
    detailtex = "detailtex.bmp",
    detailnormaltex = "detail_normals.dds",
    splatdetailtex = "splat_dummy.png",
    splatdistrtex = "splat_distribution.png",
    splatdetailnormaldiffusealpha = 1,
    splatdetailnormaltex1 = "dnts_rock.png",
    splatdetailnormaltex2 = "dnts_pebbles.png",
    splatdetailnormaltex3 = "dnts_ground.png",
    splatdetailnormaltex4 = "dnts_shore.png",{emis_line}
  }},

  splats = {{
    texscales = {{0.010, 0.007, 0.008, 0.006}},
    texmults  = {{0.85, 0.65, 0.70, 0.55}},
  }},

  atmosphere = {{
    minwind      = {b["wind"][0]},
    maxwind      = {b["wind"][1]},
    fogstart     = {b.get("fog_start", 0.6)},
    fogend       = 1.0,
    fogcolor     = {lua_tuple(b["fog"])},
    suncolor     = {lua_tuple(b["sun"])},
    skycolor     = {lua_tuple(b["sky"])},
    clouddensity = {b.get("clouds", 0.5)},
    cloudcolor   = {lua_tuple(b.get("cloud", (1.0, 1.0, 1.0)))},{sky_line}
  }},
{grass_block}

  lighting = {{
    sundir              = {lua_tuple(sd)},
    groundambientcolor  = {lua_tuple(b["gamb"])},
    grounddiffusecolor  = {lua_tuple(b["gdif"])},
    groundspecularcolor = {{0.1, 0.1, 0.1}},
    groundshadowdensity = 0.8,
    unitambientcolor    = {lua_tuple(b["gamb"])},
    unitdiffusecolor    = {lua_tuple(b["gdif"])},
    unitspecularcolor   = {lua_tuple(b["gdif"])},
    unitshadowdensity   = 0.8,
    specularexponent    = 100.0,
  }},

  water = {{
    damage         = {b.get("water_damage", 0)},
    repeatx        = 0.0,
    repeaty        = 0.0,
    absorb         = {{0.004, 0.004, 0.002}},
    basecolor      = {lua_tuple(b["water_base"])},
    mincolor       = {lua_tuple(b["water_min"])},
    surfacecolor   = {lua_tuple(b["water_surf"])},
    surfacealpha   = 0.35,
    specularcolor  = {{0.8, 0.8, 0.8}},
{plane_line}
    fresnelmin     = 0.2,
    fresnelmax     = 0.8,
    fresnelpower   = 4.0,
    shorewaves     = true,
    forcerendering = false,
  }},

  teams = {{
{teams}
  }},

  terraintypes = {{
    [0] = {{
      name = "Default",
      hardness = 1.0,
      receivetracks = true,
      movespeeds = {{ tank = 1.0, kbot = 1.0, hover = 1.0, ship = 1.0 }},
    }},{void_type}
  }},

  custom = {{}},
}}

return mapinfo
'''


def metal_layout_lua(mexes):
    lines = ["return {", "\tspots = {"]
    for m in mexes:
        lines.append(f"\t\t{{x = {m['x']:.0f}, z = {m['z']:.0f}, metal = {m['metal']:.1f}}},")
    lines += ["\t},", "}", ""]
    return "\n".join(lines)


def startboxes_lua(sym, starts):
    """Start boxes for two teams, derived from the symmetry layout."""
    W, H = sym.W, sym.H
    names = {"diag": [("North-West", "NW"), ("South-East", "SE")],
             "ns": [("North", "N"), ("South", "S")],
             "ew": [("West", "W"), ("East", "E")]}[sym.layout]
    bw, bh = 0.22 * W, 0.22 * H
    out = ["return {"]
    for k, (x, z) in enumerate(starts):
        if sym.layout == "ns":
            x0, x1 = 0.15 * W, 0.85 * W
            z0, z1 = (0, 0.2 * H) if k == 0 else (0.8 * H, H)
        elif sym.layout == "ew":
            z0, z1 = 0.15 * H, 0.85 * H
            x0, x1 = (0, 0.2 * W) if k == 0 else (0.8 * W, W)
        else:
            x0, x1 = max(0, x - bw * 0.75), min(W, x + bw * 0.75)
            z0, z1 = max(0, z - bh * 0.75), min(H, z + bh * 0.75)
        out.append(f"""\t[{k}] = {{
\t\tnameLong = "{names[k][0]}",
\t\tnameShort = "{names[k][1]}",
\t\tstartpoints = {{ {{{x:.0f}, {z:.0f}}} }},
\t\tboxes = {{ {{ {{{x0:.0f}, {z0:.0f}}}, {{{x1:.0f}, {z0:.0f}}}, {{{x1:.0f}, {z1:.0f}}}, {{{x0:.0f}, {z1:.0f}}} }} }},
\t}},""")
    out.append("}\n")
    return "\n".join(out)


def _lua_num(v):
    v = float(v)
    return str(int(v)) if v.is_integer() else repr(v)


def startboxes_to_lua(boxes):
    """Inverse of luatable.startboxes(): [{team, name, short, polygons, startpoints}] -> map_startboxes.lua text.
    Coordinates are written exactly (no rounding), so parsing the result gives back the same boxes."""
    def pt(p):
        return "{%s, %s}" % (_lua_num(p[0]), _lua_num(p[1]))

    def poly(q):
        return "{ " + ", ".join(pt(p) for p in q) + " }"

    out = ["return {"]
    for b in sorted(boxes, key=lambda b: b["team"]):
        sps = ", ".join(pt(p) for p in b["startpoints"])
        polys = ", ".join(poly(q) for q in b["polygons"])
        out.append(f"""\t[{int(b["team"])}] = {{
\t\tnameLong = "{b["name"]}",
\t\tnameShort = "{b["short"]}",
\t\tstartpoints = {{ {sps} }},
\t\tboxes = {{ {polys} }},
\t}},""")
    out.append("}\n")
    return "\n".join(out)


def west_east_boxes_lua(W, H, team0, team1, depth=1700, margin=500):
    """Two teams with several start points each: West strip vs East strip."""
    f = lambda pts: ", ".join("{%d, %d}" % (x, z) for x, z in pts)
    return f"""return {{
\t[0] = {{ nameLong = "West", nameShort = "W", startpoints = {{ {f(team0)} }},
\t\tboxes = {{ {{ {{0, {margin}}}, {{{depth}, {margin}}}, {{{depth}, {H - margin}}}, {{0, {H - margin}}} }} }} }},
\t[1] = {{ nameLong = "East", nameShort = "E", startpoints = {{ {f(team1)} }},
\t\tboxes = {{ {{ {{{W - depth}, {margin}}}, {{{W}, {margin}}}, {{{W}, {H - margin}}}, {{{W - depth}, {H - margin}}} }} }} }},
}}
"""

"""Atlas Map Forge - map generator for Zero-K (Spring/Recoil engine).

Builds complete, ready-to-play .sdz map archives: heightmap, texture (SMT tiles), minimap,
metal spots, start boxes, features and optional map gadgets (lava cliffs, lava tides, volcano).
"""
__version__ = "0.4.22"

SQ = 8              # elmos per heightmap square
TEX_PER_SQ = 8      # texels per heightmap square
TILE = 32           # SMT tile size in texels

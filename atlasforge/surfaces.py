"""Surface types: dry, water, lava and void (bottomless abyss).

A map's surface controls the ``mapinfo.lua`` water table and any extra files the
archive must carry (the void death gadget). This module is shared by the AI
pipeline (``atlasforge/ai/pipeline.py``) and the Forge Editor's "Blank Sand"
template (``atlasforge/editor.py``) so both build self-contained maps the same way.

The water table is always written with explicit ``baseColor`` / ``minColor`` /
``surfaceColor`` (and ``planeColor`` where a plane exists), so a generated map
never falls back to black water.
"""

SURFACES = ("none", "water", "lava", "void")

# Human labels shown in the editor UI (they are also the stored choice values).
SURFACE_LABELS = ("None (Dry)", "Water", "Lava", "Void (Death Pit)")
SURFACE_BY_LABEL = {label: key for label, key in zip(SURFACE_LABELS, SURFACES)}

# Standard blue water palette ("water", and a safe fallback on dry/void maps).
WATER_BASE = (0.4, 0.6, 0.75)
WATER_MIN = (0.05, 0.2, 0.3)
WATER_SURF = (0.6, 0.75, 0.85)

# Glowing orange/red lava palette.
LAVA_BASE = (0.45, 0.15, 0.05)
LAVA_MIN = (0.25, 0.06, 0.0)
LAVA_SURF = (1.0, 0.45, 0.1)
LAVA_PLANE = (0.9, 0.3, 0.05)

# Minimal synced gadget for "void" maps: destroys units that fall below the
# void floor (the map has no water plane, so a unit can otherwise fall forever).
VOID_GADGET = """-- void_death.lua: kills units that fall below the void floor (bottomless abyss maps).
if (not gadgetHandler:IsSyncedCode()) then
    return
end

local VOID_Y = -60.0   -- elmos below sea level; anything lower is destroyed
local CHECK_EVERY = 15 -- frames between sweeps

function gadget:GetInfo()
    return {
        name      = "Void Death",
        desc      = "Destroys units that fall below the void floor.",
        author    = "Atlas Map Forge",
        date      = "2026",
        license   = "GPL v2+",
        layer     = 0,
        enabled   = true,
    }
end

function gadget:GameFrame(n)
    if n % CHECK_EVERY ~= 0 then
        return
    end
    for _, unitID in ipairs(Spring.GetAllUnits()) do
        local _, y = Spring.GetUnitPosition(unitID)
        if y and y < VOID_Y then
            Spring.DestroyUnit(unitID, false, true)
        end
    end
end
"""


def surface_key(value):
    """Normalise a surface name (key or UI label) to one of ``SURFACES``."""
    if value in SURFACES:
        return value
    if value in SURFACE_BY_LABEL:
        return SURFACE_BY_LABEL[value]
    raise ValueError(f"unknown surface {value!r}, expected one of {SURFACES} or {SURFACE_LABELS}")


def surface_water(surface_type, waterlevel=0.0):
    """``mapinfo.lua`` water override for a surface type.

    * ``none``  - no water plane (``voidwater = true``, water level far below terrain).
    * ``water`` - a real blue water plane at ``waterlevel`` (default 0), no damage.
    * ``lava``  - a real orange/red water plane at ``waterlevel``, ``water.damage = 100``.
    * ``void``  - no water plane (``voidwater = true``, level 0); the death gadget kills
      units that fall below the map.
    """
    surface_type = surface_key(surface_type)
    if surface_type == "water":
        return dict(voidwater=False, waterlevel=float(waterlevel), damage=0.0,
                    base=WATER_BASE, min=WATER_MIN, surf=WATER_SURF, plane=WATER_MIN)
    if surface_type == "lava":
        return dict(voidwater=False, waterlevel=float(waterlevel), damage=100.0,
                    base=LAVA_BASE, min=LAVA_MIN, surf=LAVA_SURF, plane=LAVA_PLANE)
    if surface_type == "void":
        return dict(voidwater=True, waterlevel=0.0, damage=0.0,
                    base=WATER_BASE, min=WATER_MIN, surf=WATER_SURF, plane=None)
    # none: dry map, no water plane, water level far below the terrain
    return dict(voidwater=True, waterlevel=-1000.0, damage=0.0,
                base=WATER_BASE, min=WATER_MIN, surf=WATER_SURF, plane=None)


def surface_extra_files(surface_type):
    """Extra ``.sdz`` files required by a surface type (the void death gadget)."""
    if surface_key(surface_type) == "void":
        return {"LuaRules/Gadgets/void_death.lua": VOID_GADGET}
    return {}

# Writing a map template for Atlas Map Forge

A guide for a developer or an AI agent who builds a new map template. Read it fully before you start.
It explains what a template is, which building blocks exist, the rules every map must follow, and what
to hand over at the end.

Repository: https://github.com/Scuide/atlas-map-forge (Python 3.9+, numpy/scipy, GPL-2.0-or-later).
Game: Zero-K (Recoil engine). Only Zero-K matters; ignore other Spring games.

---

## 1. What you deliver

| File | Content |
|---|---|
| `atlasforge/templates/<id>.py` | one `Template` subclass (required) |
| `atlasforge/templates/__init__.py` | one import + one entry in `_REGISTRY` (required) |
| `tests/test_template_<id>.py` | tests from section 9 (required) |
| `atlasforge/gadgets/lua_<name>.lua` + a helper in `atlasforge/gadgets/__init__.py` | only if the template needs a new map gadget (Lua) |
| `HANDOFF_<id>.md` | short report, see section 10 (required) |
| `<id>_preview.png` | `atlasforge preview <id> --seed 1` output (required) |

Do **not** change the core modules (`terrain.py`, `noise.py`, `symmetry.py`, `checks.py`, `forge.py`,
`archive.py`, `render.py`, `formats.py`, `design.py`, `templates/base.py`, `templates/common.py`, the app).
If you need something there, write it as a private helper in your template file and describe the wish in
the handoff; it will be moved into the core during integration.

No new dependencies. Everything must run with numpy, scipy, Pillow and scikit-image.

## 2. Setup and quick loop

```
git clone https://github.com/Scuide/atlas-map-forge
cd atlas-map-forge
pip install -e .[test]
pytest                                   # must be green before and after your work
```

While developing, a template can be tried without touching the registry
(see `examples/template_twin_plateaus.py`, a complete working template):

```
python examples/template_twin_plateaus.py
```

After registering it:

```
atlasforge templates                                     # your template must be listed
atlasforge preview <id> --seed 1 --set key=value         # picture + check report in seconds
atlasforge preview <id> --advanced --set size=6          # advanced-mode limits
atlasforge build <id> --seed 1 --author Test --out out   # full map (.sdz), 20-70 s
atlasforge app --browser                                 # the app in your browser
```

## 3. Units, coordinates, heights

- All lengths are **elmos**. The heightmap has one sample every `SQ = 8` elmos.
- A map of size `S` (Spring map units, even number) has a heightmap of `n = S * 64 + 1` samples per side,
  width `W = (n - 1) * 8` elmos. Size 16 = 8192 elmos.
- Arrays are indexed `h[z, x]`. `x` grows to the east, `z` to the south. `xx, zz = grid(n)` gives elmo
  coordinates of every sample.
- Points are `(x, z)` tuples in elmos.
- Height in elmos. Normal ground in templates is about `H_LOW = 100`. Water surface is `0`; below 0 is
  water (or lava if the template says so). Typical walls are 250-650 elmos above the ground.
- Angles: 0 degrees = east (+x), 90 degrees = south (+z).

## 4. Engine rules you must respect

| Rule | Value | Where it matters |
|---|---|---|
| Tanks and hovers climb | movedef 18 degrees = about 27 degrees real slope | ramps, gates; design ramps at 12-18 degrees real |
| Bots and amphibians climb | movedef 36 = about 54 degrees real | rock humps (only bots pass) |
| Spiders | any slope | walls must be lava-protected if spiders must not walk on them (see lava cliffs) |
| Water depth | tanks up to 22, bots up to 16 elmos; hovers on any water; amphibians anywhere | fords, channels |
| Slope test | `move_slope(h)` reproduces the engine (averages 16-elmo cells) | use it, never your own slope formula |
| Start areas | flat disc radius 330 (core) / 650 (blend) | `flatten_all` does it |
| Metal spots | flat disc 45/100 elmos, values 1.5-4.0 (2.0 normal, 3+ rich) | `flatten_all` |
| Geovents | flat disc 55/110 | `flatten_all` |

Unit class masks for checks: `checks.unit_masks(h)` returns bool grids for
`tanks, bots, spiders, amphibians, hovers`.

## 5. The template interface

```python
from atlasforge.templates.base import Param, Template
from atlasforge.templates.common import biome_param, size_param

class MyTemplate(Template):
    id = "my_template"            # lowercase, underscores; used on the command line
    title = "My Template"         # shown in the app gallery
    modes = ("1v1", "team")       # any of "1v1", "team", "ffa", "coop" - filters in the app
    tags = ("land", "chokes")     # any of "land", "sea", "twist" (map gadget changes the game), "chokes"
    players = "1v1 to 3v3"        # short text on the gallery card
    description = "One or two sentences for the player: what makes this map special."
    params = (
        size_param((12, 14, 16, 18, 20), 16, adv_smallest=10),
        biome_param("temperate"),
        Param("gates", "Gates", "int", 3, min=1, max=4, step=1, adv_max=8,
              help="Number of openings in the wall"),
    )

    def make(self, v, seed, log=print):
        ...                       # v: dict of checked parameter values
        return Design(...)
```

### Parameters (`Param`)

| Field | Meaning |
|---|---|
| `key`, `label` | id and English label shown in the app |
| `kind` | `"int"`, `"float"`, `"choice"`, `"bool"` |
| `default` | must lie inside `min..max` / `choices` |
| `min`, `max`, `step` | safe range (the normal slider) |
| `choices` | tuple for `"choice"` |
| `adv_min`, `adv_max`, `adv_choices` | wider range for **advanced mode**. The template must not crash anywhere inside it (a failing check is fine) |
| `help` | one short English sentence, shown under the control |
| `info` | **required**: 2-5 English sentences for the info popup ("i" next to the label): what the setting does, its unit, and what it changes in a game (which units profit, faster/slower, easier/harder to defend). Write for players who have never made a map. Alternatively set a class attribute `infos = {key: text}` |
| `group` | leave empty: the app shows Map (size, biome), Resources, Terrain and then your settings under the template's title |

- `size_param(choices, default, adv_smallest)` and `biome_param(default)` are the standard map size and
  biome controls. `adv_smallest` = smallest size your template can still build without crashing.
- **Do not** add `mex_count`, `metal`, `geos`, `wind`, `tidal`, `trees`, `rocks`, `wrecks` or `erosion`
  (and no own "number of metal spots" setting): every template gets them automatically
  (`general_params()`); `forge.make` applies them after your `make()`. Rocks and wrecks keep away from
  starts, metal spots, `gates`, `keep_clear`, `hazard` and `blocked`, so register those areas.
- Metal spot and geo counts (`atlasforge.resources`): the user picks "Metal spots" per side (per quarter on
  four-way maps, whole map when not symmetric) and "Geothermal vents" per side. The core removes the most
  crowded expansion spots or adds new ones in mirrored sets on flat ground that builders reach
  (tanks; amphibians on naval maps), outside `keep_clear`, `blocked`, `hazard` and `gates`. Spots within
  900 elmos of a start and spots with `"fixed": True` in their dict are never removed - mark spots that
  your design depends on (e.g. the metal in a ring centre) as fixed. Your template should still pick a good
  default count for the map size.
- Make as much adjustable as is sensible (counts, widths, heights, timings, on/off features). The user
  wants many settings; give every numeric setting a generous advanced range.

### Determinism

`make()` must give the same map for the same `v` and `seed`. Use only
`rng = np.random.default_rng(seed)` (and derived generators). No `random`, no time, no global state.

### Performance

`make()` at size 20 should take under 5 seconds (vectorised numpy; avoid Python loops over samples).
The app calls it on every slider change.

## 6. The `Design` you return

`from atlasforge.design import Design`

| Field | Required | Meaning |
|---|---|---|
| `hm` | yes | heightmap, `float32`, shape `(n, n)` |
| `sym` | yes | `Symmetry(layout, W, W)`; layout `"ew"`, `"ns"` or `"diag"` (180 degree rotation) |
| `starts` | yes | all start points `[(x, z), ...]` in mapinfo team order |
| `teams` | yes | start points per side `[[team 0 points], [team 1 points]]` (exactly two sides) |
| `mexes` | yes | `[{"x", "z", "metal", "side"}]`, use `mirror_pairs()` |
| `geos` | yes | `[(x, z)]` (may be empty) |
| `biome` | yes | `BIOMES[v["biome"]]` (a copy if you change values) |
| `title` | yes | default map title (English) |
| `description` | yes | English text for the map page; gameplay in one or two sentences |
| `startboxes` | recommended | Lua text from `west_east_boxes_lua`, `four_base_boxes`, `coop_boxes`; default boxes from the symmetry otherwise |
| `gates` | recommended | `[(name, bool mask)]` chokes; the check report says which chokes each unit class must use, the app labels them |
| `paint` | optional | dict of 0..1 layers: `lava`, `ice`, `scorch`, `concrete`, `molten` (use `paint_field(mask)`) |
| `extra_files` | optional | `{archive path: text}` for map gadgets (`LuaRules/Gadgets/...`, `mapconfig/...`) |
| `hazard` | optional | bool grid of damaging ground (lava cliffs); red outline in the app |
| `blocked` | optional | bool grid no ground unit survives (lava sea); excluded from reachability |
| `movement_profile`, `naval_starts` | optional | `"naval"` for sea maps (ships, hovers and amphibians decide the check instead of tanks and bots); `naval_starts` = one water access point (port) per side `[[(x, z)], [(x, z)]]` in water deeper than 15 elmos |
| `event_zone`, `event_label` | optional | bool grid hit by timed events (e.g. lava bombs) + English label |
| `notes`, `notes_ok` | optional | extra English check lines (e.g. "Bases are only reachable through their gates: yes") and whether they passed |
| `tree_block`, `keep_clear` | optional | bool grids without trees / without trees and erosion (ramps, roads) |
| `marks`, `side_labels` | optional | preview markers `[(x, z, text, rgb)]`; wording of the sides (`("the players", "chicken land")`) |
| `features` | optional | designed features `[(name, x, z, rotation)]` |
| `random_trees` | optional | `False` to switch off random trees |

## 7. Building blocks

### Terrain (`atlasforge.terrain`)

| Function | Use |
|---|---|
| `grid(n)` | elmo coordinates `xx, zz` |
| `plateau(h, sdf, top, side_deg=60, noise=None, amp=0, round_=24, toe=10)` | raise ground where `sdf < 0`; soft max, rounded top edge, blended foot. Walls 70-80 degrees, gentle hills 9-20 |
| `pit(h, sdf, bottom, ...)` | cut a lake, trench or channel (soft min) |
| `box_sdf(xx, zz, cx, cz, hx, hz)` | rectangle (signed distance, elmos) |
| `ring_sdf(xx, zz, cx, cz, R, half, gates=(angles), gate_hw)` | ring wall with gaps; gaps keep natural ground |
| `ellipse_sdf(xx, zz, cx, cz, rx, rz)` | ellipse |
| combine SDFs | `np.minimum(a, b)` = union, `np.maximum(a, b)` = intersection, `np.maximum(a, -b)` = cut |
| `road(h, p0, p1, hw, h0, h1, down_deg, up_deg, ...)` | straight ramp/road with a height profile; joins plateaus without steps |
| `road_polyline(h, pts, prof, hw, ..., blend, end_fade)` | curved road along dense points with a height per point |
| `smooth_profile(s, L, h0, h1, blend)` | C1 height profile for ramps |
| `flatten_disc(h, x, z, r_in, r_out, target=None)` | flat spot |
| `move_slope(h)`, `slope_deg(h)` | engine slope / plain slope |

Ramp length for a height difference `dh` at a real slope of 15 degrees: `dh / tan(15 deg)`.

### Noise (`atlasforge.noise`)

`fbm(shape, rng, base, octaves)`, `ridged(shape, rng, base)`, `smoothstep(e0, e1, x)` (only with
`e0 < e1`; for a falling edge use `1 - smoothstep(lo, hi, x)`), `norm01`, `terrace`.
`templates.common.base_terrain(n, rng, calm_r, center_x, sym=...)` gives gentle ground plus hills and
returns `h, xx, zz, low, en` (`low`: normalised fbm, `en`: edge noise -1..1 for wobbly SDF edges).

### Symmetry (fairness)

Two-sided maps must be **exactly** symmetric (terrain, metal, geovents, start points).

1. Make the noise symmetric **before** building anything on it: `base_terrain(..., sym="ew")` or
   `sym_fields(mode, low, hills, en)` with mode `"ew"`, `"ns"`, `"point"` (180 degree rotation) or `"d4"`
   (four-way). This avoids a visible crease along the centre line.
2. Build only on one half (or build symmetric shapes).
3. Copy exactly: `mirror_east_west(h)`, `mirror_point(h)` or `d4(h)`; points with `mirror_pairs(points, sym)`,
   `sym.mirror(x, z)` or `d4_points(points, W)`.
4. `flatten_all(h, starts, mexes, geos)`, then copy again (flattening may touch the centre line).

Co-op maps (like chicken defense) need no symmetry.

#### Free-for-all for 3 to 8 players (rotation, `atlasforge.symmetry.RotSymmetry`)

Reference: `templates/ffa_ring.py`. Every player gets an identical sector, rotated about the map centre.

| Piece | Use |
|---|---|
| `sym = RotSymmetry(N, W)` | design symmetry; player k's sector is centred on `sym.angle(k)` (player 0 at the top) |
| `sym.polar(r, deg, k)` | point at radius `r` and angle `deg` inside sector k (0 = the sector's centre line) |
| `sym.rotate(x, z, k)`, `sym.orbit(x, z)`, `sym.sector(x, z)` | copy points to the other players, find a sector |
| `rot_fields(sym, low, hills, en)` | noise made rotationally symmetric without losing strength (do this first) |
| `rotate_points([(x, z, metal)], sym)` | mex list for all players (`side` = player index) |
| `ffa_boxes(sym, starts, r_in, r_out)` | one wedge-shaped start box per player (`templates.common`) |
| `PLAYER_COLORS` | start colours for up to 8 players (`start_colors=`) |

- Build terrain from rotation-invariant shapes: radius `r` and the angle inside the own sector
  (`rel = (atan2 - sym.a0 + sec/2) % sec - sec/2`), or the distance to the nearest start. Grids cannot be
  rotated exactly by other angles than 90 degrees, so do not copy the heightmap; build it symmetric.
- The square's corners lie outside the fair circle: fill them with ground nobody uses (FFA Ring: a
  mountain rim, also in `keep_clear`).
- `teams=[[s] for s in starts]` (one team per player), `side_labels=("your base", "every other base")`.
  The check requires every base to reach every other base. Metal spot and geo counts, rocks, wrecks,
  trees and erosion follow the rotation automatically (counts are "per player").
- Naval free-for-all (several ports) is not supported by the naval check yet.

### Start boxes (`atlasforge.formats`, `templates.common`)

`west_east_boxes_lua(W, H, team0, team1, depth, margin)`, `four_base_boxes(team0, team1, names0, names1, W)`
(2v2 or FFA), `coop_boxes(player_box, enemy_box, players)`. Box names are English.

### Map gadgets (`atlasforge.gadgets`)

| Helper | What it adds |
|---|---|
| `lava_cliff_mask(h, starts)` + `lava_cliff_files(mask)` + `paint_field(mask)` | unreachable high ground glows as lava and slowly damages units (stops spiders from walking walls). Offer it as a bool parameter for walls |
| `lava_config(high, calm_s, high_s, ...)` | lava tides with ZK's `map_lava` (rising lava on a schedule) |
| `tide_files(fords, flood_level)` | on-screen countdown and flood markers for the tides |
| `eruption_files(...)` | volcano eruptions with lava bombs (see `templates/volcano.py`) |
| `chicken_zone_files(h, protect)` | keeps chicken roosts out of the player area |

New gadgets: Lua 5.1 compatible (the test suite parses all Lua with Lua 5.4: do not assign to a numeric
`for` loop variable). Synced and unsynced parts, English screen texts and comments, file name
`LuaRules/Gadgets/atlas_<name>.lua`, settings in `mapconfig/atlas_<name>.lua`. Only use effects and sounds
that exist in Zero-K (`lava_explo`, `lavaburst_generic`, `blacksmoke`, `napalm_firewalker_small`,
`sounds/explosion/ex_large4.wav`).

### Checks (`atlasforge.checks`)

`forge.check(design)` runs `report()`: every unit class must reach the enemy (tanks and bots required),
own bases connected, every metal spot reachable for tanks; `gates` show the chokes used; `blocked` ground
is excluded. Add template-specific checks as `notes` with `notes_ok`, using `unit_masks` and
`connected(mask, a, b)`.

## 8. Design rules

- **English only** in everything that reaches the game or the user: title, description, parameter labels
  and help, start box names, notes, Lua texts and comments.
- **Playable by default.** With default settings and seeds 1-10 the check must be OK.
- **Clean transitions.** Use the defaults of `plateau`/`pit` (rounded edges, blended feet). Ramps ease in
  and out (`road` does). Gates in walls should leave natural ground (`ring_sdf` gates, SDF cuts) instead of
  road strips with side walls. No hard creases, steps or fans of streaks; look at the preview zoomed in.
- **Walls players must not climb:** steep (70-80 degrees) and offer `lava_tops` (lava cliffs).
- **Chokes:** register them in `gates` so the report and the app can name them.
- **Metal:** both sides equal; 2.0 near the base, richer towards contested ground; total roughly
  `6-8 x map size` for 1v1 sizes. Spots on flat ground, not on ramps or wall feet (keep 150 elmos away).
- **Trees:** block them where they would clog ramps and gates (`tree_block` / `keep_clear`).
- **Advanced mode:** test the extremes of every advanced range; fix crashes (index errors at small sizes,
  empty lists, divisions by zero). Wrong-but-buildable maps are acceptable there.
- **Readable code:** short docstring at the top of the file explaining the layout; constants named in
  CAPITALS; comments in English.

## 9. Tests (copy and adapt)

```python
"""Tests for the <id> template."""
import json
import pytest
from atlasforge import forge
from atlasforge.templates import get

TID = "<id>"

@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_defaults_pass_the_check(seed):
    d = forge.make(TID, {}, seed=seed, log=lambda *a: None)
    ok, lines = forge.check(d)
    assert ok, "\n".join(lines)
    assert d.mexes and len(d.teams) == 2

def test_symmetric():                    # remove for co-op templates
    import numpy as np
    d = forge.make(TID, {"erosion": 0}, seed=1, log=lambda *a: None)
    h = d.hm
    assert min(np.abs(h - h[:, ::-1]).max(), np.abs(h - h[::-1, ::-1]).max(), np.abs(h - h[::-1]).max()) < 1e-3

def test_advanced_extremes_do_not_crash():
    t = get(TID)
    for p in t.params:
        vals = []
        if p.kind in ("int", "float"):
            vals = list(p.limits(True))
        elif p.kind == "choice":
            vals = list(p.options(True))
        for val in vals:
            forge.make(TID, {p.key: val, "erosion": 0}, seed=1, log=lambda *a: None, advanced=True)

def test_info_and_preview():
    json.dumps(get(TID).info())
    d = forge.make(TID, {}, seed=1, log=lambda *a: None)
    assert forge.preview(d, size=256).size == (256, 256)

def test_build(tmp_path):
    from atlasforge.config import ForgeConfig
    d = forge.make(TID, {"size": get(TID).param("size").choices[0]}, seed=1, log=lambda *a: None)
    info = forge.build(d, outdir=str(tmp_path), config=ForgeConfig(author="Test"), log=lambda *a: None)
    assert info["bytes"] > 1_000_000
```

Then run the whole suite: `pytest`.

## 10. Handoff report (`HANDOFF_<id>.md`)

- Template id, title, one-paragraph description of the layout and the intended gameplay.
- Parameter table: key, label, default, safe range, advanced range, what it changes.
- Check report for seeds 1-5 at defaults (copy the output of `atlasforge preview`).
- Timing: `make()` at the smallest and largest default size.
- Known weaknesses and ideas.
- Wishes for core changes (with the private helper you wrote instead).
- Attach `<id>_preview.png`. If you could build and load the map in Zero-K, say so and what you saw.

## 11. Reference templates

| File | Shows |
|---|---|
| `examples/template_twin_plateaus.py` | minimal complete template (plateaus, ramps, mirror symmetry, chokes) |
| `templates/chokepoint.py` | wall with gates of different types, lava cliffs, gate masks |
| `templates/river.py` | lake/river, fords with road profiles, lava tides and countdown gadget |
| `templates/arena.py` | four-way symmetry (`d4`), ring walls with gates, 2v2/FFA start boxes, notes |
| `templates/volcano.py` | point symmetry, causeways, eruption gadget, event zones, flood checks |
| `templates/chicken.py` | co-op map without symmetry, chicken zones gadget |
| `templates/skirmish.py` + `procedural.py` | noise styles with automatic ramp carving |

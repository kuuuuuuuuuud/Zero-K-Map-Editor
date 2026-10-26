"""Editor API: /api/edit, /api/project_dump and /api/project_load, and a build that includes manual edits."""
import json
import math
import time
import urllib.error
import urllib.request

import pytest

from atlasforge.app.server import serve
from atlasforge.project import FORMAT_ID

DUEL = {"size": 12, "gates": 2}
FFA = {"players": 5, "size": 20}


@pytest.fixture()
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "cfg"))
    srv, url, state = serve(0)

    def call(path, body=None):
        req = urllib.request.Request(url + "api/" + path, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"X-Forge-Token": state.token})
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    yield call, state, tmp_path
    srv.shutdown()


def _pts(mexes):
    return sorted((round(m["x"], 3), round(m["z"], 3)) for m in mexes)


def _free_spot(p):
    """Candidate spots off the centre line, 150+ elmos from every mex, geovent and start."""
    W, H = p["W"], p["H"]
    taken = [(m["x"], m["z"]) for m in p["mexes"]] + [tuple(g) for g in p["geos"]] + [tuple(s) for s in p["starts"]]
    for fx in (0.3, 0.25, 0.35, 0.2):
        for fz in (0.3, 0.45, 0.6, 0.2):
            c = (fx * W, fz * H)
            if all(math.hypot(c[0] - q[0], c[1] - q[1]) > 150 for q in taken):
                return c
    raise AssertionError("no free spot")


def _move_first_mex(call, p):
    m = p["mexes"][0]
    for c in [_free_spot(p)]:
        out = call("edit", {"id": p["id"], "edits": [{"op": "move_mex", "from": [m["x"], m["z"]], "to": list(c)}]})
        if not out["problems"]:
            return m, c, out
    raise AssertionError("edit was rejected")


def test_edit_1v1_moves_mex_and_its_mirror(api):
    call, _, _ = api
    p = call("preview", {"template": "chokepoint", "values": DUEL, "seed": 3})
    before = _pts(p["mexes"])
    m, c, out = _move_first_mex(call, p)
    assert {"mexes", "lines", "ok", "problems"} <= out.keys()
    after = _pts(out["mexes"])
    assert len(after) == len(before)
    assert (round(c[0], 3), round(c[1], 3)) in after
    moved = set(after) - set(before)
    assert len(moved) == 2                                  # the mex and its mirror partner, nothing else
    assert (round(m["x"], 3), round(m["z"], 3)) not in after


def test_edit_ffa_moves_whole_rotation_orbit(api):
    call, _, _ = api
    p = call("preview", {"template": "ffa_ring", "values": FFA, "seed": 2})
    n = p["sym"]["n"]
    assert p["sym"]["kind"] == "rot" and n >= 3
    before = _pts(p["mexes"])
    m, c, out = _move_first_mex(call, p)
    after = _pts(out["mexes"])
    assert (round(c[0], 3), round(c[1], 3)) in after
    assert len(set(after) - set(before)) == n               # one copy per player in the rotation
    assert len(after) == len(before)


def test_project_roundtrip_keeps_fields_and_extra(api):
    call, state, _ = api
    data = {"template": "chokepoint", "values": DUEL, "seed": 3, "symmetry": False,
            "edits": [{"op": "del_mex", "at": [100.0, 200.0]}], "title": "Roundtrip", "notes": "kept"}
    text = call("project_dump", {"data": data})["text"]
    loaded = call("project_load", {"text": text})
    p = loaded["project"]
    for k in ("template", "values", "seed", "symmetry", "edits"):
        assert p[k] == data[k], k
    assert p["format"] == FORMAT_ID and p["title"] == "Roundtrip"
    assert loaded["extra"] == {"notes": "kept"}
    assert call("project_dump", {"data": loaded["project"]})["text"] == text


def test_project_load_rejects_newer_version_and_bad_edit(api):
    call, state, _ = api
    text = call("project_dump", {"data": {"template": "chokepoint", "values": DUEL, "seed": 3}})["text"]
    p = json.loads(text)

    p["version"] = 99
    with pytest.raises(urllib.error.HTTPError) as e:
        call("project_load", {"text": json.dumps(p)})
    assert e.value.code == 400
    assert "newer version" in json.loads(e.value.read())["error"]

    p["version"] = 1
    p["edits"] = [{"op": "move_mex", "from": [1, 2]}]      # 'to' is missing
    with pytest.raises(urllib.error.HTTPError) as e:
        call("project_load", {"text": json.dumps(p)})
    assert e.value.code == 400
    assert "edits[0].to" in json.loads(e.value.read())["error"]


def test_build_with_edits_writes_moved_mex(api):
    call, _, tmp = api
    call("config", {"author": "Tester", "outdir": str(tmp / "out")})
    (tmp / "out").mkdir()
    p = call("preview", {"template": "chokepoint", "values": DUEL, "seed": 3})
    m, c, out = _move_first_mex(call, p)
    job = call("build", {"id": p["id"], "title": "Edited Test", "version": 1, "install": False})
    for _ in range(240):
        job = call("job/" + job["id"])
        if job["state"] != "running":
            break
        time.sleep(0.5)
    assert job["state"] == "done", job
    import zipfile
    with zipfile.ZipFile(tmp / "out" / "Forge_Edited_Test_v1.sdz") as z:
        layout = z.read("mapconfig/map_metal_layout.lua").decode()
    assert f"x = {c[0]:.0f}, z = {c[1]:.0f}" in layout
    assert f"x = {m['x']:.0f}, z = {m['z']:.0f}" not in layout


def test_edit_set_box_changes_returned_boxes(api):
    call, _, _ = api
    p = call("preview", {"template": "chokepoint", "values": DUEL, "seed": 3})
    box = next(b for b in p["boxes"] if b["team"] == 0)
    poly = [[x + 20, z] for x, z in box["polygons"][0]]
    out = call("edit", {"id": p["id"], "edits": [{"op": "set_box", "team": 0, "poly": 0, "points": poly}],
                        "symmetry": False})
    assert out["problems"] == []
    got = next(b for b in out["boxes"] if b["team"] == 0)
    assert got["polygons"][0] == [[float(x), float(z)] for x, z in poly]
    assert got["polygons"][1:] == box["polygons"][1:]

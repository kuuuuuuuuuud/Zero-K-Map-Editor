"""The app's local server: token check, preview with layers, start boxes, versions, a build job."""
import json
import time
import urllib.error
import urllib.request

import pytest

from atlasforge.app.luatable import startboxes
from atlasforge.app.server import serve


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "cfg"))
    srv, url, state = serve(0)

    def call(path, body=None, token=True):
        req = urllib.request.Request(url + "api/" + path, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"X-Forge-Token": state.token} if token else {})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
            return json.loads(data) if r.headers["Content-Type"].startswith("application/json") else data
    yield call, url, tmp_path
    srv.shutdown()


def test_api_needs_token(app):
    call, url, _ = app
    with pytest.raises(urllib.error.HTTPError) as e:
        call("state", token=False)
    assert e.value.code == 403
    with urllib.request.urlopen(url) as r:                    # the page itself is public and carries the token
        assert b"Atlas Map Forge" in r.read()


def test_preview_layers_and_versions(app):
    call, _, tmp = app
    st = call("state")
    assert len(st["templates"]) >= 6 and "temperate" in st["biomes"]
    p = call("preview", {"template": "chokepoint", "values": {"size": 12, "gates": 2}, "seed": 3})
    assert p["ok"] and len(p["boxes"]) == 2 and len(p["gates"]) == 2
    nx, nz = p["grid"]
    assert len(call(f"layer/{p['id']}/height")) == nx * nz * 2
    assert len(call(f"layer/{p['id']}/cells")) == nx * nz
    for name in ("relief", "gates", "hazard", "reach_tanks", "reach_hovers"):
        assert len(call(f"layer/{p['id']}/{name}")) > 1000
    with pytest.raises(urllib.error.HTTPError):
        call(f"layer/{p['id']}/reach_boats")
    call("config", {"author": "Tester", "outdir": str(tmp / "out")})
    (tmp / "out").mkdir()
    (tmp / "out" / "Forge_Iron_Wall_v1.sdz").write_bytes(b"x")
    (tmp / "out" / "Forge_Iron_Wall_v3.sdz").write_bytes(b"x")
    v = call("versions?title=Iron%20Wall")
    assert v["existing"] == [1, 3] and v["suggested"] == 4


def test_build_job(app):
    call, _, tmp = app
    p = call("preview", {"template": "skirmish", "values": {"size": 8}, "seed": 2})
    with pytest.raises(urllib.error.HTTPError) as e:              # no author name -> no build
        call("build", {"id": p["id"], "title": "Tiny Test", "version": 1, "install": False})
    assert e.value.code == 400
    st = call("config", {"author": "Tester", "outdir": str(tmp / "out"), "prefix": "Mine", "badge": "none"})
    assert st["config"]["prefix"] == "Forge" and "badge" not in st["config"]
    with pytest.raises(urllib.error.HTTPError):
        call("build", {"id": p["id"], "title": "Bad/Name", "version": 1, "install": False})
    job = call("build", {"id": p["id"], "title": "Tiny Test", "version": 2, "install": False})
    for _ in range(240):
        job = call("job/" + job["id"])
        if job["state"] != "running":
            break
        time.sleep(0.5)
    assert job["state"] == "done", job
    assert job["result"]["name"] == "Forge Tiny Test v2"
    assert (tmp / "out" / "Forge_Tiny_Test_v2.sdz").exists()


def test_startbox_reader():
    src = '''-- comment
if GetTeamCount and GetTeamCount() <= 2 then
  return { [0] = { nameLong = "West", nameShort = "W", startpoints = { {10, 20} },
                  boxes = { { {0, 0}, {5, 0}, {5, 5}, {0, 5} } } } }
end
return { [0] = { nameLong = "Base 1" } }'''
    b = startboxes(src)
    assert b[0]["name"] == "West" and b[0]["polygons"][0][2] == [5.0, 5.0] and b[0]["startpoints"] == [[10.0, 20.0]]

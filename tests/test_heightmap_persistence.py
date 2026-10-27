"""Heightmap save/load/build lifecycle: painted terrain must survive a restart and the build
must report the actual height range in mapinfo.lua (numeric checks only - no image files read)."""
import os
import zipfile

from atlasforge.app import server as S


@pytest.fixture()
def forge(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "cfg"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    return S.Forge()


def _new_editor_design(forge, width=16, height=4):
    import uuid

    from atlasforge import forge as F
    from atlasforge.app.server import Entry
    d = F.make("editor", {"width": width, "height": height}, seed=1, log=lambda *a: None)
    ok, lines = F.check(d)
    e = Entry(d, ok, lines)
    did = uuid.uuid4().hex[:12]
    forge.designs[did] = e
    return did


def test_save_load_roundtrip_keeps_painted_height(forge, tmp_path):
    forge.set_config(dict(projdir=str(tmp_path / "proj"), outdir=str(tmp_path / "out"), author="Tester"))
    did = _new_editor_design(forge)
    r = forge.brush(dict(id=did, x=100, y=100, radius=1, strength=100.0,
                         mode="raise", symmetry="none", begin=True))
    assert float(forge.designs[did].design.hm[100, 100]) == 150.0

    saved = forge.project_save(dict(id=did, data=dict(
        template="editor", values={"width": 16, "height": 4}, seed=1,
        symmetry=True, edits=[], title="Hill")))
    assert os.path.isfile(os.path.join(saved["folder"], "Hill.heightmap.npy"))
    assert os.path.isfile(os.path.join(saved["folder"], "Hill.texture.png"))
    with open(saved["path"], encoding="utf-8") as f:
        assert '"heightmap_path"' in f.read()

    loaded = forge.project_load(dict(path=saved["path"]))
    assert "design" in loaded
    lh = forge.designs[loaded["design"]["id"]].design.hm
    assert float(lh[100, 100]) == 150.0


def test_build_mapinfo_uses_actual_height_range(forge, tmp_path):
    from atlasforge import config as C
    from atlasforge import forge as F
    forge.set_config(dict(projdir=str(tmp_path / "proj"), outdir=str(tmp_path / "out"), author="Tester"))
    did = _new_editor_design(forge)
    forge.designs[did].design.hm[100, 100] = 150.0
    forge.designs[did].base.hm[100, 100] = 150.0

    cfg = C.load()
    info = F.build(forge.designs[did].design, outdir=cfg.outdir, config=cfg,
                   title="Hill", version=1, log=lambda *a: None)
    assert info["hmin"] == 50.0 and info["hmax"] == 150.0
    with zipfile.ZipFile(info["path"]) as z:
        smf = [n for n in z.namelist() if n.endswith(".smf")][0]
        assert z.getinfo(smf).file_size > 0
        mi = z.read("mapinfo.lua").decode()
        assert "minheight    = 50.0," in mi
        assert "maxheight    = 150.0," in mi

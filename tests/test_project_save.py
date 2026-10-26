import os
import subprocess
import sys

import pytest

from atlasforge import project as P
from atlasforge.app import server as S


@pytest.fixture()
def forge(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "cfg"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    return S.Forge()


def _data(forge, title="My Map", **kw):
    tid = sorted(forge._template_ids())[0]
    d = dict(template=tid, values={}, seed=7, symmetry=True, edits=[], title=title, app_version="test")
    d.update(kw)
    return d


def test_save_writes_file_at_returned_path(forge, tmp_path):
    folder = tmp_path / "projects" / "new"                  # does not exist yet
    forge.set_config(dict(projdir=str(folder)))
    r = forge.project_save(dict(data=_data(forge)))
    assert r["path"] == os.path.join(str(folder), "My Map.forge.json")
    assert r["folder"] == str(folder)
    with open(r["path"], encoding="utf-8") as f:
        assert f.read() == P.dumps(forge._project_from(_data(forge))) + "\n"


def test_load_by_path_matches_saved_project(forge, tmp_path):
    forge.set_config(dict(projdir=str(tmp_path / "p")))
    data = _data(forge, edits=[{"op": "add_mex", "at": [10, 20], "metal": 2.0}])
    r = forge.project_save(dict(data=data))
    loaded = forge.project_load(dict(path=r["path"]))
    text = forge.project_dump(dict(data=data))["text"]
    assert loaded["project"] == forge.project_load(dict(text=text))["project"]
    assert loaded["project"]["edits"] == data["edits"]
    assert loaded["project"]["seed"] == 7
    assert loaded["project"]["template"] == data["template"]


def test_title_is_sanitised(forge, tmp_path):
    forge.set_config(dict(projdir=str(tmp_path / "p")))
    r = forge.project_save(dict(data=_data(forge, title="a/b:c")))
    assert os.path.basename(r["path"]) == "a_b_c.forge.json"
    assert os.path.dirname(r["path"]) == str(tmp_path / "p")


def test_empty_title_falls_back_to_map(forge, tmp_path):
    forge.set_config(dict(projdir=str(tmp_path / "p")))
    r = forge.project_save(dict(data=_data(forge, title="")))
    assert os.path.basename(r["path"]) == "map.forge.json"


def test_save_overwrites_existing_file(forge, tmp_path):
    forge.set_config(dict(projdir=str(tmp_path / "p")))
    first = forge.project_save(dict(data=_data(forge, seed=1)))
    second = forge.project_save(dict(data=_data(forge, seed=2)))
    assert first["path"] == second["path"]
    assert forge.project_load(dict(path=second["path"]))["project"]["seed"] == 2


def test_load_by_path_rejects_wrong_extension(forge, tmp_path):
    p = tmp_path / "project.txt"
    p.write_text(P.dumps(forge._project_from(_data(forge))), encoding="utf-8")
    with pytest.raises(ValueError):
        forge.project_load(dict(path=str(p)))


def test_load_by_path_rejects_large_file(forge, tmp_path):
    p = tmp_path / "big.forge.json"
    p.write_bytes(b" " * (5 * 1024 * 1024 + 1))
    with pytest.raises(ValueError, match="larger than 5 MB"):
        forge.project_load(dict(path=str(p)))


def test_set_config_projdir_persisted(forge, tmp_path):
    folder = str(tmp_path / "chosen")
    st = forge.set_config(dict(projdir=folder))
    assert st["projdir"] == folder
    assert forge.settings()["projdir"] == folder
    assert forge.settings()["default_projdir"] == S.C.default_projdir()


def test_default_projdir_used_when_unset(forge):
    assert forge.settings()["projdir"] == S.C.default_projdir()


def test_open_path_allows_file_in_projdir(forge, tmp_path, monkeypatch):
    folder = tmp_path / "proj"
    forge.set_config(dict(projdir=str(folder)))
    r = forge.project_save(dict(data=_data(forge)))
    opened = []
    monkeypatch.setattr(subprocess, "Popen", lambda args, **kw: opened.append(args))
    monkeypatch.setattr(os, "startfile", lambda p: opened.append(p), raising=False)
    forge.open_path(r["path"])
    assert opened


def test_open_path_refuses_outside_folders(forge, tmp_path):
    forge.set_config(dict(projdir=str(tmp_path / "proj")))
    with pytest.raises(PermissionError, match="project and Zero-K"):
        forge.open_path(str(tmp_path / "elsewhere.txt"))

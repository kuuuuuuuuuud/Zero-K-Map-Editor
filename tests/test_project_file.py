import copy

import pytest

from atlasforge import project as P


def _proj(**kw):
    return P.new_project("islands", {"size": 12}, 7, **kw)


def test_roundtrip():
    d = _proj(edits=[{"op": "add_mex", "at": [10, 20], "metal": 2.0}],
              title="Größe")
    assert P.loads(P.dumps(d)) == d


def test_extra_fields_preserved():
    d = _proj()
    d["future_thing"] = {"a": 1}
    out = P.loads(P.dumps(d))
    assert out["future_thing"] == {"a": 1}
    assert P.dumps(out) == P.dumps(d)


def test_future_version():
    d = _proj()
    d["version"] = 99
    with pytest.raises(ValueError, match="newer version"):
        P.loads(P.dumps(d))


def test_missing_format():
    d = _proj()
    del d["format"]
    with pytest.raises(ValueError, match="format"):
        P.loads(P.dumps(d))


def test_invalid_json():
    with pytest.raises(ValueError, match="invalid .forge.json"):
        P.loads("{nope")


def test_unknown_template():
    with pytest.raises(ValueError, match="template: unknown"):
        P.validate(_proj(), templates={"other"})
    assert P.validate(_proj(), templates={"islands"})


def test_empty_edits_ok():
    d = _proj(edits=[])
    assert P.validate_edits(d["edits"]) == []


BAD = [
    ({"op": "move_mex", "from": [1, 2]}, r"edits\[0\]\.to: expected \[x, z\]"),
    ({"op": "add_mex", "at": [1, 2], "metal": 0}, r"edits\[0\]\.metal"),
    ({"op": "del_mex"}, r"edits\[0\]\.at"),
    ({"op": "set_metal", "at": [1, 2], "metal": -1}, r"edits\[0\]\.metal"),
    ({"op": "move_geo", "from": [1], "to": [1, 2]}, r"edits\[0\]\.from"),
    ({"op": "add_geo", "at": "x"}, r"edits\[0\]\.at"),
    ({"op": "del_geo", "at": [1, 2, 3]}, r"edits\[0\]\.at"),
    ({"op": "move_start", "from": [1, 2], "to": [True, 2]},
     r"edits\[0\]\.to"),
    ({"op": "bogus"}, r"edits\[0\]\.op"),
    ({"op": "del_mex", "at": [float("nan"), 1]}, r"edits\[0\]\.at"),
    ({"op": "del_mex", "at": [float("inf"), 1]}, r"edits\[0\]\.at"),
    ({"op": "add_mex", "at": [1, 2], "metal": True}, r"edits\[0\]\.metal"),
]


@pytest.mark.parametrize("edit,pat", BAD)
def test_bad_edit(edit, pat):
    with pytest.raises(ValueError, match=pat):
        P.validate_edits([edit])


def test_edit_index_in_path():
    ok = {"op": "del_geo", "at": [1, 2]}
    with pytest.raises(ValueError, match=r"edits\[2\]"):
        P.validate_edits([ok, ok, {"op": "del_geo"}])


def test_bool_seed_and_symmetry():
    d = _proj()
    d["seed"] = True
    with pytest.raises(ValueError, match="seed"):
        P.validate(d)
    d = _proj()
    d["symmetry"] = 1
    with pytest.raises(ValueError, match="symmetry"):
        P.validate(d)


def test_migration_chain(monkeypatch):
    def v0_to_v1(data):
        data = copy.deepcopy(data)
        data["edits"] = data.pop("changes", [])
        data["version"] = 1
        return data

    monkeypatch.setitem(P.MIGRATIONS, 0, v0_to_v1)
    old = _proj()
    old["version"] = 0
    del old["edits"]
    old["changes"] = [{"op": "del_mex", "at": [3, 4]}]
    out = P.loads(P.dumps(old))
    assert out["version"] == 1
    assert out["edits"] == [{"op": "del_mex", "at": [3, 4]}]


def test_no_migration_path():
    d = _proj()
    d["version"] = 0
    with pytest.raises(ValueError, match="no migration path"):
        P.loads(P.dumps(d))


def test_save_load(tmp_path):
    d = _proj(title="Größe ü")
    p = tmp_path / "a.forge.json"
    P.save(p, d)
    assert P.load(p) == d


def test_set_box_edits_roundtrip_and_validate():
    edit = {"op": "set_box", "team": 1, "poly": 0, "points": [[10, 20], [300, 20], [300, 200], [10, 200]]}
    d = _proj(edits=[edit])
    assert P.loads(P.dumps(d))["edits"] == [edit]
    P.validate_edits([edit])


@pytest.mark.parametrize("edit,pat", [
    ({"op": "set_box", "team": "0", "poly": 0, "points": [[1, 2], [3, 4], [5, 6]]}, r"edits\[0\]\.team"),
    ({"op": "set_box", "team": 0, "poly": 0, "points": [[1, 2], [3, 4]]}, r"edits\[0\]\.points"),
    ({"op": "set_box", "team": 0, "poly": 0, "points": [[1, 2], [3, "z"], [5, 6]]}, r"edits\[0\]\.points"),
])
def test_bad_set_box(edit, pat):
    with pytest.raises(ValueError, match=pat):
        P.validate_edits([edit])


def test_file_without_box_edits_loads_unchanged():
    d = _proj(edits=[{"op": "del_geo", "at": [1, 2]}])
    assert P.loads(P.dumps(d)) == d

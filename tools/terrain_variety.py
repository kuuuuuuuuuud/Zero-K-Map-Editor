"""Audit flat terrain share, largest flat patch and seed influence per template."""
import argparse
import csv
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage

from atlasforge import SQ
from atlasforge import forge
from atlasforge.templates import all_templates, get


def slope_percent(h):
    """Local rise over run in percent between adjacent land cells; water is ignored."""
    h = np.ascontiguousarray(h, dtype=np.float64)
    land = h >= 0
    gx = np.zeros_like(h)
    gz = np.zeros_like(h)
    bx = land[:, :-1] & land[:, 1:]
    dx = np.abs(h[:, 1:] - h[:, :-1]) / SQ
    gx[:, :-1][bx] = dx[bx]
    gx[:, 1:][bx] = dx[bx]
    bz = land[:-1, :] & land[1:, :]
    dz = np.abs(h[1:, :] - h[:-1, :]) / SQ
    gz[:-1, :][bz] = dz[bz]
    gz[1:, :][bz] = dz[bz]
    return np.hypot(gx, gz) * 100.0


def flat_metrics(h, threshold=0.5):
    """Flat-land share and largest connected flat patch, both as shares of land cells."""
    h = np.ascontiguousarray(h, dtype=np.float64)
    land = h >= 0
    flat = land & (slope_percent(h) < threshold)
    labels, count = ndimage.label(flat)
    if count == 0 or not land.any():
        largest = 0.0
    else:
        largest = float(np.bincount(labels.ravel())[1:].max()) / int(land.sum())
    return {
        "flat_share": float(flat.sum() / land.sum()) if land.any() else 0.0,
        "largest_flat": largest,
    }


def height_difference(reference, h):
    """Mean |dh| against the reference map, normalized by the reference's height span."""
    r = np.ascontiguousarray(reference, dtype=np.float64)
    span = float(r.max() - r.min())
    if span <= 0:
        return 0.0
    return float(np.abs(h.astype(np.float64) - r).mean()) / span


def used_size_of(d):
    """Recover the grid size actually generated (hm side = size*SQ*SQ + 1)."""
    n = int(np.asarray(d.hm).shape[0])
    if n > 1 and (n - 1) % (SQ * SQ) == 0:
        return (n - 1) // (SQ * SQ)
    v = getattr(d, "values", None)
    if isinstance(v, dict) and "size" in v:
        return int(v["size"])
    raise ValueError(f"cannot determine map size for {getattr(d, 'template', '?')}")


def run(template_ids, seeds, size=None, threshold=0.5):
    """Measure every (template, seed) map; returns (rows, failures).

    Row: [tid, used_size, seed, flat_share, largest_flat, seed_diff] where
    seed_diff is 0 for the first successfully built seed of a template.
    """
    ids = [t.id for t in all_templates()] if not template_ids else list(template_ids)
    seeds = list(seeds)
    rows, failures = [], []
    for tid in ids:
        values = dict(get(tid).defaults())
        if size is not None:
            values["size"] = int(size)
        ref = None
        for s in seeds:
            try:
                d = forge.make(tid, values, seed=s, log=lambda *a: None)
            except Exception as e:
                failures.append((f"{tid} seed {s}", repr(e)))
                print(f"FAIL {tid} seed {s}: {e!r}", file=sys.stderr)
                continue
            used_size = used_size_of(d)
            m = flat_metrics(d.hm, threshold=threshold)
            diff = 0.0 if ref is None else height_difference(ref, d.hm)
            if ref is None:
                ref = d.hm
            rows.append([tid, used_size, s, m["flat_share"], m["largest_flat"], diff])
            print(f"ok   {tid:<15} seed={s} size={used_size}"
                  f" flat={m['flat_share']:.3f} largest={m['largest_flat']:.3f}", file=sys.stderr)
    return rows, failures


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Audit flat terrain share, largest flat patch and seed influence per template.")
    p.add_argument("templates", nargs="*", metavar="TEMPLATE_ID",
                   help="ids to audit (default: every registered template)")
    p.add_argument("--seeds", type=int, default=5, metavar="N", help="audit seeds 1..N (default: 5)")
    p.add_argument("--size", type=int, metavar="S",
                   help="override the standard size of every audited template")
    p.add_argument("--threshold", type=float, default=0.5, metavar="PCT",
                   help="slope below which land counts as flat, in percent (default: 0.5)")
    p.add_argument("-o", "--output", metavar="CSV",
                   help="write the per-map CSV here (default: out/terrain_variety.csv)")
    a = p.parse_args(argv)

    rows, failures = run(a.templates or None, range(1, a.seeds + 1),
                         size=a.size, threshold=a.threshold)
    if not rows:
        print("no maps could be generated", file=sys.stderr)
        return 2

    out = Path(a.output) if a.output else Path(__file__).resolve().parents[1] / "out" / "terrain_variety.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["template", "size", "seed", "flat_share", "largest_flat", "seed_diff"])
        for r in rows:
            w.writerow([r[0], r[1], r[2]] + [f"{v:.6f}" for v in r[3:]])

    by_template = {}
    for tid, _size, _seed, flat, largest, diff in rows:
        e = by_template.setdefault(tid, {"flat": [], "largest": 0.0, "diff": []})
        e["flat"].append(flat)
        e["largest"] = max(e["largest"], largest)
        e["diff"].append(diff)

    print("| template | mean flat share | max largest flat patch | mean seed diff |")
    print("|---|---|---|---|")
    for tid, e in sorted(by_template.items(), key=lambda kv: -sum(kv[1]["flat"]) / len(kv[1]["flat"])):
        mf = sum(e["flat"]) / len(e["flat"])
        md = sum(e["diff"]) / len(e["diff"])
        print(f"| {tid} | {mf:.3f} | {e['largest']:.3f} | {md:.4f} |")
    print(f"\nCSV written to {out}")

    if failures:
        print(f"{len(failures)} map(s) failed:", file=sys.stderr)
        for tag, err in failures:
            print(f"  {tag}: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

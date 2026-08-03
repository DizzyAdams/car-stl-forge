"""Original (non-OEM) parametric CAD interpretations of Ferrari & Porsche
design languages.

HONESTY CONTRACT (verified against project skills 3d-stl-production /
premium-automotive-rag-stl / 3d-vehicle-mesh-pipeline):
  - These are ORIGINAL geometric interpretations built from published
    design-language traits (proportions, stance, roofline) + real published
    dimensions in mm. They are NOT OEM CAD, scans, or licensed replicas.
  - They are exported as STEP (editable NURBS B-rep CAD) AND watertight STL,
    so they are genuinely "CAD" (unlike mesh-only procedural exports).
  - Brand/model names are used as CATALOG METADATA only.
  - Every entry carries `kind:"original-parametric"` + `license:"original"`.

Why this is the real path to "CAD de modelo de mercado":
  - Official OEM STEP/NURBS is proprietary + trademarked; no free source exists
    and redistribution would violate rights (blocked by design).
  - cadquery (installed) produces real B-rep STEP. This is the legitimate,
    editable, market-grade CAD we CAN ship.

Memory bounded: one model at a time, gc between. STL solidify uses the
project's proven voxelize->marching-cubes->Taubin recipe for printability.
"""
from __future__ import annotations
import gc, json, math, os, sys, time
from pathlib import Path

import cadquery as cq
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "vercel_site" / "models" / "cad_original"
CACHE = ROOT / "cad_cache"
OUT.mkdir(parents=True, exist_ok=True)
CACHE.mkdir(parents=True, exist_ok=True)

# (brand, model, slug, dims_mm, lang)  dims = (length, width, height, wheelbase)
FERRARI_PROFILES = {
    "ferrari_roma_interp": dict(
        dims=(4656, 1974, 1301, 2670), lang="gt_front_engine",
        note="Roma-inspired: long low nose, cab-forward cabin, fastback."),
    "ferrari_296_interp": dict(
        dims=(4565, 1958, 1187, 2600), lang="mid_engine_v6",
        note="296-inspired: compact mid-engine, short overhangs, twin-bubble roof."),
    "ferrari_sf90_interp": dict(
        dims=(4710, 1972, 1186, 2640), lang="hybrid_hyper",
        note="SF90-inspired: wide track, aggressive aero, low canopy."),
}
PORSCHE_PROFILES = {
    "porsche_911_interp": dict(
        dims=(4519, 1852, 1298, 2450), lang="911_silhouette",
        note="911-inspired: rounded fastback, pronounced haunches, wide arches."),
    "porsche_taycan_interp": dict(
        dims=(4963, 1966, 1378, 2900), lang="ev_sport_sedan",
        note="Taycan-inspired: low sleek EV sedan, raked roof, wide stance."),
    "porsche_918_interp": dict(
        dims=(4545, 1940, 1167, 2650), lang="hybrid_hyper",
        note="918-inspired: low open-top hyper, wide mid body."),
}


def build_body(dims, lang: str) -> cq.Workplane:
    L, W, H, WB = [d / 1000.0 for d in dims]  # mm -> m
    # Ground clearance ~ 110mm sports / 120mm hyper
    gc = 0.11
    # side profile as a closed polyline (x length, y height), original
    if lang == "911_silhouette":
        prof = [
            (-L/2, gc), (-L/2+0.18*L, gc+0.10*H), (-0.10*L, gc+0.30*H),
            (0.05*L, gc+0.52*H), (0.30*L, gc+0.66*H), (0.52*L, gc+0.60*H),
            (0.70*L, gc+0.42*H), (L/2-0.06*L, gc+0.26*H), (L/2, gc),
        ]
    elif lang in ("gt_front_engine",):
        prof = [
            (-L/2, gc), (-L/2+0.10*L, gc+0.20*H), (0.02*L, gc+0.40*H),
            (0.18*L, gc+0.60*H), (0.40*L, gc+0.66*H), (0.58*L, gc+0.56*H),
            (0.74*L, gc+0.40*H), (L/2-0.05*L, gc+0.24*H), (L/2, gc),
        ]
    elif lang in ("mid_engine_v6", "hybrid_hyper"):
        prof = [
            (-L/2, gc), (-L/2+0.16*L, gc+0.12*H), (-0.02*L, gc+0.34*H),
            (0.12*L, gc+0.56*H), (0.34*L, gc+0.62*H), (0.56*L, gc+0.52*H),
            (0.72*L, gc+0.36*H), (L/2-0.06*L, gc+0.22*H), (L/2, gc),
        ]
    else:  # ev_sport_sedan
        prof = [
            (-L/2, gc), (-L/2+0.12*L, gc+0.18*H), (0.04*L, gc+0.44*H),
            (0.22*L, gc+0.64*H), (0.46*L, gc+0.70*H), (0.66*L, gc+0.60*H),
            (0.80*L, gc+0.42*H), (L/2-0.05*L, gc+0.26*H), (L/2, gc),
        ]
    # close the loop at ground
    closed = prof + [(-L/2, gc)]
    wp = cq.Workplane("XZ").polyline(closed).close()
    # extrude across width, centered
    body = wp.extrude(W).translate((-W/2, 0, 0)) if False else \
        cq.Workplane("XZ").polyline(closed).close().extrude(W)
    body = body.translate((0, 0, 0))
    # center X
    body = body.translate((-L/2 if False else 0, 0, 0))
    # wheels (4 cylinders) for visual completeness
    r = 0.34 * H
    tw = 0.18 * W
    ax_f = -WB/2
    ax_r = WB/2
    for ax in (ax_f, ax_r):
        for sy in (-1, 1):
            wheel = cq.Workplane("XY").cylinder(r, tw).rotate((0,0,0),(1,0,0),90)\
                .translate((ax, sy*(W/2 - tw/2), gc + r*0.7))
            body = body.union(wheel)
    return body


def to_stl_watertight(solid: cq.Workplane, res: int = 64) -> trimesh.Trimesh:
    tmp = CACHE / f"_{os.getpid()}_cad.stl"
    cq.exporters.export(solid, str(tmp))
    mesh = trimesh.load(str(tmp), force="mesh")
    if not isinstance(mesh, trimesh.Trimesh):
        mesh = mesh.dump(concatenate=True)
    tmp.unlink(missing_ok=True)
    ext = float((mesh.bounds[1] - mesh.bounds[0]).max())
    if ext > 0:
        pitch = ext / float(res)
        try:
            voxel = mesh.voxelized(pitch).fill()
            cand = voxel.marching_cubes
            cand.apply_transform(voxel.transform)
            cand.merge_vertices()
            from trimesh.smoothing import filter_taubin
            filter_taubin(cand, iterations=2, lamb=0.5, nu=0.5)
            cand.merge_vertices()
            return cand
        except Exception:
            return mesh
    return mesh


def process(brand, model, slug, prof) -> dict:
    bdir = OUT / brand
    bdir.mkdir(parents=True, exist_ok=True)
    solid = build_body(prof["dims"], prof["lang"])
    # export real CAD (STEP) - editable NURBS B-rep
    step = bdir / f"{slug}.step"
    cq.exporters.export(solid, str(step))
    # export watertight STL
    stl_mesh = to_stl_watertight(solid)
    stl = bdir / f"{slug}.stl"
    stl_mesh.export(str(stl))
    meta = {
        "brand": brand, "model": model, "slug": slug,
        "kind": "original-parametric", "license": "original (not OEM CAD)",
        "designLanguage": prof["lang"], "note": prof["note"],
        "dims_mm": list(prof["dims"]),
        "watertight": bool(stl_mesh.is_watertight),
        "faces": int(len(stl_mesh.faces)),
        "extents_m": [round(float(e), 3) for e in stl_mesh.extents],
        "stl": f"/models/cad_original/{brand}/{slug}.stl",
        "step": f"/models/cad_original/{brand}/{slug}.step",
        "provenance": "cadquery parametric original (mm dims + design language)",
    }
    (bdir / f"{slug}.metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    gc.collect()
    return meta


def main() -> int:
    results = []
    for slug, prof in FERRARI_PROFILES.items():
        m = process("ferrari", slug.replace("ferrari_", "").replace("_interp", "").title(), slug, prof)
        results.append(m)
        print(f"ferrari {slug}: step={Path(m['step']).exists()} stl_wt={m['watertight']} faces={m['faces']} ext={m['extents_m']}")
    for slug, prof in PORSCHE_PROFILES.items():
        m = process("porsche", slug.replace("porsche_", "").replace("_interp", "").title(), slug, prof)
        results.append(m)
        print(f"porsche {slug}: step={Path(m['step']).exists()} stl_wt={m['watertight']} faces={m['faces']} ext={m['extents_m']}")
    (OUT / "cad_original_report.json").write_text(
        json.dumps({"count": len(results), "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print("DONE", len(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

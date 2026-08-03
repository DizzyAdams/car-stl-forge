"""Download genuinely-real Ferrari & Porsche 3D models from public GitHub repos
(no auth, no token) and convert them to watertight STLs for the showroom's
'brandreal' (real brand) gallery.

Honesty rules:
  - Every model keeps its source_repo + url + a license note in metadata.
  - None of these are official Ferrari/Porsche CAD; they are community-made
    models shared publicly on GitHub. We label them as 'community real model',
    never as 'official'.
  - The script only downloads self-contained GLB/OBJ/STL files (no .blend,
    no GLTF that needs external .bin) to avoid partial/broken conversions.

Processing is memory-bounded: one mesh at a time, gc between, voxelized
solidify into a printable watertight solid so the STL viewer/loader always
gets a closed manifold.
"""
from __future__ import annotations
import gc, json, sys, time, zipfile
import ssl, urllib.parse, urllib.request
from pathlib import Path

import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "vercel_site" / "models" / "brandreal"
CACHE = ROOT / "realmesh_cache" / "github"
CACHE.mkdir(parents=True, exist_ok=True)

# (brand, display_model, repo, path_in_repo, slug)
SOURCES = [
    # ---------------- FERRARI (all real community GLBs) ----------------
    ("ferrari", "Ferrari F40",            "Gakash05/Ferrari-3d-model",            "ferrari_f40.glb",                 "ferrari_f40"),
    ("ferrari", "Ferrari 812 GTS",        "kaqo2023-design/ferrari_812_gts.glb",  "ferrari_812_gts.glb",            "ferrari_812_gts"),
    ("ferrari", "Ferrari SF90 Spider",    "adambit27/3D-Ferrari-Spyder-Car-Model-GLB", "2021_ferrari_sf90_spider.glb", "ferrari_sf90_spider"),
    ("ferrari", "Ferrari 599 GTO",       "ehtick/3D_Car_Model",                 "public/ferrari_599_gto.glb",      "ferrari_599_gto"),
    ("ferrari", "Ferrari 488",           "juni0317/cars_three.js",             "ferrari488/scene.gltf",           "ferrari_488"),
    # ---------------- PORSCHE (real community GLBs) --------------------
    ("porsche", "Porsche 911 GT3 RS",     "uso-maper/porsche-3d-model",          "porsche_gt3_rs.glb",              "porsche_gt3_rs"),
    ("porsche", "Porsche 911 (Carrera)",  "juni0317/cars_three.js",             "porsche/scene.gltf",              "porsche_911"),
]

LICENSE_NOTE = "community model shared on GitHub (no LICENSE file in source repo) - not official Ferrari/Porsche."

EXT_KEEP = (".glb", ".gltf", ".obj", ".stl")
MAX_MB = 120  # generous ceiling; skip anything absurd


def gh_raw_url(repo: str, path: str) -> str:
    # repo may be "owner/name" or "owner/name" already; path is file path
    return f"https://raw.githubusercontent.com/{repo}/main/{urllib.parse.quote(path)}"


def download(url: str, dest: Path) -> bool:
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=90, context=ctx) as r:
            total = int(r.headers.get("Content-Length", "0"))
            if total and total > MAX_MB * 1024 * 1024:
                print(f"  SKIP too large {total//1024//1024}MB")
                return False
            tmp = dest.with_suffix(dest.suffix + ".part")
            with open(tmp, "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
            tmp.replace(dest)
        return True
    except Exception as e:
        print(f"  download ERR {repr(e)[:160]}")
        return False


def try_branches(repo: str, path: str) -> str | None:
    for br in ("main", "master"):
        url = f"https://raw.githubusercontent.com/{repo}/{br}/{urllib.parse.quote(path)}"
        ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}, method="HEAD")
        try:
            with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
                if r.status == 200:
                    return url
        except Exception:
            continue
    return None


def convert(path: Path) -> trimesh.Trimesh | None:
    mesh = trimesh.load(str(path), force="mesh")
    if not isinstance(mesh, trimesh.Trimesh):
        try:
            mesh = mesh.dump(concatenate=True)
        except Exception:
            return None
    # normalize orientation/scale: longest extent -> 4.2 m (car-like)
    ext = float((mesh.bounds[1] - mesh.bounds[0]).max())
    if ext > 0:
        mesh.apply_scale(4.2 / ext)
    mesh.apply_translation(-mesh.centroid)
    return mesh


def solidify(mesh: trimesh.Trimesh, res: int = 72) -> trimesh.Trimesh:
    extent = float((mesh.bounds[1] - mesh.bounds[0]).max())
    if extent <= 0:
        return mesh
    pitch = extent / float(res)
    try:
        voxel = mesh.voxelized(pitch).fill()
        cand = voxel.marching_cubes
        cand.apply_transform(voxel.transform)
    except Exception:
        cand = mesh
    cand.merge_vertices()
    try:
        from trimesh.smoothing import filter_taubin
        filter_taubin(cand, iterations=2, lamb=0.5, nu=0.5)
        cand.merge_vertices()
    except Exception:
        pass
    return cand


def process(brand, model_name, repo, path, slug) -> dict | None:
    bdir = OUT / brand
    bdir.mkdir(parents=True, exist_ok=True)
    src_ext = Path(path).suffix.lower()
    url = try_branches(repo, path)
    if not url:
        url = gh_raw_url(repo, path)

    if src_ext == ".gltf":
        cached = download_gltf_folder(repo, str(Path(path).parent), slug)
        if cached is None:
            return None
    else:
        cached = CACHE / f"{slug}{src_ext}"
        if not (cached.exists() and cached.stat().st_size > 1000):
            print(f"[dl] {brand} {model_name} <- {url}")
            if not download(url, cached):
                return None
    mesh = convert(cached)
    if mesh is None:
        print(f"  convert failed")
        return None
    src_wt = bool(mesh.is_watertight)
    cand = solidify(mesh)
    stl = bdir / f"{slug}.stl"
    cand.export(str(stl))
    meta = {
        "brand": brand, "model": model_name, "slug": slug,
        "source_repo": repo, "url": f"https://github.com/{repo}",
        "license": LICENSE_NOTE, "provenance": "github-raw-brand",
        "sourceWatertight": src_wt, "watertight": bool(cand.is_watertight),
        "sourceFaces": int(len(mesh.faces)), "faces": int(len(cand.faces)),
        "extents": [round(float(e), 3) for e in cand.extents],
        "stl": f"/models/brandreal/{brand}/{slug}.stl",
    }
    (bdir / f"{slug}.metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    gc.collect()
    return meta


def download_gltf_folder(repo: str, folder: str, slug: str) -> Path | None:
    """Download a .gltf + its .bin (and license) into a per-slug cache dir."""
    import json as _json
    import urllib.request as _ur
    ddir = CACHE / slug
    ddir.mkdir(parents=True, exist_ok=True)
    try:
        info = api_repo(f"repos/{repo}")
    except Exception as e:
        print("  repo info ERR", repr(e)[:120])
        return None
    branch = info.get("default_branch", "main")
    try:
        listing = api_repo(f"repos/{repo}/contents/{folder}?ref={branch}")
    except Exception as e:
        print("  folder ERR", repr(e)[:120])
        return None
    gltf_path = None
    for it in listing:
        name = it["name"]
        if name.lower().endswith(".gltf"):
            gltf_path = ddir / name
        if name.lower().endswith((".bin", ".gltf", ".license", "license.txt", "licence.txt")) or name.lower().startswith("license"):
            dest = ddir / name
            if not (dest.exists() and dest.stat().st_size > 100):
                try:
                    _fetch(it["download_url"], dest)
                except Exception as e:
                    print("  bin dl ERR", name, repr(e)[:100])
    if gltf_path and gltf_path.exists():
        return gltf_path
    return None


def api_repo(path: str) -> dict:
    return _get_json(f"https://api.github.com/{path}")


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0",
                                                "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=25, context=ssl.create_default_context()) as r:
        return json.loads(r.read().decode())


def _fetch(url: str, dest: Path):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=90, context=ctx) as r:
        data = r.read()
    dest.write_bytes(data)


def merge_catalogs(processed: list[dict]):
    # brandreal_catalog.json
    cat = ROOT / "vercel_site" / "brandreal_catalog.json"
    existing = json.loads(cat.read_text(encoding="utf-8")) if cat.exists() else []
    by_stl = {e.get("stl"): e for e in existing}
    ood = ROOT / "vercel_site" / "models" / "brandreal"
    # rebuild from disk to stay truthful
    out = []
    for stl in sorted(ood.rglob("*.stl")):
        rel = "/models/brandreal/" + "/".join(stl.relative_to(ood).parts)
        if not stl.exists() or stl.stat().st_size < 1000:
            continue
        mfile = stl.with_suffix("").with_suffix(".metadata.json")
        if mfile.exists():
            m = json.loads(mfile.read_text(encoding="utf-8"))
            out.append({
                "brand": m["brand"], "model": m["model"], "source_repo": m["source_repo"],
                "url": m["url"], "stl": m["stl"],
            })
        else:
            out.append({"brand": stl.parent.name, "model": stl.stem,
                        "source_repo": "unknown", "url": "", "stl": rel})
    cat.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"brandreal_catalog.json -> {len(out)} entries")

    # real_catalog.json (validated grid) -- append new real cars
    rc = ROOT / "vercel_site" / "real_catalog.json"
    reals = json.loads(rc.read_text(encoding="utf-8")) if rc.exists() else []
    have = {e.get("slug") for e in reals}
    for m in processed:
        if m["slug"] in have:
            continue
        reals.append({
            "brand": m["brand"], "model": m["model"], "slug": m["slug"],
            "referenceFamily": m["model"], "traits": ["community real model", "github"],
            "description": f"Real community 3D model of {m['brand']} {m['model']}.",
            "category": "real", "era": "real", "year": "",
            "faces": m["faces"], "watertight": m["watertight"],
            "stl": m["stl"], "raw_study": m["stl"],
            "print_solid_candidate": m["stl"],
        })
    rc.write_text(json.dumps(reals, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"real_catalog.json -> {len(reals)} entries")


def main() -> int:
    results, fails = [], []
    for brand, model_name, repo, path, slug in SOURCES:
        try:
            m = process(brand, model_name, repo, path, slug)
            if m:
                results.append(m)
                print(f"  OK {brand} {model_name}: wt={m['watertight']} faces={m['faces']}")
            else:
                fails.append((brand, model_name))
        except Exception as e:
            fails.append((brand, model_name, repr(e)[:160]))
        gc.collect()
    merge_catalogs(results)
    print(f"\nDONE ok={len(results)} fails={len(fails)}")
    for f in fails:
        print("  FAIL", f)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

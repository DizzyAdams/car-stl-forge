"""Canonical car generator: deterministic catalog/spec -> mesh -> STL.

This entry point is intentionally limited to procedural automotive assets. It does
not depend on LandMap, Vercel, a web marketplace, or a frontend application.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

import trimesh

ROOT = Path(__file__).resolve().parent
AGENTS = ROOT / "agents"
CATALOG = AGENTS / "porsche_catalog.json"
DEFAULT_OUT = ROOT / "car_stl_output"


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def load_catalog(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Catalog must be a JSON list: {path}")
    seen: set[str] = set()
    result: list[dict] = []
    for item in data:
        brand = str(item.get("brand", "")).strip()
        model = str(item.get("model", "")).strip()
        if not brand or not model:
            raise ValueError(f"Catalog item without brand/model: {item!r}")
        slug = slugify(f"{brand}_{model}")
        if slug in seen:
            raise ValueError(f"Duplicate catalog slug: {slug}")
        seen.add(slug)
        result.append({**item, "slug": slug})
    return result


def validate_stl(path: Path) -> dict:
    mesh = trimesh.load(str(path), force="mesh")
    if not isinstance(mesh, trimesh.Trimesh):
        raise ValueError(f"Not a mesh: {type(mesh).__name__}")
    vertices = int(len(mesh.vertices))
    faces = int(len(mesh.faces))
    if vertices < 4 or faces < 4:
        raise ValueError(f"Mesh too small: vertices={vertices}, faces={faces}")
    if not mesh.is_volume and mesh.area <= 0:
        raise ValueError("Mesh has no positive area/volume")
    return {
        "file": path.name,
        "vertices": vertices,
        "faces": faces,
        "watertight": bool(mesh.is_watertight),
        "winding_consistent": bool(mesh.is_winding_consistent),
        "components": int(len(mesh.split(only_watertight=False))),
        "volume": float(mesh.volume) if mesh.is_watertight else None,
        "bounds": mesh.bounds.tolist(),
        "bytes": path.stat().st_size,
    }


def solidify_candidate(source_path: Path, candidate_path: Path, target_resolution: int = 128) -> dict:
    """Create a watertight voxel/marching-cubes print candidate.

    The source STL remains untouched. This is a candidate because voxel
    solidification can close gaps and fill cavities that require design review.
    """
    mesh = trimesh.load(str(source_path), force="mesh")
    extent = float(max(mesh.bounds[1] - mesh.bounds[0]))
    if extent <= 0:
        raise ValueError("Cannot solidify zero-extent mesh")
    pitch = extent / float(target_resolution)
    voxel = mesh.voxelized(pitch).fill()
    candidate = voxel.marching_cubes
    candidate.apply_transform(voxel.transform)
    candidate.merge_vertices()
    from trimesh.smoothing import filter_taubin
    filter_taubin(candidate, iterations=3, lamb=0.5, nu=0.5)
    candidate.merge_vertices()
    candidate.export(str(candidate_path), file_type="stl")
    qa = validate_stl(candidate_path)
    qa["source"] = source_path.name
    qa["voxel_pitch"] = pitch
    qa["watertight_candidate"] = bool(candidate.is_watertight)
    qa["single_component_candidate"] = len(candidate.split(only_watertight=False)) == 1
    return qa


def generate_one(item: dict, out_dir: Path) -> dict:
    # Imported lazily so catalog inspection and --help remain dependency-light.
    from agents.img23_bridge import build_spec, export_stl_from_ts, generate_ts

    slug = item["slug"]
    model_dir = out_dir / slug
    model_dir.mkdir(parents=True, exist_ok=True)
    spec_path = model_dir / f"{slug}.spec.json"
    ts_path = model_dir / f"{slug}.model.ts"
    stl_path = model_dir / f"{slug}.stl"
    candidate_path = model_dir / f"{slug}.print_solid_candidate.stl"

    spec = build_spec(item["brand"], item["model"], item.get("category", "sports-car"), item.get("bodyStyle", "Coupe"))
    spec.update({
        "catalogYear": item.get("year"),
        "referenceFamily": item.get("referenceFamily"),
        "bodyStyle": item.get("bodyStyle"),
        "drivetrain": item.get("drivetrain"),
        "eraBand": item.get("eraBand"),
        "traits": item.get("traits", []),
        "description": item.get("description", ""),
        "generator": "generate_car_stl.py",
        "originalProceduralStudy": True,
    })
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    generate_ts(spec_path, ts_path)
    exported = export_stl_from_ts(ts_path, stl_path)
    if exported.get("rc") != 0 or not stl_path.exists():
        raise RuntimeError(exported.get("stderr") or exported.get("stdout") or "STL exporter failed")
    qa = validate_stl(stl_path)
    candidate_qa = solidify_candidate(stl_path, candidate_path)
    return {"brand": item["brand"], "model": item["model"], "slug": slug, "spec": str(spec_path), "model_ts": str(ts_path), "stl": str(stl_path), "print_solid_candidate": str(candidate_path), "qa": qa, "candidate_qa": candidate_qa}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate original procedural car STL files.")
    parser.add_argument("--catalog", type=Path, default=CATALOG)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--model", help="Exact catalog model name, e.g. '911 Carrera'")
    parser.add_argument("--zip", action="store_true", help="Create a ZIP containing generated STL files")
    args = parser.parse_args()

    catalog = load_catalog(args.catalog)
    if args.model:
        catalog = [item for item in catalog if item["model"].casefold() == args.model.casefold()]
        if not catalog:
            raise SystemExit(f"Model not found in catalog: {args.model}")
    if args.limit is not None:
        catalog = catalog[: max(0, args.limit)]
    if not catalog:
        raise SystemExit("No models selected")

    args.out.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    failures: list[dict] = []
    print(f"Car STL generator | models={len(catalog)} | out={args.out}")
    for index, item in enumerate(catalog, 1):
        print(f"[{index}/{len(catalog)}] {item['brand']} {item['model']}", flush=True)
        try:
            result = generate_one(item, args.out)
            results.append(result)
            print(f"  OK STL faces={result['qa']['faces']} bytes={result['qa']['bytes']}")
        except Exception as exc:
            failures.append({"brand": item["brand"], "model": item["model"], "error": str(exc)})
            print(f"  FAIL {exc}", file=sys.stderr)

    report = {"generator": "generate_car_stl.py", "catalog": str(args.catalog), "requested": len(catalog), "success": len(results), "failed": len(failures), "results": results, "failures": failures}
    report_path = args.out / "generation_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.zip and results:
        archive = args.out.with_suffix(".zip")
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for result in results:
                path = Path(result["stl"])
                zf.write(path, path.relative_to(args.out))
                candidate = Path(result["print_solid_candidate"])
                zf.write(candidate, candidate.relative_to(args.out))
            zf.write(report_path, report_path.relative_to(args.out))
        print(f"ZIP={archive} files={len(results) * 2 + 1}")
    print(f"DONE success={len(results)} failed={len(failures)} report={report_path}")
    return 0 if results and not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

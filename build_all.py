"""One-command pipeline: generate all models, crawl reference links, build the
static showroom, and produce a deployable ZIP.

Run:  python build_all.py            (uses .venv python + NODE_EXE)
"""
from __future__ import annotations

import json
import os
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(py: Path, script: Path, *args: str) -> int:
    env = dict(os.environ)
    env["NODE_EXE"] = os.environ.get("NODE_EXE", r"C:\nvm4w\nodejs\node.EXE")
    print(f"\n=== {script.name} {' '.join(args)} ===")
    p = subprocess.run([str(py), str(script), *args], capture_output=True, text=True, env=env, cwd=str(ROOT))
    print(p.stdout)
    if p.stderr.strip():
        print("STDERR:", p.stderr[-1200:])
    return p.returncode


def zip_site() -> Path:
    site = ROOT / "vercel_site"
    archive = ROOT / "vercel_site.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in site.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(site))
    print(f"ZIP {archive} ({archive.stat().st_size//1024} KB)")
    return archive


def main() -> int:
    py = ROOT / ".venv" / "Scripts" / "python.exe"
    if not py.exists():
        py = ROOT / ".venv" / "bin" / "python"
    if not py.exists():
        py = Path(os.environ.get("PY_EXE", "python"))

    rc = 0
    rc |= run(py, ROOT / "generate_car_stl.py", "--out", str(ROOT / "car_stl_output"), "--zip")
    rc |= run(py, ROOT / "crawl_3dsearch.py", "--pages", "10")
    rc |= run(py, ROOT / "build_vercel_site.py")
    zip_site()
    print("\nDONE build_all rc=", rc)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

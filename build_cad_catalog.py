import json, subprocess, sys
from pathlib import Path
# Build cad_original_catalog.json from the per-model metadata files
base = Path(r"C:\Users\forrydev\Desktop\3dmodel_text\shap-e\vercel_site\models\cad_original")
out = []
for branddir in sorted(base.iterdir()):
    if not branddir.is_dir():
        continue
    brand = branddir.name
    for meta in branddir.glob("*.metadata.json"):
        d = json.loads(meta.read_text(encoding="utf-8"))
        out.append({
            "brand": d["brand"],
            "model": d["model"],
            "slug": d["slug"],
            "kind": d["kind"],
            "license": d["license"],
            "designLanguage": d["designLanguage"],
            "note": d["note"],
            "dims_mm": d["dims_mm"],
            "faces": d["faces"],
            "watertight": d["watertight"],
            "stl": d["stl"],
            "cad": d["step"],
            "source_repo": "original-cadquery-parametric",
            "url": "https://github.com/DizzyAdams/car-stl-forge",
            "provenance": d["provenance"],
        })
out.sort(key=lambda x:(x["brand"], x["slug"]))
cat = base.parent.parent / "cad_original_catalog.json"
cat.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print("wrote", cat, "entries", len(out))
for e in out:
    print(" -", e["brand"], e["model"], "stl_ok", Path(r"C:\Users\forrydev\Desktop\3dmodel_text\shap-e\vercel_site"+e["stl"]).exists(),
          "step_ok", Path(r"C:\Users\forrydev\Desktop\3dmodel_text\shap-e\vercel_site"+e["cad"]).exists())

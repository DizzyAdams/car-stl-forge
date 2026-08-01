# Car STL Forge

Showroom público de **estudos procedurais originais** de carros — 129 modelos em 21 marcas,
com visualizador 3D, personalização de cor, modo comparar, biblioteca de referência e
envio local de STL.

## Princípio de integridade (importante)

Este projeto **não** baixa nem re-hospeda arquivos de terceiros.
- `crawl_3dsearch.py` gera `reference_library.json` contendo **apenas links externos**
  para modelos da comunidade no 3dsearch.net (Thingiverse, Printables, MakerWorld, Sketchfab…).
  O conteúdo continua sendo propriedade de seus autores e deve ser usado sob a licença de cada um.
- Todos os `.stl` em `vercel_site/models/` são gerados localmente por `generate_car_stl.py`
  a partir de **perfis proporcionais originais** (marca × família × body-style). Não são CAD OEM,
  scans oficiais ou assets licenciados. Marcas citadas são propriedade de seus respectivos donos.

## Pipeline

```
agents/porsche_catalog.json   # 129 modelos (marca, família, body-style, drivetrain, era)
        │
generate_car_stl.py  ──►  car_stl_output/<slug>/{slug}.stl  +  .print_solid_candidate.stl
        │                  (trimesh solidify; QA de vértices/faces/watertight)
crawl_3dsearch.py     ──►  reference_library.json  (links externos, sem download)
        │
build_vercel_site.py  ──►  vercel_site/  (index.html + catalog.json + models/*.stl)
```

Comando único (gera tudo, faz o zip):
```bash
python build_all.py
```

## Estrutura

- `agents/img23_bridge.py` — gera o spec procedual (BRAND_PROFILES + FAMILY_PROFILES + BODY_STYLE_PROFILES).
- `generate_car_stl.py` — spec → `.ts` → STL (Three.js exporter) → candidato print-ready.
- `crawl_3dsearch.py` — coleta links da biblioteca de referência (diretório legal).
- `build_vercel_site.py` — monta o showroom estático (Vercel-ready).
- `vercel_site/` — site estático (deploy direto na Vercel).

## Deploy (Vercel)

O conteúdo de `vercel_site/` é um static site. Na Vercel:
- Root Directory: `shap-e/vercel_site`
- Build Command: (ninguém; estático) — ou rode `python build_all.py` antes de publicar.
- Output: arquivos estáticos.

## Setup local

```bash
python -m venv .venv && .venv\Scripts\activate
pip install trimesh numpy
set NODE_EXE=<caminho do node.exe>
python build_all.py
```

Antes de imprimir qualquer STL, valide escala, watertightness, espessura, suportes e
tolerâncias no seu slicer.

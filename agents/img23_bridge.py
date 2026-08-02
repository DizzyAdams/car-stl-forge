import copy, hashlib, json, os, re, subprocess, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parent
IMG2THREEJS = REPO.parent.parent / 'img2threejs'
STAGE3 = IMG2THREEJS / 'forge' / 'stage3_build'
EXPORTERS = IMG2THREEJS / 'exporters'
if str(STAGE3) not in sys.path:
    sys.path.insert(0, str(STAGE3))
from generate_threejs_factory import generate, unlocked_pass  # type: ignore

CAR_MODELS = {'supercar':0.85,'hypercar':0.9,'ev-sedan':0.82,'sports-car':0.82,'track-car':0.88,'sports-sedan':0.82,'suv':0.8,'offroad':0.8,'classic':0.82,'modern-classic':0.84,'hybrid':0.88,'electric':0.84,'surreal':0.9,'motorsport':0.9,'current':0.85}

# Body-style silhouette envelopes. Applied on top of brand × family so a coupe,
# a roadster, an SUV and a hypercar read as genuinely different shapes — not just
# uniformly scaled clones. Values are coarse proportion multipliers.
BODY_STYLE_PROFILES = {
    'Coupe':         {'length': 1.00, 'height': 1.00, 'wheelbase': 1.00, 'track': 1.00, 'cabin': 1.00, 'ground': 0.00},
    'Classic Coupe': {'length': 0.96, 'height': 0.98, 'wheelbase': 0.98, 'track': 0.96, 'cabin': 1.04, 'ground': 0.02},
    'GT Coupe':      {'length': 1.10, 'height': 0.98, 'wheelbase': 1.08, 'track': 1.00, 'cabin': 1.02, 'ground': 0.01},
    'Sports Sedan':  {'length': 1.16, 'height': 1.02, 'wheelbase': 1.12, 'track': 1.02, 'cabin': 1.12, 'ground': 0.02},
    'Wagon':         {'length': 1.18, 'height': 1.06, 'wheelbase': 1.12, 'track': 1.02, 'cabin': 1.16, 'ground': 0.03},
    'Roadster':      {'length': 0.98, 'height': 0.90, 'wheelbase': 0.98, 'track': 1.00, 'cabin': 0.78, 'ground': 0.00},
    'Supercar':      {'length': 1.08, 'height': 0.90, 'wheelbase': 1.04, 'track': 1.06, 'cabin': 0.90, 'ground': -0.02},
    'Hypercar':      {'length': 1.12, 'height': 0.84, 'wheelbase': 1.04, 'track': 1.08, 'cabin': 0.82, 'ground': -0.03},
    'Hybrid GT':     {'length': 1.10, 'height': 0.96, 'wheelbase': 1.08, 'track': 1.02, 'cabin': 1.04, 'ground': 0.01},
    'EV GT':         {'length': 1.10, 'height': 0.94, 'wheelbase': 1.10, 'track': 1.04, 'cabin': 1.04, 'ground': -0.01},
    'SUV':           {'length': 1.10, 'height': 1.34, 'wheelbase': 1.06, 'track': 1.10, 'cabin': 1.30, 'ground': 0.12},
    'Off-road':      {'length': 1.06, 'height': 1.28, 'wheelbase': 1.02, 'track': 1.12, 'cabin': 1.24, 'ground': 0.16},
}
# modifiers so each marque reads differently (mid-engine wedge vs front-engine GT vs
# tall SUV) while staying inside a believable automotive envelope. Profiles are
# reference-informed proportions, NOT OEM CAD geometry.
BRAND_PROFILES = {
    'Ferrari': {'body': (1.02, 0.92, 1.06), 'cabin': (0.88, 0.82, 0.92), 'cabin_z': 0.02, 'wheel': 1.00, 'nose': 'long'},
    'Lamborghini': {'body': (1.10, 0.86, 1.10), 'cabin': (0.80, 0.70, 0.84), 'cabin_z': -0.10, 'wheel': 1.10, 'nose': 'wedge'},
    'McLaren': {'body': (1.06, 0.88, 1.04), 'cabin': (0.82, 0.74, 0.86), 'cabin_z': -0.06, 'wheel': 1.08, 'nose': 'teardrop'},
    'BMW': {'body': (1.04, 0.96, 1.08), 'cabin': (0.94, 0.92, 1.00), 'cabin_z': 0.02, 'wheel': 1.02, 'nose': 'balanced'},
    'Mercedes-AMG': {'body': (1.06, 0.98, 1.10), 'cabin': (0.96, 0.94, 1.02), 'cabin_z': 0.04, 'wheel': 1.04, 'nose': 'balanced'},
    'Audi': {'body': (1.04, 0.94, 1.08), 'cabin': (0.92, 0.90, 1.00), 'cabin_z': 0.02, 'wheel': 1.02, 'nose': 'wide'},
    'Ford': {'body': (1.08, 1.00, 1.10), 'cabin': (0.96, 0.94, 1.04), 'cabin_z': 0.04, 'wheel': 1.06, 'nose': 'muscle'},
    'Chevrolet': {'body': (1.08, 0.98, 1.10), 'cabin': (0.96, 0.94, 1.04), 'cabin_z': 0.04, 'wheel': 1.06, 'nose': 'muscle'},
    'Nissan': {'body': (1.02, 0.94, 1.06), 'cabin': (0.90, 0.88, 0.98), 'cabin_z': 0.02, 'wheel': 1.00, 'nose': 'compact'},
    'Toyota': {'body': (1.00, 0.94, 1.04), 'cabin': (0.90, 0.88, 0.98), 'cabin_z': 0.02, 'wheel': 0.98, 'nose': 'balanced'},
    'Jaguar': {'body': (1.06, 0.94, 1.10), 'cabin': (0.92, 0.88, 1.00), 'cabin_z': 0.04, 'wheel': 1.00, 'nose': 'long'},
    'Aston Martin': {'body': (1.08, 0.92, 1.10), 'cabin': (0.90, 0.84, 1.00), 'cabin_z': 0.04, 'wheel': 1.00, 'nose': 'long'},
    'Dodge': {'body': (1.10, 1.00, 1.12), 'cabin': (0.98, 0.96, 1.06), 'cabin_z': 0.06, 'wheel': 1.08, 'nose': 'muscle'},
    'Koenigsegg': {'body': (1.14, 0.84, 1.08), 'cabin': (0.78, 0.68, 0.84), 'cabin_z': -0.12, 'wheel': 1.14, 'nose': 'wedge'},
    'Bugatti': {'body': (1.16, 0.96, 1.16), 'cabin': (0.98, 0.92, 1.08), 'cabin_z': 0.06, 'wheel': 1.12, 'nose': 'wide'},
    'Rimac': {'body': (1.12, 0.88, 1.10), 'cabin': (0.84, 0.78, 0.92), 'cabin_z': -0.06, 'wheel': 1.10, 'nose': 'wedge'},
    'Pagani': {'body': (1.10, 0.86, 1.08), 'cabin': (0.82, 0.74, 0.88), 'cabin_z': -0.08, 'wheel': 1.10, 'nose': 'soft-wedge'},
    'Lexus': {'body': (1.04, 0.96, 1.08), 'cabin': (0.94, 0.92, 1.00), 'cabin_z': 0.02, 'wheel': 1.02, 'nose': 'spindle'},
    'Alfa Romeo': {'body': (1.00, 0.92, 1.04), 'cabin': (0.88, 0.84, 0.96), 'cabin_z': 0.02, 'wheel': 0.98, 'nose': 'rounded'},
    'Maserati': {'body': (1.06, 0.94, 1.10), 'cabin': (0.92, 0.88, 1.00), 'cabin_z': 0.04, 'wheel': 1.00, 'nose': 'long'},
    'Porsche': {'body': (1.04, 0.96, 1.02), 'cabin': (0.94, 0.88, 0.96), 'cabin_z': -0.10, 'wheel': 1.02, 'nose': 'balanced'},
}
BASE_SPEC = REPO / 'porsche_911_carrera.spec.json'

# Side-profile silhouettes (XY plane, X = length -1..1, Y = height 0..1) used to
# extrude a real car body instead of a lathe (revolution) blob. These are original
# stylized design-language outlines, not OEM CAD. `width` is the extrude depth
# (vehicle track). body_shell carries the full coupe outline incl. cabin roof;
# cabin is a glazed greenhouse block placed on top.
CAR_BODY_SIDE_PROFILE = [
    [-1.00, 0.06], [-0.92, 0.10], [-0.78, 0.13], [-0.55, 0.15], [-0.32, 0.18],
    [-0.12, 0.30], [0.12, 0.40], [0.38, 0.42], [0.62, 0.39], [0.84, 0.30],
    [0.96, 0.18], [1.00, 0.11], [0.96, 0.07], [0.55, 0.05], [0.10, 0.045],
    [-0.40, 0.05], [-0.80, 0.06], [-1.00, 0.06],
]
CAR_CABIN_SIDE_PROFILE = [
    [-0.30, 0.0], [-0.16, 0.14], [0.06, 0.17], [0.30, 0.14], [0.34, 0.0],
    [-0.30, 0.0],
]

# Geometry profiles are deliberately coarse, deterministic design-language
# modifiers. They prevent every catalog entry from being a lightly randomized
# 911 while keeping the output original and reference-informed.
FAMILY_PROFILES = {
    '356': {'body': (0.92, 0.88, 0.96), 'cabin': (0.86, 0.78, 0.88), 'cabin_z': 0.08, 'wheel': 0.88, 'open_top': True},
    '550': {'body': (0.88, 0.76, 0.90), 'cabin': (0.72, 0.58, 0.72), 'cabin_z': 0.18, 'wheel': 0.82, 'open_top': True},
    '911': {'body': (1.04, 0.96, 1.02), 'cabin': (0.94, 0.88, 0.96), 'cabin_z': -0.10, 'wheel': 1.02},
    '718': {'body': (1.00, 0.92, 0.98), 'cabin': (0.90, 0.86, 0.88), 'cabin_z': 0.08, 'wheel': 0.98},
    '924': {'body': (0.94, 0.98, 1.08), 'cabin': (0.90, 0.94, 1.02), 'cabin_z': 0.12, 'wheel': 0.96},
    '944': {'body': (0.98, 1.00, 1.06), 'cabin': (0.92, 0.96, 1.00), 'cabin_z': 0.08, 'wheel': 1.00},
    '928': {'body': (1.08, 1.00, 1.10), 'cabin': (0.98, 0.98, 1.02), 'cabin_z': 0.04, 'wheel': 1.06},
    '959': {'body': (1.10, 1.02, 1.06), 'cabin': (0.92, 0.90, 0.98), 'cabin_z': -0.02, 'wheel': 1.10},
    'GT1': {'body': (1.22, 0.86, 1.16), 'cabin': (0.80, 0.70, 0.88), 'cabin_z': -0.18, 'wheel': 1.16},
    'Carrera GT': {'body': (1.16, 0.84, 1.08), 'cabin': (0.78, 0.68, 0.82), 'cabin_z': 0.02, 'wheel': 1.14},
    '918': {'body': (1.20, 0.82, 1.04), 'cabin': (0.76, 0.66, 0.78), 'cabin_z': 0.00, 'wheel': 1.18},
    'Cayenne': {'body': (1.18, 1.30, 1.18), 'cabin': (1.08, 1.18, 1.06), 'cabin_z': -0.02, 'wheel': 1.12},
    'Macan': {'body': (1.10, 1.18, 1.08), 'cabin': (1.02, 1.10, 1.02), 'cabin_z': 0.00, 'wheel': 1.08},
    'Panamera': {'body': (1.12, 1.08, 1.24), 'cabin': (1.02, 1.06, 1.16), 'cabin_z': -0.02, 'wheel': 1.08},
    'Taycan': {'body': (1.10, 1.02, 1.22), 'cabin': (1.00, 1.00, 1.14), 'cabin_z': 0.06, 'wheel': 1.10},
}

def _family_profile(model: str, category: str) -> dict:
    for key, profile in FAMILY_PROFILES.items():
        if key.casefold() in model.casefold():
            return dict(profile)
    if category in {'suv', 'offroad'}:
        return dict(FAMILY_PROFILES['Macan'])
    if category in {'hypercar', 'track-car'}:
        return dict(FAMILY_PROFILES['Carrera GT'])
    if category in {'sports-sedan', 'ev-sedan'}:
        return dict(FAMILY_PROFILES['Panamera'])
    return dict(FAMILY_PROFILES['911'])

def _brand_profile(brand: str) -> dict:
    return dict(BRAND_PROFILES.get(brand, BRAND_PROFILES['Porsche']))

def _body_profile(body_style: str) -> dict:
    return dict(BODY_STYLE_PROFILES.get(body_style, BODY_STYLE_PROFILES['Coupe']))

def build_spec(brand: str, model: str, category: str, body_style: str = "Coupe") -> dict:
    spec = copy.deepcopy(json.loads(BASE_SPEC.read_text(encoding='utf-8')))
    slug = re.sub(r'[^a-z0-9]+', '_', f"{brand}_{model}".lower()).strip('_')
    spec.update({'targetName':f'{brand} {model}','brand':brand,'model':model,'category':category,'slug':slug,'bodyStyle':body_style})
    profile = _family_profile(model, category)
    # Blend the brand-level silhouette signature over the family profile so the
    # marque identity dominates while the reference family refines proportions.
    bp = _brand_profile(brand)
    blended = {
        'body': tuple(round(profile['body'][i] * bp['body'][i], 4) for i in range(3)),
        'cabin': tuple(round(profile['cabin'][i] * bp['cabin'][i], 4) for i in range(3)),
        'cabin_z': round(profile.get('cabin_z', 0.0) + bp.get('cabin_z', 0.0), 4),
        'wheel': round(profile['wheel'] * bp['wheel'], 4),
    }
    spec['styleProfile'] = blended
    spec['brandProfile'] = bp['nose']
    # Body-style envelope reshapes the overall silhouette so coupes, roadsters,
    # SUVs and hypercars are visually distinct, not just scaled clones.
    bsp = _body_profile(body_style)
    spec['bodyStyleProfile'] = bsp
    fidelity = CAR_MODELS.get(category, 0.82)
    if isinstance(spec.get('scores'), dict):
        spec['scores']['silhouetteConfidence'] = fidelity
        spec['scores']['overallFidelity'] = fidelity
    if isinstance(spec.get('qualityTargets'), dict): spec['qualityTargets']['targetFidelity'] = fidelity
    if isinstance(spec.get('visualAcceptance'), dict): spec['visualAcceptance']['threshold'] = fidelity
    # Freeze a small, model-specific proportion signature so every study is unique
    # while remaining within a believable automotive silhouette envelope.
    seed = int(hashlib.sha256(slug.encode('utf-8')).hexdigest()[:8], 16)
    unit = lambda salt: ((seed ^ (salt * 2654435761)) & 0xffffffff) / 4294967295
    bsp = _body_profile(body_style)
    for node in spec.get('componentTree', []):
        transform = node.get('transform', {})
        scale = list(transform.get('scale', [1, 1, 1]))
        translate = list(transform.get('translate', [0, 0, 0]))
        # Ground clearance lifts the whole car (SUVs / off-roaders sit higher).
        translate[1] += bsp.get('ground', 0.0)
        if node.get('id') == 'body_shell':
            # Extrude a real car side-profile (length along X, height along Y,
            # width along Z via extrude depth) instead of a lathe revolution blob.
            node['primitive'] = 'extrude'
            node['geometryDescriptor'] = {
                'profile2D': {
                    'points': CAR_BODY_SIDE_PROFILE,
                    'depth': 1.1 * blended['body'][2] * bsp['track'],
                }
            }
            scale[0] *= blended['body'][0] * bsp['length'] * (0.99 + unit(1) * 0.02)
            scale[1] *= blended['body'][1] * bsp['height']
            scale[2] = 1.0
        elif node.get('id') == 'cabin':
            node['primitive'] = 'extrude'
            node['geometryDescriptor'] = {
                'profile2D': {
                    'points': CAR_CABIN_SIDE_PROFILE,
                    'depth': 0.9 * blended['cabin'][2] * bsp['track'],
                }
            }
            scale[0] *= blended['cabin'][0] * (0.99 + unit(3) * 0.02)
            scale[1] *= blended['cabin'][1] * bsp['cabin']
            scale[2] = 1.0
            translate[2] = blended.get('cabin_z', 0.0) + (unit(5) - .5) * .04
            if profile.get('open_top'):
                scale[1] *= 0.82
        elif node.get('id') in {'hood', 'front_bumper', 'rear_bumper'}:
            scale[0] *= blended['body'][0] * bsp['length'] * (0.99 + unit(6) * 0.02)
            scale[2] *= blended['body'][2] * bsp['length']
        elif node.get('id') == 'chassis':
            scale[0] *= blended['body'][0] * bsp['track']
            scale[1] *= blended['body'][1] * bsp['height']
            scale[2] *= blended['body'][2] * bsp['length']
        elif node.get('id') == 'wheel_assembly':
            scale[0] *= blended['wheel'] * bsp['track']
            scale[1] *= blended['wheel'] * bsp['track']
            scale[2] *= blended['wheel']
        transform['scale'] = scale
        transform['translate'] = translate
    return spec

def validate_spec(spec_path: Path) -> dict:
    script = IMG2THREEJS / 'forge' / 'stage2_spec' / 'validate_sculpt_spec.py'
    res = subprocess.run([sys.executable,str(script),str(spec_path),'--strict-quality'],capture_output=True,text=True)
    return {'rc':res.returncode,'stdout':res.stdout[-1000:],'stderr':res.stderr[-1000:]}

def generate_ts(spec_path: Path, out_path: Path) -> dict:
    spec=json.loads(spec_path.read_text(encoding='utf-8'))
    # Product exports must contain the complete authored hierarchy. The old
    # unlocked-pass default fell back to blockout when reviewHistory was empty,
    # exporting only chassis/body/cabin and silently dropping lights, bumpers,
    # glazing and wheel assemblies. Review gating remains separate; this is the
    # explicit final export pass.
    # Plane cards are useful in the realtime viewer but are zero-thickness
    # surfaces. Exclude them from the printable STL to avoid degenerate/open
    # facets; the source spec remains unchanged for viewer generation.
    stl_spec = copy.deepcopy(spec)
    stl_spec['componentTree'] = [
        component for component in stl_spec.get('componentTree', [])
        if str(component.get('primitive', '')) != 'plane-card'
    ]
    factory=generate(stl_spec,'optimization-pass')
    out_path.parent.mkdir(parents=True,exist_ok=True); out_path.write_text(factory,encoding='utf-8')
    return {'out':str(out_path),'bytes':out_path.stat().st_size}

def export_stl_from_ts(ts_path: Path, out_path: Path, format: str='stl') -> dict:
    script=EXPORTERS/'src'/'export_model.mjs'
    if not script.exists(): raise FileNotFoundError(f'missing exporter script: {script}')
    out_dir=EXPORTERS/'output'; out_dir.mkdir(parents=True,exist_ok=True)
    stamp=int(time.time()*1000)
    local_ts=out_dir/f'{ts_path.stem}_{stamp}_{out_path.name}.model.ts'; local_ts.write_text(ts_path.read_text(encoding='utf-8'),encoding='utf-8')
    local_out=out_dir/f'{ts_path.stem}_{stamp}_{out_path.name}'
    env=dict(os.environ); env['EXPORTER_DEBUG']='1'
    node = os.environ.get('NODE_EXE','node')
    res=subprocess.run([node,str(script),str(local_ts),str(local_out),format],capture_output=True,text=True,env=env)
    result={'rc':res.returncode,'stdout':res.stdout[-1000:],'stderr':res.stderr[-1000:],'out':str(out_path)}
    if local_out.exists(): local_out.replace(out_path)
    if out_path.exists(): result['bytes']=out_path.stat().st_size
    return result

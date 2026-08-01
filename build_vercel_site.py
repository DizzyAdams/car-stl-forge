"""Build the deployable static showroom from the canonical car STL output.

Premium dark showroom featuring:
  - brand / family / body-style / era filtering + free-text search
  - color personalization (paint + metalness/roughness presets)
  - "Surprise me" random picker and A/B compare mode
  - 3D viewer + a lightweight thumbnail gallery toggle
  - a legal reference-library tab (outbound links only, no re-host)
  - a local "upload your STL" viewer (client-side only)
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CATALOG = ROOT / "agents" / "porsche_catalog.json"
SOURCE = ROOT / "car_stl_output"
SITE = ROOT / "vercel_site"


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def main() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    SITE.mkdir(exist_ok=True)
    models = []
    for item in catalog:
        key = slug(f"{item['brand']}_{item['model']}")
        stl = SOURCE / key / f"{key}.stl"
        if not stl.exists():
            raise FileNotFoundError(stl)
        candidate = SOURCE / key / f"{key}.print_solid_candidate.stl"
        if not candidate.exists():
            raise FileNotFoundError(candidate)
        models.append({**item, "slug": key, "brand": item.get("brand", ""),
                       # primary mesh is the watertight print-ready solid (always printable)
                       "stl": f"/models/{key}.print_solid_candidate.stl",
                       "print_solid_candidate": f"/models/{key}.print_solid_candidate.stl",
                       "raw_study": f"/models/{key}.stl"})
        (SITE / "models").mkdir(exist_ok=True)
        shutil.copy2(stl, SITE / "models" / f"{key}.stl")
        shutil.copy2(candidate, SITE / "models" / f"{key}.print_solid_candidate.stl")
    (SITE / "catalog.json").write_text(json.dumps(models, ensure_ascii=False, indent=2), encoding="utf-8")
    benchmark = SOURCE / "benchmark_report.json"
    if benchmark.exists():
        shutil.copy2(benchmark, SITE / "benchmark_report.json")
    ref = ROOT / "reference_library.json"
    if ref.exists():
        shutil.copy2(ref, SITE / "reference_library.json")
    brands = sorted({m["brand"] for m in models})
    bodies = sorted({m.get("bodyStyle", "Coupe") for m in models})
    eras = sorted({m.get("eraBand", "") for m in models}, reverse=True)
    n_ref = json.loads(ref.read_text(encoding="utf-8")).get("count", 0) if ref.exists() else 0

    html = r'''<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Car STL Forge</title>
<style>:root{--bg:#08070b;--panel:#14111d;--line:#30273f;--ink:#f7f4ff;--muted:#aaa1bb;--accent:#a78bfa;--accent2:#9fffe0}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 80% 0,#32205b,transparent 35%),var(--bg);color:var(--ink);font:14px Inter,system-ui,sans-serif}.shell{max-width:1480px;margin:auto;padding:24px}.top{display:flex;justify-content:space-between;gap:20px;align-items:center;border-bottom:1px solid var(--line);padding-bottom:18px;flex-wrap:wrap}.brand{font-weight:900;letter-spacing:.14em}.badge{color:#c4b5fd;font-size:11px;letter-spacing:.14em}.hero{padding:42px 0 22px;max-width:880px}.hero h1{font-size:clamp(38px,7vw,84px);line-height:.9;margin:12px 0}.hero em{color:var(--accent);font-style:normal}.hero p{color:var(--muted);line-height:1.7;max-width:680px}.tabs{display:flex;gap:8px;margin:20px 0 6px;flex-wrap:wrap}.tab{padding:10px 16px;border:1px solid var(--line);border-radius:10px;background:var(--panel);color:var(--muted);cursor:pointer;font-weight:600}.tab.active{color:#100b18;background:var(--accent);border-color:var(--accent)}.tools{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0}.tools input,.tools select{background:var(--panel);color:var(--ink);border:1px solid var(--line);border-radius:10px;padding:11px 13px}.tools input{min-width:240px}.layout{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(300px,.6fr);gap:18px}.panel{background:linear-gradient(145deg,#171321,#0f0d14);border:1px solid var(--line);border-radius:18px;overflow:hidden}.viewer{min-height:560px;position:relative}.viewer canvas{width:100%;height:560px;display:block}.caption{position:absolute;left:22px;bottom:20px}.caption small{display:block;color:#c4b5fd;letter-spacing:.14em}.caption strong{display:block;font-size:22px;margin-top:5px}.list{padding:16px;max-height:560px;overflow:auto}.card{border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin-bottom:10px;cursor:pointer;display:flex;justify-content:space-between;gap:10px;align-items:center}.card:hover,.card.active{border-color:var(--accent);background:#211a30}.card h3{margin:4px 0;font-size:15px}.card p{margin:0;color:var(--muted);font-size:11px;line-height:1.4}.meta{font-size:10px;color:#c4b5fd;letter-spacing:.08em;text-transform:uppercase}.sw{width:14px;height:14px;border-radius:50%;border:1px solid #fff3;flex:0 0 auto}.actions{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap}.actions a{color:var(--ink);text-decoration:none;border:1px solid var(--line);border-radius:8px;padding:8px 10px;font-size:12px}.actions a.primary{background:var(--accent);color:#100b18;border-color:var(--accent);font-weight:700}.colors{display:flex;gap:6px;flex-wrap:wrap;margin-top:12px}.chip{width:26px;height:26px;border-radius:50%;border:2px solid #fff2;cursor:pointer}.chip.on{border-color:#fff}.foot{color:var(--muted);font-size:12px;line-height:1.6;border-top:1px solid var(--line);margin-top:24px;padding:18px 0}.hide{display:none}.refgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px;margin-top:14px}.refcard{border:1px solid var(--line);border-radius:12px;padding:14px;background:var(--panel)}.refcard a{color:var(--ink);text-decoration:none;font-weight:600}.refcard .src{font-size:10px;color:#c4b5fd;text-transform:uppercase;letter-spacing:.08em}.upwrap{padding:24px;background:var(--panel);border:1px dashed var(--line);border-radius:14px;margin-top:16px;max-width:560px}.upwrap input{margin-top:10px}.note{color:var(--muted);font-size:12px;line-height:1.6;margin-top:10px}.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.btn{background:var(--panel);color:var(--ink);border:1px solid var(--line);border-radius:10px;padding:10px 14px;cursor:pointer;font-weight:600}.btn.accent{background:var(--accent);color:#100b18;border-color:var(--accent)}.toggle{display:flex;gap:6px;margin-top:10px}.toggle .btn{padding:7px 12px;font-size:12px}.comparewrap{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:14px}.comparewrap .panel{min-height:380px}.comparewrap canvas{height:380px}.galthumb{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:10px;margin-top:12px}.galthumb .g{height:84px;border-radius:10px;background:linear-gradient(145deg,#1d1730,#0f0d14);border:1px solid var(--line);display:flex;align-items:center;justify-content:center;font-size:10px;color:#c4b5fd;text-align:center;cursor:pointer;padding:6px}.galthumb .g:hover{border-color:var(--accent)}@media(max-width:850px){.layout{grid-template-columns:1fr}.viewer,.viewer canvas{min-height:400px;height:400px}.comparewrap{grid-template-columns:1fr}}
</style></head><body><main class="shell"><header class="top"><div class="brand">CAR STL FORGE</div><div class="badge">ORIGINAL PROCEDURAL · {nmodels} MODELOS · {nbrands} MARCAS · {nref} REFERÊNCIAS</div></header>
<section class="hero"><div class="badge">REFERENCE-INFORMED / STL-FIRST</div><h1>Carros 3D.<br><em>Arquivos reais.</em></h1>
<p>Showroom de interpretações procedurais originais — 21 marcas, body-styles distintos (cupê, roadster, SUV, hypercar, sedã), filtros por era e drivetrain. Visualize, personalize a cor, compare e baixe o STL. Não são CAD OEM, scans ou assets licenciados.</p></section>
<div class="tabs"><div class="tab active" data-tab="showroom">Showroom</div><div class="tab" data-tab="compare">Comparar</div><div class="tab" data-tab="ref">Biblioteca de Referência</div><div class="tab" data-tab="upload">Enviar seu STL</div></div>

<section id="showroom"><div class="tools"><input id="search" placeholder="Buscar modelo, marca, família…">
<select id="brand"><option value="all">Todas as marcas</option></select>
<select id="body"><option value="all">Todo body-style</option></select>
<select id="era"><option value="all">Toda era</option></select>
<select id="family"><option value="all">Toda família</option></select>
</div>
<div class="row"><span class="btn accent" id="surprise">🎲 Surpreenda-me</span>
<span class="toggle"><span class="btn on" data-view="3d">3D</span><span class="btn" data-view="gallery">Galeria</span></span>
<span class="badge" id="count"></span></div>
<div class="layout"><div class="panel viewer"><canvas id="canvas"></canvas><div class="caption"><small id="meta">SELECIONE UM MODELO</small><strong id="title">Car STL Forge</strong></div>
<div class="colors" id="colors"></div></div>
<div class="panel list" id="list"></div></div>
<div class="galthumb hide" id="gallery"></div></section>

<section id="compare" class="hide"><p class="note">Modo A/B: escolha dois modelos para sobrepor silhuetas lado a lado.</p><div class="tools"><select id="cmpA"></select><select id="cmpB"></select><span class="btn accent" id="cmpGo">Comparar</span></div><div class="comparewrap"><div class="panel viewer"><canvas id="cA"></canvas><div class="caption"><small>MODELO A</small><strong id="tA">—</strong></div></div><div class="panel viewer"><canvas id="cB"></canvas><div class="caption"><small>MODELO B</small><strong id="tB">—</strong></div></div></div></section>

<section id="ref" class="hide"><p class="note">Diretório de <b>links externos</b> para modelos da comunidade no 3dsearch.net (Thingiverse, Printables, MakerWorld, Sketchfab…). Nada é baixado ou re-hospedado aqui — o conteúdo é propriedade dos autores e deve seguir a licença de cada um. Use como referência de linguagem visual.</p><div class="tools"><input id="refsearch" placeholder="Filtrar por nome…"><span class="badge" id="refcount"></span></div><div class="refgrid" id="refgrid"></div></section>

<section id="upload" class="hide"><div class="upwrap"><div class="badge">VISUALIZADOR LOCAL</div><h3 style="margin:10px 0">Enviar seu próprio STL</h3><p class="note">O arquivo é lido e renderizado <b>apenas no navegador</b> — nada é enviado a servidores. Inspecione suas próprias meshes antes de imprimir.</p><input id="stlfile" type="file" accept=".stl"></div><div class="layout" style="margin-top:18px"><div class="panel viewer"><canvas id="canvas2"></canvas><div class="caption"><small id="meta2">SEU ARQUIVO</small><strong id="title2">Aguardando STL…</strong></div></div><div class="panel list"><div id="upstat" class="actions" style="padding:16px">Carregue um .stl para ver métricas.</div></div></div></section>

<footer class="foot">Gerado pelo pipeline local <code>generate_car_stl.py</code>. Antes de imprimir, valide escala, watertightness, espessura, suportes e tolerâncias no slicer. Marcas citadas são propriedade de seus respectivos donos; os meshes aqui são estudos procedurais originais e não representam produtos oficiais.</footer></main>

<script type="module">import * as THREE from 'https://unpkg.com/three@0.170.0/build/three.module.js';import {OrbitControls} from 'https://unpkg.com/three@0.170.0/examples/jsm/controls/OrbitControls.js';import {STLLoader} from 'https://unpkg.com/three@0.170.0/examples/jsm/loaders/STLLoader.js';import {RoomEnvironment} from 'https://unpkg.com/three@0.170.0/examples/jsm/environments/RoomEnvironment.js';
const $=s=>document.querySelector(s);
let models=[],current,refEntries=[],view='3d',paint=0xa78bfa;

const PAINTS=[[0xa78bfa,'Roxo'],[0xc0c0c8,'Prata'],[0xe23b3b,'Vermelho'],[0x1f6feb,'Azul'],[0x16a34a,'Verde'],[0xf5f5f5,'Branco'],[0x111114,'Preto'],[0xff8a00,'Laranja'],[0xffd60a,'Amarelo'],[0x9fffe0,'Mint']];

function setup(canvas){
  const sc=new THREE.Scene();sc.background=new THREE.Color(0x0d0b12);
  const cam=new THREE.PerspectiveCamera(38,1,.01,100);cam.position.set(2.8,1.7,3.2);
  const ren=new THREE.WebGLRenderer({canvas,antialias:true});ren.setPixelRatio(Math.min(devicePixelRatio,2));
  ren.toneMapping=THREE.ACESFilmicToneMapping;ren.toneMappingExposure=1.15;ren.outputColorSpace=THREE.SRGBColorSpace;
  const ctl=new OrbitControls(cam,ren.domElement);ctl.enableDamping=true;ctl.dampingFactor=.08;
  // Realistic studio reflections (procedural, no external assets)
  const pmrem=new THREE.PMREMGenerator(ren);
  sc.environment=pmrem.fromScene(new THREE.RoomEnvironment(),0.04).texture;
  sc.add(new THREE.HemisphereLight(0xe9ddff,0x100c18,1.1));
  const k=new THREE.DirectionalLight(0xffffff,2.4);k.position.set(3,5,4);k.castShadow=true;k.shadow.mapSize.set(1024,1024);sc.add(k);
  const rim=new THREE.DirectionalLight(0x9fffe0,.8);rim.position.set(-4,2,-3);sc.add(rim);
  // Contact shadow ground
  const ground=new THREE.Mesh(new THREE.PlaneGeometry(40,40),new THREE.ShadowMaterial({opacity:.32}));
  ground.rotation.x=-Math.PI/2;ground.position.y=-.05;ground.receiveShadow=true;sc.add(ground);
  const rs=()=>{const r=ren.domElement.parentElement.getBoundingClientRect();ren.setSize(r.width,r.height,false);cam.aspect=r.width/r.height;cam.updateProjectionMatrix()};addEventListener('resize',rs);rs();
  (function lp(){requestAnimationFrame(lp);ctl.update();ren.render(sc,cam)})();
  return {sc,cam,ren,ctl};
}
const main=setup($('#canvas'));
const A=setup($('#cA'));
const B=setup($('#cB'));
const up=setup($('#canvas2'));

function draw(ctx,item,color){if(ctx.mesh)ctx.sc.remove(ctx.mesh);
  new STLLoader().load(item.stl,g=>{g.computeVertexNormals();
    const mat=new THREE.MeshPhysicalMaterial({color,metalness:.78,roughness:.18,clearcoat:1,clearcoatRoughness:.12,envMapIntensity:1.25,flatShading:false});
    const m=new THREE.Mesh(g,mat);m.castShadow=true;m.receiveShadow=true;
    const box=new THREE.Box3().setFromObject(m),size=box.getSize(new THREE.Vector3()),c=box.getCenter(new THREE.Vector3());
    m.position.sub(c);m.scale.setScalar(2.2/(Math.max(size.x,size.y,size.z)||1));ctx.mesh=m;ctx.sc.add(m);ctx.cam.position.set(2.8,1.7,3.2);ctx.ctl.target.set(0,0,0);ctx.ctl.update()})}
function load(item){current=item;draw(main,item,paint);$('#title').textContent=item.brand+' '+item.model;$('#meta').textContent=item.era+' / '+item.referenceFamily+' · '+item.bodyStyle+' · '+item.drivetrain;
  $('.colors')&&renderColors();}

function renderColors(){const c=$('#colors');c.innerHTML='';PAINTS.forEach(([hex,nm])=>{const s=document.createElement('div');s.className='chip'+(hex===paint?' on':'');s.style.background='#'+hex.toString(16).padStart(6,'0');s.title=nm;s.onclick=()=>{paint=hex;renderColors();if(current)draw(main,current,paint)};c.appendChild(s)})}

function render(){const q=$('#search').value.toLowerCase(),b=$('#brand').value,bo=$('#body').value,e=$('#era').value,f=$('#family').value;
  const items=models.filter(x=>(b==='all'||x.brand===b)&&(bo==='all'||x.bodyStyle===bo)&&(e==='all'||x.eraBand===e)&&(f==='all'||x.referenceFamily===f)&&(q===''||(x.brand+' '+x.model+' '+x.referenceFamily+' '+x.era).toLowerCase().includes(q)));
  $('#count').textContent=items.length+' modelos';
  if(view==='3d'){$('#list').classList.remove('hide');$('#gallery').classList.add('hide');const list=$('#list');list.innerHTML='';
    items.forEach(it=>{const c=document.createElement('div');c.className='card';c.innerHTML=`<div><div class="meta">${it.brand} · ${it.year||''} · ${it.bodyStyle}</div><h3>${it.model}</h3><p>${it.traits?it.traits.join(', '):''}</p><div class="actions"><a class="primary" href="${it.stl}" download>STL (print-ready)</a><a href="${it.raw_study}" download>Raw study</a></div></div><div class="sw" style="background:#${paint.toString(16).padStart(6,'0')}"></div>`;c.onclick=()=>{document.querySelectorAll('.card').forEach(x=>x.classList.remove('active'));c.classList.add('active');load(it)};list.appendChild(c)});
    if(items[0]&&!current){document.querySelectorAll('.card')[0].classList.add('active');load(items[0])}else if(items[0]&&current&&items.some(x=>x.slug===current.slug)){}else if(items[0]){load(items[0])}
  }else{$('#list').classList.add('hide');$('#gallery').classList.remove('hide');const g=$('#gallery');g.innerHTML='';
    items.forEach(it=>{const c=document.createElement('div');c.className='g';c.textContent=it.brand+' '+(it.model||'').slice(0,18);c.onclick=()=>load(it);g.appendChild(c)})}}

function renderRef(){const q=$('#refsearch').value.toLowerCase();const grid=$('#refgrid');grid.innerHTML='';const items=refEntries.filter(e=>q===''||e.title.toLowerCase().includes(q));$('#refcount').textContent=items.length+' links';
  items.slice(0,400).forEach(e=>{const c=document.createElement('div');c.className='refcard';c.innerHTML=`<div class="src">${e.source}</div><a href="${e.url}" target="_blank" rel="noopener">${e.title}</a>`;grid.appendChild(c)})}

$('#surprise').onclick=()=>{const f=models.filter(x=>true);if(f.length){const it=f[Math.floor(Math.random()*f.length)];load(it);document.querySelectorAll('.tab')[0].click();const cards=document.querySelectorAll('.card');cards.forEach(c=>{if(c.querySelector('h3').textContent===it.model){c.classList.add('active');c.scrollIntoView({block:'nearest'})}});}};
document.querySelectorAll('.toggle .btn').forEach(b=>b.onclick=()=>{document.querySelectorAll('.toggle .btn').forEach(x=>x.classList.remove('on'));b.classList.add('on');view=b.dataset.view;render()});

$('#stlfile').addEventListener('change',ev=>{const f=ev.target.files[0];if(!f)return;$('#title2').textContent=f.name;$('#meta2').textContent='PROCESSANDO…';const r=new FileReader();r.onload=()=>{try{const g=new STLLoader().parse(r.result);g.computeVertexNormals();if(up.mesh)up.sc.remove(up.mesh);const m=new THREE.Mesh(g,new THREE.MeshPhysicalMaterial({color:0x9fffe0,metalness:.6,roughness:.3}));const box=new THREE.Box3().setFromObject(m),s=box.getSize(new THREE.Vector3()),c=box.getCenter(new THREE.Vector3());m.position.sub(c);m.scale.setScalar(2.2/(Math.max(s.x,s.y,s.z)||1));up.mesh=m;up.sc.add(m);up.cam.position.set(2.8,1.7,3.2);up.ctl.target.set(0,0,0);up.ctl.update();const v=g.attributes.position.count,g2=g.index?g.index.count/3:g.attributes.position.count/3;$('#meta2').textContent='VERTICES '+v+' · FACES '+g2;$('#upstat').innerHTML=`<div class="meta">Métricas locais</div><p class="note">Vértices: <b>${v}</b><br>Faces: <b>${g2}</b><br>Arquivo: ${f.name} (${(f.size/1024).toFixed(1)} KB)</p>`}catch(err){$('#meta2').textContent='STL INVÁLIDO';$('#upstat').textContent=String(err)}};r.readAsArrayBuffer(f)});

document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>{document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));t.classList.add('active');['showroom','compare','ref','upload'].forEach(id=>$('#'+id).classList.toggle('hide',id!==t.dataset.tab))});
['#search','#brand','#body','#era','#family'].forEach(s=>$(s).addEventListener('input',render));

/* compare */
function fillCmp(){const o=document.createElement('option');o.value='all';o.textContent='—';$('#cmpA').appendChild(o);$('#cmpB').appendChild(o.cloneNode(true));models.forEach(m=>{[['#cmpA'],['#cmpB']].forEach(([sel])=>{const op=document.createElement('option');op.value=m.slug;op.textContent=m.brand+' '+m.model;$(sel).appendChild(op)})});$('#cmpGo').onclick=()=>{const a=models.find(x=>x.slug===$('#cmpA').value),b=models.find(x=>x.slug===$('#cmpB').value);if(a)draw(A,a,0xa78bfa);if(b)draw(B,b,0x9fffe0);$('#tA').textContent=a?a.brand+' '+a.model:'—';$('#tB').textContent=b?b.brand+' '+b.model:'—'}}

fetch('catalog.json').then(r=>r.json()).then(data=>{models=data;
  const fam=[...new Set(models.map(m=>m.referenceFamily))].sort();fam.forEach(f=>{const o=document.createElement('option');o.value=f;o.textContent=f;$('#family').appendChild(o)});
  const brs=[...new Set(models.map(m=>m.brand))].sort();brs.forEach(b=>{const o=document.createElement('option');o.value=b;o.textContent=b;$('#brand').appendChild(o)});
  const bos=[...new Set(models.map(m=>m.bodyStyle))].sort();bos.forEach(b=>{const o=document.createElement('option');o.value=b;o.textContent=b;$('#body').appendChild(o)});
  const ers=[...new Set(models.map(m=>m.eraBand))].sort().reverse();ers.forEach(e=>{const o=document.createElement('option');o.value=e;o.textContent=e;$('#era').appendChild(o)});
  fillCmp();renderColors();render()});
fetch('reference_library.json').then(r=>r.json()).then(d=>{refEntries=d.entries||[];renderRef();$('#refsearch').addEventListener('input',renderRef)}).catch(()=>{});
</script></body></html>'''

    html = (html.replace("{nmodels}", str(len(models)))
               .replace("{nbrands}", str(len(brands)))
               .replace("{nref}", str(n_ref)))
    (SITE / "index.html").write_text(html, encoding="utf-8")
    print(f"Built {SITE}: models={len(models)} brands={len(brands)} bodies={len(bodies)} eras={len(eras)} ref={n_ref} stl={len(list((SITE/'models').glob('*.stl')))}")


if __name__ == "__main__":
    main()

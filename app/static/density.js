/* Problem-density map: India -> state -> district. Real counts from /api/public/density. SAMPLE toggle is client-side fake data, always labelled.
   Boundaries: LGD (CC0/CC-BY), simplified; see docs/GEO_SOURCES.md. Pure SVG, no tiles, works offline after first load. */
(function(){
const W=560,H=620,LON0=68,LAT1=37.4,KX=20*Math.cos(22*Math.PI/180),KY=20;
const px=(lo,la)=>[(lo-LON0)*KX,(LAT1-la)*KY];
const GEO={},CACHE={};
function titleCase(s){return (s||'').toLowerCase().replace(/\b[a-z]/g,c=>c.toUpperCase()).replace(/ And /g,' & ')}
function pathOf(g){const rings=g.type==='MultiPolygon'?g.coordinates.flat():g.coordinates;let d='';for(const r of rings){let p='';for(let i=0;i<r.length;i++){const q=px(r[i][0],r[i][1]);p+=(i?'L':'M')+q[0].toFixed(1)+' '+q[1].toFixed(1)}d+=p+'Z'}return d}
function bboxOf(g){const rings=g.type==='MultiPolygon'?g.coordinates.flat():g.coordinates;let a=1e9,b=1e9,c=-1e9,e=-1e9;for(const r of rings)for(const t of r){const q=px(t[0],t[1]);if(q[0]<a)a=q[0];if(q[0]>c)c=q[0];if(q[1]<b)b=q[1];if(q[1]>e)e=q[1]}return[a,b,c,e]}
async function geo(kind){if(GEO[kind])return GEO[kind];const r=await fetch('/static/geo/india_'+kind+'.geojson');const j=await r.json();GEO[kind]=j.features.map(f=>({id:String(f.properties.lgd),name:titleCase(f.properties.name),slgd:String(f.properties.slgd||''),state:titleCase(f.properties.state||''),d:pathOf(f.geometry),bb:bboxOf(f.geometry)}));return GEO[kind]}
function seeded(id){let x=0;for(let i=0;i<String(id).length;i++)x=(x*31+String(id).charCodeAt(i)*17+7)%9973;return (x%100)/100}
function sample(kind,feats){const o={};feats.forEach(f=>{const r=seeded(kind+f.id);o[f.id]=r<0.18?0:Math.round(Math.pow(r,3)*(kind==='states'?400:60))});return o}
function levels(vals){const pos=vals.filter(v=>v>0).sort((a,b)=>a-b);if(!pos.length)return[];const q=p=>pos[Math.min(pos.length-1,Math.floor(p*pos.length))];const t=[q(.25),q(.5),q(.75)];return[...new Set(t)]}
const lvl=(n,t)=>n<=0?0:1+t.filter(x=>n>x).length;
const LB=['None','Few','Some','More','Most'];
async function mount(id,opts){opts=opts||{};const el=document.getElementById(id);if(!el||el.__d)return;el.__d=1;
 el.innerHTML='<div class="dmh"><b>Problem density</b><span class="xs mut" id="'+id+'_sub"></span></div><div class="dmw"><svg id="'+id+'_svg" viewBox="0 0 '+W+' '+H+'" role="img" aria-label="India map coloured by number of reported problems"></svg><div class="dmz"><button class="btn out sm" data-z="1" aria-label="Zoom in">+</button><button class="btn out sm" data-z="-1" aria-label="Zoom out">−</button><button class="btn out sm" data-z="0" aria-label="Reset">⟲</button></div></div><div class="dmi" id="'+id+'_info" aria-live="polite">Tap a state to open its districts.</div><div class="dml"><span class="xs mut">Fewer</span><i class="dc0"></i><i class="dc1"></i><i class="dc2"></i><i class="dc3"></i><i class="dc4"></i><span class="xs mut">More</span></div><div class="row xs" style="gap:10px;margin-top:6px"><label><input type="checkbox" id="'+id+'_smp"> Show SAMPLE data (fake, preview only)</label></div><div class="xs mut" id="'+id+'_note"></div>';
 const svg=document.getElementById(id+'_svg'),info=document.getElementById(id+'_info'),sub=document.getElementById(id+'_sub'),note=document.getElementById(id+'_note'),smp=document.getElementById(id+'_smp');
 let D=null,SM=false,view=[0,0,W,H],cur=null,showD=false;
 const setView=(v,anim)=>{const from=view.slice();view=v;const apply=a=>svg.setAttribute('viewBox',a.map(x=>x.toFixed(1)).join(' '));if(!anim||document.documentElement.classList.contains('lite')){apply(v);return}let t0=null;const step=ts=>{t0=t0||ts;const k=Math.min(1,(ts-t0)/280);const e=1-Math.pow(1-k,3);apply(from.map((x,i)=>x+(v[i]-x)*e));if(k<1)requestAnimationFrame(step)};requestAnimationFrame(step)};
 async function draw(){const st=await geo('states');let sd=null,dd=null;
  const real=D||{states:{},districts:{},total:0};
  const sv=SM?sample('states',st):real.states;
  const empty=!SM&&real.empty;
  const needD=cur||showD;let dist=needD?await geo('districts'):[];
  const dv=SM?sample('districts',dist):real.districts;
  const ts=levels(Object.values(sv)),td=levels(Object.values(dv));
  let h='';
  st.forEach(f=>{const n=sv[f.id]||0,fadeD=needD&&(showD||cur===f.id);const l=lvl(n,ts);
   h+='<path class="ds dc'+l+(cur===f.id?' sel':'')+(fadeD?' under':'')+'" data-k="s" data-id="'+f.id+'" d="'+f.d+'"><title>'+f.name+': '+n+'</title></path>'});
  if(needD)dist.filter(f=>showD||f.slgd===cur).forEach(f=>{const n=dv[f.id]||0;const l=lvl(n,td);h+='<path class="dd dc'+l+'" data-k="d" data-id="'+f.id+'" d="'+f.d+'"><title>'+f.name+': '+n+'</title></path>'});
  svg.innerHTML=h;
  sub.textContent=SM?'SAMPLE data, not real':empty?'No complaints yet':(real.located+' placed on map'+(real.unlocated?' · '+real.unlocated+' without location':''));
  note.innerHTML=SM?'<b style="color:#c76a00">SAMPLE:</b> these numbers are generated for preview. Untick to see real data.':empty?'Honest empty state: nobody has reported a problem yet, so every area is shown as zero. The map fills as real complaints arrive.':'Real counts: user-reported complaints on this server, placed by their own coordinates (includes sandbox test records). Boundaries: LGD open data (simplified), shown as India recognises them.';
  svg.__s={st,dist,sv,dv}}
 svg.addEventListener('click',e=>{const p=e.target.closest('path');if(!p||!svg.__s)return;const S=svg.__s,id=p.dataset.id;
  if(p.dataset.k==='s'){const f=S.st.find(x=>x.id===id);cur=id;showD=false;const b=f.bb,pad=14;setView([b[0]-pad,b[1]-pad,(b[2]-b[0])+2*pad,(b[3]-b[1])+2*pad].map((x,i)=>x),1);
    info.innerHTML='<b>'+f.name+'</b>: '+(S.sv[id]||0)+' reported · <a href="#" id="'+svg.id+'_back">Back to India</a>'}
  else{const f=S.dist.find(x=>x.id===id);info.innerHTML='<b>'+f.name+'</b>, '+f.state+': '+(S.dv[id]||0)+' reported · <a href="#" id="'+svg.id+'_back">Back to India</a>'}
  const bk=document.getElementById(svg.id+'_back');if(bk)bk.onclick=ev=>{ev.preventDefault();cur=null;showD=false;setView([0,0,W,H],1);info.textContent='Tap a state to open its districts.';draw()};draw()});
 const zoom=(f,cx,cy)=>{const nw=Math.max(40,Math.min(W,view[2]/f)),nh=nw*H/W;cx=cx==null?view[0]+view[2]/2:cx;cy=cy==null?view[1]+view[3]/2:cy;const nx=Math.max(0,Math.min(W-nw,cx-nw/2)),ny=Math.max(0,Math.min(H-nh,cy-nh/2));setView([nx,ny,nw,nh]);const want=nw<W/2.3;if(want!==showD&&!cur){showD=want;draw()}};
 el.querySelectorAll('[data-z]').forEach(b=>b.onclick=()=>{const z=+b.dataset.z;if(z===0){cur=null;showD=false;setView([0,0,W,H],1);info.textContent='Tap a state to open its districts.';draw()}else zoom(z>0?1.6:1/1.6)});
 svg.addEventListener('wheel',e=>{e.preventDefault();const r=svg.getBoundingClientRect(),x=view[0]+(e.clientX-r.left)/r.width*view[2],y=view[1]+(e.clientY-r.top)/r.height*view[3];zoom(e.deltaY<0?1.25:.8,x,y)},{passive:false});
 const ptr=new Map();let last=null,moved=0;
 svg.addEventListener('pointerdown',e=>{ptr.set(e.pointerId,[e.clientX,e.clientY]);moved=0;last=null});
 svg.addEventListener('pointermove',e=>{if(!ptr.has(e.pointerId))return;const o=ptr.get(e.pointerId),n=[e.clientX,e.clientY];ptr.set(e.pointerId,n);const r=svg.getBoundingClientRect();
  if(ptr.size===1){const dx=(o[0]-n[0])/r.width*view[2],dy=(o[1]-n[1])/r.height*view[3];moved+=Math.abs(dx)+Math.abs(dy);if(view[2]<W-1)setView([Math.max(0,Math.min(W-view[2],view[0]+dx)),Math.max(0,Math.min(H-view[3],view[1]+dy)),view[2],view[3]])}
  else if(ptr.size===2){const [a,b]=[...ptr.values()],d=Math.hypot(a[0]-b[0],a[1]-b[1]);if(last){const f=d/last;if(Math.abs(f-1)>.01)zoom(f)}last=d}});
 const up=e=>{ptr.delete(e.pointerId);last=null};svg.addEventListener('pointerup',up);svg.addEventListener('pointercancel',up);
 svg.addEventListener('click',e=>{if(moved>6)e.stopImmediatePropagation()},true);
 smp.onchange=()=>{SM=smp.checked;draw()};
 const q=opts.query||'';try{D=await (await fetch('/api/public/density'+q)).json()}catch(e){D={states:{},districts:{},total:0,empty:true}}
 draw()}
window.DensityMap={mount};
})();

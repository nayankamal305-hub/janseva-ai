/* Seva Setu India - operator console (Phase 5). Auth: admin token with seva.operate permission. */
(function(){
"use strict";
const LS=(()=>{try{const s=window['local'+'Storage'];s.setItem('_t','1');s.removeItem('_t');return s}catch(e){const m={};return{getItem:k=>m[k]??null,setItem:(k,v)=>{m[k]=v},removeItem:k=>{delete m[k]}}}})();
const $=id=>document.getElementById(id);
let T=LS.getItem('ot')||'', DET=null;

const OFFICIAL=new Set(["submitted_to_portal","government_processing","approved","rejected","completed"]);
const SLBL={request_received:"Request received",documents_pending:"Documents pending",documents_received:"Documents received",under_verification:"Under verification",form_preparation:"Form being prepared",awaiting_citizen_approval:"Waiting for citizen approval",ready_for_submission:"Ready for submission",submitted_to_portal:"Submitted to official portal",government_processing:"Government processing",additional_info_required:"More info needed",approved:"Approved",rejected:"Rejected",completed:"Completed"};
function slbl(s){return SLBL[s]||s}
function sbadge(s){
 if(s=='approved'||s=='completed')return'<span class="badge b-ok">'+slbl(s)+'</span>';
 if(s=='rejected')return'<span class="badge b-rej">'+slbl(s)+'</span>';
 if(OFFICIAL.has(s))return'<span class="badge b-off">'+slbl(s)+'</span>';
 if(s=='awaiting_citizen_approval'||s=='documents_pending'||s=='additional_info_required')return'<span class="badge b-warn">'+slbl(s)+'</span>';
 return'<span class="badge b-ssi">'+slbl(s)+'</span>';}
function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}

async function api(m,p,b){const h={'Content-Type':'application/json'};if(T)h.Authorization='Bearer '+T;
 const r=await fetch(p,{method:m,headers:h,body:b?JSON.stringify(b):undefined});
 let d=null;try{d=await r.json()}catch(e){}
 if(r.status==401||r.status==403)throw Object.assign(new Error('auth'),d||{});
 if(!r.ok)throw Object.assign(new Error('api'),d||{});
 return d;}

function showLogin(){$('loginView').classList.remove('hide');$('opView').classList.add('hide');$('logoutB').classList.add('hide');}
async function boot(){
 if(!T){showLogin();return}
 try{await loadQueue();$('loginView').classList.add('hide');$('opView').classList.remove('hide');$('logoutB').classList.remove('hide')}
 catch(e){T='';LS.removeItem('ot');showLogin();$('lmsg').textContent='Token rejected - operator permission required.';$('lmsg').classList.add('err')}
}
$('loginB').onclick=()=>{T=$('otok').value.trim();LS.setItem('ot',T);boot()};
$('logoutB').onclick=()=>{T='';LS.removeItem('ot');location.reload()};

async function loadQueue(){
 const st=$('fStatus').value;
 const r=await api('GET','/api/op/applications'+(st?'?status='+encodeURIComponent(st):''));
 const items=r.items||[];
 if(!$('fStatus').options.length||$('fStatus').options.length<2){
  // statuses arrive with the first detail; use a static list matching the backend
  ["request_received","documents_pending","documents_received","under_verification","form_preparation","awaiting_citizen_approval","ready_for_submission","submitted_to_portal","government_processing","additional_info_required","approved","rejected","completed"].forEach(s=>{const o=document.createElement('option');o.value=s;o.textContent=slbl(s);$('fStatus').appendChild(o)});
 }
 $('opDetail').classList.add('hide');$('queue').classList.remove('hide');
 $('queue').innerHTML=items.length?items.map(a=>
  '<div class="appitem" data-ref="'+esc(a.ref_no)+'"><div class="top"><div><div class="ttl">'+esc(a.title||a.category_id)+'</div>'+
  '<div class="ref">'+esc(a.ref_no)+' · '+esc(a.category_id)+' · '+esc(a.citizen_name||'')+' '+esc(a.citizen_phone||'')+'</div></div>'+sbadge(a.status)+'</div>'+
  '<div class="dt">updated '+esc(a.updated_at||'')+'</div></div>').join('')
  :'<div class="empty">No applications.</div>';
 $('queue').querySelectorAll('.appitem').forEach(el=>el.onclick=()=>openApp(el.getAttribute('data-ref')));
}
$('fStatus').onchange=loadQueue;

async function openApp(ref){
 try{DET=await api('GET','/api/op/applications/'+encodeURIComponent(ref))}catch(e){return}
 const a=DET.application,c=DET.citizen,cons=DET.consent;
 $('queue').classList.add('hide');const d=$('opDetail');d.classList.remove('hide');
 const hist=(a.history||[]).map(h=>'<div class="ev"><div class="st">'+slbl(h.status)+'</div><div class="ts">'+esc(h.ts||'')+(h.actor?' · '+esc(h.actor):'')+(h.note?' · '+esc(h.note):'')+'</div></div>').join('');
 const subs=(a.submissions||[]).map(s=>'<div class="subnote'+(s.verified?'':' unv')+'">'+(s.verified?'✓ verified':'unverified')+' · '+esc(s.portal||'')+(s.ack_no?' · Ack: '+esc(s.ack_no):'')+(s.ts?' · '+esc(s.ts):'')+'</div>').join('');
 const consentState=cons?(cons.granted&&!cons.revoked_at?'<span class="badge b-ok">consent granted</span>':cons.revoked_at?'<span class="badge b-rej">consent revoked</span>':'<span class="badge b-warn">consent denied</span>'):'<span class="badge b-ssi">no consent</span>';
 const docs=(DET.documents||[]).map(x=>'<div class="appitem"><div class="top"><div><div class="ttl">'+esc(x.filename)+'</div>'+
  '<div class="ref">'+esc(x.kind)+' · '+Math.round((x.size||0)/1024)+' KB</div></div>'+
  '<button class="btn btn-navy" data-doc="'+x.document_id+'">View</button></div></div>').join('')||'<div class="mut" style="font-size:13px">No documents attached.</div>';
 const opts=(DET.statuses||[]).map(s=>'<option value="'+s+'"'+(s==a.status?' selected':'')+'>'+slbl(s)+'</option>').join('');
 d.innerHTML='<button class="btn btn-ghost" id="backQ">&larr; Queue</button>'+
  '<div class="card"><h3>'+esc(a.title||a.category_id)+'</h3>'+
  '<div class="ref" style="font-family:ui-monospace,monospace;color:var(--mut);font-size:13px">'+esc(a.ref_no)+' · '+esc(a.category_id)+'</div>'+
  '<div style="margin:10px 0">'+sbadge(a.status)+'</div>'+
  '<div class="honest">Citizen: '+esc(c.name||'')+' '+esc(c.phone||'')+(c.district?' · '+esc(c.district):'')+(c.state?', '+esc(c.state):'')+(c.preferred_lang?' · lang '+esc(c.preferred_lang):'')+'</div>'+
  '<div style="margin:8px 0">Document access: '+consentState+' <button class="btn btn-ghost" id="reqDocs">Request document access</button></div>'+
  '<h3 style="margin-top:14px">Documents</h3>'+docs+'<p id="docMsg" class="lmsg" role="status"></p>'+
  '<h3 style="margin-top:14px">Advance status</h3>'+
  '<div class="honest">Official statuses (submitted to portal and beyond) need a verified submission with a real acknowledgement number - the server rejects them otherwise.</div>'+
  '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px"><select id="stSel" class="fld" style="flex:1;min-width:200px;padding:9px;border:1.5px solid var(--line);border-radius:10px">'+opts+'</select>'+
  '<input id="stNote" class="fld" placeholder="note (optional)" style="flex:2;min-width:200px;padding:9px;border:1.5px solid var(--line);border-radius:10px">'+
  '<button class="btn btn-saffron" id="stGo">Set status</button></div><p id="stMsg" class="lmsg" role="status"></p>'+
  '<h3 style="margin-top:14px">Record government submission</h3>'+
  '<div class="honest">Record only what actually happened. "Verified" is ignored unless a real acknowledgement number is entered.</div>'+
  '<div class="grid2" style="margin-top:8px">'+
  '<label class="fld"><span>Portal</span><input id="sbPortal" placeholder="serviceplus.gov.in"></label>'+
  '<label class="fld"><span>Method</span><select id="sbMethod"><option value="guided">guided (citizen filed with help)</option><option value="operator_filed">operator filed</option><option value="citizen_self">citizen self-reported</option></select></label>'+
  '<label class="fld"><span>Acknowledgement number</span><input id="sbAck" placeholder="real ack from portal"></label>'+
  '<label class="fld"><span>Receipt URL</span><input id="sbReceipt" placeholder="https://..."></label></div>'+
  '<label style="display:flex;gap:8px;align-items:center;font-size:14px;margin:6px 0"><input type="checkbox" id="sbVer"> Verified (ack checked on the official portal)</label>'+
  '<button class="btn btn-navy" id="sbGo">Record submission</button><p id="sbMsg" class="lmsg" role="status"></p>'+
  subs+
  '<h3 style="margin-top:14px">Timeline</h3><div class="tl">'+hist+'</div></div>';
 $('backQ').onclick=loadQueue;
 $('reqDocs').onclick=async()=>{try{await api('POST','/api/op/applications/'+encodeURIComponent(ref)+'/request-docs',{});$('docMsg').textContent='Consent request sent to the citizen.'}catch(e){$('docMsg').textContent=(e&&e.error)||'Failed'}};
 d.querySelectorAll('[data-doc]').forEach(b=>b.onclick=async()=>{
  const id=b.getAttribute('data-doc'),m=$('docMsg');m.classList.remove('err');
  try{const r=await fetch('/api/op/documents/'+id+'/file?app='+encodeURIComponent(ref),{headers:{Authorization:'Bearer '+T}});
   if(r.status==403){m.textContent='Citizen has not consented yet. Use "Request document access".';m.classList.add('err');return}
   if(!r.ok){m.textContent='Not found';m.classList.add('err');return}
   const bl=await r.blob();window.open(URL.createObjectURL(bl),'_blank')}catch(e){m.textContent='Failed';m.classList.add('err')}});
 $('stGo').onclick=async()=>{
  const m=$('stMsg');m.classList.remove('err');
  try{const r=await api('POST','/api/op/applications/'+encodeURIComponent(ref)+'/status',{status:$('stSel').value,note:$('stNote').value});
   if(r.ok){openApp(ref)}else{m.textContent=r.error||'Rejected';m.classList.add('err')}
  }catch(e){m.textContent=(e&&e.error)||'Failed';m.classList.add('err')}};
 $('sbGo').onclick=async()=>{
  const m=$('sbMsg');m.classList.remove('err');
  try{const r=await api('POST','/api/op/applications/'+encodeURIComponent(ref)+'/submissions',{portal:$('sbPortal').value,method:$('sbMethod').value,ack_no:$('sbAck').value,receipt_url:$('sbReceipt').value,verified:$('sbVer').checked});
   if(r.ok){m.textContent=r.verified?'Recorded as verified (ack present).':'Recorded as UNVERIFIED (no ack number).';openApp(ref)}else{m.textContent=r.error||'Failed';m.classList.add('err')}
  }catch(e){m.textContent=(e&&e.error)||'Failed';m.classList.add('err')}};
}

boot();
})();

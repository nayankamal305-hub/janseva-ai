// Loads app.js in a stub DOM: must not throw, and every section must open without throwing.
const fs=require('fs'),vm=require('vm');
const el=()=>new Proxy(function(){},{get:(t,k)=>k==='style'?{}:k==='classList'?{toggle(){},add(){},remove(){},contains(){return false}}:k==='dataset'?{}:k==='children'?[]:k==='value'?'':k==='checked'?false:(k==='innerHTML'||k==='textContent')?'':(()=>el()),set:()=>true,apply:()=>el()});
const doc={getElementById:()=>el(),querySelectorAll:()=>[],querySelector:()=>el(),createElement:()=>el(),addEventListener(){},body:el(),documentElement:el()};
const win={document:doc,addEventListener(){},location:{hash:'',origin:'http://x',reload(){}},history:{replaceState(){}},localStorage:{getItem:()=>null,setItem(){},removeItem(){}},navigator:{serviceWorker:{register:()=>Promise.resolve()},onLine:true},scrollTo(){},ICONS:{},fetch:()=>Promise.resolve({json:()=>Promise.resolve({})}),setTimeout:()=>0,clearTimeout(){},confirm:()=>false,prompt:()=>null,toast(){}};
win.window=win; const ctx=vm.createContext(Object.assign(win,{localStorage:win.localStorage,document:doc,console,Promise,JSON,Math,Date,Array,Object,String,Number,encodeURIComponent,URL,Blob:function(){},Image:function(){},FileReader:function(){}}));
const src=fs.readFileSync(process.argv[2],'utf8'); let bad=0;
try{vm.runInContext(src,ctx,{filename:'app.js'})}catch(e){console.error('LOAD FAIL',e.message);process.exit(1)}
for(const f of ['go','openLogin','submitC','rateOpen','rateSearch','tweetC','supportSim','nextW']) if(typeof ctx.window[f]!=='function'){console.error('missing window.'+f);bad++}
for(const s of ['home','report','mine','nearby','pub','dir','rate','assist','emergency']){try{ctx.window.go(s)}catch(e){console.error('go('+s+') threw',e.message);bad++}}
// Dead-token regression: with a stored token that the server rejects (401),
// openLogin must clear it and open the login sheet instead of looping to 'mine'.
(async()=>{
  let removed='', sheetOn=false, asked=[];
  const sheetEl={classList:{add:c=>{if(c==='on')sheetOn=true},remove(){},toggle(){},contains:()=>false},style:{}};
  const store={jt:'dead-token'};
  const doc2=Object.assign({},doc,{getElementById:id=>id==='sheet'?sheetEl:el()});
  const ls2={getItem:()=>null,setItem(){},removeItem:k=>{removed=k;delete store[k]}};
  Object.defineProperty(ls2,'jt',{get:()=>store.jt,set:v=>{store.jt=v},configurable:true});
  const win2=Object.assign({},win,{document:doc2,localStorage:ls2,fetch:u=>{asked.push(u);return Promise.resolve({status:401,json:()=>Promise.resolve({error:'bad token'})})}});
  win2.window=win2;
  const ctx2=vm.createContext(Object.assign(win2,{document:doc2,localStorage:ls2,console,Promise,JSON,Math,Date,Array,Object,String,Number,encodeURIComponent,URL,Blob:function(){},Image:function(){},FileReader:function(){}}));
  try{
    vm.runInContext(src,ctx2,{filename:'app.js'});
    await ctx2.window.openLogin();
    if(!sheetOn){console.error('dead token: login sheet did not open');bad++}
    if(!asked.some(u=>String(u).includes('/api/complaints'))){console.error('dead token: token was not validated against the API');bad++}
    if(removed!=='jt'){console.error('dead token: stored token was not cleared');bad++}
  }catch(e){console.error('dead-token test threw',e.message);bad++}
  process.exit(bad?1:0);
})();

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
process.exit(bad?1:0);

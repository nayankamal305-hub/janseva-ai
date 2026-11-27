// Clicking Login must open the login sheet when logged out, with a stale token (server forgot it), and with blocked storage.
const fs=require('fs'),vm=require('vm');
function run(name,{token,status,body,blocked}){return new Promise(async(res)=>{
  const els={};const mk=id=>els[id]||(els[id]=(()=>{const cls=new Set();const o={id,style:{},dataset:{},children:[],value:'',checked:false,innerHTML:'',textContent:'',
    classList:{add:c=>cls.add(c),remove:c=>cls.delete(c),toggle:(c,f)=>{(f===undefined?!cls.has(c):f)?cls.add(c):cls.delete(c)},contains:c=>cls.has(c)},_cls:cls,
    addEventListener(){},appendChild(){},querySelectorAll:()=>[],querySelector:()=>mk('q'),setAttribute(){},getBoundingClientRect:()=>({}),focus(){},click(){}};return o})());
  const doc={getElementById:mk,querySelectorAll:()=>[],querySelector:()=>mk('q'),createElement:()=>mk('c'+Math.random()),addEventListener(){},body:mk('body'),documentElement:mk('html')};
  const store={};if(token)store.jt=token;
  const ls=blocked?new Proxy({},{get(){throw new Error('SecurityError')},set(){throw new Error('SecurityError')}}):new Proxy(store,{get:(o,k)=>k==='removeItem'?(x=>{delete o[x]}):k==='setItem'?((a,b)=>{o[a]=b}):k==='getItem'?(a=>o[a]===undefined?null:o[a]):o[k],set:(o,k,v)=>{o[k]=v;return true}});
  const win={document:doc,addEventListener(){},location:{hash:'#home',search:'',origin:'http://x',reload(){}},history:{replaceState(){}},navigator:{serviceWorker:{register:()=>Promise.resolve()},onLine:true},scrollTo(){},ICONS:{},matchMedia:()=>({matches:false}),
    fetch:(u)=>Promise.resolve({status:status,json:()=>Promise.resolve(body)}),setTimeout:(f)=>0,clearTimeout(){},confirm:()=>false,prompt:()=>null,toast(){}};
  Object.defineProperty(win,'localStorage',{get(){if(blocked)throw new Error('SecurityError');return ls}});
  win.window=win;const ctx=vm.createContext(Object.assign(win,{document:doc,console,Promise,JSON,Math,Date,Array,Object,String,Number,Proxy,Set,encodeURIComponent,URL,Blob:function(){},Image:function(){},FileReader:function(){}}));
  vm.runInContext(fs.readFileSync(process.argv[2],'utf8'),ctx,{filename:'app.js'});
  await ctx.window.openLogin();await new Promise(r=>setImmediate(r));
  res({name,sheetOpen:mk('sheet')._cls.has('on'),stored:store.jt});
});}
(async()=>{let bad=0;
 const cases=[[ 'logged out',{status:401,body:{error:'x'}},true],['stale token',{token:'stale',status:401,body:{error:'x'}},true],['blocked storage',{blocked:true,status:401,body:{error:'x'}},true],['valid token',{token:'ok',status:200,body:[]},false]];
 for(const [n,o,want] of cases){const r=await run(n,o);const ok=r.sheetOpen===want&&(n!=='stale token'||r.stored===undefined);console.log((ok?'PASS ':'FAIL ')+n,JSON.stringify(r));if(!ok)bad++}
 process.exit(bad?1:0)})();

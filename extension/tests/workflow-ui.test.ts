import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {JSDOM} from 'jsdom';
import {setupWorkflow} from '../src/workflow-ui';

const html=readFileSync('extension/public/manager.html','utf8');
const settle=()=>new Promise<void>(resolve=>setImmediate(resolve));
async function environment(catalogError="", session:any=null){
  const dom=new JSDOM(html,{url:'https://example.test/manager.html#automation'});
  const p={schema:1,name:'Test paketi',initial:'TITLE-ABS-KEY("test")',topics:[{code:'Q01',label:'İlk konu',query:'"test"'}]};
  const state={package:p,revision:'first',saved:null as any,error:'',session,launches:[] as any[],messages:[] as string[]};
  const originals=new Map<string,PropertyDescriptor|undefined>();
  const globals:any={document:dom.window.document,location:dom.window.location,Option:dom.window.Option,
    addEventListener:dom.window.addEventListener.bind(dom.window),setInterval:()=>0,
    chrome:{runtime:{sendMessage:async(m:any)=>{if(m.kind==='workflow_launch')state.launches.push(m.payload);return {ok:true,data:m.kind==='workflow_targets'?[{id:10,title:'Scopus',urlSafe:'https://test'}]:{}};}},permissions:{request:async()=>true}}};
  for(const [key,value] of Object.entries(globals)){originals.set(key,Object.getOwnPropertyDescriptor(globalThis,key));Object.defineProperty(globalThis,key,{value,writable:true,configurable:true});}
  const catalog=()=>({package:structuredClone(state.package),revision:state.revision,path:'test/03_Calisma/sorgu-paketi.json',project_root:'test',library:'TEZ',clock_confirmed:true});
  setupWorkflow(async(kind,payload)=>{
    if(kind==='workflow_catalog'){if(catalogError)throw new Error(catalogError);return catalog();}
    if(kind==='workflow_status')return {session:state.session,running:false};
    if(kind==='workflow_save_package'){
      if(state.error)throw new Error(state.error);
      state.saved=payload;state.package=payload!.package;state.revision='saved';return catalog();
    }
    throw new Error('Unexpected RPC: '+kind);
  },message=>state.messages.push(message));
  await settle();await settle();
  const field=(id:string)=>dom.window.document.getElementById(id) as HTMLInputElement;
  return {dom,state,field,close(){dom.window.close();for(const [key,original] of originals){if(original)Object.defineProperty(globalThis,key,original);else delete (globalThis as any)[key];}}};
}

test('saved edits are passed to the next workflow without a new build',async()=>{
  const e=await environment();
  try{
    assert.equal(e.field('query-package-name').value,'Test paketi');
    e.field('topic-query-Q01').value='"yeni terim"';
    e.field('topic-query-Q01').dispatchEvent(new e.dom.window.Event('input',{bubbles:true}));
    assert.equal(e.field('workflow-start').disabled,true);
    e.field('query-package-form').dispatchEvent(new e.dom.window.Event('submit',{bubbles:true,cancelable:true}));
    await settle();await settle();
    assert.equal(e.state.saved.package.topics[0].query,'"yeni terim"');
    assert.equal(e.state.saved.revision,'first');
    assert.equal(e.field('workflow-start').disabled,false,JSON.stringify(e.state.messages));
    assert.equal(e.field('workflow-target').value,'10',JSON.stringify(e.state.messages));
    e.field('workflow-start').click();await settle();
    assert.equal(e.state.launches.length,1,JSON.stringify(e.state.messages));
    assert.equal(e.state.launches[0].options.package_revision,'saved');
  }finally{e.close();}
});

test('failed save preserves the draft and cannot start an unsaved search',async()=>{
  const e=await environment();
  try{
    e.state.error='Dosya değişti';e.field('query-package-name').value='Kaybolmaması gereken taslak';
    e.field('query-package-name').dispatchEvent(new e.dom.window.Event('input',{bubbles:true}));
    e.field('query-package-form').dispatchEvent(new e.dom.window.Event('submit',{bubbles:true,cancelable:true}));
    await settle();await settle();
    assert.equal(e.field('query-package-name').value,'Kaybolmaması gereken taslak');
    assert.equal(e.field('workflow-start').disabled,true);
    assert.ok(e.state.messages.includes('Dosya değişti'));
  }finally{e.close();}
});

test('adding and removing topics preserves remaining topic identities',async()=>{
  const e=await environment();
  try{
    e.field('query-topic-add').click();
    e.field('topic-label-Q02').value='İkinci konu';e.field('topic-query-Q02').value='"ikinci"';
    e.dom.window.document.querySelector<HTMLButtonElement>('[data-code="Q01"] button')!.click();
    e.field('query-package-form').dispatchEvent(new e.dom.window.Event('submit',{bubbles:true,cancelable:true}));
    await settle();await settle();
    assert.deepEqual(e.state.saved.package.topics,[{code:'Q02',label:'İkinci konu',query:'"ikinci"'}]);
  }finally{e.close();}
});


test('a broken external package does not prevent resuming the saved session',async()=>{
  const e=await environment('Sorgu dosyası bozuk',{id:'saved-session',state:'paused',elapsed:0,steps:[],snapshot:{package_name:'Kaydedilen paket'}});
  try{
    assert.equal(e.field('workflow-start').disabled,true);
    assert.equal(e.field('workflow-resume').disabled,false);
    assert.ok(e.field('workflow-progress').textContent?.includes('Kaydedilen paket'));
    e.field('workflow-resume').click();await settle();
    assert.equal(e.state.launches[0].id,'saved-session');
    assert.ok(e.state.messages.includes('Sorgu dosyası bozuk'));
  }finally{e.close();}
});

test('a wrong capture is set aside only after a second click and leaves the pending list',async()=>{
  const {build}=await import('esbuild');
  const script=await build({entryPoints:['extension/src/manager.ts'],bundle:true,write:false,format:'iife'});
  const dom=new JSDOM(html,{url:'https://extension.test/manager.html#pending',runScripts:'outside-only'});
  const calls:any[]=[];let pending=[{id:'job-1',state:'incomplete',created_at:'2026-10-16T13:35:47Z',captured_at:null,error:'Sorgu/sonuç doğrulanamadı.'}];
  const answers:Record<string,()=>any>={
    status:()=>({project_root:'D:/Tez',settings:{project_name:'P',team_code:'OEC-1017',operator:'Hasan',hotkey:'CTRL+M',monitor:'active',clock_confirmed:true,collection_mapping:{},library:'groups/1',zotero_mode:'local'},
      paused:false,busy:false,bound_windows:1,hotkey_error:null,run_count:0,pending_count:pending.length,monitors:[],note_template:'',note_templates:{},last_export:null}),
    list_runs:()=>({rows:[],total:0}),list_pending:()=>({rows:pending,total:pending.length}),list_papers:()=>({rows:[],total:0}),
    discard_job:()=>{pending=[];return {id:'job-1',state:'discarded'};}};
  (dom.window as any).chrome={runtime:{sendMessage:async(m:any)=>{calls.push(m.type||m.kind);const f=answers[m.type];return f?{ok:true,data:f()}:{ok:false,error:'test: '+(m.type||m.kind)};}},
    storage:{local:{get:async()=>({}),set:async()=>{},remove:async()=>{}}},permissions:{request:async()=>true,contains:async()=>true}};
  try{
    dom.window.eval(script.outputFiles[0].text);
    for(let i=0;i<10;i++)await settle();
    const d=dom.window.document,discard=()=>d.querySelector<HTMLButtonElement>('[data-discard="job-1"]');
    assert.ok(discard(),'pending item offers the discard action');
    discard()!.click();for(let i=0;i<3;i++)await settle();
    assert.equal(calls.filter(c=>c==='discard_job').length,0,'first click only asks for confirmation');
    assert.match(discard()!.textContent!,/Emin misin/);
    discard()!.click();for(let i=0;i<10;i++)await settle();
    assert.equal(calls.filter(c=>c==='discard_job').length,1);
    assert.equal(discard(),null);
    assert.match(d.getElementById('message')!.textContent!,/PNG silinmedi/);
  }finally{dom.window.close();}
});

test('every pattern in the manager compiles in the v mode Chrome uses for pattern attributes',()=>{
  // 16.10.2026: Chrome reported [A-Za-z0-9_-]{1,40} as invalid and silently dropped the check.
  const patterns=[...html.matchAll(/pattern="([^"]*)"/g)].map(m=>m[1].replace(/&quot;/g,'"').replace(/&amp;/g,'&'));
  assert.ok(patterns.length>0);
  for(const p of patterns){
    assert.doesNotThrow(()=>new RegExp('^(?:'+p+')$','v'),p);
    assert.ok(new RegExp('^(?:'+p+')$','v').test('OEC-1017'),p);
  }
});

test('a pasted project path switches the project without a native dialog',async()=>{
  const {build}=await import('esbuild');
  const script=await build({entryPoints:['extension/src/manager.ts'],bundle:true,write:false,format:'iife'});
  const dom=new JSDOM(html,{url:'https://extension.test/manager.html#settings',runScripts:'outside-only'});
  const calls:any[]=[];let root='D:/Tez/OEC-1017_O2';
  const status=()=>({project_root:root,settings:{project_name:'P',team_code:'OEC-1017',operator:'Hasan',hotkey:'CTRL+M',monitor:'active',clock_confirmed:true,collection_mapping:{},library:'groups/1',zotero_mode:'local'},
    paused:false,busy:false,bound_windows:1,hotkey_error:null,run_count:0,pending_count:0,monitors:[],note_template:'',note_templates:{},last_export:null});
  const answers:Record<string,(p:any)=>any>={status,list_runs:()=>({rows:[],total:0}),list_pending:()=>({rows:[],total:0}),list_papers:()=>({rows:[],total:0}),
    switch_project:(p:any)=>{root=p.path;return {project_root:p.path,run_count:0};}};
  (dom.window as any).chrome={runtime:{sendMessage:async(m:any)=>{calls.push({type:m.type,payload:m.payload});const f=answers[m.type];return f?{ok:true,data:f(m.payload)}:{ok:false,error:'test: '+m.type};}},
    storage:{local:{get:async()=>({}),set:async()=>{},remove:async()=>{}}},permissions:{request:async()=>true,contains:async()=>true}};
  try{
    dom.window.eval(script.outputFiles[0].text);
    for(let i=0;i<10;i++)await settle();
    const d=dom.window.document,input=d.getElementById('project-path') as HTMLInputElement;
    input.value='D:/Tez/Deneme';
    (d.getElementById('switch-project') as HTMLButtonElement).click();
    for(let i=0;i<10;i++)await settle();
    assert.equal(calls.find(c=>c.type==='switch_project')?.payload?.path,'D:/Tez/Deneme');
    assert.equal(calls.filter(c=>c.type==='pick_project').length,0);
    assert.equal(d.getElementById('project-root')!.textContent,'D:/Tez/Deneme');
    assert.match(d.getElementById('message')!.textContent!,/Ctrl\+M bundan sonra buraya/);
    assert.equal(input.value,'');
  }finally{dom.window.close();}
});

test('screening decisions are applied only after an explicit approval of a clean file',async()=>{
  const {build}=await import('esbuild');
  const script=await build({entryPoints:['extension/src/manager.ts'],bundle:true,write:false,format:'iife'});
  const dom=new JSDOM(html,{url:'https://extension.test/manager.html#zotero',runScripts:'outside-only'});
  const calls:any[]=[];let approved=false,problems:string[]=['K1: başlık Zotero kaydıyla aynı değil'];
  const counts={aday:4,baslik_haric:1,ozet_incelenen:3,ozet_haric:1,haric:2,haric_kod:{H2:1,H5:1},gecen:2,tam_metin_secilen:1,yedek:1,ozet_okunmadi:0};
  const screening=()=>({path:'D:/Tez/03_Calisma/Eleme/eleme_kararlari.json',exists:true,job:{running:false,lines:[],summary:'',error:''},counts,
    problems,problem_count:problems.length,approved,approval:approved?'Onaylı: Hasan, 18.10.2026':'Onaylanmadı',
    plan:{not:approved?2:0,erisim_kontrol:1},zotero:{durumlar:{candidate:4},etiketler:{}},applied:{},in_zotero:false});
  const status=()=>({project_root:'D:/Tez',settings:{project_name:'P',team_code:'OEC-1017',operator:'Hasan',hotkey:'CTRL+M',monitor:'active',clock_confirmed:true,collection_mapping:{},library:'groups/1',zotero_mode:'local'},
    paused:false,busy:false,bound_windows:1,hotkey_error:null,run_count:0,pending_count:0,monitors:[],note_template:'',note_templates:{},last_export:null});
  const answers:Record<string,(p:any)=>any>={status,list_runs:()=>({rows:[],total:0}),list_pending:()=>({rows:[],total:0}),list_papers:()=>({rows:[],total:0}),
    screening_status:screening,screening_approve:(p:any)=>{assert.equal(p.confirmed,true);approved=true;return screening();},
    screening_apply:()=>({running:true,lines:[],summary:'',error:''})};
  (dom.window as any).chrome={runtime:{sendMessage:async(m:any)=>{calls.push(m.type);const f=answers[m.type];return f?{ok:true,data:f(m.payload)}:{ok:false,error:'test: '+m.type};}},
    storage:{local:{get:async()=>({}),set:async()=>{},remove:async()=>{}}},permissions:{request:async()=>true,contains:async()=>true}};
  try{
    dom.window.eval(script.outputFiles[0].text);
    for(let i=0;i<10;i++)await settle();
    const d=dom.window.document,b=(id:string)=>d.getElementById(id) as HTMLButtonElement;
    assert.match(d.getElementById('screening-summary')!.textContent!,/başlıktan hariç 1/);
    assert.equal(d.getElementById('screening-problems')!.hidden,false);
    assert.equal(b('screening-approve').disabled,true,'a file with problems cannot be approved');
    assert.equal(b('screening-apply').disabled,true);
    problems=[];b('screening-refresh').click();for(let i=0;i<10;i++)await settle();
    assert.equal(b('screening-approve').disabled,false);
    assert.equal(b('screening-apply').disabled,true,'nothing is applied before approval');
    b('screening-approve').click();for(let i=0;i<10;i++)await settle();
    assert.equal(calls.filter(c=>c==='screening_approve').length,0,'approval needs the confirmation box');
    assert.match(d.getElementById('message')!.textContent!,/kontrol ettiğini işaretle/);
    (d.getElementById('screening-confirm') as HTMLInputElement).checked=true;
    b('screening-approve').click();for(let i=0;i<10;i++)await settle();
    assert.equal(calls.filter(c=>c==='screening_approve').length,1);
    assert.equal(b('screening-approve').disabled,true,'an approved file is not approved twice');
    assert.equal(b('screening-apply').disabled,false);
    b('screening-apply').click();for(let i=0;i<10;i++)await settle();
    assert.equal(calls.filter(c=>c==='screening_apply').length,1);
  }finally{dom.window.close();}
});

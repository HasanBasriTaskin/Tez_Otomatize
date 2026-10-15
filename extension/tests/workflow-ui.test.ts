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

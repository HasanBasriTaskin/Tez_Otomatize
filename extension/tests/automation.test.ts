import test from 'node:test';
import assert from 'node:assert/strict';
import {JSDOM} from 'jsdom';
import {build} from 'esbuild';
import {readFileSync} from 'node:fs';
import {runScopusAction} from '../src/automation-dom';

const url='https://proxy.example.test/pages/search/publications';
const query='TITLE-ABS-KEY ( "retrieval augmented generation" OR "retrieval-augmented generation" ) AND ( DOCTYPE ( ar ) OR DOCTYPE ( cp ) OR DOCTYPE ( re ) )';
const plan={query,expectedCount:12773};
function page(body?:string){
  const dom=new JSDOM(body===undefined?readFileSync('extension/tests/fixtures/scopus-publications.html','utf8'):
    '<html lang="en"><head><title>Scopus - Documents Search</title></head><body>'+body+'</body></html>',{url,runScripts:'outside-only'});
  dom.window.HTMLElement.prototype.getClientRects=function(){return [{width:100,height:20}] as any;};
  dom.window.HTMLElement.prototype.getBoundingClientRect=function(){return {x:0,y:20,top:20,bottom:40,left:0,right:100,width:100,height:20,toJSON(){}};};
  dom.window.HTMLElement.prototype.scrollIntoView=function(){};
  return dom;
}
function dialog(){const dom=page();dom.window.document.body.insertAdjacentHTML('beforeend',readFileSync('extension/tests/fixtures/scopus-export-dialog.html','utf8'));return dom;}
async function configure(d:Document,p=plan){
  let r:Record<string,any>={};
  for(let i=0;i<12;i++){r=await runScopusAction(d,url,'export_configure',p);if(r.stage==='export-configured')return r;assert.equal(r.nextAction,'export_configure');}
  assert.fail('Export configuration did not converge');
}

test('inspection reads executed results and distinguishes stale query/count',async()=>{
  const dom=page(),d=dom.window.document;
  try{
    const r=await runScopusAction(d,url,'inspect',plan);
    assert.equal(r.stage,'results');assert.equal(r.data.count_value,12773);assert.equal(r.queryMatches,true);assert.equal(r.countMatches,true);
    const stale=await runScopusAction(d,url,'inspect',{query:'TITLE-ABS-KEY ( other )',expectedCount:3});
    assert.equal(stale.queryMatches,false);assert.equal(stale.countMatches,false);
  }finally{dom.window.close();}
});
test('inspection preserves zero, unknown and approximate counts',async()=>{
  for(const [text,value,qualifier] of [['0 documents found',0,'exact'],['Please wait',null,'unknown'],['About 12,773 documents found',12773,'approximate']]){
    const dom=page(),d=dom.window.document;
    try{d.querySelector('h2')!.textContent=String(text);const r=await runScopusAction(d,url,'inspect',plan);assert.equal(r.data.count_value,value);assert.equal(r.data.count_qualifier,qualifier);}
    finally{dom.window.close();}
  }
});
test('a persistent export notification cannot hide the executed results from the next search',async()=>{
  const dom=page();dom.window.document.body.insertAdjacentHTML('beforeend','<div role="status">Your export is ready to download</div>');
  try{assert.equal((await runScopusAction(dom.window.document,url,'inspect',plan)).stage,'results');}finally{dom.window.close();}
});
test('challenge and login detection prevents search/export clicks',async()=>{
  for(const [markup,stage] of [['<h1>Verify you are human</h1>','challenge'],['<div role="dialog"><h2>Sign in to export</h2></div>','login']]){
    const dom=page(markup+'<button>Edit in advanced search</button>');let clicks=0;
    dom.window.document.querySelector('button')!.onclick=()=>{clicks++;};
    try{assert.equal((await runScopusAction(dom.window.document,url,'inspect',{})).stage,stage);
      await assert.rejects(runScopusAction(dom.window.document,url,'open_search',{}));assert.equal(clicks,0);
    }finally{dom.window.close();}
  }
});
test('open_search uses the actual edit control and never guesses a destination',async()=>{
  const dom=page();const d=dom.window.document;let clicks=0;
  d.body.insertAdjacentHTML('beforeend','<button data-testid="button-edit-in-advanced-search">Edit in advanced search</button>');
  d.querySelector('[data-testid="button-edit-in-advanced-search"]')!.addEventListener('click',()=>clicks++);
  try{assert.equal((await runScopusAction(d,url,'open_search',{})).nextAction,'inspect');assert.equal(clicks,1);}
  finally{dom.window.close();}
});
test('home navigation follows the observed same-origin advanced search link',async()=>{
  const dom=page('<a href="/pages/search/advanced">Advanced document search</a>');let clicks=0;
  dom.window.document.querySelector('a')!.addEventListener('click',e=>{e.preventDefault();clicks++;});
  try{const r=await runScopusAction(dom.window.document,'https://proxy.example.test/pages/home','open_search',{});assert.equal(r.nextAction,'inspect');assert.equal(clicks,1);}
  finally{dom.window.close();}
});
test('open_search refuses duplicate controls and links to unrelated origins',async()=>{
  for(const markup of ['<button>Edit in advanced search</button><button>Edit in advanced search</button>',
    '<a href="https://unrelated.test/login">Advanced document search</a>']){
    const dom=page(markup);let clicks=0;dom.window.document.body.addEventListener('click',()=>clicks++);
    try{await assert.rejects(runScopusAction(dom.window.document,url,'open_search',{}));assert.equal(clicks,0);}
    finally{dom.window.close();}
  }
});
test('native setter, input and blur commit the full query through a controlled React editor',async()=>{
  const script=await build({entryPoints:['extension/tests/fixtures/scopus-advanced-controls.tsx'],bundle:true,write:false,format:'iife'});
  const dom=page('');
  try{dom.window.eval(script.outputFiles[0].text);const d=dom.window.document;
    const r=await runScopusAction(d,url,'fill_search',{query});assert.equal(r.stage,'search-filled');
    await new Promise(r=>setImmediate(r));
    await runScopusAction(d,url,'submit_search',{query});
    assert.equal((dom.window as any).submittedQuery,query);
  }finally{dom.window.close();}
});

// Model-backed event contract; live selector shape comes from the supplied Scopus DOM.
function monacoPage(initial='old query\nsecond line',pasteDelay=0){
  const dom=page(readFileSync('extension/tests/fixtures/scopus-monaco-editor.html','utf8'));
  const w=dom.window,d=w.document,editor=d.querySelector<HTMLElement>('.native-edit-context')!;
  const context={text:'',selectionStart:0,selectionEnd:0};
  let model=initial,submitted='',pastes=0;
  Object.defineProperty(editor,'editContext',{value:context,configurable:true});
  (w as any).DataTransfer=class{data=new Map<string,string>();get types(){return [...this.data.keys()];}setData(type:string,value:string){this.data.set(type,value);}getData(type:string){return this.data.get(type)||'';}};
  (w as any).ClipboardEvent=class extends w.Event{clipboardData:any;constructor(type:string,options:any){super(type,options);this.clipboardData=options.clipboardData;}};
  editor.addEventListener('keydown',event=>{
    if(event.ctrlKey&&event.key==='a'){
      event.preventDefault();context.text=model;context.selectionStart=0;context.selectionEnd=model.length;
    }
  });
  editor.addEventListener('paste',event=>{
    event.preventDefault();pastes++;
    const value=model.slice(0,context.selectionStart)+event.clipboardData!.getData('text/plain')+model.slice(context.selectionEnd);
    const commit=()=>{model=value;context.text=model;context.selectionStart=context.selectionEnd=model.length;};
    if(pasteDelay)w.setTimeout(commit,pasteDelay);else commit();
  });
  editor.addEventListener('copy',event=>{
    event.preventDefault();event.clipboardData!.setData('text/plain',model.slice(context.selectionStart,context.selectionEnd));
  });
  d.querySelector('button')!.onclick=()=>{submitted=model;};
  return {dom,d,editor,context,get model(){return model;},get submitted(){return submitted;},get pastes(){return pastes;}};
}
test('Scopus Monaco native EditContext is recognized without treating its readonly IME textarea as the editor',async()=>{
  const p=monacoPage();
  try{const result=await runScopusAction(p.d,url,'inspect',{});assert.equal(result.stage,'search');assert.equal(result.editorReady,true);}
  finally{p.dom.window.close();}
});
test('Monaco replaces the complete model through editor events and verifies it before submitting',async()=>{
  const p=monacoPage();const target='TITLE-ABS-KEY("Türkçe"\nAND "retrieval augmented generation")';
  try{
    await runScopusAction(p.d,url,'fill_search',{query:target});
    assert.equal(p.model,target);assert.equal(p.pastes,1);
    assert.equal(p.editor.textContent,'');assert.equal(p.d.querySelector('textarea')!.value,'');
    await runScopusAction(p.d,url,'submit_search',{query:target});assert.equal(p.submitted,target);
  }finally{p.dom.window.close();}
});
test('Monaco submit rejects hidden extra model lines even if the rendered first line matches',async()=>{
  const p=monacoPage(query+'\nAND unexpected');
  p.d.querySelector('.view-line')!.textContent=query;
  try{await assert.rejects(runScopusAction(p.d,url,'submit_search',{query}));assert.equal(p.submitted,'');}
  finally{p.dom.window.close();}
});
test('Monaco waits for asynchronous paste to commit without duplicating it',async()=>{
  const p=monacoPage('old query',160);
  try{
    await runScopusAction(p.d,url,'fill_search',{query});
    assert.equal(p.model,query);assert.equal(p.pastes,1);
    await runScopusAction(p.d,url,'submit_search',{query});assert.equal(p.submitted,query);
  }finally{p.dom.window.close();}
});
test('Monaco stops if copy cannot verify the model or paste never updates it',async()=>{
  for(const eventType of ['copy','paste']){
    const p=monacoPage('old query');
    p.editor.addEventListener(eventType,event=>{event.stopImmediatePropagation();if(eventType==='paste')event.preventDefault();},true);
    try{await assert.rejects(runScopusAction(p.d,url,'fill_search',{query}));assert.equal(p.model,'old query');assert.equal(p.submitted,'');}
    finally{p.dom.window.close();}
  }
});
test('Monaco missing native context, readonly and duplicate editors stop without writing',async()=>{
  for(const change of ['missing','readonly','duplicate']){
    const p=monacoPage();
    if(change==='missing')delete (p.editor as any).editContext;
    if(change==='readonly')p.editor.setAttribute('aria-readonly','true');
    if(change==='duplicate')p.d.body.insertAdjacentHTML('beforeend',readFileSync('extension/tests/fixtures/scopus-monaco-editor.html','utf8'));
    try{await assert.rejects(runScopusAction(p.d,url,'fill_search',{query}));assert.equal(p.pastes,0);assert.equal(p.submitted,'');}
    finally{p.dom.window.close();}
  }
});
test('fill and submit refuse ambiguous editors, wrong queries and ambiguous buttons',async()=>{
  for(const body of [
    '<form><textarea aria-label="Advanced search query"></textarea><textarea aria-label="Advanced search query"></textarea><button>Search</button></form>',
    '<form><textarea aria-label="Advanced search query">TITLE-ABS-KEY ( other )</textarea><button>Search</button></form>',
    '<form><textarea aria-label="Advanced search query">'+query+'</textarea><button>Search</button><button>Search</button></form>']){
    const dom=page(body);let clicks=0;dom.window.document.body.addEventListener('click',()=>clicks++);
    try{await assert.rejects(runScopusAction(dom.window.document,url,'submit_search',{query}));assert.equal(clicks,0);}
    finally{dom.window.close();}
  }
  const dom=page('<textarea aria-label="Advanced search query"></textarea><textarea aria-label="Advanced search query"></textarea>');
  try{await assert.rejects(runScopusAction(dom.window.document,url,'fill_search',{query}));assert.deepEqual([...dom.window.document.querySelectorAll('textarea')].map(x=>x.value),['','']);}
  finally{dom.window.close();}
});
test('submit refuses loading state and malformed or truncated target expressions',async()=>{
  const dom=page('<form><textarea id="advancedQueryTextArea">'+query+'</textarea><button>Search</button></form><div aria-busy="true"></div>');
  try{await assert.rejects(runScopusAction(dom.window.document,url,'submit_search',{query}));
    dom.window.document.querySelector('[aria-busy]')!.remove();
    for(const q of ['RAG','TITLE-ABS-KEY ( "unfinished )','TITLE-ABS-KEY ( test ) AND'])await assert.rejects(runScopusAction(dom.window.document,url,'fill_search',{query:q}));
  }finally{dom.window.close();}
});
test('evidence expands the executed query before declaring visible evidence ready',async()=>{
  const dom=page(),d=dom.window.document,b=d.querySelector<HTMLButtonElement>('[data-testid="button-show-less"]')!;
  b.textContent='Show more';b.dataset.testid='button-show-more';
  b.onclick=()=>{b.textContent='Show less';b.dataset.testid='button-show-less';};
  try{const first=await runScopusAction(d,url,'prepare_evidence',plan);assert.equal(first.ready,false);assert.equal(first.nextAction,'prepare_evidence');
    const r=await runScopusAction(d,url,'prepare_evidence',plan);assert.equal(r.ready,true);assert.equal(r.evidence.queryVisible,true);assert.equal(r.evidence.countVisible,true);
  }finally{dom.window.close();}
});
test('evidence reports separate viewport requirements and rejects stale results',async()=>{
  const dom=page(),d=dom.window.document;
  try{d.querySelector('h2')!.getBoundingClientRect=()=>({x:0,y:2000,top:2000,bottom:2020,left:0,right:100,width:100,height:20,toJSON(){}});
    const r=await runScopusAction(d,url,'prepare_evidence',plan);assert.equal(r.ready,false);assert.equal(r.evidence.requiresExtraViewport,true);
    await assert.rejects(runScopusAction(d,url,'prepare_evidence',{...plan,expectedCount:1}));
  }finally{dom.window.close();}
});
test('export opening refuses observed login-gated control and stale, zero, unknown or approximate totals',async()=>{
  for(const count of ['0 documents found','No count available','About 12,773 documents found','12,773 documents found']){
    const dom=page(),d=dom.window.document;let clicks=0;d.querySelector('h2')!.textContent=count;
    d.body.insertAdjacentHTML('beforeend','<button id="export-login-modal">Export</button>');d.querySelector('#export-login-modal')!.addEventListener('click',()=>clicks++);
    try{await assert.rejects(runScopusAction(d,url,'export_open',plan));assert.equal(clicks,0);}finally{dom.window.close();}
  }
});
test('export dialog can open for a total above the limit before a bounded range is configured',async()=>{
  const dom=page(),d=dom.window.document;d.querySelector('h2')!.textContent='25,000 documents found';d.body.insertAdjacentHTML('beforeend','<button>Export</button>');let clicks=0;
  d.querySelector('body > button')!.addEventListener('click',()=>clicks++);
  try{assert.equal((await runScopusAction(d,url,'export_open',{query,expectedCount:25000})).nextAction,'export_configure');assert.equal(clicks,1);}finally{dom.window.close();}
});
test('export selection configures RIS with required metadata and all results before submission',async()=>{
  const dom=dialog(),d=dom.window.document;let clicks=0;d.querySelector('[role="dialog"] button')!.addEventListener('click',()=>clicks++);
  try{const r=await configure(d);assert.equal(r.selection.count,12773);assert.equal(r.selection.all,true);assert.equal(clicks,0);
    assert.equal(d.querySelector<HTMLInputElement>('[value="ris"]')!.checked,true);
    assert.equal([...d.querySelectorAll<HTMLInputElement>('[type="checkbox"]')].filter(x=>x.closest('[role="dialog"]')).every(x=>x.checked),true);
    const submitted=await runScopusAction(d,url,'export_submit',plan);assert.equal(submitted.submitted,true);assert.equal(clicks,1);
  }finally{dom.window.close();}
});
test('export submit cannot silently accept selected page, wrong format or missing metadata',async()=>{
  for(const change of [(d:Document)=>{d.querySelector<HTMLInputElement>('[value="selected"]')!.checked=true;},
    (d:Document)=>{d.querySelector<HTMLInputElement>('[value="csv"]')!.checked=true;},
    (d:Document)=>{d.querySelector<HTMLInputElement>('[name="abstract"]')!.checked=false;},
    (d:Document)=>{d.querySelector('h2')!.textContent='127 documents found';}]){
    const dom=dialog(),d=dom.window.document;let clicks=0;d.querySelector('[role="dialog"] button')!.addEventListener('click',()=>clicks++);
    try{await configure(d);change(d);await assert.rejects(runScopusAction(d,url,'export_submit',plan));assert.equal(clicks,0);}
    finally{dom.window.close();}
  }
});
test('export refuses unsupported all-results limits and validates explicit bounded ranges',async()=>{
  const dom=dialog(),d=dom.window.document;d.querySelector('h2')!.textContent='25,000 documents found';
  try{await assert.rejects(runScopusAction(d,url,'export_configure',{query,expectedCount:25000}));
    const p={query,expectedCount:25000,rangeStart:20001,rangeEnd:25000};
    const r=await configure(d,p);assert.deepEqual(r.selection,{start:20001,end:25000,count:5000,all:false});
    await runScopusAction(d,url,'export_submit',p);
    for(const range of [{rangeStart:0,rangeEnd:10},{rangeStart:1,rangeEnd:20001},{rangeStart:5,rangeEnd:4},{rangeStart:1,rangeEnd:25001}])
      await assert.rejects(runScopusAction(d,url,'export_submit',{query,expectedCount:25000,...range}));
  }finally{dom.window.close();}
});
test('ambiguous export controls and partial-only selection fail without exporting',async()=>{
  for(const change of [(d:Document)=>d.querySelector('[value="all"]')!.closest('label')!.remove(),
    (d:Document)=>d.querySelector('[role="dialog"]')!.insertAdjacentHTML('beforeend','<label><input type="radio">RIS</label>')]){
    const dom=dialog(),d=dom.window.document;let clicks=0;d.querySelector('[role="dialog"] button')!.addEventListener('click',()=>clicks++);change(d);
    try{await assert.rejects(configure(d));assert.equal(clicks,0);}finally{dom.window.close();}
  }
});
test('an all-documents label with a smaller count cannot certify a full export',async()=>{
  const dom=dialog(),d=dom.window.document;
  d.querySelector('[value="all"]')!.closest('label')!.append(' (10)');
  try{await assert.rejects(configure(d),/seçim|sayısı/i);}finally{dom.window.close();}
});
test('a checked all-documents radio cannot overrule an explicit partial selection summary',async()=>{
  const dom=dialog(),d=dom.window.document;await configure(d);
  d.querySelector('[role="dialog"]')!.insertAdjacentHTML('beforeend','<p>10 documents selected</p>');
  try{await assert.rejects(runScopusAction(d,url,'export_submit',plan),/seçim|sayısı/i);}finally{dom.window.close();}
});
test('export inspection can read pending status while its progress indicator is visible',async()=>{
  const dom=page('<div role="status">Your export is being prepared</div><div role="progressbar"></div>');
  try{const r=await runScopusAction(dom.window.document,url,'export_inspect',{});assert.equal(r.status,'pending');assert.equal(r.completed,false);}
  finally{dom.window.close();}
});
test('standalone sign-in heading is detected even when another heading follows',async()=>{
  const dom=page('<h1>Sign in</h1><h2>Welcome to Scopus</h2>');
  try{assert.equal((await runScopusAction(dom.window.document,url,'inspect',{})).stage,'login');}
  finally{dom.window.close();}
});
test('export status is evidence only and never reports a completed disk download',async()=>{
  const dom=page('<div role="status">Your export is being prepared</div>');
  try{const r=await runScopusAction(dom.window.document,url,'export_inspect',{});assert.equal(r.status,'pending');assert.equal(r.completed,false);
    dom.window.document.querySelector('[role="status"]')!.textContent='Your export is ready to download';
    const ready=await runScopusAction(dom.window.document,url,'export_inspect',{});assert.equal(ready.status,'ready');assert.equal(ready.completed,false);
  }finally{dom.window.close();}
});

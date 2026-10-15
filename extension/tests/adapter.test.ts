import test from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import { parseCount, extract, platform } from '../src/adapters';
import { build } from 'esbuild';
import { readFileSync } from 'node:fs';
import { applyYears } from '../src/refinement-dom';

test('zero, locale grouping and approximate counts remain distinct',()=>{
  assert.equal(parseCount('0 results','en').value,0);
  assert.equal(parseCount('1–25 of 2,798 results','en').value,2798);
  assert.equal(parseCount('2.798 sonuç','tr').value,2798);
  assert.equal(parseCount('10,000+ results','en').qualifier,'at_least');
  assert.equal(parseCount('About 12,000 results','en').qualifier,'approximate');
  assert.equal(parseCount('1.234 results','').value,null);
  assert.equal(parseCount('page 2 of 10','en').value,null);
});

test('visibility-only SPA panel switch invalidates an armed capture',async()=>{
  const script=await build({entryPoints:['extension/src/content.ts'],bundle:true,write:false,format:'iife'});
  const dom=new JSDOM('<html lang="en"><body><section id="old"><h1>10 results</h1><p>Search results for: OLD</p></section><section id="next" hidden><h1>20 results</h1><p>Search results for: NEW</p></section><p>Search field: All fields</p><div aria-label="Filters">No filters</div></body></html>',{url:'https://www.scopus.com/results',runScripts:'outside-only'});
  try{
    let listener:any;
    (dom.window as any).chrome={runtime:{onMessage:{addListener:(fn:any)=>{listener=fn;}}}};
    dom.window.HTMLElement.prototype.getClientRects=function(){return [{width:100,height:20}] as any;};
    dom.window.eval(script.outputFiles[0].text);
    const request=(message:any)=>{let result:any;listener(message,{},(r:any)=>{result=r;});return result;};
    request({kind:'arm',jobId:'visibility-test'});
    dom.window.document.getElementById('old')!.hidden=true;
    dom.window.document.getElementById('next')!.hidden=false;
    const result=request({kind:'extract',jobId:'visibility-test'});
    assert.equal(result.data.query_raw,'NEW');
    assert.equal(result.stable,false);
    request({kind:'release'});
  }finally{dom.window.close();}
});
function page(body:string){
  const dom=new JSDOM('<html lang="en"><body>'+body+'<section aria-label="Filters">No filters applied</section><p>Search field: All fields</p></body></html>',{url:'https://www.scopus.com/results'});
  dom.window.HTMLElement.prototype.getClientRects=function(){return [{width:100,height:20}] as any;};
  return dom.window.document;
}
test('synthetic semantic results extract the executed query',()=>{
  const result=extract(page('<h1>0 results</h1><p>Search results for: RAG AND Turkish</p><input type="search" value="RAG AND Turkish">'),'https://www.scopus.com/results');
  assert.equal(result.count_value,0);assert.equal(result.query_raw,'RAG AND Turkish');assert.equal(result.status,'complete');
  assert.equal(result.adapter_support,'unverified');
});
test('unsubmitted input cannot replace executed query',()=>{
  const result=extract(page('<h1>123 results</h1><p>Search results for: RAG</p><input type="search" value="NEW QUERY">'),'https://www.scopus.com/results');
  assert.equal(result.query_raw,'RAG');assert.equal(result.status,'incomplete');
});
test('loading, login and conflicting totals do not become valid results',()=>{
  for (const body of ['<h1>Sign in</h1>','<h1>0 results</h1><div aria-busy="true">Loading</div>',
    '<h1>10 results</h1><h2>20 results</h2><p>Search results for: RAG</p>']){
    assert.equal(extract(page(body),'https://www.scopus.com/results').status,'incomplete');
  }
});
test('article page has no fabricated query or count',()=>{
  const result=extract(page('<h1>A RAG article</h1><p>DOI: 10.1/example</p>'),'https://ieeexplore.ieee.org/document/123');
  assert.equal(result.count_value,null);assert.equal(result.query_verified,false);
});
test('a hostname suffix spoof is not recognized as Scopus',()=>{
  assert.equal(platform('https://scopus.com.evil.test/results',''),'Genel');
});

const publicationsUrl='https://proxy.example.test/pages/search/publications?searchId=example';
function publications(){
  const dom=new JSDOM(readFileSync('extension/tests/fixtures/scopus-publications.html','utf8'),{url:publicationsUrl});
  dom.window.HTMLElement.prototype.getClientRects=function(){return [{width:100,height:20}] as any;};
  return dom.window.document;
}
test('Scopus publications reads the executed query and total, not facet counts or pagination',()=>{
  const r=extract(publications(),publicationsUrl);
  assert.equal(r.status,'complete');
  assert.equal(r.count_value,12773);
  assert.equal(r.count_raw,'12,773 documents found');
  assert.equal(r.fields,'TITLE-ABS-KEY');
  assert.equal(r.query_raw,'TITLE-ABS-KEY ( "retrieval augmented generation" OR "retrieval-augmented generation" ) AND ( DOCTYPE ( ar ) OR DOCTYPE ( cp ) OR DOCTYPE ( re ) )');
  assert.deepEqual(r.filters,['( DOCTYPE ( ar ) OR DOCTYPE ( cp ) OR DOCTYPE ( re ) )']);
  assert.equal(r.source,'scopus_publications_dom');
});
test('Scopus publications preserves zero and an explicit query without additional restrictions',()=>{
  const d=publications();d.querySelector('#advancedQueryTextArea')!.textContent='TITLE-ABS-KEY ( "nothing" )';
  d.querySelector('[data-testid="label-search-results-header"]')!.textContent='0 documents found';
  const r=extract(d,publicationsUrl);
  assert.equal(r.status,'complete');assert.equal(r.count_value,0);assert.deepEqual(r.filters,[]);
});
test('Scopus editable query, pending facet changes and missing facet panel stay incomplete',()=>{
  for(const change of [(d:Document)=>d.querySelector('#advancedQueryTextArea')!.setAttribute('contenteditable','true'),
    (d:Document)=>(d.querySelector('input[type="checkbox"]') as HTMLInputElement).checked=true,
    (d:Document)=>d.querySelector('[data-testid="facet-s"]')!.remove()]){
    const d=publications();change(d);assert.equal(extract(d,publicationsUrl).status,'incomplete');
  }
});
test('Scopus result selectors cannot validate a different page or conflicting total',()=>{
  assert.equal(extract(publications(),'https://proxy.example.test/pages/home').status,'incomplete');
  const d=publications();const other=d.querySelector('h2')!.cloneNode(true) as Element;
  other.textContent='999 documents found';d.body.append(other);
  assert.equal(extract(d,publicationsUrl).status,'incomplete');
});

function yearInputs(d:Document){
  const group=d.createElement('div');group.dataset.testid='facet-group-year';
  group.innerHTML='<input type="number" data-testid="input-range-from"><input type="number" data-testid="input-range-to">';
  d.querySelector('[data-testid="facet-s"]')!.append(group);
  return group;
}
function refinementPlan(d:Document){
  const data=extract(d,publicationsUrl);
  return {id:'example',source_query:data.query_raw,source_count:12773,query:data.query_raw+' AND PUBYEAR > 2021 AND PUBYEAR < 2027',year_from:2022,year_to:2026};
}
test('workflow topic types followed by common year validate actual facet inputs',()=>{
  const d=publications(),g=yearInputs(d);
  d.querySelector('#advancedQueryTextArea')!.textContent='TITLE-ABS-KEY(test) AND (DOCTYPE(ar) OR DOCTYPE(cp)) AND PUBYEAR > 2021 AND PUBYEAR < 2027';
  (g.querySelector('[data-testid="input-range-from"]') as HTMLInputElement).value='2022';
  (g.querySelector('[data-testid="input-range-to"]') as HTMLInputElement).value='2026';
  assert.equal(extract(d,publicationsUrl).status,'complete');
  (g.querySelector('[data-testid="input-range-from"]') as HTMLInputElement).value='2024';
  assert.equal(extract(d,publicationsUrl).status,'incomplete');
});
test('approved year action submits once and read-back distinguishes applied and edited years',async()=>{
  const d=publications(),group=yearInputs(d),p=refinementPlan(d);let clicks=0;
  const b=d.createElement('button');b.textContent='Apply selected year range';
  group.querySelector('[data-testid="input-range-to"]')!.addEventListener('focusout',()=>group.append(b),{once:true});
  b.onclick=()=>{clicks++;d.querySelector('#advancedQueryTextArea')!.textContent=p.query;};
  assert.equal((await applyYears(d,publicationsUrl,p)).submitted,true);
  assert.equal(clicks,1);
  assert.equal((group.querySelector('[data-testid="input-range-from"]') as HTMLInputElement).value,'2022');
  assert.equal(extract(d,publicationsUrl).status,'complete');
  (group.querySelector('[data-testid="input-range-from"]') as HTMLInputElement).value='2024';
  assert.equal(extract(d,publicationsUrl).status,'incomplete');
});
test('stale query or count cannot change any year field',async()=>{
  for(const change of [(d:Document)=>{d.querySelector('#advancedQueryTextArea')!.textContent='TITLE("changed")';},
    (d:Document)=>{d.querySelector('[data-testid="label-search-results-header"]')!.textContent='999 documents found';}]){
    const d=publications(),group=yearInputs(d),p=refinementPlan(d);change(d);
    await assert.rejects(applyYears(d,publicationsUrl,p),/değişmiş/);
    assert.equal((group.querySelector('input') as HTMLInputElement).value,'');
  }
});
test('missing apply control restores original fields and offers manual execution',async()=>{
  const d=publications(),group=yearInputs(d),p=refinementPlan(d);
  await assert.rejects(applyYears(d,publicationsUrl,p),/düğmesi bulunamadı/);
  assert.deepEqual(Array.from(group.querySelectorAll('input')).map(x=>x.value),['','']);
});

test('a filter change or loading during year editing prevents submission',async()=>{
  for(const change of [(d:Document)=>(d.querySelector('input[type="checkbox"]') as HTMLInputElement).checked=true,
    (d:Document)=>d.querySelector('[data-testid="facet-s"]')!.setAttribute('aria-busy','true')]){
    const d=publications(),group=yearInputs(d),p=refinementPlan(d);let clicks=0;
    const b=d.createElement('button');b.textContent='Apply selected year range';group.append(b);
    b.onclick=()=>{clicks++;};
    group.querySelector('input')!.addEventListener('input',()=>change(d),{once:true});
    await assert.rejects(applyYears(d,publicationsUrl,p),/değişti/);
    assert.equal(clicks,0);
  }
});

test('confirmation page waits for a click and retains manual fallback after application fails',async()=>{
  const script=await build({entryPoints:['extension/src/refine.ts'],bundle:true,write:false,format:'iife'});
  const dom=new JSDOM(readFileSync('extension/public/refine.html','utf8'),{url:'https://extension.test/refine.html?id=example',runScripts:'outside-only'});
  const calls:string[]=[];let state='offered',copied='';
  (dom.window as any).chrome={runtime:{sendMessage:async(m:any)=>{
    calls.push(m.type||m.kind);
    if(m.kind==='refinement_apply'){state='approved';return {ok:false,error:'Yıl düğmesi bulunamadı; sorguyu elle uygulayın.'};}
    return {ok:true,data:{query:'TITLE("test") AND PUBYEAR > 2021 AND PUBYEAR < 2027',display_id:'S001',reason:'12.000 sonuç',state}};
  }}};
  Object.defineProperty(dom.window.navigator,'clipboard',{value:{writeText:async(t:string)=>{copied=t;}}});
  try{
    dom.window.eval(script.outputFiles[0].text);
    await new Promise(r=>setImmediate(r));
    assert.deepEqual(calls,['get_refinement']);
    const d=dom.window.document;
    (d.getElementById('apply') as HTMLButtonElement).click();await new Promise(r=>setImmediate(r));
    assert.match(d.getElementById('message')!.textContent!,/elle uygulayın/);
    (d.getElementById('copy') as HTMLButtonElement).click();await new Promise(r=>setImmediate(r));
    assert.match(copied,/PUBYEAR > 2021/);
    assert.equal(calls.filter(x=>x==='refinement_apply').length,1);
    assert.match(d.getElementById('message')!.textContent!,/Ctrl\+M/);
  }finally{dom.window.close();}
});

test('Scopus controlled React year range receives both requested values',async()=>{
  const script=await build({entryPoints:['extension/tests/fixtures/scopus-year-controls.tsx'],bundle:true,write:false,format:'iife'});
  const dom=new JSDOM(readFileSync('extension/tests/fixtures/scopus-publications.html','utf8'),{url:publicationsUrl,runScripts:'outside-only'});
  dom.window.HTMLElement.prototype.getClientRects=function(){return [{width:100,height:20}] as any;};
  try{
    dom.window.eval(script.outputFiles[0].text);
    await new Promise(r=>setTimeout(r,50));
    const d=dom.window.document,p=refinementPlan(d);
    await applyYears(d,publicationsUrl,p);
    assert.equal((dom.window as any).appliedRange.from,'2022');
    assert.equal((dom.window as any).appliedRange.to,'2026');
    d.querySelector('#advancedQueryTextArea')!.textContent=p.query;
    await applyYears(d,publicationsUrl,{...p,source_query:p.query,year_from:2024});
    assert.equal((dom.window as any).appliedRange.from,'2024');
    assert.equal((dom.window as any).appliedRange.to,'2026');
  }finally{dom.window.close();}
});

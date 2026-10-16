import test from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import { readFileSync } from 'node:fs';
import { extract, ieeeResults, platform } from '../src/adapters';
import { applyIeeeFilters, ieeeTargetUrl } from '../src/refinement-dom';

// Fixtures are trimmed copies of live IEEE Xplore pages saved on 16.10.2026 (Q01, 195 → 194 results).
const query='( ("Abstract":"retrieval augmented generation" OR "Abstract":"retrieval-augmented generation") AND ("Abstract":Turkish OR "Abstract":multilingual OR "Abstract":"cross-lingual" OR "Abstract":"low-resource"))';
const queryText='(   ("Abstract":"retrieval augmented generation" OR "Abstract":"retrieval-augmented generation") AND ("Abstract":Turkish OR "Abstract":multilingual OR "Abstract":"cross-lingual" OR "Abstract":"low-resource"))';
const base='https://c85689232ea394a8dc08a512c1f46793a2397178.vetisonline.com/search/searchresult.jsp?action=search&matchBoolean=true&queryText='+encodeURIComponent(queryText)+'&highlight=true&returnType=SEARCH&matchPubs=true&returnFacets=ALL';
const filteredUrl=base+'&refinements=ContentType:Conferences&refinements=ContentType:Journals';

function load(name:string,url:string,years:[string,string]|null=['2024','2026']){
  const dom=new JSDOM(readFileSync('extension/tests/fixtures/'+name,'utf8'),{url});
  dom.window.HTMLElement.prototype.getClientRects=function(){return [{width:100,height:20}] as any;};
  const d=dom.window.document;
  if(years){
    (d.querySelector('input[aria-label="Enter start year of range"]') as HTMLInputElement).value=years[0];
    (d.querySelector('input[aria-label="Enter end year of range"]') as HTMLInputElement).value=years[1];
  }
  return {dom,d};
}

test('proxy-served IEEE Xplore is recognised from the page title',()=>{
  assert.equal(platform(base,'IEEE Xplore Search Results'),'IEEE Xplore');
});

test('unfiltered IEEE results: query, count, field and IEEE default year range are read',()=>{
  const {d}=load('ieee-results.html',base);
  const r=extract(d,base);
  assert.equal(r.database,'IEEE Xplore');
  assert.equal(r.query_raw,query);
  assert.equal(r.query_verified,true);
  assert.equal(r.count_value,195);assert.equal(r.count_qualifier,'exact');
  assert.equal(r.fields,'Abstract');
  assert.deepEqual(r.filters,['Yıl (sonuç aralığı): 2024–2026']);
  assert.equal(r.status,'complete',JSON.stringify(r.missing_fields)+r.warnings.join());
  assert.equal(r.source,'ieee_searchresult_dom');
});

test('filtered IEEE results list each applied content type separately',()=>{
  const {d}=load('ieee-results-filtered.html',filteredUrl);
  const r=extract(d,filteredUrl);
  assert.equal(r.count_value,194);
  assert.deepEqual(r.filters,['Tür: Conferences','Tür: Journals','Yıl (sonuç aralığı): 2024–2026']);
  assert.equal(r.status,'complete');
});

test('an applied year range is taken from the address, not from the input boxes',()=>{
  const url=filteredUrl+'&ranges=2024_2026_Year';
  const {d}=load('ieee-results-filtered.html',url,['2024','2026']);
  assert.deepEqual(extract(d,url).filters,['Tür: Conferences','Tür: Journals','Yıl: 2024–2026']);
});

test('the year crumb that IEEE adds for an applied range is not listed twice',()=>{
  const url=filteredUrl+'&ranges=2024_2026_Year';
  const {d}=load('ieee-results-filtered.html',url);
  const crumb=d.querySelector('.Dashboard-breadcrumbs-container [data-type="refinement"]')!.closest('.Breadcrumb')!;
  const copy=crumb.cloneNode(true) as Element;
  copy.querySelector('[data-type="refinement"]')!.id='2024_2026';
  copy.querySelector('.Breadcrumb-title')!.textContent='2024 - 2026';
  crumb.parentElement!.append(copy);
  assert.deepEqual(extract(d,url).filters,['Tür: Conferences','Tür: Journals','Yıl: 2024–2026']);
});

test('without a readable year the reader says nothing about years instead of guessing',()=>{
  const {d}=load('ieee-results.html',base,null);
  const r=ieeeResults(d,base)!;
  assert.deepEqual(r.filters,[]);
  assert.equal(r.yearsKnown,false);
  assert.equal(r.filtersKnown,true);
});

test('a dedicated IEEE reader wins over an older manual mapping of the filter label',()=>{
  const {d}=load('ieee-results-filtered.html',filteredUrl);
  const label=d.querySelector('.Dashboard-breadcrumbs-toggle')!;label.id='mapped-label';
  const r=extract(d,filteredUrl,{filters:'#mapped-label',query:'#mapped-label',count:'#mapped-label'});
  assert.deepEqual(r.filters.slice(0,2),['Tür: Conferences','Tür: Journals']);
  assert.equal(r.query_raw,query);assert.equal(r.count_value,194);
  assert.equal(r.adapter_support,'unverified');
});

test('a query that differs from the address bar is not verified',()=>{
  const other=base.replace('Turkish','Arabic');
  const {d}=load('ieee-results.html',other);
  const r=extract(d,other);
  assert.equal(r.query_verified,false);
  assert.equal(r.status,'incomplete');
  assert.match(r.warnings.join(),/eşleşmiyor/);
});

test('a ticked but not yet applied content type keeps the record incomplete',()=>{
  const {d}=load('ieee-results.html',base);
  (d.querySelector('input.facet-ctype-option-checkbox') as HTMLInputElement).checked=true;
  const r=extract(d,base);
  assert.equal(r.status,'incomplete');
  assert.match(r.warnings.join(),/uygulanmamış/);
});

test('thousands separators and mixed field names',()=>{
  const {d}=load('ieee-results.html',base);
  const strong=d.querySelectorAll('h1.Dashboard-header .strong')[1];strong.textContent='10,824';
  assert.equal(extract(d,base).count_value,10824);
  const title=d.querySelector('h1.Dashboard-header .Breadcrumb-title span')!;
  title.textContent='("Abstract":rag) AND ("Document Title":turkish)';
  const u=new URL(base);u.searchParams.set('queryText',title.textContent);
  assert.equal(ieeeResults(d,u.href)!.fields,'Abstract; Document Title');
});

const plan=(over:any={})=>({id:'p',source_query:query,source_count:195,query,year_from:2024,year_to:2026,
  context:{kind:'ieee',apply_years:true,types:['Conferences','Journals']},...over});

test('the target address replaces content types and years and keeps the query',()=>{
  const target=new URL(ieeeTargetUrl(filteredUrl+'&ranges=2010_2026_Year&pageNumber=3',plan()));
  assert.deepEqual(target.searchParams.getAll('refinements'),['ContentType:Conferences','ContentType:Journals']);
  assert.deepEqual(target.searchParams.getAll('ranges'),['2024_2026_Year']);
  assert.equal(target.searchParams.get('pageNumber'),null);
  assert.equal(target.searchParams.get('queryText'),queryText);
  assert.equal(target.host,new URL(base).host);
  const noYears=new URL(ieeeTargetUrl(base,plan({context:{kind:'ieee',apply_years:false,types:['Conferences','Journals']}})));
  assert.deepEqual(noYears.searchParams.getAll('ranges'),[]);
});

test('applying navigates once on the verified page and refuses a changed page',async()=>{
  const {d}=load('ieee-results.html',base);
  const visits:string[]=[];
  const r=await applyIeeeFilters(d,base,plan(),u=>{visits.push(u);});
  assert.equal(r.submitted,true);assert.equal(visits.length,1);
  assert.match(visits[0],/ranges=2024_2026_Year/);
  await assert.rejects(applyIeeeFilters(d,base,plan({source_count:999}),u=>{visits.push(u);}),/değişmiş/);
  await assert.rejects(applyIeeeFilters(d,base,plan({context:{kind:'ieee',apply_years:true,types:['Books']}}),u=>{visits.push(u);}),/Desteklenmeyen/);
  assert.equal(visits.length,1);
});

test('nothing to change is reported instead of reloading the same page',async()=>{
  const url=filteredUrl+'&ranges=2024_2026_Year';
  const {d}=load('ieee-results-filtered.html',url);
  await assert.rejects(applyIeeeFilters(d,url,plan({source_count:194}),()=>{throw new Error('navigated');}),/zaten/);
});

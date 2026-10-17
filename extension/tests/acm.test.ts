import test from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import { readFileSync } from 'node:fs';
import { extract, acmResults, acmYears, platform, ACM_TYPE_FILTER } from '../src/adapters';
import { acmItems, acmPageUrl, collectAcm, acmArticle, acmArticleUrl } from '../src/acm-dom';

// Fixtures are trimmed copies of live ACM DL pages saved on 16.10.2026 (Q01, 33 results; first 20 of them).
const base='https://dl.acm.org/action/doSearch?AllField=Abstract%3A%28%22retrieval+augmented+generation%22+OR+%22retrieval-augmented+generation%22%29+AND+Abstract%3A%28Turkish+OR+multilingual+OR+%22cross-lingual%22+OR+%22low-resource%22%29';
const yearsUrl=base+'&AfterYear=2024&BeforeYear=2026';
const query='[[Abstract: "retrieval augmented generation"] OR [Abstract: "retrieval-augmented generation"]] AND [[Abstract: turkish] OR [Abstract: multilingual] OR [Abstract: "cross-lingual"] OR [Abstract: "low-resource"]]';
const yearsQuery=query+' AND [E-Publication Date: (01/01/2024 TO 12/31/2026)]';

function load(name:string,url:string){
  const dom=new JSDOM(readFileSync('extension/tests/fixtures/'+name,'utf8'),{url});
  dom.window.HTMLElement.prototype.getClientRects=function(){return [{width:100,height:20}] as any;};
  return dom.window.document;
}
/** The same page with `total` results and `shown` records on it (records cloned with new DOIs). */
function page(name:string,total:number,shown:number,first=0){
  const dom=new JSDOM(readFileSync('extension/tests/fixtures/'+name,'utf8'));
  const d=dom.window.document;
  d.querySelector('.hitsLength')!.textContent=total+' ';
  d.querySelector('.result__count')!.textContent=total.toLocaleString('en-US')+' Results';
  const list=d.querySelector('ul.search-result__xsl-body')!;
  const template=list.querySelector('li.search__item')!;
  list.replaceChildren();
  for(let i=0;i<shown;i++){
    const li=template.cloneNode(true) as Element;
    li.querySelector('.issue-item__title a')!.setAttribute('href','https://dl.acm.org/doi/10.1145/9999.'+(first+i));
    list.append(li);
  }
  return d.documentElement.outerHTML;
}
const parse=(html:string)=>new JSDOM(html).window.document;

test('ACM DL is recognised from its address',()=>{
  assert.equal(platform(base,'Search'),'ACM Digital Library');
});

test('ACM results without a date filter: query, count, field and the type rule',()=>{
  const d=load('acm-results.html',base);
  const r=extract(d,base);
  assert.equal(r.database,'ACM Digital Library');
  assert.equal(r.query_raw,query);
  assert.equal(r.query_verified,true);
  assert.equal(r.count_value,33);assert.equal(r.count_qualifier,'exact');
  assert.equal(r.fields,'Abstract');
  assert.deepEqual(r.filters,[ACM_TYPE_FILTER]);
  assert.equal(ACM_TYPE_FILTER,'Tür: research-article, short-paper');
  assert.equal(r.status,'complete',JSON.stringify(r.missing_fields)+r.warnings.join());
  assert.equal(r.source,'acm_dosearch_dom');
});

test('the date filter is read from ACM\'s own query line and written as Yıl: 2024–2026',()=>{
  const d=load('acm-results-years.html',yearsUrl);
  const r=extract(d,yearsUrl);
  assert.equal(r.query_raw,yearsQuery);
  assert.deepEqual(r.filters,['Yıl: 2024–2026',ACM_TYPE_FILTER]);
  assert.equal(r.fields,'Abstract');
  assert.equal(r.status,'complete');
});

test('a partial-year date range is written as it is',()=>{
  assert.equal(acmYears('[E-Publication Date: (01/01/2025 TO 12/31/2026)]'),'Yıl: 2025–2026');
  assert.equal(acmYears('[E-Publication Date: (03/01/2024 TO 12/31/2026)]'),'Yıl: 03/01/2024–12/31/2026');
  assert.equal(acmYears(query),null);
});

test('the typed text in ACM\'s search box does not make the capture incomplete',()=>{
  const d=load('acm-results-years.html',yearsUrl);
  const input=d.createElement('input');input.type='search';input.value='Abstract:("retrieval augmented generation")';
  d.body.prepend(input);
  assert.equal(extract(d,yearsUrl).status,'complete');
});

test('a page whose title shows another query is not verified',()=>{
  const d=load('acm-results.html',base);
  d.title='[[Abstract: \'something else\']] : Search';
  assert.equal(extract(d,base).query_verified,false);
});

test('result list records: DOI, type, date, title, authors, venue, pages',()=>{
  const items=acmItems(load('acm-results.html',base),1);
  assert.equal(items.length,20);
  assert.deepEqual(items[0],{doi:'10.1145/3805712.3809921',type:'short-paper',published:'19 July 2026',
    title:'CroSearch-R1: Better Leveraging Cross-lingual Knowledge for Retrieval-Augmented Generation',
    authors:['Rui Qi','Fengran Mo','Sijin Lu','Yufeng Chen','Jian-Yun Nie','Kaiyu Huang'],
    venue:"SIGIR '26: Proceedings of the 49th International ACM SIGIR Conference on Research and Development in Information Retrieval",
    pages:'4045–4051',page:1,position:1});
  assert.deepEqual([...new Set(items.map(i=>i.type))].sort(),['abstract','demonstration','extended-abstract','poster','research-article','short-paper']);
  assert.ok(items.every(i=>/^10\.\d{4,9}\//.test(i.doi)&&i.title&&i.published));
});

test('page addresses keep the search and its date filter; only page size and number change',()=>{
  const u=new URL(acmPageUrl(yearsUrl+'&pageSize=20&startPage=0#x',1));
  assert.equal(u.searchParams.get('pageSize'),'50');assert.equal(u.searchParams.get('startPage'),'1');
  assert.equal(u.searchParams.get('AfterYear'),'2024');assert.equal(u.searchParams.get('BeforeYear'),'2026');
  assert.equal(u.searchParams.get('AllField'),new URL(base).searchParams.get('AllField'));
  assert.equal(u.hash,'');
});

const article=readFileSync('extension/tests/fixtures/acm-article.html','utf8');

test('abstract and full-text availability are read from an ACM article page',()=>{
  const a=acmArticle(parse(article));
  assert.ok(a!.abstract.startsWith('A multilingual collection may contain useful knowledge in other languages'));
  assert.ok(!a!.abstract.startsWith('Abstract'));
  assert.equal(a!.access,'Açık (ACM PDF)');
  const paid=parse(article.replace(/<a [^>]*btn--eReader[\s\S]*?<\/a>/,'<a class="btn">Get this Publication</a>'));
  assert.equal(acmArticle(paid)!.access,'Ücretli (ACM: Get this Publication)');
  assert.equal(acmArticle(parse('<html><title>Just a moment</title><body>Verify you are human</body></html>')),null);
  assert.equal(acmArticleUrl(yearsUrl,'10.1145/3805712.3809921'),'https://dl.acm.org/doi/10.1145/3805712.3809921');
});

test('collection reads every page of 50, one after another, and checks each page',async()=>{
  const live=parse(page('acm-results-years.html',70,20));
  (live.defaultView as any).HTMLElement.prototype.getClientRects=function(){return [{width:100,height:20}] as any;};
  const asked:string[]=[];let waits=0;const notes:string[]=[];
  const fetcher=async(url:string)=>{asked.push(url);
    if(new URL(url).pathname.startsWith('/doi/'))return {ok:true,status:200,url,text:async()=>article};
    const n=new URL(url).searchParams.get('startPage')==='0'?50:20;
    return {ok:true,status:200,url,text:async()=>page('acm-results-years.html',70,n,asked.length*100)};};
  const r=await collectAcm(live,yearsUrl,{id:'x',query:yearsQuery,count:70,display_id:'S032'},{fetcher,parse,wait:async()=>{waits++;},progress:t=>notes.push(t)});
  const listPages=asked.filter(u=>new URL(u).pathname==='/action/doSearch');
  assert.equal(r.items.length,70);assert.equal(r.pages,2);
  assert.deepEqual(listPages.map(u=>new URL(u).searchParams.get('startPage')),['0','1']);
  // every cloned record is a short-paper (first fixture record): each one's article page is read once
  assert.equal(asked.length-listPages.length,70);assert.equal(waits,1+70);
  assert.ok(r.items.every(i=>i.abstract?.startsWith('A multilingual')&&i.access==='Açık (ACM PDF)'));
  assert.deepEqual([notes[0],notes.at(-1)],['ACM sonuç sayfası 1/2 okundu.','Özetler okunuyor: 70/70']);
  asked.length=0;
  assert.ok(listPages.every(u=>new URL(u).searchParams.get('pageSize')==='50'&&new URL(u).searchParams.get('AfterYear')==='2024'));
  assert.deepEqual([r.items[0].page,r.items[69].page,r.items[69].position],[1,2,20]);
});

test('only kept types get an article page; repeated failures stop abstract reading but keep the list',async()=>{
  const live=parse(page('acm-results-years.html',33,20));
  (live.defaultView as any).HTMLElement.prototype.getClientRects=function(){return [{width:100,height:20}] as any;};
  const real=parse(readFileSync('extension/tests/fixtures/acm-results-years.html','utf8'));
  const list=real.documentElement.outerHTML.replace(/>33 </g,'>20 <').replace('33 Results','20 Results');
  const plan={id:'x',query:yearsQuery,count:20,display_id:'S032'};
  const live20=parse(list);(live20.defaultView as any).HTMLElement.prototype.getClientRects=function(){return [{width:100,height:20}] as any;};
  const asked:string[]=[];
  const r=await collectAcm(live20,yearsUrl,plan,{parse,wait:async()=>{},fetcher:async(url:string)=>{asked.push(url);
    if(new URL(url).pathname.startsWith('/doi/'))return {ok:false,status:403,url,text:async()=>''};
    return {ok:true,status:200,url,text:async()=>list};}});
  const wanted=r.items.filter(i=>['research-article','short-paper'].includes(i.type));
  assert.equal(r.items.length,20);
  assert.equal(asked.filter(u=>u.includes('/doi/')).length,3);
  assert.ok(wanted.slice(0,3).every(i=>i.abstract_status==='alınamadı (HTTP 403)'));
  assert.ok(wanted.slice(3).every(i=>i.abstract_status?.startsWith('atlandı')));
  assert.ok(r.items.filter(i=>!['research-article','short-paper'].includes(i.type)).every(i=>i.abstract_status===undefined));
  void live;
});

test('collection stops when the tab no longer shows the recorded search',async()=>{
  const live=load('acm-results.html',base);
  await assert.rejects(collectAcm(live,base,{id:'x',query:yearsQuery,count:33,display_id:'S032'},{fetcher:async()=>{throw new Error('no');},parse}),/S032 aramasını göstermiyor/);
});

test('collection stops on a verification page or a changed total',async()=>{
  const live=parse(page('acm-results-years.html',33,20));
  (live.defaultView as any).HTMLElement.prototype.getClientRects=function(){return [{width:100,height:20}] as any;};
  const plan={id:'x',query:yearsQuery,count:33,display_id:'S032'};
  await assert.rejects(collectAcm(live,yearsUrl,plan,{parse,fetcher:async(url:string)=>({ok:true,status:200,url,text:async()=>'<html><title>Just a moment</title></html>'})}),/robot kontrolü/);
  await assert.rejects(collectAcm(live,yearsUrl,plan,{parse,fetcher:async(url:string)=>({ok:true,status:200,url,text:async()=>page('acm-results-years.html',34,34)})}),/değişti/);
  await assert.rejects(collectAcm(live,yearsUrl,plan,{parse,fetcher:async(url:string)=>({ok:false,status:403,url,text:async()=>''})}),/HTTP 403/);
  await assert.rejects(collectAcm(live,yearsUrl,plan,{parse,fetcher:async(url:string)=>({ok:true,status:200,url,text:async()=>page('acm-results-years.html',33,30)})}),/30 kayıt gösterdi, 33/);
});

test('ACM pages fetched in the background are read without layout',()=>{
  const d=parse(page('acm-results-years.html',33,20));
  const r=acmResults(d,yearsUrl,false);
  assert.equal(r?.count.value,33);assert.equal(r?.query,yearsQuery);
});

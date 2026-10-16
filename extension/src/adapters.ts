export type Mapping = Partial<Record<'query'|'count'|'filters'|'fields',string>>;
export type Extraction = {
  database:string; query_raw:string; query_verified:boolean; fields:string; filters:string[];
  count_raw:string; count_value:number|null; count_qualifier:string; safe_url:string;
  status:'complete'|'incomplete'; missing_fields:string[]; warnings:string[];
  adapter_version:string; adapter_support:'unverified'|'user_mapped'; source:string; observed_at_utc:string;
};

export function platform(url:string,title:string):string {
  let host='';try{host=new URL(url).hostname.toLowerCase();}catch{return 'Genel';}
  const matches=(domain:string)=>host===domain||host.endsWith('.'+domain);
  if(matches('scopus.com'))return 'Scopus';
  if(matches('ieeexplore.ieee.org'))return 'IEEE Xplore';
  if(matches('dl.acm.org'))return 'ACM Digital Library';
  if(matches('webofscience.com'))return 'Web of Science';
  // Proxy recognition is a candidate only; field extraction still has to succeed.
  if(/\bscopus\b/i.test(title))return 'Scopus';
  if(/IEEE Xplore/i.test(title))return 'IEEE Xplore';
  if(/ACM Digital Library/i.test(title))return 'ACM Digital Library';
  if(/Web of Science/i.test(title))return 'Web of Science';
  return 'Genel';
}

export function parseCount(raw:string,locale:string) {
  const text=raw.trim();const unknown={raw:text,value:null as number|null,qualifier:'unknown'};
  if(/^(no results|no documents|sonuç bulunamadı|0 sonuç)$/i.test(text))return {raw:text,value:0,qualifier:'exact'};
  const number='(?<![\\d.,])((?:\\d{1,3}(?:[.,\\u00a0\\u202f ]\\d{3})+)|\\d+)(\\+)?';
  const word='(?:results?|documents?|records?|sonuç|kayıt)';
  const match=text.match(new RegExp(number+'\\s*'+word,'i')) || text.match(new RegExp(word+'\\s*[:(]?\\s*'+number,'i'))
    || text.match(new RegExp('^'+number+'$'));
  if(!match)return unknown;
  const digits=match[1];
  const language=locale.toLowerCase().split(/[-_]/)[0];
  if(/[.,]/.test(digits)){
    const separator=language==='tr'||language==='de'?'.':language==='en'?',':null;
    if(!separator||digits.includes(separator==='.'?',':'.'))return unknown;
    if(!new RegExp('^\\d{1,3}(?:\\'+separator+'\\d{3})+$').test(digits))return unknown;
  }
  const value=Number(digits.replace(/[.,\s\u00a0\u202f]/g,''));
  if(!Number.isSafeInteger(value)||value<0)return unknown;
  return {raw:text,value,qualifier:match[2]?'at_least':/about|approx|yaklaşık|[~≈]/i.test(text)?'approximate':'exact'};
}

export function visible(el:Element):boolean {
  if(el.closest('[hidden],[aria-hidden="true"],script,style,template,noscript'))return false;
  const style=el.ownerDocument.defaultView?.getComputedStyle(el);
  return style?.display!=='none'&&style?.visibility!=='hidden'&&el.getClientRects().length>0;
}

const text=(el:Element|null)=>el?.textContent?.replace(/\s+/g,' ').trim()||'';

function mapped(doc:Document,selector:string|undefined):Element|null {
  if(!selector||selector.length>2048)return null;
  try{const found=doc.querySelectorAll(selector);return found.length===1&&visible(found[0])?found[0]:null;}catch{return null;}
}

function scopusQueryParts(query:string):{fields:string;filters:string[]}|null {
  const start=query.match(/^(TITLE-ABS-KEY|TITLE|ABS|KEY|ALL)\s*\(/i);
  if(!start)return null;
  let depth=1,quote=false,braces=0;
  for(let i=start[0].length;i<query.length;i++){
    const c=query[i];
    if(c==='"'&&query[i-1]!=='\\')quote=!quote;
    if(quote)continue;
    if(c==='{')braces++;if(c==='}')braces--;
    if(braces)continue;
    if(c==='(')depth++;
    if(c===')'&&--depth===0){
      const rest=query.slice(i+1).trim();
      if(rest&&!/^AND\s+\S/i.test(rest))return null;
      // Keep the entire remaining Boolean expression, including OR groups and exclusions.
      return {fields:start[1].toUpperCase(),filters:rest?[rest.replace(/^AND\s+/i,'')]:[]};
    }
  }
  return null;
}

function scopusPublications(doc:Document,url:string){
  if(!/^\/pages\/search\/publications\/?$/.test(new URL(url).pathname))return null;
  const queryNode=mapped(doc,'#pendo-advanced-search-bar #advancedQueryTextArea');
  const header=mapped(doc,'[data-testid="label-search-results-header"]');
  const facets=mapped(doc,'[data-testid="facet-s"]');
  if(!queryNode||!header)return null;
  const query=text(queryNode),parts=scopusQueryParts(query);
  const editable=queryNode.closest('input,textarea,[contenteditable="true"],[contenteditable=""]');
  const years=query.match(/\bAND\s+PUBYEAR\s*>\s*(\d{4})\s+AND\s+PUBYEAR\s*<\s*(\d{4})\s*$/i);
  const pending=!!facets&&Array.from(facets.querySelectorAll('input[type="checkbox"]:checked,[role="checkbox"][aria-checked="true"],input[type="number"]'))
    .some(e=>{
      if(!visible(e))return false;
      if(e.getAttribute('type')!=='number')return true;
      const value=(e as HTMLInputElement).value.trim();if(!value)return false;
      const id=e.getAttribute('data-testid');
      return !years||!e.closest('[data-testid="facet-group-year"]')||
        (id==='input-range-from'?Number(value)!==Number(years[1])+1:id==='input-range-to'?Number(value)!==Number(years[2])-1:true);
    });
  return {query,verified:!!query&&!editable,count:parseCount(text(header),doc.documentElement.lang),
    fields:parts?.fields||'',filters:parts?.filters||[],filtersKnown:!!facets&&!!parts&&!pending,
    pending};
}

/** IEEE content types that count under CEN401 K2 (peer-reviewed journal articles and conference papers). */
export const IEEE_WANTED_TYPES=['Conferences','Journals'];
export const IEEE_YEAR_PARAM=/^(\d{4})_(\d{4})_Year$/;
const ieeeQueryKey=(q:string)=>q.replace(/\s+/g,'');

/** IEEE Xplore search results (/search/searchresult.jsp), structure taken from live pages saved on 16.10.2026.
 *  Filters are written as `Tür: Conferences`, `Yıl: 2024–2026` (applied) or `Yıl (sonuç aralığı): 2024–2026`
 *  (IEEE's own default range, nothing applied); the host parses these exact prefixes. */
export function ieeeResults(doc:Document,url:string){
  let u:URL;try{u=new URL(url);}catch{return null;}
  if(!/\/search\/searchresult\.jsp$/.test(u.pathname))return null;
  const header=mapped(doc,'h1.Dashboard-header');
  if(!header)return null;
  const showing=Array.from(header.querySelectorAll(':scope > span')).find(e=>/^Showing\b/i.test(text(e)));
  const crumbs=Array.from(header.querySelectorAll('.Breadcrumb')).filter(c=>c.querySelector('[data-type="search"]'));
  const query=crumbs.length===1?text(crumbs[0].querySelector('.Breadcrumb-title')):'';
  const fromUrl=u.searchParams.get('queryText');
  const verified=!!query&&(fromUrl===null||ieeeQueryKey(fromUrl)===ieeeQueryKey(query));
  const names=[...query.matchAll(/"([^"]+)"\s*:/g)].map(m=>m[1]);
  const fields=!query?'':names.length?[...new Set(names)].join('; '):'All Metadata';
  const filters:string[]=[];
  const container=doc.querySelector('.Dashboard-breadcrumbs-container');
  for(const close of Array.from(container?.querySelectorAll('[data-type="refinement"],[data-type="range"]')||[])){
    const id=close.id||'';const title=text(close.closest('.Breadcrumb')?.querySelector('.Breadcrumb-title')||null);
    if(id.startsWith('ContentType:'))filters.push('Tür: '+id.slice('ContentType:'.length));
    // The applied year range also appears as a "2024 - 2026" crumb; it is reported once, as 'Yıl: …'.
    else if(!/Year/i.test(id)&&!/^\d{4}\s*[-–]\s*\d{4}$/.test(title))filters.push('Filtre: '+(title||id));
  }
  const ranges=u.searchParams.getAll('ranges').map(r=>r.match(IEEE_YEAR_PARAM)).filter(Boolean) as RegExpMatchArray[];
  const start=doc.querySelector<HTMLInputElement>('input[aria-label="Enter start year of range"]');
  const end=doc.querySelector<HTMLInputElement>('input[aria-label="Enter end year of range"]');
  const natural=[start?.value.trim()||'',end?.value.trim()||''];
  if(ranges.length===1)filters.push(`Yıl: ${ranges[0][1]}–${ranges[0][2]}`);
  else if(/^\d{4}$/.test(natural[0])&&/^\d{4}$/.test(natural[1]))filters.push(`Yıl (sonuç aralığı): ${natural[0]}–${natural[1]}`);
  const pending=Array.from(doc.querySelectorAll<HTMLInputElement>('input.facet-ctype-option-checkbox')).some(e=>e.checked);
  return {query,verified,count:parseCount(text(showing||null),'en'),fields,filters,
    filtersKnown:!!showing&&ranges.length<=1&&!pending,pending,yearsKnown:ranges.length===1||filters.some(f=>f.startsWith('Yıl (sonuç'))};
}

export function extract(doc:Document,url:string,mapping:Mapping={}):Extraction {
  const database=platform(url,doc.title);
  const scopus=database==='Scopus'?scopusPublications(doc,url):null;
  const ieee=database==='IEEE Xplore'?ieeeResults(doc,url):null;
  const candidates=Array.from(doc.querySelectorAll('h1,h2,h3,p,span,div,[role="status"]'))
    .filter(visible).map(e=>({element:e,value:text(e)})).filter(x=>x.value.length>0&&x.value.length<500);
  const warnings:string[]=[];
  const selectedQuery=mapped(doc,mapping.query);
  const queryTexts=candidates.filter(x=>!x.element.closest('form')&&/^(?:search results for|results for|executed query|çalıştırılan sorgu)\s*[:：]?\s*\S/i.test(x.value))
    .map(x=>x.value.replace(/^(?:search results for|results for|executed query|çalıştırılan sorgu)\s*[:：]?\s*/i,''));
  const uniqueQueries=[...new Set(queryTexts)];
  let query=ieee?ieee.query:selectedQuery?text(selectedQuery):scopus?scopus.query:uniqueQueries.length===1?uniqueQueries[0]:'';
  let queryVerified=!!query&&!selectedQuery?.matches('input,textarea,[contenteditable="true"]');
  if(scopus&&!selectedQuery)queryVerified=scopus.verified;
  if(ieee)queryVerified=ieee.verified;
  if(!ieee&&selectedQuery?.matches('input,textarea'))query=(selectedQuery as HTMLInputElement).value;
  if(ieee&&ieee.query&&!ieee.verified)warnings.push('IEEE sonuç sayfasındaki sorgu adres çubuğundaki sorguyla eşleşmiyor.');
  for(const input of Array.from(doc.querySelectorAll<HTMLInputElement>('input[type="search"],textarea[aria-label*="search" i]')).filter(visible)){
    if(query&&input.value.trim()&&input.value.trim()!==query){warnings.push('Arama kutusu ile çalıştırılmış sorgu farklı.');queryVerified=false;}
  }
  const locale=doc.documentElement.lang;
  const countElement=ieee?null:mapped(doc,mapping.count);
  const countCandidates=ieee?[ieee.count]:countElement?[parseCount(text(countElement),locale)]:scopus?[scopus.count]:candidates
    .filter(x=>!x.element.closest('form,aside,nav,[aria-label*="filter" i]'))
    .map(x=>parseCount(x.value,locale)).filter(x=>x.value!==null);
  const counts=new Map(countCandidates.filter(x=>x.value!==null).map(x=>[x.value+'|'+x.qualifier,x]));
  const count=counts.size===1?[...counts.values()][0]:{raw:countElement?text(countElement):'',value:null,qualifier:'unknown'};
  const filtersElement=ieee?null:mapped(doc,mapping.filters);
  const filterRegions=Array.from(doc.querySelectorAll('[aria-label*="filter" i],[aria-label*="filtre" i]')).filter(visible);
  let filters:string[]=[];
  let filtersKnown=false;
  if(filtersElement){filters=[text(filtersElement)];filtersKnown=true;}
  else {
    const removals=Array.from(doc.querySelectorAll('[aria-label^="Remove filter" i],[aria-label^="Filtreyi kaldır" i]')).filter(visible);
    if(removals.length){filters=removals.map(e=>e.getAttribute('aria-label')||text(e));filtersKnown=true;}
    else if(filterRegions.some(e=>/no (?:active |applied )?filters|filtre uygulanmadı/i.test(text(e))))filtersKnown=true;
  }
  if(scopus&&!filtersElement){filters=scopus.filters;filtersKnown=scopus.filtersKnown;}
  if(ieee){filters=ieee.filters;filtersKnown=ieee.filtersKnown;
    if(ieee.pending)warnings.push('IEEE yayın türü seçimi henüz uygulanmamış olabilir. Sayfa yenilenince Ctrl+M yapın.');}
  if(scopus?.pending)warnings.push('Scopus filtre seçimi henüz uygulanmamış olabilir. Önce filtreleri uygulayın.');
  const fieldElement=ieee?null:mapped(doc,mapping.fields);
  const fieldValues=candidates.filter(x=>/^(?:search field|aranan alan)\s*:/i.test(x.value)).map(x=>x.value.replace(/^[^:]+:\s*/,''));
  const fields=ieee?ieee.fields:fieldElement?text(fieldElement):scopus?scopus.fields:[...new Set(fieldValues)].length===1?fieldValues[0]:'';
  if(Array.from(doc.querySelectorAll('[aria-busy="true"],[role="progressbar"]')).some(visible))warnings.push('Sayfa yükleniyor.');
  const headingText=Array.from(doc.querySelectorAll('h1,h2,[role="alert"]')).filter(visible).map(text).join(' ');
  if(/captcha|access denied|verify you are human|sign in to continue|erişim reddedildi/i.test(headingText))warnings.push('Giriş veya erişim kontrolü sayfası.');
  const missing:string[]=[];
  if(!queryVerified)missing.push('query');if(count.value===null)missing.push('count');
  if(!filtersKnown)missing.push('filters');if(!fields)missing.push('fields');
  let cleaned='';try{const u=new URL(url);cleaned=u.origin+u.pathname;}catch{}
  return {database,query_raw:query,query_verified:queryVerified,fields,filters,count_raw:count.raw,
    count_value:count.value,count_qualifier:count.qualifier,safe_url:cleaned,
    status:missing.length||warnings.length?'incomplete':'complete',missing_fields:missing,warnings,
    adapter_version:ieee?'ieee-searchresult-0.1.0':scopus?'scopus-publications-0.1.2':'semantic-0.1.0',
    adapter_support:!ieee&&Object.keys(mapping).length?'user_mapped':'unverified',
    source:ieee?'ieee_searchresult_dom':Object.keys(mapping).length?'user_mapped_dom':scopus?'scopus_publications_dom':'semantic_dom',observed_at_utc:new Date().toISOString()};
}

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

export function extract(doc:Document,url:string,mapping:Mapping={}):Extraction {
  const database=platform(url,doc.title);
  const candidates=Array.from(doc.querySelectorAll('h1,h2,h3,p,span,div,[role="status"]'))
    .filter(visible).map(e=>({element:e,value:text(e)})).filter(x=>x.value.length>0&&x.value.length<500);
  const warnings:string[]=[];
  const selectedQuery=mapped(doc,mapping.query);
  const queryTexts=candidates.filter(x=>!x.element.closest('form')&&/^(?:search results for|results for|executed query|çalıştırılan sorgu)\s*[:：]?\s*\S/i.test(x.value))
    .map(x=>x.value.replace(/^(?:search results for|results for|executed query|çalıştırılan sorgu)\s*[:：]?\s*/i,''));
  const uniqueQueries=[...new Set(queryTexts)];
  let query=selectedQuery?text(selectedQuery):uniqueQueries.length===1?uniqueQueries[0]:'';
  let queryVerified=!!query&&!selectedQuery?.matches('input,textarea,[contenteditable="true"]');
  if(selectedQuery?.matches('input,textarea'))query=(selectedQuery as HTMLInputElement).value;
  for(const input of Array.from(doc.querySelectorAll<HTMLInputElement>('input[type="search"],textarea[aria-label*="search" i]')).filter(visible)){
    if(query&&input.value.trim()&&input.value.trim()!==query){warnings.push('Arama kutusu ile çalıştırılmış sorgu farklı.');queryVerified=false;}
  }
  const locale=doc.documentElement.lang;
  const countElement=mapped(doc,mapping.count);
  const countCandidates=countElement?[parseCount(text(countElement),locale)]:candidates
    .filter(x=>!x.element.closest('form,aside,nav,[aria-label*="filter" i]'))
    .map(x=>parseCount(x.value,locale)).filter(x=>x.value!==null);
  const counts=new Map(countCandidates.filter(x=>x.value!==null).map(x=>[x.value+'|'+x.qualifier,x]));
  const count=counts.size===1?[...counts.values()][0]:{raw:countElement?text(countElement):'',value:null,qualifier:'unknown'};
  const filtersElement=mapped(doc,mapping.filters);
  const filterRegions=Array.from(doc.querySelectorAll('[aria-label*="filter" i],[aria-label*="filtre" i]')).filter(visible);
  let filters:string[]=[];
  let filtersKnown=false;
  if(filtersElement){filters=[text(filtersElement)];filtersKnown=true;}
  else {
    const removals=Array.from(doc.querySelectorAll('[aria-label^="Remove filter" i],[aria-label^="Filtreyi kaldır" i]')).filter(visible);
    if(removals.length){filters=removals.map(e=>e.getAttribute('aria-label')||text(e));filtersKnown=true;}
    else if(filterRegions.some(e=>/no (?:active |applied )?filters|filtre uygulanmadı/i.test(text(e))))filtersKnown=true;
  }
  const fieldElement=mapped(doc,mapping.fields);
  const fieldValues=candidates.filter(x=>/^(?:search field|aranan alan)\s*:/i.test(x.value)).map(x=>x.value.replace(/^[^:]+:\s*/,''));
  const fields=fieldElement?text(fieldElement):[...new Set(fieldValues)].length===1?fieldValues[0]:'';
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
    adapter_version:'semantic-0.1.0',adapter_support:Object.keys(mapping).length?'user_mapped':'unverified',
    source:Object.keys(mapping).length?'user_mapped_dom':'semantic_dom',observed_at_utc:new Date().toISOString()};
}

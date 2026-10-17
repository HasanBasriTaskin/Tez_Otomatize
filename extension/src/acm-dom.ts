import { acmResults, ACM_PAGE_SIZE } from './adapters';

/** One record of an ACM DL result list, read from the list itself (no article page is opened). */
export type AcmItem={doi:string;type:string;published:string;title:string;authors:string[];venue:string;pages:string;page:number;position:number};
export type AcmPlan={id:string;query:string;count:number;display_id:string};
export type AcmCollection={items:AcmItem[];pages:number;total:number;query:string;url:string};

const clean=(s:string|null|undefined)=>(s||'').replace(/\s+/g,' ').trim();
const DOI=/\/doi\/(?:abs\/|full\/|pdf\/|epdf\/)?(10\.\d{4,9}\/[^?#\s"]+)/i;
/** Never more pages than this in one collection (2.000 records); larger searches are narrowed first. */
export const ACM_MAX_PAGES=40;

export function acmItems(doc:Document,page=0):AcmItem[]{
  const out:AcmItem[]=[];
  doc.querySelectorAll('.issue-item.issue-item--search').forEach((item,index)=>{
    const link=item.querySelector<HTMLAnchorElement>('.issue-item__title a');
    const box=item.closest('li')?.querySelector<HTMLInputElement>('input.issue-Item__checkbox');
    const fromLink=(link?.getAttribute('href')||'').match(DOI)?.[1]||'';
    const fromDoi=(item.querySelector('.issue-item__doi')?.getAttribute('href')||'').replace(/^https?:\/\/(?:dx\.)?doi\.org\//i,'');
    const doi=decodeURIComponent(fromLink||fromDoi||box?.name||'').trim();
    const date=item.querySelector('.bookPubDate');
    const published=clean(date?.getAttribute('data-title')).replace(/^Published:\s*/i,'')||clean(date?.textContent);
    const authors=Array.from(item.querySelectorAll('.hlFld-ContribAuthor')).map(a=>clean(a.querySelector('a')?.getAttribute('title')||a.textContent)).filter(Boolean);
    const pages=Array.from(item.querySelectorAll('.issue-item__detail .dot-separator span, .issue-item__detail span'))
      .map(e=>clean(e.textContent).match(/^Pages?\s+(.+)$/i)?.[1]||'').find(Boolean)||'';
    out.push({doi,type:clean(item.querySelector('.issue-heading')?.textContent),published,title:clean(link?.textContent),
      authors,venue:clean(item.querySelector('.issue-item__detail .epub-section__title')?.textContent),pages,page,position:index+1});
  });
  return out;
}

/** The same search, one result page of 50 (ACM Basic's largest page). Nothing else in the address changes. */
export function acmPageUrl(href:string,page:number,size=ACM_PAGE_SIZE):string{
  const u=new URL(href);u.hash='';
  u.searchParams.set('pageSize',String(size));u.searchParams.set('startPage',String(page));
  return u.toString();
}

const key=(q:string)=>q.replace(/[‘’']/g,'"').replace(/\s+/g,'');
type Fetcher=(url:string,init:RequestInit)=>Promise<{ok:boolean;status:number;url?:string;text():Promise<string>}>;

/** Reads every result page of the search shown in this tab, one page after another, at a human pace.
 *  Each page must show the same query and total as the recorded search; otherwise nothing is returned. */
export async function collectAcm(doc:Document,href:string,plan:AcmPlan,{fetcher=fetch as unknown as Fetcher,
  parse=(html:string)=>new DOMParser().parseFromString(html,'text/html'),wait=(ms:number)=>new Promise(r=>setTimeout(r,ms)),
  pause=1500,progress=(_done:number,_all:number)=>{}}={}):Promise<AcmCollection>{
  const shown=acmResults(doc,href);
  if(!shown||key(shown.query)!==key(plan.query)||shown.count.value!==plan.count)
    throw new Error(`Bu sekme artık ${plan.display_id} aramasını göstermiyor. Aynı arama sayfasını açıp yeniden deneyin.`);
  const pages=Math.ceil(plan.count/ACM_PAGE_SIZE);
  if(pages>ACM_MAX_PAGES)throw new Error(`ACM ${plan.count} sonuç gösteriyor; tek seferde en fazla ${ACM_MAX_PAGES*ACM_PAGE_SIZE} kayıt toplanır. Aramayı daraltın.`);
  const items:AcmItem[]=[];
  for(let page=0;page<pages;page++){
    if(page)await wait(pause);
    const url=acmPageUrl(href,page);
    let response;
    try{response=await fetcher(url,{credentials:'include',cache:'no-store'});}
    catch{throw new Error(`ACM sonuç sayfası ${page+1}/${pages} alınamadı (bağlantı). Biraz bekleyip yeniden deneyin.`);}
    if(!response.ok)throw new Error(`ACM sonuç sayfası ${page+1}/${pages} alınamadı (HTTP ${response.status}). ACM doğrulama istiyorsa sayfayı yenileyip yeniden deneyin.`);
    const d=parse(await response.text());
    const r=acmResults(d,response.url||url,false);
    if(!r)throw new Error(`ACM sonuç sayfası ${page+1}/${pages} okunamadı; ACM doğrulama (robot kontrolü) istemiş olabilir. Sayfayı yenileyip yeniden deneyin.`);
    if(key(r.query)!==key(plan.query)||r.count.value!==plan.count)
      throw new Error(`ACM sonuçları okunurken değişti (sayfa ${page+1}: ${r.count.value??'?'} sonuç). Yeniden Ctrl+M yapın.`);
    const found=acmItems(d,page+1);
    const expected=page<pages-1?ACM_PAGE_SIZE:plan.count-ACM_PAGE_SIZE*(pages-1);
    if(found.length!==expected)throw new Error(`ACM sonuç sayfası ${page+1}/${pages} ${found.length} kayıt gösterdi, ${expected} bekleniyordu. Yeniden deneyin.`);
    if(found.some(i=>!/^10\.\d{4,9}\/\S+$/.test(i.doi)))throw new Error(`Sayfa ${page+1}'de DOI'si okunamayan kayıt var; ACM sayfa yapısı değişmiş olabilir.`);
    items.push(...found);progress(page+1,pages);
  }
  return {items,pages,total:plan.count,query:shown.query,url:acmPageUrl(href,0)};
}

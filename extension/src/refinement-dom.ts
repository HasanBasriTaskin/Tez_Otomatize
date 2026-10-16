import {extract, visible} from './adapters';

/** Prefix of the error raised when Scopus narrows the year inputs itself; refine.ts copies the query then. */
export const CLAMPED='[yıl-kutusu]';
export type Refinement ={id:string;source_query:string;source_count:number;query:string;year_from:number;year_to:number};
const compact=(q:string)=>(q.match(/"(?:\\.|[^"\\])*"|\S/g)||[]).join('');
function one<T extends Element>(doc:Document,selector:string):T {
  const nodes=Array.from(doc.querySelectorAll<T>(selector)).filter(visible);
  if(nodes.length!==1)throw new Error('Scopus yıl alanları kesin olarak bulunamadı. Hazırlanan sorguyu elle uygulayın.');
  return nodes[0];
}
function setValue(input:HTMLInputElement,value:string){
  if(input.disabled||input.readOnly)throw new Error('Yıl alanı düzenlenemiyor.');
  const win=input.ownerDocument.defaultView!;
  Object.getOwnPropertyDescriptor(win.HTMLInputElement.prototype,'value')!.set!.call(input,value);
  input.dispatchEvent(new win.Event('input',{bubbles:true}));
  input.dispatchEvent(new win.Event('change',{bubbles:true}));
}
async function commitRange(doc:Document,selector:string){
  // Scopus fills the other bound on blur; let that render settle before editing the next bound.
  await new Promise(r=>setTimeout(r,40));
  const input=one<HTMLInputElement>(doc,selector);input.focus();input.blur();
  await new Promise(r=>setTimeout(r,40));
}

export async function applyYears(doc:Document,url:string,plan:Refinement):Promise<{submitted:boolean;message:string}> {
  if(!Number.isInteger(plan.year_from)||plan.year_from<1990||plan.year_from>2026||plan.year_to!==2026)throw new Error('Desteklenmeyen yıl aralığı.');
  const data=extract(doc,url);
  if(data.status!=='complete'||data.database!=='Scopus'||data.count_qualifier!=='exact'||compact(data.query_raw)!==compact(plan.source_query)||data.count_value!==plan.source_count)
    throw new Error('Sorgu, sonuç sayısı veya filtreler değişmiş. Yeni sayfada Ctrl+M yapın.');
  const prefix='[data-testid="facet-group-year"] ';
  const fromSelector=prefix+'input[data-testid="input-range-from"]';
  const toSelector=prefix+'input[data-testid="input-range-to"]';
  const from=one<HTMLInputElement>(doc,fromSelector),to=one<HTMLInputElement>(doc,toSelector);
  const oldFrom=from.value,oldTo=to.value;
  try {
    setValue(from,String(plan.year_from));
    await commitRange(doc,fromSelector);
    setValue(one<HTMLInputElement>(doc,toSelector),String(plan.year_to));
    await commitRange(doc,toSelector);
    for(let attempt=0;attempt<15;attempt++){
      await new Promise(r=>setTimeout(r,100));
      const current=extract(doc,url);
      const changed=Array.from(doc.querySelectorAll('[aria-busy="true"],[role="progressbar"],[data-testid="facet-s"] input[type="checkbox"]:checked,[data-testid="facet-s"] [role="checkbox"][aria-checked="true"]')).some(visible);
      if(changed||!current.query_verified||current.count_qualifier!=='exact'||compact(current.query_raw)!==compact(plan.source_query)||current.count_value!==plan.source_count)
        throw new Error('Sayfa işlem sırasında değişti. Yeni sayfada Ctrl+M yapın.');
      const buttons=Array.from(doc.querySelectorAll<HTMLButtonElement>('[data-testid="facet-s"] button'))
        .filter(b=>visible(b)&&!b.disabled&&(b.textContent?.trim()==='Apply selected year range'||b.getAttribute('aria-label')==='Apply selected year range'));
      if(buttons.length===1){
        const actualFrom=one<HTMLInputElement>(doc,fromSelector).value,actualTo=one<HTMLInputElement>(doc,toSelector).value;
        // Scopus clamps the range to the years present in the results (e.g. no 2022 papers → 2023).
        // The facet then cannot express the planned query, so the full query must run instead.
        if(/^\d{4}$/.test(actualFrom)&&/^\d{4}$/.test(actualTo)&&(Number(actualFrom)>plan.year_from||Number(actualTo)<plan.year_to)
          &&Number(actualFrom)>=plan.year_from&&Number(actualTo)<=plan.year_to)
          throw new Error(`${CLAMPED} Scopus yıl kutusunu ${plan.year_from}–${plan.year_to} yerine ${actualFrom}–${actualTo} yaptı; bu sonuçlarda daha eski yayın yok. Otomatik uygulama yapılmadı.`);
        if(actualFrom!==String(plan.year_from)||actualTo!==String(plan.year_to))
          throw new Error(`Yıl seçimi değişti (beklenen ${plan.year_from}–${plan.year_to}, okunan ${actualFrom||'boş'}–${actualTo||'boş'}); arama çalıştırılmadı.`);
        buttons[0].click();
        return {submitted:true,message:'Yıl aralığı uygulandı. Sonuçların yüklenmesini bekleyip Ctrl+M yapın; yeni sorgu ve sayı o anda doğrulanacak.'};
      }
    }
    throw new Error('Yıl aralığını uygulama düğmesi bulunamadı. Sorguyu kopyalayıp Scopus gelişmiş aramada elle çalıştırın.');
  } catch(error) {
    // Restore only our own edits, and only while the executed query is unchanged.
    if(compact(extract(doc,url).query_raw)===compact(plan.source_query)){
      const f=doc.querySelector<HTMLInputElement>(fromSelector),t=doc.querySelector<HTMLInputElement>(toSelector);
      if(f?.value===String(plan.year_from))setValue(f,oldFrom);
      if(t?.value===String(plan.year_to))setValue(t,oldTo);
      if(f&&t)await commitRange(doc,toSelector);
    }
    throw error;
  }
}

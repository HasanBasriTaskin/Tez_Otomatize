import {extract, visible} from './adapters';

export type Refinement = {id:string;source_query:string;source_count:number;query:string;year_from:number;year_to:number};
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
async function commitRange(doc:Document,toSelector:string){
  // Scopus commits its controlled range on blur, after React has processed both input events.
  await new Promise(r=>setTimeout(r,40));
  const input=one<HTMLInputElement>(doc,toSelector);input.focus();input.blur();
}

export async function applyYears(doc:Document,url:string,plan:Refinement):Promise<{submitted:boolean;message:string}> {
  if(![2022,2024].includes(plan.year_from)||plan.year_to!==2026)throw new Error('Desteklenmeyen yıl aralığı.');
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
    await new Promise(r=>setTimeout(r,40));
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
        if(one<HTMLInputElement>(doc,fromSelector).value!==String(plan.year_from)||one<HTMLInputElement>(doc,toSelector).value!==String(plan.year_to))
          throw new Error('Yıl seçimi değişti; işlem durduruldu.');
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

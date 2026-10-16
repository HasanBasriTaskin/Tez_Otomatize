import {CLAMPED} from './refinement-dom';
const id=new URLSearchParams(location.search).get('id');
const apply=document.getElementById('apply') as HTMLButtonElement;
const copy=document.getElementById('copy') as HTMLButtonElement;
const query=document.getElementById('query') as HTMLTextAreaElement;
const status=document.getElementById('message')!;
let approved=false,ieee=false,manualHelp='';
async function send(message:Record<string,unknown>){
  const r=await chrome.runtime.sendMessage(message);
  if(!r?.ok)throw new Error(r?.error||'Windows bağlantısı kurulamadı.');
  return r.data;
}
async function rpc(type:string,payload:Record<string,unknown>){return send({kind:'rpc',type,payload});}
document.getElementById('close')!.onclick=()=>window.close();
apply.onclick=async()=>{
  apply.disabled=true;copy.disabled=true;status.textContent=`Onay kaydediliyor ve ${ieee?'IEEE':'Scopus'} kontrol ediliyor…`;
  try{
    const result=await send({kind:'refinement_apply',id});approved=true;
    status.textContent=result.message;setTimeout(()=>window.close(),1200);
  }catch(e){
    const text=e instanceof Error?e.message:String(e);
    status.textContent=text.replace(CLAMPED,'').trim();status.classList.add('error');
    try{approved=(await rpc('get_refinement',{id})).state!=='offered';}catch{}
    // The year facet cannot express this range; the full query is the only way, so copy it right away.
    if(text.startsWith(CLAMPED)){
      try{await copyQuery();status.textContent=text.replace(CLAMPED,'').trim()+' '+status.textContent;}
      catch{status.textContent=text.replace(CLAMPED,'').trim()+' “Sorguyu kopyala, elle uygula” düğmesini kullanın.';}
    }
  }finally{copy.disabled=false;}
};
async function copyQuery(){
  if(!approved){await rpc('approve_refinement',{id});approved=true;}
  if(ieee){status.classList.remove('error');status.textContent=manualHelp;return;}
  await navigator.clipboard.writeText(query.value);
  status.classList.remove('error');
  status.textContent='Sorgu kopyalandı. Aynı Scopus sekmesinde gelişmiş aramaya yapıştırıp çalıştırın; sonuçlar yüklenince Ctrl+M yapın.';
}
copy.onclick=async()=>{
  copy.disabled=true;apply.disabled=true;
  try{await copyQuery();}
  catch(e){status.textContent=e instanceof Error?e.message:String(e);}
  finally{copy.disabled=false;}
};
void rpc('get_refinement',{id}).then(p=>{
  query.value=p.query;document.getElementById('reason')!.textContent=p.display_id+' · '+p.reason;
  if(p.context?.kind==='ieee'){
    ieee=true;
    const filters=document.getElementById('filters')!;filters.hidden=false;
    filters.textContent='Uygulanacak filtreler: '+p.filters_label;
    document.getElementById('query-label')!.textContent='Sorgu (değişmez)';
    document.getElementById('how')!.textContent='Onaylarsan aynı IEEE sekmesi bu filtrelerle yeniden yüklenir. Sonuçlar yüklenince tekrar Ctrl+M yap; yeni kayıt, önceki adıma bağlanır.';
    copy.textContent='Filtreleri elle uygula';
    const years=p.context.apply_years?` Year kutularına ${p.year_from} ve ${p.year_to} yazıp Apply'a basın.`:'';
    manualHelp='Sol paneldeki Content Type bölümünde yalnız Conferences ve Journals işaretleyip Apply\'a basın.'+years+' Sonuçlar yüklenince Ctrl+M yapın.';
  }
  approved=p.state!=='offered';apply.disabled=approved;copy.disabled=false;
  if(approved)status.textContent='Bu öneri daha önce onaylandı. Yeniden otomatik çalıştırılmaz; sorguyu kopyalayabilirsiniz.';
}).catch(e=>{status.textContent=e.message;status.classList.add('error');});

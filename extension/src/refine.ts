export {};
const id=new URLSearchParams(location.search).get('id');
const apply=document.getElementById('apply') as HTMLButtonElement;
const copy=document.getElementById('copy') as HTMLButtonElement;
const query=document.getElementById('query') as HTMLTextAreaElement;
const status=document.getElementById('message')!;
let approved=false;
async function send(message:Record<string,unknown>){
  const r=await chrome.runtime.sendMessage(message);
  if(!r?.ok)throw new Error(r?.error||'Windows bağlantısı kurulamadı.');
  return r.data;
}
async function rpc(type:string,payload:Record<string,unknown>){return send({kind:'rpc',type,payload});}
document.getElementById('close')!.onclick=()=>window.close();
apply.onclick=async()=>{
  apply.disabled=true;copy.disabled=true;status.textContent='Onay kaydediliyor ve Scopus kontrol ediliyor…';
  try{
    const result=await send({kind:'refinement_apply',id});approved=true;
    status.textContent=result.message;setTimeout(()=>window.close(),1200);
  }catch(e){
    status.textContent=e instanceof Error?e.message:String(e);status.classList.add('error');
    try{approved=(await rpc('get_refinement',{id})).state!=='offered';}catch{}
  }finally{copy.disabled=false;}
};
copy.onclick=async()=>{
  copy.disabled=true;apply.disabled=true;
  try{
    if(!approved){await rpc('approve_refinement',{id});approved=true;}
    await navigator.clipboard.writeText(query.value);
    status.textContent='Sorgu kopyalandı. Aynı Scopus sekmesinde gelişmiş aramaya yapıştırıp çalıştırın; sonuçlar yüklenince Ctrl+M yapın.';
  }catch(e){status.textContent=e instanceof Error?e.message:String(e);}
  finally{copy.disabled=false;}
};
void rpc('get_refinement',{id}).then(p=>{
  query.value=p.query;document.getElementById('reason')!.textContent=p.display_id+' · '+p.reason;
  approved=p.state!=='offered';apply.disabled=approved;copy.disabled=false;
  if(approved)status.textContent='Bu öneri daha önce onaylandı. Yeniden otomatik çalıştırılmaz; sorguyu kopyalayabilirsiniz.';
}).catch(e=>{status.textContent=e.message;status.classList.add('error');});

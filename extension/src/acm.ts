export {};
const id=new URLSearchParams(location.search).get('id');
const collect=document.getElementById('collect') as HTMLButtonElement;
const status=document.getElementById('message')!;
let timer:ReturnType<typeof setTimeout>|undefined;
async function send(message:Record<string,unknown>){
  const r=await chrome.runtime.sendMessage(message);
  if(!r?.ok)throw new Error(r?.error||'Windows bağlantısı kurulamadı.');
  return r.data;
}
const rpc=(type:string,payload:Record<string,unknown>)=>send({kind:'rpc',type,payload});
function show(text:string,error=false){status.textContent=text;status.classList.toggle('error',error);}
const BUSY=['collecting','processing'];
function render(p:any){
  document.getElementById('reason')!.textContent=`${p.display_id} · ACM'de ${p.count.toLocaleString('tr-TR')} sonuç · ${p.fields||'alan okunamadı'}`;
  (document.getElementById('query') as HTMLTextAreaElement).value=p.query;
  const rules=document.getElementById('rules')!;rules.replaceChildren();
  const item=(text:string,cls='')=>{const li=document.createElement('li');li.textContent=text;if(cls)li.className=cls;rules.append(li);};
  if(p.years)item(p.years,'ok');else item('Aramada yıl filtresi yok: kayıtlar bütün yıllardan toplanır.','hata');
  item(p.types+' (diğer türler Zotero\'ya alınmaz)','ok');
  document.getElementById('how')!.textContent=`Topla'ya basınca ${p.pages} sonuç sayfası sırayla okunur. Arama sekmesi açık kalsın; bitene kadar o sekmede başka arama yapmayın.`;
  collect.disabled=!p.can_collect;
  collect.textContent=p.state==='failed'?'Yeniden topla':'Topla';
  if(p.message)show(p.message,p.state==='failed');
  else if(p.state==='done')show('Bu arama daha önce toplandı.');
  clearTimeout(timer);
  if(BUSY.includes(p.state))timer=setTimeout(refresh,2000);
}
async function refresh(){try{render(await rpc('acm_get',{id}));}catch(e){show(e instanceof Error?e.message:String(e),true);}}
document.getElementById('close')!.onclick=()=>window.close();
collect.onclick=async()=>{
  collect.disabled=true;show('ACM sonuç sayfaları okunuyor… Bu pencereyi kapatmayın.');
  try{await send({kind:'acm_collect',id});}
  catch(e){show(e instanceof Error?e.message:String(e),true);}
  await refresh();
};
void refresh();

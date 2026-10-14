export {};
const status=document.querySelector<HTMLElement>('#status')!;
document.querySelector('#manage')!.addEventListener('click',()=>chrome.runtime.openOptionsPage());
document.querySelector('#enable')!.addEventListener('click',async()=>{
  try{
    const [tab]=await chrome.tabs.query({active:true,currentWindow:true});
    if(!tab?.url||!/^https?:/.test(tab.url))throw new Error('Önce veri tabanının arama sonuçlarını açın.');
    const origin=new URL(tab.url).origin+'/*';
    if(!await chrome.permissions.request({origins:[origin]}))throw new Error('Site izni verilmedi.');
    const r=await chrome.runtime.sendMessage({kind:'enable_tab',tabId:tab.id});
    if(!r.ok)throw new Error(r.error);
    status.textContent='Site etkin. Bu pencereyi kapatıp Ctrl+M kullanabilirsiniz.';
  }catch(e){status.textContent=String((e as Error).message);}
});
document.querySelector('#fixture')!.addEventListener('click',async()=>{
  try{
    const [tab]=await chrome.tabs.query({active:true,currentWindow:true});
    const r=await chrome.runtime.sendMessage({kind:'fixture',tabId:tab.id});
    if(!r.ok)throw new Error(r.error);status.textContent='Temizlenmiş tanılama dosyası kaydedildi.';
  }catch(e){status.textContent=String((e as Error).message);}
});
void chrome.runtime.sendMessage({kind:'connection'}).then(async r=>{
  status.textContent=r.data?.connected?'Windows bağlantısı hazır.':'Windows yardımcı uygulaması bulunamadı. Kurulum paketindeki Kurulum aracını çalıştırın.';
  const saved=await chrome.storage.local.get('lastMappingError');
  if(saved.lastMappingError){status.textContent=String(saved.lastMappingError);await chrome.storage.local.remove('lastMappingError');}
});

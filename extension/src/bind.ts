export {};
const windowId=Number(new URL(location.href).searchParams.get('window'));
void (async()=>{
  const response=await chrome.runtime.sendMessage({kind:'binding_info'});
  if(!response.ok)throw new Error(response.error);
  const port=chrome.runtime.connectNative(response.data.host);
  const id=crypto.randomUUID();
  port.onMessage.addListener(async message=>{
    if(message.id===id&&message.ok)await chrome.runtime.sendMessage({kind:'bound',windowId});
  });
  port.postMessage({v:1,id,type:'hello',payload:{profile:response.data.profile,role:'binder',windowId}});
})().catch(()=>{document.body.textContent='Windows bağlantısı kurulamadı. Eklentinin yönetim sayfasını açın.';});

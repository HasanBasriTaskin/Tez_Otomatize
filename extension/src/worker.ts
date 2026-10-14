import type { Mapping } from './adapters';
declare const HOST_NAME:string;
type Envelope={v:1;id:string;type:string;payload:Record<string,any>;ok?:boolean;error?:string};
type Context={profile:string;windowId:number;tabId:number;documentId:string;epoch:number;};
let native:chrome.runtime.Port|null=null;
let profile='';
let ready:Promise<void>|null=null;
const pending=new Map<string,{resolve:(v:any)=>void;reject:(e:Error)=>void;timer:ReturnType<typeof setTimeout>}>();
const jobs=new Map<string,{context:Context;changed:boolean}>();
const binding=new Set<number>();
const bound=new Set<number>();
let nativeError='Windows uygulamasına bağlanılıyor…';

async function identity(){
  const saved=await chrome.storage.local.get('profileId');
  const session=await chrome.storage.session.get('sessionId');
  const pid=saved.profileId||crypto.randomUUID();const sid=session.sessionId||crypto.randomUUID();
  await chrome.storage.local.set({profileId:pid});await chrome.storage.session.set({sessionId:sid});
  profile=pid+'/'+sid;
}
function rpcRaw(type:string,payload:Record<string,any>={}):Promise<any>{
  return new Promise((resolve,reject)=>{
    if(!native){reject(new Error(nativeError));return;}
    const id=crypto.randomUUID();const timer=setTimeout(()=>{pending.delete(id);reject(new Error('Windows uygulaması zamanında yanıt vermedi.'));},120000);
    pending.set(id,{resolve,reject,timer});
    try{native.postMessage({v:1,id,type,payload});}catch(e){clearTimeout(timer);pending.delete(id);reject(e);}
  });
}
async function connect(){
  if(ready)return ready;
  ready=(async()=>{
    await identity();native=chrome.runtime.connectNative(HOST_NAME);
    native.onMessage.addListener((message:Envelope)=>{
      if(message.type==='reply'){
        const waiter=pending.get(message.id);if(!waiter)return;
        clearTimeout(waiter.timer);pending.delete(message.id);
        message.ok?waiter.resolve(message.payload):waiter.reject(new Error(message.error||'İşlem başarısız.'));
      }else{
        void handleCapture(message).then(payload=>native?.postMessage({v:1,id:message.id,type:'reply',ok:true,payload}))
          .catch(e=>native?.postMessage({v:1,id:message.id,type:'reply',ok:false,error:String(e.message||e),payload:{}}));
      }
    });
    native.onDisconnect.addListener(()=>{
      nativeError=chrome.runtime.lastError?.message||'Windows bağlantısı kapandı.';native=null;ready=null;bound.clear();
      for(const task of jobs.values())task.changed=true;
      for(const waiter of pending.values()){clearTimeout(waiter.timer);waiter.reject(new Error(nativeError));}pending.clear();
      chrome.action.setBadgeText({text:'!'});chrome.action.setBadgeBackgroundColor({color:'#9E451C'});
      void chrome.alarms.create('native-reconnect',{delayInMinutes:.5});
    });
    await rpcRaw('hello',{profile,role:'worker'});nativeError='';
    await chrome.action.setBadgeText({text:''});
    for(const win of await chrome.windows.getAll({windowTypes:['normal']}))if(win.id)void bindWindow(win.id);
  })();
  try{await ready;}catch(e){ready=null;throw e;}
}
async function rpc(type:string,payload:Record<string,any>={}){await connect();return rpcRaw(type,payload);}

async function bindWindow(windowId:number){
  if(bound.has(windowId)||binding.has(windowId)||jobs.size)return;
  binding.add(windowId);
  let tab:chrome.tabs.Tab|undefined;
  try{
    // This extension-owned tab never receives focus and exists only for exact HWND binding.
    tab=await chrome.tabs.create({windowId,active:false,url:chrome.runtime.getURL('bind.html')+'?window='+windowId});
    const start=Date.now();
    while(!bound.has(windowId)&&Date.now()-start<8000)await new Promise(r=>setTimeout(r,150));
  }catch{}finally{
    if(tab?.id)try{await chrome.tabs.remove(tab.id);}catch{}
    binding.delete(windowId);
  }
}
function invalidate(tabId?:number,windowId?:number){
  for(const task of jobs.values())if((tabId===undefined||task.context.tabId===tabId)&&(windowId===undefined||task.context.windowId===windowId))task.changed=true;
}
chrome.tabs.onActivated.addListener(info=>invalidate(undefined,info.windowId));
chrome.tabs.onUpdated.addListener((tabId,change)=>{if(change.status==='loading'||change.url)invalidate(tabId);});
chrome.tabs.onRemoved.addListener(tabId=>invalidate(tabId));
chrome.windows.onFocusChanged.addListener(()=>invalidate());
chrome.windows.onCreated.addListener(win=>{if(win.type==='normal'&&win.id)void connect().then(()=>bindWindow(win.id!)).catch(()=>{});});
chrome.windows.onRemoved.addListener(id=>{bound.delete(id);void rpc('unbind_window',{windowId:id}).catch(()=>{});});
chrome.webNavigation.onCommitted.addListener(details=>{if(details.frameId===0)invalidate(details.tabId);});
chrome.webNavigation.onHistoryStateUpdated.addListener(details=>{if(details.frameId===0)invalidate(details.tabId);});

async function allowed(tab:chrome.tabs.Tab){
  if(!tab.id||!tab.url||tab.incognito)return false;
  const url=new URL(tab.url);
  if(!['https:','http:'].includes(url.protocol))return false;
  return chrome.permissions.contains({origins:[url.origin+'/*']});
}
async function inject(tabId:number){await chrome.scripting.executeScript({target:{tabId},files:['content.js']});}
async function mappingFor(tab:chrome.tabs.Tab):Promise<Mapping>{
  if(!tab.url)return {};
  const u=new URL(tab.url);const key='map:'+u.origin+u.pathname;
  return (await chrome.storage.local.get(key))[key]||{};
}
async function handleCapture(message:Envelope):Promise<Record<string,any>>{
  const p=message.payload;
  if(message.type==='prepare_capture'){
    const win=await chrome.windows.get(p.windowId);
    const [tab]=await chrome.tabs.query({active:true,windowId:p.windowId});
    if(!win.focused||!tab||!await allowed(tab))return {ready:false,reason:'Aktif sayfa izni yok. Eklenti simgesinden bu siteyi etkinleştirin.'};
    if(!bound.has(p.windowId))return {ready:false,reason:'Chrome penceresi henüz bağlanmadı.'};
    await inject(tab.id!);
    const frame=await chrome.webNavigation.getFrame({tabId:tab.id!,frameId:0});
    if(!frame?.documentId)return {ready:false,reason:'Sayfa kimliği okunamadı.'};
    const context:Context={profile,windowId:p.windowId,tabId:tab.id!,documentId:frame.documentId,epoch:0};
    jobs.set(p.jobId,{context,changed:false});
    const armed=await chrome.tabs.sendMessage(tab.id!,{kind:'arm',jobId:p.jobId},{documentId:frame.documentId});
    if(!armed?.ready)throw new Error('Sayfa yakalama kontrolü başlatılamadı.');
    return {ready:true,context};
  }
  if(message.type==='extract_capture'){
    const task=jobs.get(p.jobId);if(!task)throw new Error('Yakalama işi bulunamadı.');
    const tab=await chrome.tabs.get(task.context.tabId);
    const frame=await chrome.webNavigation.getFrame({tabId:tab.id!,frameId:0});
    const result=await chrome.tabs.sendMessage(tab.id!,{kind:'extract',jobId:p.jobId,mapping:await mappingFor(tab)},{documentId:task.context.documentId});
    if(result.error)throw new Error(result.error);
    const same=frame?.documentId===task.context.documentId&&tab.active&&tab.windowId===task.context.windowId&&!task.changed&&result.stable;
    return {context:{...task.context,epoch:same?0:1},data:result.data};
  }
  if(message.type==='release_capture'){
    const task=jobs.get(p.jobId);jobs.delete(p.jobId);
    if(task)try{await chrome.tabs.sendMessage(task.context.tabId,{kind:'release'},{documentId:task.context.documentId});}catch{}
    return {};
  }
  throw new Error('Bilinmeyen Chrome komutu.');
}

chrome.runtime.onMessage.addListener((message,sender,sendResponse)=>{
  if(sender.id!==chrome.runtime.id||!sender.url?.startsWith(chrome.runtime.getURL('')))return;
  const run=async()=>{
    if(message.kind==='binding_info'){await connect();return {profile,host:HOST_NAME};}
    if(message.kind==='bound'){
      if(!sender.url?.startsWith(chrome.runtime.getURL('bind.html'))||sender.tab?.windowId!==message.windowId)throw new Error('Pencere eşleşmedi.');
      bound.add(message.windowId);return {};
    }
    if(message.kind==='rpc')return rpc(message.type,message.payload||{});
    if(message.kind==='connection'){
      try{await connect();return {connected:true,bound:bound.size};}catch{return {connected:false,error:nativeError};}
    }
    if(message.kind==='enable_tab'){
      const tab=await chrome.tabs.get(message.tabId);if(!await allowed(tab))throw new Error('Site izni verilmedi.');
      await inject(tab.id!);await connect();await bindWindow(tab.windowId);return {};
    }
    if(message.kind==='fixture'){
      const tab=await chrome.tabs.get(message.tabId);if(!await allowed(tab))throw new Error('Site izni yok.');
      await inject(tab.id!);
      const data=await chrome.tabs.sendMessage(tab.id!,{kind:'fixture',mapping:await mappingFor(tab)});
      return rpc('save_fixture',data);
    }
    throw new Error('Desteklenmeyen istek.');
  };
  void run().then(data=>sendResponse({ok:true,data})).catch(e=>sendResponse({ok:false,error:e.message}));
  return true;
});

chrome.contextMenus.onClicked.addListener((info,tab)=>{
  if(!tab?.id||!String(info.menuItemId).startsWith('map_'))return;
  void (async()=>{
    if(!await allowed(tab))throw new Error('Önce eklenti simgesinden bu sitede erişimi etkinleştirin.');
    await inject(tab.id!);const result=await chrome.tabs.sendMessage(tab.id!,{kind:'map_selection'});
    if(result.error)throw new Error(result.error);
    const u=new URL(tab.url!);const key='map:'+u.origin+u.pathname;
    const previous:Record<string,string>=(await chrome.storage.local.get(key))[key] as Record<string,string>||{};
    previous[String(info.menuItemId).slice(4)]=result.selector;
    await chrome.storage.local.set({[key]:previous});
    await chrome.action.setBadgeText({text:'✓'});await chrome.action.setBadgeBackgroundColor({color:'#28645C'});
  })().catch(async e=>{await chrome.storage.local.set({lastMappingError:e.message});await chrome.action.setBadgeText({text:'!'});});
});
chrome.runtime.onInstalled.addListener(()=>{
  void chrome.contextMenus.removeAll().then(()=>{
    for(const [field,label] of Object.entries({query:'Çalıştırılmış sorgu',count:'Toplam sonuç sayısı',filters:'Uygulanan filtreler',fields:'Aranan alan'}))
      chrome.contextMenus.create({id:'map_'+field,title:'Literatür kaydı: '+label,contexts:['selection']});
  });
  void connect().catch(()=>{});
});
chrome.runtime.onStartup.addListener(()=>{void connect().catch(()=>{});});
chrome.alarms.onAlarm.addListener(alarm=>{if(alarm.name==='native-reconnect')void connect().catch(()=>{});});
void connect().catch(()=>{});

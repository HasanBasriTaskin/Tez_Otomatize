import {platform} from './adapters';

type Context={profile:string;windowId:number;tabId:number};
type Watch={exportId:string;stepId:string;fingerprint:string;started:number;pageUrl:string;ids:number[];terminal?:boolean};
type Flow={context:Context;sessionId?:string;latched:boolean;watch?:Watch};
const storageKey='workflow.browser';
const mutations=new Set(['open_search','fill_search','submit_search','prepare_evidence','export_open','export_configure','export_submit']);
const id=(value:unknown)=>typeof value==='string'&&/^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,159}$/.test(value)&&!value.includes('..');
function canonical(value:any):string {
  if(value===null||typeof value!=='object')return JSON.stringify(value);
  if(Array.isArray(value))return '['+value.map(canonical).join(',')+']';
  return '{'+Object.keys(value).sort().filter(k=>value[k]!==undefined).map(k=>JSON.stringify(k)+':'+canonical(value[k])).join(',')+'}';
}
function sameContext(a:Context,b:Context){return a.profile===b.profile&&a.windowId===b.windowId&&a.tabId===b.tabId;}
function exportFingerprint(p:Record<string,any>){return canonical({stepId:p.stepId,expectedCount:p.expectedCount,rangeStart:p.rangeStart??1,rangeEnd:p.rangeEnd??p.expectedCount});}
function pageUrl(url:string){const u=new URL(url);u.hash='';return u.href;}
function matchesDownload(item:chrome.downloads.DownloadItem,watch:Watch){
  try{
    const origin=new URL(watch.pageUrl).origin;
    return Date.parse(item.startTime)>=watch.started&&pageUrl(item.referrer)===pageUrl(watch.pageUrl)&&
      new URL(item.url).origin===origin&&(!item.finalUrl||new URL(item.finalUrl).origin===origin)&&
      (/\.ris$/i.test(item.filename)||/\.ris(?:[?#]|$)/i.test(item.url)||/research-info-systems|x-ris/i.test(item.mime));
  }catch{return false;}
}

export class WorkflowBrowser {
  private flow:Flow|null=null;
  private ready:Promise<void>;
  private queue:Promise<unknown>=Promise.resolve();
  private writes:Promise<unknown>=Promise.resolve();
  private downloadsRegistered=false;
  constructor(private api:typeof chrome,private profile:()=>string,private bind:(windowId:number)=>Promise<boolean>,
    private rpc:(type:string,payload:Record<string,any>)=>Promise<any>){
    this.ready=Promise.all([api.storage.session.get(storageKey),api.storage.local.get(storageKey)]).then(([session,local])=>{
      const warm=session[storageKey] as Flow|undefined;
      const saved=(local[storageKey]===undefined?warm:local[storageKey]) as Flow|null|undefined;
      this.flow=saved?{...saved,latched:saved.latched||!warm||canonical(warm)!==canonical(saved)}:null;
    });
    api.tabs.onActivated.addListener(info=>this.invalidate(f=>info.windowId===f.context.windowId&&info.tabId!==f.context.tabId));
    api.tabs.onRemoved.addListener(tabId=>this.invalidate(f=>tabId===f.context.tabId));
    api.tabs.onDetached.addListener(tabId=>this.invalidate(f=>tabId===f.context.tabId));
    api.windows.onFocusChanged.addListener(windowId=>this.invalidate(f=>windowId!==f.context.windowId));
    api.windows.onRemoved.addListener(windowId=>this.invalidate(f=>windowId===f.context.windowId));
    this.registerDownloads();
  }
  private registerDownloads(){
    if(this.downloadsRegistered||!this.api.downloads)return;
    this.downloadsRegistered=true;
    // Register at startup, or immediately after the first optional permission grant.
    this.api.downloads.onCreated.addListener(item=>{void this.serial(()=>this.record(item)).catch(()=>{});});
    this.api.downloads.onDeterminingFilename.addListener((item,suggest)=>{
      void this.serial(async()=>{
        if(!await this.record(item))return;
        const flow=this.flow!;
        if(flow.watch!.ids.length!==1)return;
        return {filename:`LiteraturKayit/${flow.sessionId}/${flow.watch!.exportId}.ris`,conflictAction:'uniquify' as const};
      }).then(result=>suggest(result),()=>suggest());
      return true;
    });
  }
  private serial<T>(fn:()=>Promise<T>):Promise<T>{
    const task=this.queue.then(()=>this.ready).then(fn);this.queue=task.catch(()=>{});return task;
  }
  private save(key:string,value:unknown){
    const snapshot=structuredClone(value);
    // Keep a durable recovery ledger; session is only a warm-worker indicator/cache.
    const write=this.writes.then(()=>Promise.all([
      this.api.storage.local.set({[key]:snapshot}),this.api.storage.session.set({[key]:snapshot})
    ]));
    this.writes=write.catch(()=>{});return write;
  }
  private persist(){return this.save(storageKey,this.flow);}
  private invalidate(predicate:(flow:Flow)=>boolean){
    const apply=()=>{if(this.flow&&predicate(this.flow)){this.flow.latched=true;void this.persist().catch(()=>{});}};
    if(this.flow)apply();else void this.ready.then(apply);
  }
  private async allowed(tab:chrome.tabs.Tab){
    if(!tab.id||!tab.url||tab.incognito)return false;
    const u=new URL(tab.url);return ['https:','http:'].includes(u.protocol)&&this.api.permissions.contains({origins:[u.origin+'/*']});
  }
  private async inspectTab(tab:chrome.tabs.Tab,action='inspect',p:Record<string,any>={}){
    await this.api.scripting.executeScript({target:{tabId:tab.id!},files:['content.js']});
    const frame=await this.api.webNavigation.getFrame({tabId:tab.id!,frameId:0});
    if(!frame?.documentId)throw new Error('Scopus sayfa kimliği okunamadı.');
    return this.api.tabs.sendMessage(tab.id!,{kind:'workflow_action',action,p},{documentId:frame.documentId});
  }
  async targets(){
    const result=[];
    for(const tab of await this.api.tabs.query({})){if(!await this.allowed(tab)||platform(tab.url!,tab.title||'')!=='Scopus')continue;
      try{const r=await this.inspectTab(tab);if(r?.recognized)result.push({id:tab.id,windowId:tab.windowId,title:tab.title||'Scopus',urlSafe:new URL(tab.url!).origin+new URL(tab.url!).pathname});}catch{}
    }
    return result;
  }
  async launch(p:Record<string,any>){
    await this.ready;
    if(!await this.api.permissions.contains({permissions:['downloads']}))throw new Error('Önce indirme iznini etkinleştirin.');
    this.registerDownloads();
    const tab=await this.api.tabs.get(p.tabId);
    if(!await this.allowed(tab))throw new Error('Scopus sekmesine erişim izni yok.');
    const observed=await this.inspectTab(tab);if(!observed?.recognized)throw new Error('Seçilen sekme Scopus olarak doğrulanamadı.');
    if(p.id!==undefined&&!id(p.id))throw new Error('Geçersiz iş akışı kimliği.');
    if(this.flow&&this.flow.sessionId!==p.id&&!this.flow.latched)throw new Error('Başka bir iş akışı tarayıcıyı kullanıyor; önce durdurun.');
    await this.api.windows.update(tab.windowId,{focused:true});await this.api.tabs.update(tab.id!,{active:true});
    if(!await this.bind(tab.windowId))throw new Error('Chrome penceresi Windows uygulamasına bağlanamadı.');
    const context={profile:this.profile(),windowId:tab.windowId,tabId:tab.id!};
    const previous=this.flow;
    if(previous&&previous.sessionId===p.id&&previous.context.profile.split('/')[0]!==context.profile.split('/')[0])throw new Error('Tarama farklı bir Chrome profiline ait.');
    this.flow={context,sessionId:p.id,latched:false,watch:previous?.sessionId===p.id?previous?.watch:undefined};await this.persist();
    const active=await this.api.tabs.get(tab.id!),win=await this.api.windows.get(tab.windowId);
    if(!active.active||!win.focused)throw new Error('Başlatma sırasında odak değişti.');
    const session=await this.rpc(p.id?'workflow_resume':'workflow_start',{...(p.id?{id:p.id}:{}),options:p.options||{},context});
    if(this.flow&&!this.flow.sessionId&&id(session?.id)){this.flow.sessionId=session.id;await this.persist();}
    return session;
  }
  private async validate(p:Record<string,any>,release=false){
    const ctx=(release&&!p.context?this.flow?.context:p.context) as Context;
    if(!this.flow||!ctx||!sameContext(ctx,this.flow.context)||ctx.profile!==this.profile()||!id(p.sessionId)||
      this.flow.sessionId&&this.flow.sessionId!==p.sessionId)throw new Error('İş akışı Chrome oturumu veya sekmesi eşleşmiyor.');
    if(!this.flow.sessionId){this.flow.sessionId=p.sessionId;await this.persist();}
    if(release)return;
    if(this.flow.latched)throw new Error('Sekme veya pencere odağı değişti. Devam düğmesiyle yeniden başlatın.');
    const tab=await this.api.tabs.get(ctx.tabId),win=await this.api.windows.get(ctx.windowId);
    if(tab.windowId!==ctx.windowId||!tab.active||!win.focused||!await this.allowed(tab))throw new Error('Scopus sekmesi aktif değil veya erişim izni değişti.');
    if(this.flow.latched)throw new Error('Doğrulama sırasında sekme veya pencere odağı değişti. Devam düğmesini kullanın.');
    return tab;
  }
  private async record(item:chrome.downloads.DownloadItem){
    const watch=this.flow?.watch;
    if(!watch||!matchesDownload(item,watch))return false;
    if(!watch.ids.includes(item.id)){watch.ids.push(item.id);await this.persist();}
    return true;
  }
  handle(type:string,p:Record<string,any>){return this.serial(async()=>{
    const tab=await this.validate(p,type==='workflow_release');
    if(type==='workflow_release'){this.flow=null;await this.persist();return {released:true};}
    if(type==='workflow_guard')return {ready:true};
    if(type==='workflow_browser'){
      if(typeof p.action!=='string')throw new Error('Scopus adımı eksik.');
      const mutating=mutations.has(p.action);
      if(!mutating&&!['inspect','export_inspect'].includes(p.action))throw new Error('Desteklenmeyen Scopus adımı.');
      if(!mutating){const result=await this.inspectTab(tab!,p.action,p);if(result?.error)throw new Error(result.error);return result;}
      if(!id(p.actionId))throw new Error('Yazma adımının benzersiz işlem kimliği eksik.');
      const key=`workflow.action.${p.sessionId}.${p.actionId}`,fingerprint=canonical(p);
      const durable=(await this.api.storage.local.get(key))[key];
      const previous=durable??(await this.api.storage.session.get(key))[key] as any;
      if(previous){
        if(previous.fingerprint!==fingerprint)throw new Error('İşlem kimliği başka bir içerikle tekrar kullanıldı.');
        if(previous.state==='pending')throw new Error('Önceki işlem sonucu belirsiz; aynı tıklama tekrar gönderilmedi.');
        if(previous.result?.error)throw new Error(previous.result.error);
        return previous.result;
      }
      if(p.action==='export_submit'&&(!this.flow?.watch||this.flow.watch.exportId!==p.exportId||this.flow.watch.fingerprint!==exportFingerprint(p)))throw new Error('RIS indirme izlemesi dışa aktarma aralığıyla eşleşmiyor.');
      await this.save(key,{fingerprint,state:'pending'});
      const result=await this.inspectTab(tab!,p.action,p);
      if(!result||typeof result!=='object')throw new Error('Scopus işlem yanıtı alınamadı; sonuç belirsiz.');
      if(this.flow?.latched)throw new Error('İşlem sırasında odak değişti; sonucu doğrulamadan tekrar tıklanmayacak.');
      await this.save(key,{fingerprint,state:'done',result});
      if(result?.error)throw new Error(result.error);
      return result;
    }
    if(type==='workflow_download_arm'){
      if(!await this.api.permissions.contains({permissions:['downloads']}))throw new Error('RIS indirme izni verilmedi.');
      if(!id(p.exportId)||!id(p.stepId))throw new Error('Geçersiz dışa aktarma kimliği.');
      if(!Number.isSafeInteger(p.expectedCount)||p.expectedCount<1)throw new Error('Dışa aktarma kayıt sayısı doğrulanamadı.');
      const start=p.rangeStart??1,end=p.rangeEnd??p.expectedCount;
      if(!Number.isSafeInteger(start)||!Number.isSafeInteger(end)||start<1||end<start||end>p.expectedCount||end-start+1>20000)throw new Error('Geçersiz RIS dışa aktarma aralığı.');
      const watch=this.flow!.watch;
      if(watch&&watch.exportId===p.exportId){
        if(watch.fingerprint!==exportFingerprint(p))throw new Error('Dışa aktarma kimliği başka bir aralık veya adımla eşleşiyor.');
        return {armed:true,exportId:watch.exportId};
      }
      if(watch&&!watch.terminal)throw new Error('Önceki dışa aktarma indirmesi henüz sonuçlanmadı.');
      const observed=await this.inspectTab(tab!);
      if(observed?.data?.count_value!==p.expectedCount||observed?.data?.count_qualifier!=='exact')throw new Error('Dışa aktarma öncesi sonuç sayısı değişmiş.');
      this.flow!.watch={exportId:p.exportId,stepId:p.stepId,fingerprint:exportFingerprint(p),started:Date.now(),pageUrl:tab!.url!,ids:[]};await this.persist();
      return {armed:true,exportId:p.exportId};
    }
    if(type==='workflow_download_status'){
      if(!await this.api.permissions.contains({permissions:['downloads']}))throw new Error('RIS indirme izni kaldırıldı.');
      const watch=this.flow!.watch;if(!watch||watch.exportId!==p.exportId||watch.stepId!==p.stepId||watch.fingerprint!==exportFingerprint(p))throw new Error('Dışa aktarma indirme izlemesi eşleşmiyor.');
      const found=await this.api.downloads.search({startedAfter:new Date(watch.started).toISOString()});
      for(const item of found)await this.record(item);
      if(watch.ids.length>1)return {state:'ambiguous',downloadIds:watch.ids};
      if(!watch.ids.length)return {state:'waiting'};
      const [item]=await this.api.downloads.search({id:watch.ids[0]});
      if(!item||!matchesDownload(item,watch))return {state:'ambiguous',downloadId:watch.ids[0]};
      const filename=item.filename.replace(/\\/g,'/'),directory=`/LiteraturKayit/${this.flow!.sessionId}/`;
      const base=filename.slice(filename.lastIndexOf('/')+1),escaped=watch.exportId.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
      if(item.state==='complete'&&(!filename.includes(directory)||!new RegExp('^'+escaped+'(?: \\(\\d+\\))?\\.ris$','i').test(base)))return {state:'ambiguous',downloadId:item.id,filename:item.filename};
      const state=item.state==='complete'&&item.exists!==false?'complete':item.state==='interrupted'?'interrupted':'waiting';
      if(state==='complete'||state==='interrupted'){watch.terminal=true;await this.persist();}
      return {state,downloadId:item.id,filename:item.filename,error:item.error};
    }
    throw new Error('Desteklenmeyen tarayıcı iş akışı komutu.');
  });}
}

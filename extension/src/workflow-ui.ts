type RPC=(type:string,payload?:Record<string,any>)=>Promise<any>;
const element=<T extends HTMLElement=HTMLElement>(id:string)=>document.getElementById(id) as T;
const node=(tag:string,text:string)=>{const n=document.createElement(tag);n.textContent=text;return n;};
const states:Record<string,string>={queued:'Bekliyor',opening:'Arama açılıyor',filling:'Sorgu hazırlanıyor',submitting:'Sorgu gönderiliyor',waiting:'Sonuç bekleniyor',capturing:'Görüntü alınıyor',captured:'Kanıt kaydedildi',exporting:'RIS indiriliyor',importing:'Zotero’ya aktarılıyor',done:'Tamamlandı',running:'Çalışıyor',paused:'Durakladı',completed:'Tamamlandı',stopped:'Durduruldu'};

export function setupWorkflow(rpc:RPC,message:(text:string,error?:boolean)=>void){
  let session:any=null,polling=false,loading=false,initialized=false,commands=0;
  async function browser(kind:string,payload:Record<string,any>={}){
    const reply=await chrome.runtime.sendMessage({kind,payload});
    if(!reply?.ok)throw new Error(reply?.error||'Chrome bağlantısı kurulamadı.');
    return reply.data;
  }
  function click(id:string,handler:()=>Promise<unknown>){
    const b=element<HTMLButtonElement>(id);
    b.addEventListener('click',()=>{b.disabled=true;commands++;void handler().catch(e=>message(e.message,true)).finally(()=>{commands--;b.disabled=false;void status();});});
  }
  async function targets(){
    const result=await browser('workflow_targets');
    const select=element<HTMLSelectElement>('workflow-target');const old=select.value;
    select.replaceChildren(new Option('Scopus sekmesini seçin',''));
    for(const tab of result.tabs??result.targets??result)select.add(new Option(tab.title+' · '+tab.urlSafe,String(tab.id)));
    if([...select.options].some(o=>o.value===old))select.value=old;
    else if(select.options.length===2)select.selectedIndex=1;
  }
  async function permissions(){
    const granted=await chrome.permissions.request({permissions:['downloads']});
    if(!granted)throw new Error('RIS dosyalarını izlemek için indirme izni gerekli.');
    message('İndirme izni hazır.');
  }
  async function start(resume=false){
    const selected=element<HTMLSelectElement>('workflow-target').value;
    if(!selected)throw new Error('Önce izin verilmiş Scopus sekmesini seçin.');
    await browser('workflow_launch',{tabId:Number(selected),...(resume?{id:session.id}:{}),options:{include_review:element<HTMLInputElement>('workflow-review').checked}});
    message('Tarama başladı. Scopus önde kalsın; durum için yönetim ekranına dönersen tarama duraklar.');
  }
  async function status(){
    if(polling||commands)return;polling=true;
    try{
      const result=await rpc('workflow_status');session=result.session;
      const active=!!session&&!['completed','stopped'].includes(session.state);
      element<HTMLButtonElement>('workflow-start').disabled=active||result.running;
      element<HTMLButtonElement>('workflow-resume').disabled=!active||result.running;
      element<HTMLButtonElement>('workflow-pause').disabled=!result.running;
      element<HTMLButtonElement>('workflow-stop').disabled=!active;
      element<HTMLInputElement>('workflow-review').disabled=active;
      const box=element('workflow-progress');box.replaceChildren();
      if(!session){box.append(node('p','Henüz otomatik tarama başlatılmadı.'));return;}
      box.append(node('h2',states[session.state]||session.state));
      box.append(node('p','Oturum '+session.id.slice(0,8)+' · Gerçek çalışma süresi: '+Math.round(session.elapsed)+' saniye'));
      if(session.error){const error=node('p',session.error);error.className='notice error';box.append(error);}
      const totals=session.totals||{};
      box.append(node('p',`Ham RIS: ${totals.raw??0} · Zotero ile eşleşen benzersiz Scopus kaydı: ${totals.unique??0} · Kontrol bekleyen benzerlik: ${totals.suspects??0}`));
      for(const step of session.steps){
        const item=document.createElement('details');item.className='panel';
        item.append(node('summary',`${step.code} · ${step.label} — ${states[step.state]||step.state}${step.display_id?' · '+step.display_id:''}${step.count_value==null?'':' · '+step.count_value+' sonuç'}`));
        item.append(node('p',step.query));
        for(const exp of step.exports)item.append(node('p',`${exp.range_start}–${exp.range_end}: ${exp.state==='complete'?'Doğrulandı':exp.state} · ${exp.record_count??'?'} künye${exp.relative_path?' · '+exp.relative_path:''}`));
        const z=step.detail?.zotero;
        if(z)item.append(node('p',`Zotero: ${z.imported} yeni, ${z.reused} mevcut, ${z.failed} başarısız.`));
        const excel=step.detail?.excel;
        if(excel)item.append(node('p','Excel: '+excel.path+(excel.status==='updated'?'':' (özgün dosya korundu; ayrı sürüm)')));
        box.append(item);
      }
    }catch(e){message((e as Error).message,true);}finally{polling=false;}
  }
  async function initialize(){
    if(location.hash!=='#automation'||loading)return;loading=true;
    try{
      if(!initialized){
        const catalog=await rpc('workflow_catalog');
        element('workflow-project').textContent=catalog.project_root;
        element('workflow-library').textContent=catalog.library+' → 01_Aday + 00_AramaKayitlari';
        element('workflow-clock').textContent=catalog.clock_confirmed?'Saat/tarih için ilk PNG kontrolü kayıtlı.':'Önce Ayarlar’da test PNG’sinin saat/tarih kontrolünü tamamlayın.';
        const list=element('workflow-queries');list.replaceChildren(node('h3','Başlangıç (yıl ve yayın türü sınırı yok)'),node('p',catalog.initial));
        for(const [code,label,query] of catalog.topics)list.append(node('h3',code+' · '+label),node('p','TITLE-ABS-KEY('+query+')'));
        await targets();initialized=true;
      }
      await status();
    }catch(e){message((e as Error).message,true);}finally{loading=false;}
  }
  click('workflow-targets',targets);click('workflow-downloads',permissions);
  click('workflow-zotero',async()=>{const r=await rpc('workflow_zotero');element('workflow-zotero-status').textContent=r.message||'Zotero bağlantısı hazır.';});
  click('workflow-authorize',async()=>{
    element('workflow-zotero-status').textContent='Zotero penceresindeki izin isteğini yanıtlayın…';
    const r=await rpc('workflow_authorize_zotero');element('workflow-zotero-status').textContent=r.message||'Yazma izni hazır.';
  });
  click('workflow-start',()=>start());click('workflow-resume',()=>start(true));
  click('workflow-pause',()=>rpc('workflow_pause',{id:session.id}));click('workflow-stop',()=>rpc('workflow_stop',{id:session.id}));
  addEventListener('hashchange',()=>void initialize());void initialize();
  setInterval(()=>{if(location.hash==='#automation')void status();},2000);
}

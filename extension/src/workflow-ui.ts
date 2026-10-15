type RPC=(type:string,payload?:Record<string,any>)=>Promise<any>;
const element=<T extends HTMLElement=HTMLElement>(id:string)=>document.getElementById(id) as T;
const node=(tag:string,text:string)=>{const n=document.createElement(tag);n.textContent=text;return n;};
const states:Record<string,string>={queued:'Bekliyor',opening:'Arama açılıyor',filling:'Sorgu hazırlanıyor',submitting:'Sorgu gönderiliyor',waiting:'Sonuç bekleniyor',capturing:'Görüntü alınıyor',captured:'Kanıt kaydedildi',exporting:'RIS indiriliyor',importing:'Zotero’ya aktarılıyor',done:'Tamamlandı',running:'Çalışıyor',paused:'Durakladı',completed:'Tamamlandı',stopped:'Durduruldu'};

export function setupWorkflow(rpc:RPC,message:(text:string,error?:boolean)=>void){
  let session:any=null,polling=false,loading=false,initialized=false,commands=0,packageRevision='',dirty=false;
  const topicBox=element('query-package-topics');
  function markDirty(){
    dirty=true;element('query-package-state').textContent='Kaydedilmemiş değişiklikler var. Yeni taramadan önce kaydet.';
    element<HTMLButtonElement>('workflow-start').disabled=true;
  }
  function topicRow(topic:{code:string;label:string;query:string}){
    const row=document.createElement('fieldset');row.dataset.code=topic.code;row.append(node('legend',topic.code));
    const label=document.createElement('label');label.htmlFor='topic-label-'+topic.code;label.textContent='Konu adı';
    const name=document.createElement('input');name.id=label.htmlFor;name.name='label';name.required=true;name.maxLength=120;name.value=topic.label;
    const queryLabel=document.createElement('label');queryLabel.htmlFor='topic-query-'+topic.code;queryLabel.textContent='Arama terimleri / kavram blokları';
    const query=document.createElement('textarea');query.id=queryLabel.htmlFor;query.name='query';query.required=true;query.maxLength=4096;query.value=topic.query;
    const help=node('p','Yalnız kavram bloklarını yaz; TITLE-ABS-KEY(...), yıl ve yayın türü uygulama tarafından eklenir.');help.className='muted';
    const remove=document.createElement('button');remove.type='button';remove.className='secondary';remove.textContent='Bu konuyu çıkar';
    remove.addEventListener('click',()=>{row.remove();markDirty();});
    row.append(label,name,queryLabel,query,help,remove);topicBox.append(row);
  }
  function renderPackage(catalog:any){
    const p=catalog.package;packageRevision=catalog.revision;dirty=false;
    element<HTMLInputElement>('query-package-name').value=p.name;
    element<HTMLTextAreaElement>('query-package-initial').value=p.initial;
    topicBox.replaceChildren();for(const topic of p.topics)topicRow(topic);
    element('query-package-path').textContent=catalog.path;
    element('query-package-state').textContent='Kaydedildi. '+p.topics.length+' konu; yeni taramada bu paket kullanılacak.';
    const list=element('workflow-queries');list.replaceChildren(node('h3',p.name),node('h4','Başlangıç'),node('p',p.initial));
    for(const t of p.topics)list.append(node('h4',t.code+' · '+t.label),node('p','TITLE-ABS-KEY('+t.query+')'));
  }
  async function catalog(){
    const result=await rpc('workflow_catalog');renderPackage(result);
    element('workflow-project').textContent=result.project_root;
    element('workflow-library').textContent=result.library+' → 01_Aday + 00_AramaKayitlari';
    element('workflow-clock').textContent=result.clock_confirmed?'Saat/tarih için ilk PNG kontrolü kayıtlı.':'Önce Ayarlar’da test PNG’sinin saat/tarih kontrolünü tamamlayın.';
  }
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
    if(old&&[...select.options].some(o=>o.value===old))select.value=old;
    else if(select.options.length===2)select.selectedIndex=1;
  }
  async function permissions(){
    const granted=await chrome.permissions.request({permissions:['downloads']});
    if(!granted)throw new Error('RIS dosyalarını izlemek için indirme izni gerekli.');
    message('İndirme izni hazır.');
  }
  async function start(resume=false){
    if(!resume&&(dirty||!packageRevision))throw new Error('Önce sorgu paketini yükleyip değişikliklerini kaydet.');
    const selected=element<HTMLSelectElement>('workflow-target').value;
    if(!selected)throw new Error('Önce izin verilmiş Scopus sekmesini seçin.');
    await browser('workflow_launch',{tabId:Number(selected),...(resume?{id:session.id}:{}),options:{include_review:element<HTMLInputElement>('workflow-review').checked,package_revision:packageRevision}});
    message('Tarama başladı. Scopus önde kalsın; durum için yönetim ekranına dönersen tarama duraklar.');
  }
  async function status(){
    if(polling||commands)return;polling=true;
    try{
      const result=await rpc('workflow_status');if(commands)return;session=result.session;
      const active=!!session&&!['completed','stopped'].includes(session.state);
      element<HTMLButtonElement>('workflow-start').disabled=active||result.running||dirty||!packageRevision;
      element<HTMLButtonElement>('workflow-resume').disabled=!active||result.running;
      element<HTMLButtonElement>('workflow-pause').disabled=!result.running;
      element<HTMLButtonElement>('workflow-stop').disabled=!active;
      element<HTMLInputElement>('workflow-review').disabled=active;
      element<HTMLFieldSetElement>('query-package-fields').disabled=active||result.running;
      const box=element('workflow-progress');box.replaceChildren();
      if(!session){box.append(node('p','Henüz otomatik tarama başlatılmadı.'));return;}
      box.append(node('h2',states[session.state]||session.state));
      box.append(node('p','Oturum '+session.id.slice(0,8)+' · Gerçek çalışma süresi: '+Math.round(session.elapsed)+' saniye'));
      if(session.snapshot?.package_name)box.append(node('p','Bu taramanın paketi: '+session.snapshot.package_name));
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
        const results=await Promise.allSettled([catalog(),targets()]);
        for(const result of results)if(result.status==='rejected')message(result.reason.message,true);
        initialized=true;
      }
      await status();
    }catch(e){message((e as Error).message,true);}finally{loading=false;}
  }
  click('workflow-targets',targets);click('workflow-downloads',permissions);
  element('query-package-form').addEventListener('input',markDirty);
  element('query-topic-add').addEventListener('click',()=>{
    const used=new Set([...topicBox.children].map(e=>(e as HTMLElement).dataset.code));
    if(used.size>=20){message('En fazla 20 konu ekleyebilirsin.',true);return;}
    let n=1;while(used.has('Q'+String(n).padStart(2,'0')))n++;
    topicRow({code:'Q'+String(n).padStart(2,'0'),label:'',query:''});markDirty();
  });
  element<HTMLFormElement>('query-package-form').addEventListener('submit',event=>{
    event.preventDefault();if(commands)return;commands++;
    const button=element<HTMLButtonElement>('query-package-save');button.disabled=true;
    element<HTMLFieldSetElement>('query-package-fields').disabled=true;
    const payload={schema:1,name:element<HTMLInputElement>('query-package-name').value,initial:element<HTMLTextAreaElement>('query-package-initial').value,
      topics:[...topicBox.children].map(e=>({code:(e as HTMLElement).dataset.code,label:e.querySelector<HTMLInputElement>('input[name=label]')!.value,query:e.querySelector<HTMLTextAreaElement>('textarea[name=query]')!.value}))};
    void rpc('workflow_save_package',{package:payload,revision:packageRevision}).then(result=>{
      renderPackage(result);message('Sorgu paketi kaydedildi. Yeniden build gerekmez.');
    }).catch(e=>message(e.message,true)).finally(()=>{commands--;button.disabled=false;void status();});
  });
  click('query-package-reload',catalog);
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

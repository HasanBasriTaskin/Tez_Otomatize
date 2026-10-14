export {};
const $=<T extends HTMLElement=HTMLElement>(id:string)=>document.getElementById(id) as T;
const value=(id:string)=>$(id) as HTMLInputElement;
const info=$('message');let currentJob='';let currentPaper='';let offset=0;let pendingOffset=0;let paperOffset=0;let paused=false;
let settings:Record<string,any>={};let noteTemplate='';
function message(text:string,error=false){info.textContent=text;info.classList.toggle('error',error);}
async function rpc(type:string,payload:Record<string,any>={}){
  const reply=await chrome.runtime.sendMessage({kind:'rpc',type,payload});
  if(!reply?.ok)throw new Error(reply?.error||'Windows bağlantısı kesildi. Kurulumu kontrol edin.');
  return reply.data;
}
function on(id:string,handler:()=>Promise<unknown>){$(id).addEventListener('click',()=>void action($(id) as HTMLButtonElement,handler));}
async function action(button:HTMLButtonElement,handler:()=>Promise<unknown>){
  button.disabled=true;try{await handler();}catch(e){message((e as Error).message,true);}finally{button.disabled=false;}
}
function el<K extends keyof HTMLElementTagNameMap>(tag:K,text?:string){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;return e;}
function button(label:string,handler:()=>Promise<unknown>){const b=el('button',label);b.className='secondary';b.addEventListener('click',()=>void action(b,handler));return b;}
function empty(container:HTMLElement,title:string,body:string){container.replaceChildren();const box=el('div');box.className='empty';box.append(el('strong',title),el('p',body));container.append(box);}
function date(stamp:string){return stamp?new Intl.DateTimeFormat('tr-TR',{dateStyle:'short',timeStyle:'short',timeZone:'Europe/Istanbul'}).format(new Date(stamp)):'Bilinmiyor';}
function navigate(){
  const id=location.hash.slice(1)||'records';
  for(const s of document.querySelectorAll<HTMLElement>('main>section'))s.hidden=s.id!==id;
  for(const a of document.querySelectorAll('nav a'))a.setAttribute('aria-current',a.getAttribute('href')==='#'+id?'page':'false');
}
addEventListener('hashchange',navigate);navigate();
document.querySelectorAll<HTMLButtonElement>('[data-close]').forEach(b=>b.addEventListener('click',()=>$(b.dataset.close!) instanceof HTMLDialogElement&&($(b.dataset.close!) as HTMLDialogElement).close()));

async function loadStatus(){
  const s=await rpc('status');settings=s.settings;paused=s.paused;noteTemplate=s.note_template;
  $('connection-label').textContent=paused?'Yakalama duraklatıldı':'Windows bağlantısı hazır';
  $('project-root').textContent=s.project_root;
  $('stats').replaceChildren();
  for(const [n,t] of [[s.run_count,'arama'],[s.pending_count,'eksik kayıt']]){const cell=el('div');cell.append(el('strong',String(n)),el('span',String(t)));$('stats').append(cell);}
  $('pending-badge').textContent=s.pending_count?'('+s.pending_count+')':'';
  for(const [id,key] of Object.entries({'project-name':'project_name','team-code':'team_code',operator:'operator',hotkey:'hotkey','zotero-mode':'zotero_mode',library:'library'}))value(id).value=settings[key]||'';
  const select=$<HTMLSelectElement>('monitor');select.replaceChildren(new Option('Chrome’un bulunduğu monitörün tamamı','active'),new Option('Tüm monitörler','all'));
  for(let i=1;i<s.monitors.length;i++)select.add(new Option(`Monitör ${i} (${s.monitors[i].width} × ${s.monitors[i].height})`,String(i)));
  select.value=String(settings.monitor);value('clock-confirmed').checked=settings.clock_confirmed;
  $('pause').textContent=paused?'Yakalamayı sürdür':'Yakalamayı duraklat';
  if(s.hotkey_error)message(s.hotkey_error,true);
  else if(!settings.clock_confirmed)message('İlk testte PNG’yi açıp Windows saatinin ve tarihin göründüğünü kontrol et. Ardından Ayarlar bölümündeki kontrolü işaretle.');
  else message('Hazır. Sonuç sayfasına dönüp '+settings.hotkey+' kullanabilirsin.');
}
async function loadRuns(){
  const r=await rpc('list_runs',{offset});const container=$('run-list');
  if(!r.rows.length)empty(container,'Henüz arama kaydı yok','İlk aramanı Chrome’da Ctrl+M ile kaydet.');
  else{
    const wrap=el('div');wrap.className='table-wrap';const table=el('table');const head=el('tr');
    for(const label of ['Arama','Platform ve sorgu','Sonuç','Kayıt zamanı',''])head.append(el('th',label));
    const thead=el('thead');thead.append(head);table.append(thead);const body=el('tbody');
    for(const run of r.rows){const row=el('tr');row.append(el('td',run.display_id));const query=el('td');query.className='query';query.append(el('strong',run.database_name),el('div',run.query_preview));row.append(query,el('td',String(run.count_value)+(run.count_qualifier==='at_least'?'+':run.count_qualifier==='approximate'?' (yaklaşık)':'')),el('td',date(run.observed_at_utc)));const cell=el('td');cell.append(button('Aç',()=>openRun(run.id)));row.append(cell);body.append(row);}
    table.append(body);wrap.append(table);container.replaceChildren(wrap);
  }
  $('page-number').textContent=`${Math.floor(offset/50)+1} / ${Math.max(1,Math.ceil(r.total/50))}`;
  ($('prev') as HTMLButtonElement).disabled=offset===0;($('next') as HTMLButtonElement).disabled=offset+50>=r.total;
}
async function openRun(id:string){
  const {run,captures}=await rpc('get_run',{id});$('record-title').textContent=run.display_id+' · '+run.database_name;
  const body=$('record-body');body.replaceChildren(el('p',run.query_raw),el('p','Sonuç: '+run.count_raw),el('p','Filtre: '+JSON.parse(run.filters_json).join(', ')));
  const controls=el('div');controls.className='actions';
  controls.append(button('Klasörü aç',()=>rpc('open_folder',{runId:id})));
  for(const [role,label] of [['sorgu','Sorgu görüntüsü ekle'],['filtre','Filtre görüntüsü ekle']])controls.append(button(label,async()=>{await rpc('next_capture',{attach_to:id,role});$<HTMLDialogElement>('record-dialog').close();message(run.display_id+' için sonuç sayfasına dönüp Ctrl+M yap. Sorgu ve filtre değişmemiş olmalı.');}));
  body.append(controls);
  for(const cap of captures){const item=el('div');item.className='record';item.append(el('span',cap.relative_path),button('PNG’yi aç',()=>rpc('open_capture',{id:cap.id})));body.append(item);}
  const label=el('label','Açıklama');const notes=el('textarea');notes.value=run.notes||'';label.append(notes);body.append(label,button('Açıklamayı kaydet',async()=>{await rpc('update_run',{id,notes:notes.value});message('Açıklama kaydedildi.');}));
  $<HTMLDialogElement>('record-dialog').showModal();
}
async function loadPending(){
  const r=await rpc('list_pending',{offset:pendingOffset});const box=$('pending-list');box.replaceChildren();
  if(!r.rows.length&&pendingOffset>0){pendingOffset=Math.max(0,pendingOffset-50);return loadPending();}
  if(!r.rows.length){empty(box,'Tamamlanacak kayıt yok','Eksik veya belirsiz yakalamalar burada görünür.');return;}
  for(const job of r.rows){const item=el('div');item.className='record';const details=el('div');details.append(el('strong',date(job.created_at)),el('p',job.error||'Kontrol bekliyor'));item.append(details,button('Kontrol et',()=>openDraft(job.id)));box.append(item);}
  const pager=el('div');pager.className='actions pager';
  const prev=button('Önceki eksik kayıtlar',async()=>{pendingOffset-=50;await loadPending();});prev.disabled=pendingOffset===0;
  const next=button('Sonraki eksik kayıtlar',async()=>{pendingOffset+=50;await loadPending();});next.disabled=pendingOffset+50>=r.total;
  pager.append(prev,el('span',`${pendingOffset+1}–${pendingOffset+r.rows.length} / ${r.total}`),next);box.append(pager);
}
async function openDraft(id:string){
  currentJob=id;const job=await rpc('get_job',{id});const data=JSON.parse(job.extraction_json||'{}');
  const saved=(await chrome.storage.local.get('draft:'+id))['draft:'+id] as Record<string,string>|undefined;
  const base:Record<string,string>={database:data.database||'',query:data.query_raw||'',fields:data.fields||'',filters:(data.filters||[]).join('\n'),
    count:data.count_value==null?'':String(data.count_value),qualifier:['exact','approximate','at_least'].includes(data.count_qualifier)?data.count_qualifier:'exact',
    'count-raw':data.count_raw||'','draft-notes':data.notes||'',role:'sonuc','attach-to':''};
  for(const [key,val] of Object.entries({...base,...saved}))if(document.getElementById(key))value(key).value=val;
  value('draft-confirm').checked=false;$('draft-reason').textContent=job.error||'';
  const preview=await rpc('thumbnail',{jobId:id});$<HTMLImageElement>('draft-preview').src=preview.data||'';$('draft-preview').hidden=!preview.data;
  $<HTMLDialogElement>('draft-dialog').showModal();
}
$('draft-form').addEventListener('input',()=>{
  if(!currentJob)return;const fields:Record<string,string>={};
  for(const id of ['database','query','fields','filters','count','qualifier','count-raw','draft-notes','role','attach-to'])fields[id]=value(id).value;
  void chrome.storage.local.set({['draft:'+currentJob]:fields});
});
$('draft-form').addEventListener('submit',event=>{event.preventDefault();void action($('draft-form').querySelector('button[type=submit]')!,async()=>{
  const data={database:value('database').value,query_raw:value('query').value,fields:value('fields').value,filters:value('filters').value.split('\n').map(s=>s.trim()).filter(Boolean),
    count_value:Number(value('count').value),count_raw:value('count-raw').value||value('count').value,count_qualifier:value('qualifier').value,notes:value('draft-notes').value};
  const r=await rpc('save_draft',{id:currentJob,data,confirmed:value('draft-confirm').checked,attach_to:value('attach-to').value.trim(),role:value('role').value});
  await chrome.storage.local.remove('draft:'+currentJob);$<HTMLDialogElement>('draft-dialog').close();await refresh();message(r.run.display_id+' kaydedildi.'+(r.warning?' '+r.warning:''));
});});
async function refresh(){await loadStatus();await Promise.all([loadRuns(),loadPending()]);}
on('refresh',refresh);on('prev',async()=>{offset=Math.max(0,offset-50);await loadRuns();});on('next',async()=>{offset+=50;await loadRuns();});
on('new-next',async()=>{await rpc('next_capture',{new_run:true});message('Sonraki Ctrl+M yeni bir arama kaydı oluşturacak.');});
on('open-original',()=>rpc('open_capture',{jobId:currentJob}));
on('import-png',async()=>{const r=await rpc('import_png');if(!r.cancelled){await loadPending();await openDraft(r.id);}});
on('export-excel',async()=>{const r=await rpc('export_excel');message('Excel kaydedildi: '+r.path+(r.status==='updated'?'':'\nÖzgün dosya korundu; ayrı sürüm oluşturuldu.'));});
on('pause',async()=>{await rpc(paused?'resume':'pause');await loadStatus();});
on('pick-project',async()=>{await rpc('pick_project');await refresh();});
on('open-project',()=>rpc('open_folder',{folder:'project'}));on('open-outputs',()=>rpc('open_folder',{folder:'outputs'}));on('open-backups',()=>rpc('open_folder',{folder:'backups'}));
$('settings-form').addEventListener('submit',event=>{event.preventDefault();void action($('settings-form').querySelector('button[type=submit]')!,async()=>{
  await rpc('update_settings',{project_name:value('project-name').value,team_code:value('team-code').value,operator:value('operator').value,
    hotkey:value('hotkey').value,monitor:value('monitor').value,clock_confirmed:value('clock-confirmed').checked});await loadStatus();
});});
on('save-zotero',async()=>{settings=await rpc('update_settings',{zotero_mode:value('zotero-mode').value,library:value('library').value.trim()});message('Zotero bağlantı ayarları kaydedildi.');});
on('save-key',async()=>{await rpc('zotero_key',{key:value('api-key').value});value('api-key').value='';message('Anahtar Windows kimlik bilgileri deposuna kaydedildi.');});
on('copy-template',async()=>{await navigator.clipboard.writeText(noteTemplate);message('Not şablonu kopyalandı. Zotero’da makaleye bağlı bir nota yapıştır.');});
on('get-collections',async()=>{
  const r=await rpc('zotero_collections');const box=$('collection-mapping');box.replaceChildren();
  for(const [key,label] of Object.entries({candidate:'Aday',title_abstract:'Başlık/özet geçti',included:'Tam metin dahil',excluded:'Hariç'})){
    const wrapper=el('div');const select=el('select');select.id='collection-'+key;select.add(new Option('Eşleştirme yok',''));
    for(const c of r.rows)select.add(new Option(c.name,c.key));select.value=settings.collection_mapping?.[key]||'';
    const title=el('label',label);title.htmlFor=select.id;wrapper.append(title,select);box.append(wrapper);
  }$('save-mapping').hidden=false;
});
on('save-mapping',async()=>{const map:Record<string,string>={};for(const key of ['candidate','title_abstract','included','excluded'])map[key]=value('collection-'+key).value;settings=await rpc('update_settings',{collection_mapping:map});message('Koleksiyon eşleştirmesi kaydedildi.');});
async function loadPapers(){
  const r=await rpc('list_papers',{offset:paperOffset});const box=$('paper-list');box.replaceChildren();
  if(!r.rows.length){empty(box,'Bu sayfada kaynak yok','Zotero koleksiyonlarını eşleştirip Zotero’dan oku düğmesini kullan.');return;}
  const names:Record<string,string>={candidate:'Aday',included:'Dahil',excluded:'Hariç',conflict:'Çelişki',unavailable:'Zotero’da artık bulunamıyor'};
  for(const p of r.rows){const item=el('div');item.className='record';const text=el('div');text.append(el('strong',p.title),el('p',p.key+' · '+names[p.state]+(p.verified?' · Anotasyon kontrol edildi':'')));item.append(text,button('Notları aç',()=>openPaper(p.id)));box.append(item);}
}
on('sync-zotero',async()=>{message('Zotero okunuyor…');const r=await rpc('zotero_sync');paperOffset=0;await loadPapers();message(`${r.count} kaynak okundu. ${r.conflicts} çelişki. DOI tekrar adayı: ${r.duplicates.length}.`);});
on('more-papers',async()=>{paperOffset+=100;await loadPapers();});
async function openPaper(id:string){
  currentPaper=id;const r=await rpc('get_paper',{id});const data=JSON.parse(r.paper.data_json);
  $('paper-title').textContent=data.title;$('paper-state').textContent='Koleksiyon durumu: '+r.paper.state+'. Zotero notu asıl kayıttır.';
  $('paper-annotation').textContent=r.paper.annotation||'Zotero notunda Anotasyon alanı yok.';
  $('paper-fields').textContent=Object.entries(JSON.parse(r.notes.fields_json||'{}')).map(([k,v])=>k+': '+v).join('\n\n');
  value('local-draft').value=r.notes.local_draft||'';value('paper-links').value=r.links.join(', ');value('paper-verified').checked=!!r.paper.verified;
  $<HTMLDialogElement>('paper-dialog').showModal();
}
on('save-paper',async()=>{await rpc('update_paper',{id:currentPaper,verified:value('paper-verified').checked,local_draft:value('local-draft').value});await rpc('link_paper',{paper_id:currentPaper,search_ids:value('paper-links').value.split(',').map(x=>x.trim()).filter(Boolean)});$<HTMLDialogElement>('paper-dialog').close();await loadPapers();message('Kaynak kontrolü kaydedildi.');});
async function output(kind:string){const r=await rpc('export_deliverables',{kind,draft:value('draft-export').checked});$('export-report').hidden=false;$('export-report').textContent=JSON.stringify(r,null,2);message('Çıktı oluşturuldu. Eksik alanlar varsa raporda listelendi.');}
on('sources-export',()=>output('sources'));on('evidence-export',()=>output('evidence'));
on('backup',async()=>{const r=await rpc('backup');message('Yedek kaydedildi: '+r.path);});
on('restore',async()=>{const r=await rpc('restore');if(!r.cancelled)message('Yeni klasöre geri yüklendi: '+r.path+'\nBu projeye geçmek için Ayarlar → Proje klasörü seç.');});
void refresh().then(loadPapers).catch(e=>{$('connection-label').textContent='Windows bağlantısı yok';message('Windows uygulamasına bağlanılamadı. Kurulum paketindeki Kurulum.exe dosyasını çalıştır, ardından Yenile düğmesini kullan. Taslakların korunur.\n'+e.message,true);});

import {extract, platform, visible, parseCount, type Extraction} from './adapters';

type Params=Record<string,any>;
type Root=Document|Element;
const text=(e:Element|null)=>(e?.textContent||'').replace(/\s+/g,' ').trim();
const tokenized=(q:string)=>(q.match(/"(?:\\.|[^"\\])*"|[\p{L}\p{N}_-]+|[^\s]/gu)||[]).join('\u001f');
const matchesQuery=(a:string,b:string)=>tokenized(a)===tokenized(b);
const list=(root:Root,selector:string)=>Array.from(root.querySelectorAll<HTMLElement>(selector)).filter(visible);
function name(e:Element):string {
  const labelled=e.getAttribute('aria-labelledby');
  if(labelled)return labelled.split(/\s+/).map(id=>text(e.ownerDocument.getElementById(id))).join(' ').trim();
  const aria=e.getAttribute('aria-label');if(aria)return aria.trim();
  if(e.matches('input,textarea,select')){
    const labels=(e as HTMLInputElement).labels;
    if(labels?.length)return Array.from(labels).map(text).join(' ');
  }
  return text(e);
}
function unique<T extends Element>(items:T[],description:string):T {
  if(items.length!==1)throw new Error(description+' kesin olarak bulunamadı (aday: '+items.length+').');
  return items[0];
}
function editable(e:Element){return !e.matches(':disabled,[readonly],[aria-disabled="true"]');}
function click(e:HTMLElement){
  if(!visible(e)||!editable(e))throw new Error('Scopus kontrolü etkin değil.');
  if(e.matches('a')){
    const target=new URL((e as HTMLAnchorElement).href,e.ownerDocument.URL),source=new URL(e.ownerDocument.URL);
    if(!['http:','https:'].includes(target.protocol)||target.origin!==source.origin||e.getAttribute('target')==='_blank')
      throw new Error('Scopus bağlantısının hedefi desteklenmiyor.');
  }
  e.click();
}
function buttons(root:Root,pattern:RegExp){return list(root,'button,[role="button"],input[type="submit"]').filter(e=>pattern.test(name(e)));}
function editors(doc:Document){
  return list(doc,'textarea,[contenteditable="true"],[contenteditable=""]')
    .filter(e=>e.id==='advancedQueryTextArea'||!!e.closest('#pendo-advanced-search-bar')||/^Advanced (?:search )?query$/i.test(name(e)));
}
function queryValue(e:HTMLElement){return e.matches('textarea')?(e as HTMLTextAreaElement).value:e.textContent||'';}
function validateQuery(p:Params):string {
  const q=p.query;
  if(typeof q!=='string'||q.length>16000||!/^TITLE-ABS-KEY\s*\(\s*\S/i.test(q)||/[\u0000-\u0008\u000b\u000c]/.test(q))
    throw new Error('Tam TITLE-ABS-KEY sorgusu gerekli.');
  let depth=0,quote=false,braces=0;
  for(let i=0;i<q.length;i++){
    const c=q[i];if(c==='"'&&q[i-1]!=='\\'){quote=!quote;continue;}if(quote)continue;
    if(c==='{')braces++;if(c==='}'&&--braces<0)throw new Error('Sorgu tamamlanmamış.');if(braces)continue;
    if(c==='(')depth++;if(c===')'&&--depth<0)throw new Error('Sorgu tamamlanmamış.');
  }
  if(depth||quote||braces||/\b(?:AND|OR|NOT)\s*$/i.test(q)||/[><=]\s*$/.test(q))throw new Error('Sorgu tamamlanmamış.');
  return q;
}
async function setText(e:HTMLElement,value:string){
  if(!editable(e))throw new Error('Scopus alanı düzenlenemiyor.');
  const w=e.ownerDocument.defaultView!;e.focus();
  if(e.matches('input,textarea')){
    const proto=e.matches('textarea')?w.HTMLTextAreaElement.prototype:w.HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto,'value')!.set!.call(e,value);
  }else e.textContent=value;
  e.dispatchEvent(new w.InputEvent('input',{bubbles:true,inputType:'insertText',data:value}));
  e.dispatchEvent(new w.Event('change',{bubbles:true}));
  // Let event-driven controlled state flush before blur commits its draft.
  await Promise.resolve();e.blur();await Promise.resolve();
}
function exportDialogs(doc:Document){
  return list(doc,'[role="dialog"],dialog[open]').filter(e=>/^Export(?: documents| results| references)?$/i.test(name(e))||
    list(e,'h1,h2,h3').some(h=>/^Export(?: documents| results| references)?$/i.test(text(h))));
}
function statusEvidence(doc:Document){
  const messages=[...new Set(list(doc,'[role="status"],[role="alert"]').map(text).filter(t=>t.length<1500&&/\bexport\b/i.test(t)))];
  const statuses=messages.map(t=>/failed|error|unable|cancelled/i.test(t)?'failed':
    /ready (?:to|for) download|export (?:is |has been )?(?:ready|complete|completed)/i.test(t)?'ready':
    /prepar|progress|processing|queued|exporting/i.test(t)?'pending':'unknown');
  return {status:new Set(statuses).size===1?statuses[0]:'unknown',messages,completed:false,correlated:false};
}
function inspect(doc:Document,url:string,p:Params){
  const data=extract(doc,url);let recognized=false;
  try{const u=new URL(url);recognized=['http:','https:'].includes(u.protocol)&&platform(url,doc.title)==='Scopus'&&/^\/pages\/(?:home|search(?:\/[^/]+)?)\/?$/.test(u.pathname);}catch{}
  const heads=list(doc,'h1,h2,[role="alert"],[role="dialog"] h3').map(text);
  const challenge=heads.some(t=>/captcha|verify (?:that )?you are human|access denied|checking your browser|erişim reddedildi/i.test(t))||
    list(doc,'iframe').some(e=>/captcha|challenge/i.test(e.getAttribute('src')||''));
  const login=heads.some(t=>/sign in(?: to|$)|log in(?: to|$)|login required|institutional login|oturum aç/i.test(t));
  const loading=list(doc,'[aria-busy="true"],[role="progressbar"]').length>0;
  const dialogs=exportDialogs(doc),status=statusEvidence(doc);
  const advancedLinks=list(doc,'button,a,[role="button"]').filter(e=>/^(?:Edit in advanced search|Advanced document search)$/i.test(name(e)));
  const editorReady=editors(doc).length===1;
  const stage=!recognized?'unsupported':challenge?'challenge':login?'login':loading?'loading':dialogs.length?'export-dialog':
    editors(doc).length?'search':data.source==='scopus_publications_dom'?'results':advancedLinks.length?'search':status.messages.length?'export-status':'unsupported';
  return {recognized,stage,editorReady,nextAction:stage==='search'?(editorReady?'fill_search':'open_search'):'inspect',data,queryMatches:typeof p.query==='string'?data.query_verified&&matchesQuery(data.query_raw,p.query):null,
    countMatches:Number.isSafeInteger(p.expectedCount)?data.count_qualifier==='exact'&&data.count_value===p.expectedCount:null,
    blockers:['challenge','login','loading','unsupported'].includes(stage)?[stage]:[],
    support:data.source==='scopus_publications_dom'?'saved-dom':'semantic-unverified'};
}
function assertResults(data:Extraction,p:Params){
  const q=validateQuery(p);
  if(!Number.isSafeInteger(p.expectedCount)||p.expectedCount<0||data.status!=='complete'||data.source!=='scopus_publications_dom'||
    data.count_qualifier!=='exact'||data.count_value!==p.expectedCount||!matchesQuery(data.query_raw,q))
    throw new Error('Sorgu, tam sonuç sayısı veya filtreler değişmiş ya da doğrulanamıyor.');
}
function selection(p:Params){
  const all=p.rangeStart===undefined&&p.rangeEnd===undefined,start=all?1:p.rangeStart,end=all?p.expectedCount:p.rangeEnd;
  if(!Number.isSafeInteger(start)||!Number.isSafeInteger(end)||start<1||end<start||end>p.expectedCount||end-start+1>20000)
    throw new Error('RIS dışa aktarma için 1–20.000 kayıtlık doğrulanmış tam seçim veya açık aralık gerekli.');
  return {start,end,count:end-start+1,all};
}
function choice(root:Root,kind:string,pattern:RegExp,description:string){
  return unique(list(root,`input[type="${kind}"],[role="${kind}"]`).filter(e=>pattern.test(name(e))),description);
}
const checked=(e:HTMLElement)=>e.matches('input')?(e as HTMLInputElement).checked:e.getAttribute('aria-checked')==='true';
const fields=[/^Citation information$/i,/^Bibliographical information$/i,/^Abstract(?:s)?\s*(?:&|and)\s*keywords$/i];
function exportControls(dialog:HTMLElement,p:Params){
  const s=selection(p);
  const format=choice(dialog,'radio',/^RIS(?: format)?(?:\s*\([^)]*\))?$/i,'RIS biçimi');
  const scope=choice(dialog,'radio',s.all?/^All (?:documents|results)(?:\s*\([\d, .]+\))?$/i:/^(?:Range|Specify range|Specify a range)$/i,'Tam kayıt seçimi');
  const labelCount=name(scope).match(/\(([\d, .]+)\)/)?.[1];
  if(labelCount&&parseCount(labelCount,dialog.ownerDocument.documentElement.lang).value!==s.count)throw new Error('Tam seçimde gösterilen kayıt sayısı beklenen toplamla eşleşmiyor.');
  const metadata=fields.map(pattern=>choice(dialog,'checkbox',pattern,'RIS bilgi alanı'));
  const range=s.all?[]:[
    unique(list(dialog,'input[type="number"],input[type="text"]').filter(e=>/^(?:From|Start|Start record)$/i.test(name(e))),'Aralık başlangıcı'),
    unique(list(dialog,'input[type="number"],input[type="text"]').filter(e=>/^(?:To|End|End record)$/i.test(name(e))),'Aralık sonu')];
  return {selection:s,format,scope,metadata,range};
}
function configured(c:ReturnType<typeof exportControls>){
  return checked(c.format)&&checked(c.scope)&&c.metadata.every(checked)&&
    (c.selection.all||(c.range[0] as HTMLInputElement).value===String(c.selection.start)&&(c.range[1] as HTMLInputElement).value===String(c.selection.end));
}
function validateSelectionSummary(dialog:HTMLElement,count:number){
  const summaries=list(dialog,'p,span,[role="status"]').map(text).filter(t=>/^\d[\d, .]*\s+(?:documents?|results?|records?)\s+selected$/i.test(t));
  if(summaries.some(t=>parseCount(t,dialog.ownerDocument.documentElement.lang).value!==count))throw new Error('Dışa aktarma seçimindeki kayıt sayısı beklenen aralıkla eşleşmiyor.');
}
function inViewport(e:HTMLElement){
  const r=e.getBoundingClientRect(),w=e.ownerDocument.defaultView!;
  return visible(e)&&r.width>0&&r.height>0&&r.top>=0&&r.left>=0&&r.bottom<=w.innerHeight&&r.right<=w.innerWidth;
}

// Search/export dialog paths are conservative semantic contracts, not live-validated selectors.
export async function runScopusAction(doc:Document,url:string,action:string,p:Params):Promise<Record<string,any>> {
  const state=inspect(doc,url,p);
  if(action==='inspect')return state;
  if(action==='export_inspect'&&state.recognized&&!['challenge','login'].includes(state.stage))return {stage:'export-status',nextAction:'export_inspect',...statusEvidence(doc),data:state.data};
  if(state.blockers.length)throw new Error('Scopus adımı engellendi: '+state.blockers.join(', ')+'.');
  const dialogs=exportDialogs(doc);
  if(action==='export_inspect')return {stage:'export-status',nextAction:'export_inspect',...statusEvidence(doc),data:state.data};
  if(list(doc,'[role="dialog"][aria-modal="true"],dialog[open]').some(e=>!dialogs.includes(e)))throw new Error('Başka bir iletişim penceresi açık.');
  if(action==='open_search'){
    if(dialogs.length)throw new Error('Önce dışa aktarma penceresini kapatın.');
    if(editors(doc).length===1)return {stage:'search',nextAction:'fill_search'};
    const control=unique(list(doc,'button,a,[role="button"]').filter(e=>/^(?:Edit in advanced search|Advanced document search)$/i.test(name(e))),'Gelişmiş arama bağlantısı');
    click(control);return {stage:'search-opened',nextAction:'inspect'};
  }
  if(action==='fill_search'||action==='submit_search'){
    if(dialogs.length)throw new Error('Dışa aktarma penceresi açık.');
    const q=validateQuery(p),editor=unique(editors(doc),'Gelişmiş sorgu alanı');
    if(!editable(editor))throw new Error('Sorgu alanı düzenlenemiyor.');
    if(action==='fill_search'){
      await setText(editor,q);
      if(!matchesQuery(queryValue(unique(editors(doc),'Gelişmiş sorgu alanı')),q))throw new Error('Sorgunun tamamı arama alanına yazılamadı.');
      return {stage:'search-filled',nextAction:'submit_search',query:q,support:'semantic-unverified'};
    }
    if(!matchesQuery(queryValue(editor),q))throw new Error('Arama alanındaki sorgu beklenen sorguyla eşleşmiyor.');
    const root=editor.closest('form')||doc;
    const button=unique(buttons(root,/^(?:Search|Search documents)$/i),'Arama düğmesi');
    click(button);return {stage:'search-submitted',nextAction:'inspect',submitted:true};
  }
  if(action==='prepare_evidence'){
    if(dialogs.length)throw new Error('Kanıt için dışa aktarma penceresi kapalı olmalı.');
    assertResults(state.data,p);
    const query=unique(list(doc,'#pendo-advanced-search-bar #advancedQueryTextArea'),'Çalıştırılmış sorgu');
    const count=unique(list(doc,'[data-testid="label-search-results-header"]'),'Sonuç sayısı');
    const expand=buttons(query.parentElement!,/^Show more$/i);
    if(expand.length){click(unique(expand,'Sorguyu genişletme düğmesi'));return {stage:'evidence-expanding',ready:false,nextAction:'prepare_evidence',data:state.data};}
    const target=p.viewport==='count'?count:query;target.scrollIntoView({block:'start',behavior:'instant'});
    const clipped=query.clientHeight>0&&query.scrollHeight>query.clientHeight+1;
    const queryVisible=inViewport(query)&&!clipped,countVisible=inViewport(count);
    const ready=p.viewport==='count'?countVisible:p.viewport==='query'?queryVisible:queryVisible&&countVisible;
    return {stage:'evidence',ready,nextAction:ready?'capture':'prepare_evidence',data:state.data,
      evidence:{queryVisible,countVisible,requiresExtraViewport:!queryVisible||!countVisible,viewport:p.viewport||'combined',queryClipped:clipped}};
  }
  if(action==='export_open'||action==='export_configure'||action==='export_submit'){
    assertResults(state.data,p);
    if(p.expectedCount===0)throw new Error('Sıfır sonuç için RIS dışa aktarımı yapılamaz.');
    if(action==='export_open'){
      if(dialogs.length===1)return {stage:'export-dialog',nextAction:'export_configure'};
      if(dialogs.length>1)throw new Error('Birden çok dışa aktarma penceresi açık.');
      const button=unique(buttons(doc,/^Export$/i),'Dışa aktarma düğmesi');
      if(button.id==='export-login-modal'||/login|sign.?in/i.test(button.getAttribute('aria-controls')||''))throw new Error('RIS dışa aktarma için Scopus hesabında oturum açılması gerekiyor.');
      click(button);return {stage:'export-opened',nextAction:'export_configure'};
    }
    const chosen=selection(p);
    const dialog=unique(dialogs,'Dışa aktarma penceresi'),controls=exportControls(dialog,p);
    if(action==='export_configure'){
      const next=[controls.format,controls.scope,...controls.metadata].find(e=>!checked(e));
      if(next){click(next);return {stage:'export-configuring',nextAction:'export_configure',support:'semantic-unverified'};}
      for(let i=0;i<controls.range.length;i++){
        const value=String(i===0?chosen.start:chosen.end);
        if((controls.range[i] as HTMLInputElement).value!==value){await setText(controls.range[i],value);return {stage:'export-configuring',nextAction:'export_configure'};}
      }
      if(!configured(controls))throw new Error('RIS dışa aktarma seçenekleri doğrulanamadı.');
      validateSelectionSummary(dialog,chosen.count);
      return {stage:'export-configured',nextAction:'export_submit',selection:chosen,support:'semantic-unverified'};
    }
    if(!configured(controls))throw new Error('RIS biçimi, tam kayıt seçimi veya gerekli bilgi alanları doğrulanamadı.');
    validateSelectionSummary(dialog,chosen.count);
    const button=unique(buttons(dialog,/^Export(?: documents| results)?$/i),'RIS dışa aktarma düğmesi');
    click(button);return {stage:'export-submitted',nextAction:'export_inspect',submitted:true,selection:chosen};
  }
  throw new Error('Desteklenmeyen Scopus otomasyon adımı: '+action);
}

import { extract, visible, type Mapping } from './adapters';
import { applyYears, applyIeeeFilters } from './refinement-dom';
import { runScopusAction } from './automation-dom';
import { collectAcm } from './acm-dom';

type AgentState={jobId:string;epoch:number;observer:MutationObserver;timer:ReturnType<typeof setTimeout>;changed:()=>void};
const global=globalThis as typeof globalThis & {literatureAgent?:boolean};
if(!global.literatureAgent){
  global.literatureAgent=true;
  let state:AgentState|null=null;
  const release=()=>{if(state){state.observer.disconnect();clearTimeout(state.timer);document.removeEventListener('input',state.changed,true);document.removeEventListener('change',state.changed,true);state=null;}};
  function selectorFor(el:Element):string{
    if(el.id&&document.querySelectorAll('#'+CSS.escape(el.id)).length===1)return '#'+CSS.escape(el.id);
    const parts:string[]=[];
    let current:Element|null=el;
    for(let i=0;current&&i<12;i++,current=current.parentElement){
      const parent:Element|null=current.parentElement;
      const position=parent?Array.from(parent.children).indexOf(current)+1:1;
      parts.unshift(current.tagName.toLowerCase()+`:nth-child(${position})`);
      if(current===document.body)break;
    }
    return parts.join(' > ');
  }
  chrome.runtime.onMessage.addListener((message,_sender,reply)=>{
    if(message.kind==='workflow_action'){
      if(state){reply({error:'Kanıt yakalama devam ediyor.'});return;}
      void runScopusAction(document,location.href,message.action,message.p||{}).then(reply).catch(e=>reply({error:e.message}));
      return true;
    }
    if(message.kind==='acm_collect'){
      if(state){reply({error:'Yakalama devam ediyor; bitince yeniden deneyin.'});return;}
      void collectAcm(document,location.href,message.plan).then(reply).catch(e=>reply({error:e.message}));
      return true;
    }
    if(message.kind==='apply_refinement'){
      if(state){reply({error:'Yakalama devam ediyor.'});return;}
      const apply=message.plan?.context?.kind==='ieee'?applyIeeeFilters:applyYears;
      void apply(document,location.href,message.plan).then(reply).catch(e=>reply({error:e.message}));
      return true;
    }
    if(message.kind==='arm'){
      release();
      const changed=()=>{if(state)state.epoch++;};
      const observer=new MutationObserver(records=>{if(records.length)changed();});
      // Visibility and selector changes can swap an existing results panel without replacing text.
      observer.observe(document.documentElement,{subtree:true,childList:true,characterData:true,attributes:true});
      state={jobId:message.jobId,epoch:0,observer,changed,timer:setTimeout(release,15000)};
      document.addEventListener('input',changed,true);document.addEventListener('change',changed,true);
      reply({ready:true,epoch:0});
    }else if(message.kind==='extract'){
      if(!state||state.jobId!==message.jobId){reply({error:'Yakalama bağlamı sona erdi.'});return;}
      if(state.observer.takeRecords().length)state.epoch++;
      const before=state.epoch;
      const data=extract(document,location.href,message.mapping as Mapping);
      if(state.observer.takeRecords().length)state.epoch++;
      reply({data,epoch:state.epoch,stable:before===0&&state.epoch===0});
    }else if(message.kind==='release'){release();reply({});}
    else if(message.kind==='map_selection'){
      const selection=window.getSelection();
      let el=selection?.anchorNode?.nodeType===Node.ELEMENT_NODE?selection.anchorNode as Element:selection?.anchorNode?.parentElement;
      if(!el||!visible(el)||el.closest('input,textarea,[contenteditable="true"]')||!(el.textContent?.trim())||el.textContent.length>8000){reply({error:'Sonuç sayfasındaki kısa bir metin bölümünü seçin; düzenlenen arama kutusunu seçmeyin.'});return;}
      reply({selector:selectorFor(el),preview:el.textContent.trim().slice(0,200)});
    }else if(message.kind==='fixture'){
      // Diagnostic fixture is bounded text, never full HTML, input values, cookies or attributes.
      const data=extract(document,location.href,message.mapping||{});
      reply({fixture:{kind:'sanitized-extraction',database:data.database,query:data.query_raw,
        count:data.count_raw,fields:data.fields,filters:data.filters,warnings:data.warnings,
        adapter:data.adapter_version,live_verified:false}});
    }
  });
}

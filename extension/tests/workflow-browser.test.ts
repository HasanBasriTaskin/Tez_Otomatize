import test from 'node:test';
import assert from 'node:assert/strict';
import {WorkflowBrowser} from '../src/workflow-browser';

function event(){const listeners:Function[]=[];return {addListener(fn:Function){listeners.push(fn);},emit(...args:any[]){return listeners.map(fn=>fn(...args));}};}
const context={profile:'profile/session',windowId:10,tabId:20};
const payload={sessionId:'session-one',stepId:'step-one',context,action:'submit_search',actionId:'action-one',query:'TITLE-ABS-KEY(test)',expectedCount:3};
function environment(saved:Record<string,any>={},local:Record<string,any>={}){
  const state={tab:{id:20,windowId:10,active:true,incognito:false,title:'Scopus',url:'https://www.scopus.com/pages/search/publications?searchId=abc'},
    profile:context.profile,focused:true,permission:true,downloadsPermission:true,sent:0,injected:0,fail:false,result:{stage:'search-submitted',submitted:true},items:[] as any[]};
  const area=(data:Record<string,any>)=>({get:async(k:string)=>({[k]:structuredClone(data[k])}),set:async(v:any)=>Object.assign(data,structuredClone(v))});
  const api:any={storage:{session:area(saved),local:area(local)},
    tabs:{get:async()=>({...state.tab}),query:async()=>[{...state.tab}],update:async(_id:number,v:any)=>Object.assign(state.tab,v),
      sendMessage:async(_id:number,m:any)=>{if(m.action==='inspect')return {recognized:true,stage:'results',data:{count_value:3,count_qualifier:'exact'}};state.sent++;if(state.fail)throw new Error('port disconnected');return state.result;},
      onActivated:event(),onRemoved:event(),onDetached:event()},
    windows:{get:async()=>({id:10,focused:state.focused}),update:async()=>{state.focused=true;},onFocusChanged:event(),onRemoved:event()},
    permissions:{contains:async(p:any)=>p.permissions?state.downloadsPermission:state.permission},
    scripting:{executeScript:async()=>{state.injected++;return [];}},webNavigation:{getFrame:async()=>({documentId:'doc-current'})},
    downloads:{onCreated:event(),onDeterminingFilename:event(),search:async(q:any)=>state.items.filter(x=>q.id===undefined||x.id===q.id)}};
  const bridge=new WorkflowBrowser(api,()=>state.profile,async()=>true,async()=>({id:'session-one'}));
  return {api,bridge,state,saved,local};
}
async function launched(e:ReturnType<typeof environment>){await e.bridge.launch({tabId:20});return e;}
const arm={sessionId:'session-one',stepId:'step-one',context,exportId:'export-one',expectedCount:3,rangeStart:1,rangeEnd:3};
function download(id:number,change:any={}){return {id,url:'https://www.scopus.com/export/results.ris',finalUrl:'https://www.scopus.com/export/results.ris',
  referrer:'https://www.scopus.com/pages/search/publications?searchId=abc',filename:'C:\\Downloads\\LiteraturKayit\\session-one\\export-one.ris',mime:'application/x-research-info-systems',
  startTime:new Date(Date.now()+100).toISOString(),state:'in_progress',exists:true,...change};}

test('a successful mutating action is dispatched once across worker recreation',async()=>{
  const e=await launched(environment());
  assert.equal((await e.bridge.handle('workflow_browser',payload)).submitted,true);
  assert.equal((await e.bridge.handle('workflow_browser',payload)).submitted,true);assert.equal(e.state.sent,1);
  const restored=environment(e.saved);await restored.bridge.handle('workflow_browser',payload);assert.equal(restored.state.sent,0);
});
test('an uncertain action outcome persists and is never blindly dispatched again',async()=>{
  const e=await launched(environment());e.state.fail=true;
  await assert.rejects(e.bridge.handle('workflow_browser',payload),/port disconnected/);assert.equal(e.state.sent,1);
  const restored=environment(e.saved);
  await assert.rejects(restored.bridge.handle('workflow_browser',payload),/belirsiz/i);assert.equal(restored.state.sent,0);
});
test('reusing an action id with a different query is rejected',async()=>{
  const e=await launched(environment());await e.bridge.handle('workflow_browser',payload);
  await assert.rejects(e.bridge.handle('workflow_browser',{...payload,query:'TITLE-ABS-KEY(other)'}),/kimliği/i);assert.equal(e.state.sent,1);
});
test('away-and-back tab focus remains latched until explicit resume',async()=>{
  const e=await launched(environment());e.api.tabs.onActivated.emit({windowId:10,tabId:99});e.api.tabs.onActivated.emit({windowId:10,tabId:20});
  await assert.rejects(e.bridge.handle('workflow_browser',payload),/odak|sekme/i);assert.equal(e.state.sent,0);
  await e.bridge.launch({id:'session-one',tabId:20});await e.bridge.handle('workflow_browser',payload);assert.equal(e.state.sent,1);
});
test('window focus latch survives worker recreation',async()=>{
  const e=await launched(environment());e.api.windows.onFocusChanged.emit(-1);await new Promise(r=>setImmediate(r));
  const restored=environment(e.saved);await assert.rejects(restored.bridge.handle('workflow_browser',payload),/odak|sekme/i);
});
test('profile, permission and active window are checked before dispatch',async()=>{
  for(const change of [(e:any)=>{e.state.permission=false;},(e:any)=>{e.state.focused=false;},(e:any)=>{e.state.tab.active=false;}]){
    const e=await launched(environment());change(e);await assert.rejects(e.bridge.handle('workflow_browser',payload));assert.equal(e.state.sent,0);
  }
  const e=await launched(environment());await assert.rejects(e.bridge.handle('workflow_browser',{...payload,context:{...context,profile:'other'}}));assert.equal(e.state.sent,0);
});
test('download arm requires permission and allows only one unresolved export',async()=>{
  const e=await launched(environment());e.state.downloadsPermission=false;await assert.rejects(e.bridge.handle('workflow_download_arm',arm));
  e.state.downloadsPermission=true;await e.bridge.handle('workflow_download_arm',arm);
  await assert.rejects(e.bridge.handle('workflow_download_arm',{...arm,exportId:'another'}),/dışa aktarma|indirme/i);
});
test('unrelated origin, referrer and pre-arm downloads never become this export',async()=>{
  const e=await launched(environment());await e.bridge.handle('workflow_download_arm',arm);
  e.state.items=[download(1,{referrer:'https://www.scopus.com/pages/search/publications?searchId=other'}),download(2,{url:'https://evil.test/a.ris',finalUrl:'https://evil.test/a.ris'}),download(3,{startTime:'2020-01-01T00:00:00Z'})];
  const r=await e.bridge.handle('workflow_download_status',arm);assert.equal(r.state,'waiting');assert.equal(r.downloadId,undefined);
});
test('only a unique correlated complete Chrome download is reported complete',async()=>{
  const e=await launched(environment());await e.bridge.handle('workflow_download_arm',arm);e.state.items=[download(4)];
  assert.equal((await e.bridge.handle('workflow_download_status',arm)).state,'waiting');
  e.state.items[0].state='complete';const r=await e.bridge.handle('workflow_download_status',arm);assert.equal(r.state,'complete');assert.equal(r.downloadId,4);assert.equal(r.filename,'C:\\Downloads\\LiteraturKayit\\session-one\\export-one.ris');
});
test('multiple correlated files are ambiguous, never the newest file',async()=>{
  const e=await launched(environment());await e.bridge.handle('workflow_download_arm',arm);e.state.items=[download(4,{state:'complete'}),download(5,{state:'complete'})];
  assert.equal((await e.bridge.handle('workflow_download_status',arm)).state,'ambiguous');
});
test('filename suggestion changes only the correlated export',async()=>{
  const e=await launched(environment());await e.bridge.handle('workflow_download_arm',arm);
  const values:any[]=[];e.api.downloads.onDeterminingFilename.emit(download(4),v=>values.push(v));await new Promise(r=>setImmediate(r));
  assert.equal(values[0].filename,'LiteraturKayit/session-one/export-one.ris');
  values.length=0;e.api.downloads.onDeterminingFilename.emit(download(8,{referrer:'https://other.test/'}),v=>values.push(v));await new Promise(r=>setImmediate(r));assert.deepEqual(values,[undefined]);
});
test('release removes the watcher without cancelling unrelated downloads',async()=>{
  const e=await launched(environment());await e.bridge.handle('workflow_download_arm',arm);await e.bridge.handle('workflow_release',{sessionId:'session-one'});
  await assert.rejects(e.bridge.handle('workflow_download_status',arm));
});
test('a missing content reply remains uncertain and cannot be cached as success',async()=>{
  const e=await launched(environment());e.state.result=undefined as any;
  await assert.rejects(e.bridge.handle('workflow_browser',payload));
  await assert.rejects(e.bridge.handle('workflow_browser',payload),/belirsiz/);assert.equal(e.state.sent,1);
});
test('export id cannot be rebound to a different range or step',async()=>{
  const e=await launched(environment());await e.bridge.handle('workflow_download_arm',arm);
  await assert.rejects(e.bridge.handle('workflow_download_arm',{...arm,stepId:'step-other'}),/kimliği|eşleş/i);
  await assert.rejects(e.bridge.handle('workflow_download_arm',{...arm,rangeEnd:2}),/kimliği|eşleş/i);
});
test('complete download outside the owned destination is not accepted',async()=>{
  const e=await launched(environment());await e.bridge.handle('workflow_download_arm',arm);e.state.items=[download(4,{state:'complete',filename:'C:\\Downloads\\unrelated.ris'})];
  assert.equal((await e.bridge.handle('workflow_download_status',arm)).state,'ambiguous');
});
test('parallel retry of one action still produces only one dispatch',async()=>{
  const e=await launched(environment());await Promise.all([e.bridge.handle('workflow_browser',payload),e.bridge.handle('workflow_browser',payload)]);assert.equal(e.state.sent,1);
});

test('cold restart requires explicit resume and retains the original export provenance across a new tab/session',async()=>{
  const e=await launched(environment());await e.bridge.handle('workflow_download_arm',arm);
  const restarted=environment({},e.local);
  await assert.rejects(restarted.bridge.handle('workflow_download_status',arm),/odak|sekme/i);
  restarted.state.profile='profile/new-browser-session';restarted.state.tab.id=22;restarted.state.tab.windowId=11;
  restarted.state.tab.url='https://www.scopus.com/pages/search/publications?searchId=new-search';
  const rebound={...context,profile:restarted.state.profile,tabId:22,windowId:11};
  await restarted.bridge.launch({id:'session-one',tabId:22});
  restarted.state.items=[download(4,{state:'complete'})];
  const r=await restarted.bridge.handle('workflow_download_status',{...arm,context:rebound});
  assert.equal(r.state,'complete');assert.equal(r.downloadId,4);assert.equal(restarted.state.sent,0);
  await assert.rejects(restarted.bridge.handle('workflow_download_status',{...arm,context:rebound,exportId:'different-export'}),/eşleş/i);
  await assert.rejects(restarted.bridge.handle('workflow_download_status',{...arm,context:rebound,rangeEnd:2}),/eşleş/i);
});

test('a new search download cannot replace the original export after cold resume',async()=>{
  const e=await launched(environment());await e.bridge.handle('workflow_download_arm',arm);
  const restarted=environment({},e.local);await restarted.bridge.launch({id:'session-one',tabId:20});
  restarted.state.items=[download(5,{state:'complete',referrer:'https://www.scopus.com/pages/search/publications?searchId=new-search'})];
  assert.equal((await restarted.bridge.handle('workflow_download_status',arm)).state,'waiting');
});

test('cold restart preserves completed and uncertain action ledgers without another click',async()=>{
  for(const uncertain of [false,true]){
    const e=await launched(environment());e.state.fail=uncertain;
    if(uncertain)await assert.rejects(e.bridge.handle('workflow_browser',payload));else await e.bridge.handle('workflow_browser',payload);
    const restarted=environment({},e.local);await restarted.bridge.launch({id:'session-one',tabId:20});
    if(uncertain)await assert.rejects(restarted.bridge.handle('workflow_browser',payload),/belirsiz/i);
    else assert.equal((await restarted.bridge.handle('workflow_browser',payload)).submitted,true);
    assert.equal(restarted.state.sent,0);
  }
});

test('release clears recoverable flow so a cold restart cannot revive its export watch',async()=>{
  const e=await launched(environment());await e.bridge.handle('workflow_download_arm',arm);
  await e.bridge.handle('workflow_release',{sessionId:'session-one'});
  const restarted=environment({},e.local);await restarted.bridge.launch({id:'session-one',tabId:20});
  await assert.rejects(restarted.bridge.handle('workflow_download_status',arm),/eşleş/i);
});

test('workflow_guard validates active context without injecting or sending DOM actions',async()=>{
  const e=await launched(environment()),before=e.state.injected;
  assert.deepEqual(await e.bridge.handle('workflow_guard',{sessionId:'session-one',context}),{ready:true});
  assert.equal(e.state.injected,before);assert.equal(e.state.sent,0);
  e.api.tabs.onActivated.emit({windowId:10,tabId:99});e.api.tabs.onActivated.emit({windowId:10,tabId:20});
  await assert.rejects(e.bridge.handle('workflow_guard',{sessionId:'session-one',context}),/odak|sekme/i);
  assert.equal(e.state.injected,before);
});

test('workflow_guard rejects wrong session/profile, inactive tab and unfocused window',async()=>{
  const e=await launched(environment());
  assert.equal((await e.bridge.handle('workflow_guard',{sessionId:'session-one',context})).ready,true);
  for(const p of [{sessionId:'another-session',context},{sessionId:'session-one',context:{...context,profile:'other-profile'}}])
    await assert.rejects(e.bridge.handle('workflow_guard',p),/eşleş/i);
  e.state.tab.active=false;await assert.rejects(e.bridge.handle('workflow_guard',{sessionId:'session-one',context}));
  e.state.tab.active=true;e.state.focused=false;await assert.rejects(e.bridge.handle('workflow_guard',{sessionId:'session-one',context}));
});

test('a focus event during guard validation cannot return ready',async()=>{
  const e=await launched(environment());
  e.api.windows.get=async()=>{e.api.windows.onFocusChanged.emit(-1);return {id:10,focused:true};};
  await assert.rejects(e.bridge.handle('workflow_guard',{sessionId:'session-one',context}),/odak|sekme/i);
});

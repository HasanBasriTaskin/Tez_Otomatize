"""Generate isolated visual QA material. None of these rows enters the user's project."""
import json
import shutil
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from literature.storage import Store
from literature.exports import export_sources,export_evidence
from literature.zotero import import_items

qa=ROOT/'qa-output';ui=qa/'ui';ui.mkdir(parents=True,exist_ok=True)
for name in ['style.css','manager.js']:shutil.copy2(ROOT/'artifacts/extension'/name,ui/name)
page=(ROOT/'extension/public/manager.html').read_text(encoding='utf-8').replace('<script src="manager.js">','<script src="qa-stub.js"></script><script src="manager.js">')
(ui/'index.html').write_text(page,encoding='utf-8')
stub='''
// Visual QA only: Chrome transport substituted with explicit synthetic data.
const qaSettings={project_name:'Arayüz testi — sentetik veri',team_code:'TEST',operator:'Test',hotkey:'CTRL+M',monitor:'active',clock_confirmed:false,zotero_mode:'local',library:'users/0'};
window.chrome={runtime:{sendMessage:async m=>{
const result={status:{settings:qaSettings,paused:false,run_count:0,pending_count:0,monitors:[{}, {width:1920,height:1080}],project_root:'İzole test klasörü',note_template:''},list_runs:{rows:[],total:0},list_pending:{rows:[]},list_papers:{rows:[]}}[m.type];
return {ok:true,data:result||{}};
}},storage:{local:{get:async()=>({}),set:async()=>{}}}};
'''
(ui/'qa-stub.js').write_text(stub,encoding='utf-8')
store=Store(qa/'document-project')
items=[{'key':'TEST0001','data':{'itemType':'journalArticle','title':'Görsel kontrol için sentetik Türkçe kaynak','creators':[{'creatorType':'author','firstName':'Örnek','lastName':'Yazar'}],'date':'2026','collections':['IN']}},
       {'key':'NOTE0001','data':{'itemType':'note','parentItem':'TEST0001','note':'<p>Anotasyon: Bu metin yalnız PDF yerleşimini sınamak için hazırlanmış sentetik bir örnektir. Gerçek bir yayın veya bilimsel bulgu değildir. Türkçe karakterlerin, uzun satırların ve kaynak başlığı ile açıklama arasındaki boşlukların kontrolü için kullanılır.</p>'}}]
import_items(store,'users/0',items,{'included':'IN'})
with store.db:store.db.execute('UPDATE papers SET verified=1')
result=export_sources(store)
image=qa/'windows-monitor.png'
if image.exists() and not store.list_runs():
    store.begin_job('qa-document',{})
    store.save_capture('qa-document',image.read_bytes(),source='import')
    store.complete_job('qa-document',{'database':'Görsel test','query_raw':'Sentetik test kaydı','query_verified':True,'status':'complete','count_value':0,'filters':[]},{},manual=True)
if store.list_runs():result['evidence']=export_evidence(store)['pdf']
store.close()
(qa/'documents.json').write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))

import base64
import io
import json
import os
import subprocess
import threading
import uuid
from pathlib import Path

from PIL import Image
import win32ui
import pythoncom
from win32com.shell import shell,shellcon

from .storage import Store,ValidationError,json_text,utcnow
from .capture import CaptureController
from .windows import Desktop,parse_hotkey
from .runtime import configuration,settings_file,product
from .backup import create_backup,restore_backup
from .zotero import ZoteroClient,import_items,save_api_key,NOTE_TEMPLATE
from .exports import export_sources,export_evidence,check_project


def choose_file(pattern):
    pythoncom.CoInitialize()
    try:
        dialog=win32ui.CreateFileDialog(1,None,None,0x1000|0x800,pattern)
        return dialog.GetPathName() if dialog.DoModal()==1 else None
    finally:pythoncom.CoUninitialize()


def choose_folder(title):
    pythoncom.CoInitialize()
    try:
        result=shell.SHBrowseForFolder(0,None,title,shellcon.BIF_RETURNONLYFSDIRS|shellcon.BIF_NEWDIALOGSTYLE)
        return os.fsdecode(shell.SHGetPathFromIDList(result[0])) if result and result[0] else None
    finally:pythoncom.CoUninitialize()


class Application:
    def __init__(self,root,notify=lambda *args:None):
        self.store=Store(root);self.desktop=Desktop();self.notify=notify
        self.controller=CaptureController(self.store,self.desktop,notify)
        self.peers={};self.peer_lock=threading.RLock();self.command_lock=threading.RLock()
        self.extension_id=product()['extension_id']
        self.last_export=None

    def start(self):self.desktop.start(self.store.settings()['hotkey'],self.controller.capture,self.controller.unbind)

    def disconnect(self,peer):
        self.controller.disconnect(peer)
        with self.peer_lock:
            if self.peers.get(peer.profile) is peer:self.peers.pop(peer.profile,None)

    def handle(self,peer,message):
        kind=message['type'];p=message.get('payload',{})
        if kind=='hello':
            if p.get('origin')!='chrome-extension://'+self.extension_id+'/':raise ValidationError('Eklenti kimliği eşleşmiyor.')
            profile=p.get('profile')
            if not isinstance(profile,str) or not 1<=len(profile)<=100:raise ValidationError('Profil kimliği eksik.')
            role=p.get('role')
            if role=='worker':
                peer.profile,peer.role=profile,role
                with self.peer_lock:
                    old=self.peers.get(profile)
                    if old and old is not peer:self.controller.disconnect(old)
                    self.peers[profile]=peer
            elif role=='binder':
                with self.peer_lock:worker=self.peers.get(profile)
                if not worker or not worker.connected:raise ValidationError('Kalıcı Chrome bağlantısı henüz hazır değil.')
                hwnd=p.get('parentHwnd');window=p.get('windowId')
                if type(hwnd)is not int or type(window)is not int:raise ValidationError('Geçersiz pencere kimliği.')
                self.controller.bind(hwnd,window,worker)
                peer.profile,peer.role=profile,role
            else:raise ValidationError('Geçersiz bağlantı türü.')
            return {'version':1}
        if peer.role!='worker':raise ValidationError('Önce Chrome bağlantısını doğrulayın.')
        with self.command_lock:
            return self.command(kind,p,peer)

    def command(self,kind,p,peer=None):
        s=self.store
        if kind=='status':
            return {'project_root':str(s.root),'settings':s.settings(),'paused':self.controller.paused,
                    'busy':self.controller.busy.locked(),'bound_windows':len(self.controller.bindings),
                    'hotkey_error':self.desktop.hotkey_error,'run_count':len(s.list_runs()),
                    'pending_count':len(s.pending()),'monitors':self.desktop.monitors(),
                    'note_template':NOTE_TEMPLATE,'last_export':self.last_export}
        if kind=='settings':return s.settings()
        if kind=='next_capture':
            action={'role':p.get('role','sonuc'),'new_run':p.get('new_run') is True}
            if action['role'] not in ('sonuc','sorgu','filtre'):raise ValidationError('Geçersiz kanıt türü.')
            if p.get('attach_to'):action['attach_to']=s.get_run(str(p['attach_to']))['id']
            self.controller.next_action=action
            return {'armed':True}
        if kind=='update_settings':
            if 'hotkey' in p:parse_hotkey(p['hotkey'])
            settings=s.update_settings(p)
            self.desktop.configure(settings['hotkey'],self.controller.paused)
            return settings
        if kind in ('pause','resume'):
            self.controller.paused=kind=='pause'
            self.desktop.configure(s.settings()['hotkey'],self.controller.paused)
            return {'paused':self.controller.paused}
        if kind=='list_runs':
            start=max(0,int(p.get('offset',0)))
            return {'rows':[{k:r[k] for k in ('id','display_id','database_name','count_value','count_qualifier','verification_status','observed_at_utc')}|{'query_preview':r['query_raw'][:180]} for r in s.list_runs()[start:start+50]],'total':len(s.list_runs())}
        if kind=='get_run':
            run=s.get_run(str(p['id']));return {'run':run,'captures':s.captures(run['id'])}
        if kind=='list_pending':
            return {'rows':[{k:r[k] for k in ('id','state','created_at','captured_at','error')} for r in s.pending()]}
        if kind=='get_job':return s.get_job(str(p['id']))
        if kind=='save_draft':
            if p.get('confirmed') is not True:raise ValidationError('PNG ile bilgilerin eşleştiğini doğrulayın.')
            job=s.get_job(str(p['id']));data=p.get('data')
            if not isinstance(data,dict):raise ValidationError('Arama bilgileri eksik.')
            for field in ('database','query_raw','fields','count_raw','notes'):
                if field in data and (not isinstance(data[field],str) or len(data[field])>32767):raise ValidationError('Geçersiz alan: '+field)
            if not isinstance(data.get('filters'),list) or any(not isinstance(x,str) for x in data['filters']):raise ValidationError('Filtreler liste olmalı.')
            if data.get('count_qualifier') not in ('exact','approximate','at_least'):raise ValidationError('Sonuç sayısının niteliğini seçin.')
            data.update(query_verified=True,status='complete',source='user_confirmed')
            result=s.complete_job(job['id'],data,json.loads(job['context_json']),manual=True,new_run=True,
                                  attach_to=p.get('attach_to') or None,role=p.get('role','sonuc'))
            if result.get('state')=='incomplete':raise ValidationError(result['error'])
            try:self.last_export=s.export_excel()
            except Exception:return {'run':result,'warning':'Kayıt saklandı; Excel güncellenemedi.'}
            return {'run':result,'export':self.last_export}
        if kind=='update_run':s.update_run(str(p['id']),{'notes':p.get('notes','')});return {}
        if kind=='export_excel':self.last_export=s.export_excel();return self.last_export
        if kind=='open_capture':
            row=s.db.execute('SELECT relative_path FROM captures WHERE id=?',(p.get('id'),)).fetchone()
            if row:relative=row[0]
            elif p.get('jobId'):relative=s.get_job(str(p['jobId']))['image_path']
            else:raise ValidationError('Görsel bulunamadı.')
            if not relative or not s.path(relative).exists():raise ValidationError('Görsel diskte bulunamadı.')
            os.startfile(s.path(relative));return {}
        if kind=='thumbnail':
            if p.get('jobId'):relative=s.get_job(str(p['jobId']))['image_path']
            else:
                row=s.db.execute('SELECT relative_path FROM captures WHERE id=?',(p.get('id'),)).fetchone();relative=row[0] if row else None
            if not relative or not s.path(relative).exists():return {'data':None}
            with Image.open(s.path(relative)) as img:
                img.thumbnail((1000,650));out=io.BytesIO();img.convert('RGB').save(out,'JPEG',quality=65)
            return {'data':'data:image/jpeg;base64,'+base64.b64encode(out.getvalue()).decode()}
        if kind=='open_folder':
            if p.get('runId'):path=s.path('02_Ekranlar/'+s.get_run(str(p['runId']))['display_id'])
            else:
                folder={'project':'','screens':'02_Ekranlar','outputs':'05_Teslim','backups':'Yedekler','work':'03_Calisma'}.get(p.get('folder','project'))
                if folder is None:raise ValidationError('Geçersiz klasör.')
                path=s.path(folder) if folder else s.root
            os.startfile(path);return {}
        if kind=='import_png':
            filename=choose_file('PNG görüntüleri (*.png)|*.png||')
            if not filename:return {'cancelled':True}
            identity=str(uuid.uuid4());s.begin_job(identity,{'source':'import'})
            s.save_capture(identity,Path(filename).read_bytes(),source='import')
            return s.mark_incomplete(identity,'Elle içe aktarıldı. Gerçek çekim zamanı bilinmiyor; sorgu ve sonuç bilgilerini tamamlayın.')
        if kind=='pick_project':
            folder=choose_folder('Literatür projesinin ana klasörünü seçin')
            if not folder:return {'cancelled':True}
            if not self.controller.busy.acquire(blocking=False):raise ValidationError('Önce yakalamanın bitmesini bekleyin.')
            try:
                new_store=Store(folder)
                s.close();self.store=new_store;self.controller.store=new_store
                config=configuration();config['project_root']=str(new_store.root)
                f=settings_file();f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json_text(config),encoding='utf-8')
                self.desktop.configure(new_store.settings()['hotkey'],self.controller.paused)
                return {'project_root':folder}
            finally:self.controller.busy.release()
        if kind=='unbind_window':
            with self.controller.binding_lock:
                self.controller.bindings={hwnd:b for hwnd,b in self.controller.bindings.items() if not(b[0]==p.get('windowId') and b[1] is peer)}
            return {}
        if kind=='backup':return {'path':create_backup(s)}
        if kind=='restore':
            archive=choose_file('Proje yedeği (*.zip)|*.zip||')
            if not archive:return {'cancelled':True}
            parent=choose_folder('Yeni geri yükleme klasörünün bulunacağı yeri seçin')
            if not parent:return {'cancelled':True}
            destination=Path(parent)/('Literatur_GeriYukleme_'+uuid.uuid4().hex[:8])
            return {'path':restore_backup(archive,destination)}
        if kind=='save_fixture':
            content=p.get('fixture')
            if not isinstance(content,dict) or len(json_text(content))>50000:raise ValidationError('Geçersiz tanılama içeriği.')
            allowed={'kind','database','query','count','fields','filters','warnings','adapter','live_verified'}
            if set(content)-allowed:raise ValidationError('Tanılama alanları geçersiz.')
            relative='03_Calisma/Veri/tanilama/'+str(uuid.uuid4())+'.json'
            s._atomic_write(relative,json_text(content).encode());return {'path':str(s.path(relative))}
        if kind=='zotero_key':
            mode=s.settings().get('zotero_mode','local');save_api_key(p.get('key',''),mode);return {'saved':True}
        if kind=='zotero_collections':
            items=ZoteroClient(s.settings()).all('collections')
            return {'rows':[{'key':i['key'],'name':i['data'].get('name',''),'parent':i['data'].get('parentCollection')} for i in items]}
        if kind=='zotero_sync':
            client=ZoteroClient(s.settings());items=client.all('items')
            return import_items(s,client.library,items,s.settings().get('collection_mapping',{}))
        if kind=='list_papers':
            rows=s.db.execute('SELECT id,item_key,state,verified,data_json FROM papers ORDER BY item_key LIMIT 100 OFFSET ?',(max(0,int(p.get('offset',0))),))
            return {'rows':[{'id':r['id'],'key':r['item_key'],'state':r['state'],'verified':r['verified'],'title':json.loads(r['data_json']).get('title','')} for r in rows]}
        if kind=='get_paper':
            row=s.db.execute('SELECT * FROM papers WHERE id=?',(p['id'],)).fetchone()
            if not row:raise ValidationError('Kaynak bulunamadı.')
            notes=s.db.execute('SELECT * FROM reading_notes WHERE paper_id=?',(p['id'],)).fetchone()
            links=[r[0] for r in s.db.execute('SELECT r.display_id FROM search_runs r JOIN search_paper_links l ON r.id=l.search_id WHERE l.paper_id=?',(p['id'],))]
            return {'paper':dict(row),'notes':dict(notes) if notes else {},'links':links}
        if kind=='update_paper':
            row=s.db.execute('SELECT * FROM papers WHERE id=?',(p['id'],)).fetchone()
            if not row:raise ValidationError('Kaynak bulunamadı.')
            if p.get('verified') and not row['annotation'].strip():raise ValidationError('Önce Zotero bağlı notuna Anotasyon alanını ekleyip yeniden okuyun.')
            draft=p.get('local_draft','')
            if not isinstance(draft,str) or len(draft)>30000:raise ValidationError('Yerel taslak çok uzun.')
            with s.db:
                s.db.execute('UPDATE papers SET verified=?,updated_at=? WHERE id=?',(int(p.get('verified') is True),utcnow(),p['id']))
                s.db.execute('UPDATE reading_notes SET local_draft=? WHERE paper_id=?',(draft,p['id']))
                s.audit('paper_reviewed',p['id'])
            return {}
        if kind=='link_paper':
            with s.db:
                if not s.db.execute('SELECT 1 FROM papers WHERE id=?',(p['paper_id'],)).fetchone():raise ValidationError('Kaynak bulunamadı.')
                runs=[s.get_run(str(x)) for x in p.get('search_ids',[])]
                s.db.execute('DELETE FROM search_paper_links WHERE paper_id=?',(p['paper_id'],))
                for run in runs:s.db.execute('INSERT INTO search_paper_links VALUES(?,?)',(run['id'],p['paper_id']))
                s.audit('paper_search_links',p['paper_id'])
            return {}
        if kind=='export_deliverables':
            result=export_evidence(s) if p.get('kind')=='evidence' else export_sources(s,p.get('draft') is True)
            result['issues']=check_project(s);return result
        raise ValidationError('Desteklenmeyen komut.')

    def open_manager(self):
        candidates=[Path(os.environ.get('PROGRAMFILES','C:/Program Files'))/'Google/Chrome/Application/chrome.exe',
                    Path(os.environ.get('LOCALAPPDATA',''))/'Google/Chrome/Application/chrome.exe']
        exe=next((p for p in candidates if p.exists()),None)
        if exe:subprocess.Popen([str(exe),'chrome-extension://'+self.extension_id+'/manager.html'])
        else:self.notify('Chrome eklenti simgesinden Kayıtlar ve ayarlar bölümünü açın.','')

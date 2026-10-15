"""Durable Scopus research sessions. The browser executes bounded actions only."""
import json
import threading
import time
import uuid
from pathlib import Path

from .storage import ValidationError, json_text, utcnow, digest
from .refinement import canonical

from .query_package import QueryPackage

WORKFLOW_SCHEMA = '''
CREATE TABLE IF NOT EXISTS workflow_sessions(
 id TEXT PRIMARY KEY, state TEXT NOT NULL, snapshot_json TEXT NOT NULL, context_json TEXT NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, error TEXT NOT NULL DEFAULT '', elapsed REAL NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS workflow_steps(
 id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES workflow_sessions(id), ordinal INTEGER NOT NULL,
 code TEXT NOT NULL, label TEXT NOT NULL, query TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'queued',
 run_id TEXT REFERENCES search_runs(id), capture_job_id TEXT, count_value INTEGER,
 detail_json TEXT NOT NULL DEFAULT '{}', UNIQUE(session_id,code));
CREATE TABLE IF NOT EXISTS workflow_actions(
 id TEXT PRIMARY KEY, step_id TEXT NOT NULL REFERENCES workflow_steps(id), action TEXT NOT NULL,
 state TEXT NOT NULL, created_at TEXT NOT NULL, result_json TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS workflow_exports(
 id TEXT PRIMARY KEY, step_id TEXT NOT NULL REFERENCES workflow_steps(id), range_start INTEGER NOT NULL,
 range_end INTEGER NOT NULL, state TEXT NOT NULL, download_id INTEGER, relative_path TEXT,
 sha256 TEXT, record_count INTEGER, error TEXT NOT NULL DEFAULT '', UNIQUE(step_id,range_start,range_end));
'''


class ClockGuard:
    def __init__(self, wall=None, monotonic=None):
        self.wall=time.time() if wall is None else wall
        self.monotonic=time.monotonic() if monotonic is None else monotonic

    def elapsed(self, wall=None, monotonic=None):
        delta=(time.monotonic() if monotonic is None else monotonic)-self.monotonic
        if abs((time.time() if wall is None else wall)-self.wall-delta)>5:
            raise ValidationError('Windows saati değişti. Tarih/saat ayarını kontrol edip devam edin; eski kanıtlar korundu.')
        return delta


class StableResult:
    def __init__(self, query, seconds=2):
        self.query=query;self.seconds=seconds;self.signature=None;self.since=None

    def observe(self, data, now):
        valid=(data.get('database')=='Scopus' and data.get('status')=='complete' and data.get('query_verified')
               and canonical(data.get('query_raw',''))==canonical(self.query) and data.get('count_qualifier')=='exact'
               and type(data.get('count_value')) is int and data['count_value']>=0)
        if not valid:self.signature=None;self.since=None;return False
        signature=json_text([data['count_value'],data.get('filters',[]),data.get('fields','')])
        if signature!=self.signature:self.signature=signature;self.since=now
        return now-self.since>=self.seconds


def validate_download(filename, downloads_root, expected, parser):
    file=Path(filename).resolve();root=Path(downloads_root).resolve()
    if not file.is_relative_to(root) or file.suffix.lower()!='.ris' or not file.is_file():
        raise ValidationError('RIS dosyası doğrulanan indirme klasöründe değil.')
    if file.stat().st_size>128*1024*1024:raise ValidationError('RIS dosyası 128 MB sınırını aşıyor.')
    data=file.read_bytes();records=parser(data)
    if len(records)!=expected:raise ValidationError(f'RIS içinde {len(records)} kayıt var; beklenen {expected}. Aktarım tamamlanmadı.')
    return data,records


def year_query(query, year):
    return query + (f' AND PUBYEAR > {year - 1} AND PUBYEAR < 2027' if year else '')


class WorkflowRecords:
    def __init__(self, store):
        self.store = store

    def get(self, identity=None):
        with self.store.lock:
            row = self.store.db.execute('SELECT * FROM workflow_sessions WHERE id=?', (identity,)).fetchone() if identity else self.store.db.execute('SELECT * FROM workflow_sessions ORDER BY created_at DESC LIMIT 1').fetchone()
            if not row:
                if identity:raise ValidationError('Tarama oturumu bulunamadı.')
                return None
            result = dict(row)
            result['snapshot'] = json.loads(result.pop('snapshot_json'))
            result['context'] = json.loads(result.pop('context_json'))
            result['steps'] = [dict(r) for r in self.store.db.execute('SELECT * FROM workflow_steps WHERE session_id=? ORDER BY ordinal', (result['id'],))]
            for step in result['steps']:
                step['detail'] = json.loads(step.pop('detail_json'))
                step['exports'] = [dict(r) for r in self.store.db.execute('SELECT * FROM workflow_exports WHERE step_id=? ORDER BY range_start', (step['id'],))]
                if step['run_id']:step['display_id'] = self.store.get_run(step['run_id'])['display_id']
            result['totals']={
                'raw':sum(e['record_count'] or 0 for s in result['steps'] for e in s['exports'] if e['state']=='complete'),
                'unique':self.store.db.execute('SELECT COUNT(DISTINCT eid) FROM zotero_source_refs WHERE session_id=?',(result['id'],)).fetchone()[0],
                'suspects':self.store.db.execute('SELECT COUNT(*) FROM zotero_duplicate_suspects d WHERE EXISTS (SELECT 1 FROM zotero_source_refs r WHERE r.session_id=? AND r.server_id=d.server_id AND r.library_id=d.library_id AND r.eid=d.eid)',(result['id'],)).fetchone()[0]}
            return result

    def create(self, options, context):
        if not isinstance(options,dict) or set(options) - {'include_review','package_revision'} or type(options.get('include_review',False)) is not bool:
            raise ValidationError('Tarama seçenekleri geçersiz.')
        with self.store.lock, self.store.db:
            if self.store.db.execute("SELECT 1 FROM workflow_sessions WHERE state NOT IN ('completed','stopped')").fetchone():
                raise ValidationError('Önce mevcut taramaya devam edin veya onu durdurun.')
            catalog=QueryPackage(self.store).load();package=catalog['package']
            if 'package_revision' in options and options['package_revision']!=catalog['revision']:
                raise ValidationError('Sorgu paketi önizlemeden sonra değişti. Dosyadan yeniden yükleyip kontrol edin.')
            identity = str(uuid.uuid4()); now=utcnow()
            snapshot = {'package_version':1,'package_name':package['name'],'package_revision':catalog['revision'],
                        'initial':package['initial'],'topics':[(t['code'],t['label'],t['query']) for t in package['topics']],
                        'types':['ar','cp'] + (['re'] if options.get('include_review') else []),
                        'settings':self.store.settings(), 'seed_terms_verified':False}
            self.store.db.execute('INSERT INTO workflow_sessions(id,state,snapshot_json,context_json,created_at,updated_at) VALUES(?,?,?,?,?,?)',
                                  (identity,'paused',json_text(snapshot),json_text(context),now,now))
            self._add(identity,'P00','Başlangıç — yıl ve tür sınırı yok',snapshot['initial'])
            self.store.audit('workflow_created',identity,{'package':1,'types':snapshot['types']})
        return self.get(identity)


    def _add(self, session, code, label, query):
        ordinal=self.store.db.execute('SELECT COUNT(*) FROM workflow_steps WHERE session_id=?',(session,)).fetchone()[0]
        self.store.db.execute('INSERT OR IGNORE INTO workflow_steps(id,session_id,ordinal,code,label,query) VALUES(?,?,?,?,?,?)',
                              (str(uuid.uuid4()),session,ordinal,code,label,query))

    def set_session(self, identity, **changes):
        if set(changes)-{'state','error','elapsed','context_json'}:raise ValueError('Unsupported session fields')
        changes['updated_at']=utcnow()
        with self.store.lock,self.store.db:
            self.store.db.execute('UPDATE workflow_sessions SET '+','.join(k+'=?' for k in changes)+' WHERE id=?',(*changes.values(),identity))

    def update_step(self, identity, **changes):
        if set(changes)-{'state','run_id','capture_job_id','count_value','detail_json'}:raise ValueError('Unsupported step fields')
        with self.store.lock,self.store.db:
            self.store.db.execute('UPDATE workflow_steps SET '+','.join(k+'=?' for k in changes)+' WHERE id=?',(*changes.values(),identity))

    def stop(self, identity):
        self.get(identity)
        self.set_session(identity,state='stopped',error='Kullanıcı durdurdu. Kaydedilen işler korundu.')

    def advance(self, identity, count, code=None):
        if type(count) is not int or count<0:raise ValidationError('Kesin sonuç sayısı gerekli.')
        with self.store.lock,self.store.db:
            session=self.get(identity)
            step=next((s for s in session['steps'] if s['code']==code),None) if code else next((s for s in session['steps'] if s['state']!='done'),None)
            if not step or step['state']=='done':return session
            self.store.db.execute("UPDATE workflow_steps SET state='done',count_value=? WHERE id=?",(count,step['id']))
            if step['code']=='P00' and count>300:
                self._add(identity,'P01','Yıl aralığı — 2022–2026',year_query(session['snapshot']['initial'],2022))
            elif step['code']=='P01' and session['steps'][0]['count_value']>1000 and count>500:
                self._add(identity,'P02','Yıl aralığı — 2024–2026',year_query(session['snapshot']['initial'],2024))
            elif step['code'].startswith('P'):
                year={'P00':None,'P01':2022,'P02':2024}[step['code']]
                types=' AND ('+' OR '.join('DOCTYPE('+t+')' for t in session['snapshot']['types'])+')'
                for topic,label,query in session['snapshot']['topics']:
                    self._add(identity,topic,label,year_query('TITLE-ABS-KEY('+query+')'+types,year))
            if not self.store.db.execute("SELECT 1 FROM workflow_steps WHERE session_id=? AND state!='done'",(identity,)).fetchone():
                self.store.db.execute("UPDATE workflow_sessions SET state='completed',error='',updated_at=? WHERE id=?",(utcnow(),identity))
        return self.get(identity)



class WorkflowEngine:
    """One foreground workflow at a time; no network call holds the Store lock."""
    stable_seconds=2
    page_timeout=120
    export_timeout=900

    def __init__(self, store, capture, notify=lambda *args:None, writer=None, downloads_root=None):
        self.store=store;self.capture=capture;self.notify=notify;self.records=WorkflowRecords(store)
        self.writer=writer;self.downloads_root=downloads_root
        self.thread=None;self.launch_lock=threading.Lock();self.clock=None;self.peer=None;self.identity=None

    @property
    def running(self):return bool(self.thread and self.thread.is_alive())

    def _writer(self):
        if self.writer is None:
            from .zotero_writer import ZoteroWriter
            self.writer=ZoteroWriter(self.store)
        return self.writer

    def launch(self, peer, context, identity=None, options=None):
        with self.launch_lock:
            if self.running:raise ValidationError('Tarama zaten çalışıyor.')
            if self.capture.paused or self.capture.busy.locked() or self.capture.next_action:
                raise ValidationError('Önce duraklatılmış/bekleyen manuel yakalamayı tamamlayın.')
            if not self.store.settings().get('clock_confirmed'):
                raise ValidationError('Önce bir test PNG’sinde saat/tarihi kontrol edip Ayarlar’dan doğrulayın.')
            if context.get('profile')!=peer.profile or any(type(context.get(k)) is not int for k in ('windowId','tabId')):
                raise ValidationError('Tarama sekmesi doğrulanamadı.')
            ready=self._writer().preflight()
            if not ready.get('authorized'):raise ValidationError(ready.get('message','Önce Zotero yazma iznini verin.'))
            if identity:
                session=self.records.get(identity)
                if session['state'] in ('completed','stopped'):raise ValidationError('Bu tarama sona erdi; yeni tarama başlatın.')
                # A restart can change Chrome's session component; the selected target is explicitly rebound.
                if session['context'].get('profile','').split('/')[0]!=peer.profile.split('/')[0]:
                    raise ValidationError('Tarama farklı bir Chrome profiline ait.')
                self.records.set_session(identity,context_json=json_text(context))
            else:session=self.records.create(options or {},context);identity=session['id']
            self.records.set_session(identity,state='running',error='')
            self.capture.automation_active=True
            self.identity=identity
            self.thread=threading.Thread(target=self.run,args=(identity,peer),daemon=True,name='scopus-workflow')
            self.thread.start()
            return self.records.get(identity)

    def pause(self, identity):
        session=self.records.get(identity)
        if session['state'] not in ('completed','stopped'):self.records.set_session(identity,state='paused',error='Kullanıcı duraklattı.')
        return self.records.get(identity)

    def check(self):
        session=self.records.get(self.identity)
        if session['state']!='running':raise ValidationError(session['error'] or 'Tarama duraklatıldı.')
        self.clock.elapsed()
        if not self.peer.connected:raise ValidationError('Chrome bağlantısı koptu. Yeniden bağlanınca devam edin.')
        if self.capture.desktop.foreground()!=self.hwnd or self.capture.desktop.epoch!=self.epoch:
            raise ValidationError('Öndeki pencere değişti. Scopus’a dönüp Devam et seçin.')
        guard=self.peer.request('workflow_guard',{'sessionId':self.identity,'context':session['context']},timeout=5)
        if guard.get('ready') is not True:raise ValidationError('Scopus sekmesi etkin değil. Kontrol edip devam edin.')
        return session

    def _action(self, step, action, **extra):
        session=self.check();identity=str(uuid.uuid4())
        with self.store.lock,self.store.db:
            self.store.db.execute('INSERT INTO workflow_actions(id,step_id,action,state,created_at) VALUES(?,?,?,?,?)',
                                  (identity,step['id'],action,'pending',utcnow()))
        payload=dict(sessionId=self.identity,stepId=step['id'],actionId=identity,context=session['context'],
                     action=action,query=step['query'],expectedCount=step.get('count_value'),**extra)
        result=self.peer.request('workflow_browser',payload,timeout=12)
        self.check()
        with self.store.lock,self.store.db:
            self.store.db.execute("UPDATE workflow_actions SET state='done',result_json=? WHERE id=?",(json_text(result),identity))
        if result.get('stage') in ('login','challenge','unsupported'):
            raise ValidationError('Scopus oturumu veya sayfa düzeni kontrol gerekiyor: '+', '.join(result.get('blockers',[])))
        return result

    def _wait_results(self, step):
        stable=StableResult(step['query'],self.stable_seconds);deadline=time.monotonic()+self.page_timeout
        while time.monotonic()<deadline:
            result=self._action(step,'inspect')
            if stable.observe(result.get('data',{}),time.monotonic()):return result['data']
            time.sleep(.35)
        raise ValidationError('120 saniye içinde beklenen sorgu ve kesin sonuç doğrulanamadı. Sayfayı kontrol edip devam edin.')

    def _search(self, step):
        if step['state'] in ('queued','opening','filling'):
            self.records.update_step(step['id'],state='opening')
            deadline=time.monotonic()+self.page_timeout
            opened=False
            while time.monotonic()<deadline:
                result=self._action(step,'inspect')
                if result.get('stage')=='search' and result.get('editorReady',True):break
                if (result.get('stage')=='results' or result.get('nextAction')=='open_search') and not opened:
                    self._action(step,'open_search');opened=True
                time.sleep(.35)
            else:raise ValidationError('Scopus gelişmiş arama alanı açılamadı.')
            self.records.update_step(step['id'],state='filling')
            self._action(step,'fill_search')
            # Persist before clicking: after a lost reply, only inspect results, never blindly click again.
            self.records.update_step(step['id'],state='submitting')
            self._action(step,'submit_search')
            self.records.update_step(step['id'],state='waiting')
        return self._wait_results(step)

    def _capture(self, step, data):
        run=None;detail=dict(step.get('detail',{}))
        if step.get('capture_job_id'):
            try:job=self.store.get_job(step['capture_job_id'])
            except ValidationError:job=None
            if job and job['state']=='verified':run=self.store.get_run(job['run_id'])
        step['count_value']=data['count_value']
        session=self.check()
        if run is None:
            evidence=self._prepare_evidence(step,'query')
            detail['extra_evidence_required']=bool(evidence.get('evidence',{}).get('requiresExtraViewport'))
            job_id=str(uuid.uuid4())
            self.records.update_step(step['id'],state='capturing',capture_job_id=job_id,count_value=data['count_value'],detail_json=json_text(detail))
            run=self.capture.capture(automatic={'job_id':job_id,'context':session['context'],'query':step['query']})
            if not run or run.get('state')=='incomplete':raise ValidationError('PNG kaydı doğrulanamadı. Eksik kayıt korunuyor.')
        self.records.update_step(step['id'],run_id=run['id'],count_value=run['count_value'])
        if detail.get('extra_evidence_required') and not detail.get('evidence_complete'):
            extra_job=None
            if detail.get('extra_job_id'):
                try:extra_job=self.store.get_job(detail['extra_job_id'])
                except ValidationError:pass
            if not extra_job or extra_job['state']!='verified':
                self._prepare_evidence(step,'count')
                detail['extra_job_id']=str(uuid.uuid4())
                self.records.update_step(step['id'],detail_json=json_text(detail))
                extra=self.capture.capture(automatic={'job_id':detail['extra_job_id'],'context':session['context'],'query':step['query'],
                    'capture_action':{'attach_to':run['id'],'new_run':False,'role':'sonuc'}})
                if not extra or extra.get('state')=='incomplete':raise ValidationError('Ek kanıt görüntüsü tamamlanamadı.')
        detail['evidence_complete']=True
        self.records.update_step(step['id'],state='captured',detail_json=json_text(detail))
        self._note(step,run,'Sonuç ekranı otomatik kaydedildi.')
        return run

    def _prepare_evidence(self,step,viewport):
        deadline=time.monotonic()+15
        while True:
            result=self._action(step,'prepare_evidence',viewport=viewport)
            if result.get('ready'):
                self._wait_results(step)
                return result
            if time.monotonic()>deadline:raise ValidationError('Sorgu/sonuç ekran kanıtı için görünür yapılamadı.')
            time.sleep(.3)

    def _note(self, step, run, message):
        with self.store.lock,self.store.db:
            previous=self.store.get_run(run['id'])['notes'] or ''
            line=f"Otomatik tarama {self.identity[:8]} · {step['code']} · {step['label']}: {message}"
            if line not in previous:self.store.db.execute('UPDATE search_runs SET notes=? WHERE id=?',('\n'.join(x for x in (previous,line) if x),run['id']))

    def _export_update(self, identity, **changes):
        if set(changes)-{'state','download_id','relative_path','sha256','record_count','error'}:raise ValueError('Unsupported export fields')
        with self.store.lock,self.store.db:
            self.store.db.execute('UPDATE workflow_exports SET '+','.join(k+'=?' for k in changes)+' WHERE id=?',(*changes.values(),identity))

    def _export(self, step, run):
        from .ris import parse_ris
        count=run['count_value'];records=[]
        self.records.update_step(step['id'],state='exporting')
        # Each chunk uses Scopus's actual range control; absence of that control is a blocking error.
        for start in range(1,count+1,20000):
            end=min(count,start+19999)
            with self.store.lock,self.store.db:
                self.store.db.execute('INSERT OR IGNORE INTO workflow_exports(id,step_id,range_start,range_end,state) VALUES(?,?,?,?,?)',
                                      (str(uuid.uuid4()),step['id'],start,end,'queued'))
                export=dict(self.store.db.execute('SELECT * FROM workflow_exports WHERE step_id=? AND range_start=?',(step['id'],start)).fetchone())
            if export['state']=='complete':
                data=self.store.path(export['relative_path']).read_bytes()
                if digest(data)!=export['sha256']:raise ValidationError('Kaydedilmiş RIS dosyası değişmiş.')
                batch=parse_ris(data)
                if len(batch)!=end-start+1:raise ValidationError('Kaydedilmiş RIS sayısı değişmiş.')
                records.extend(batch);continue
            payload=dict(sessionId=self.identity,stepId=step['id'],context=self.check()['context'],exportId=export['id'],
                         expectedCount=count,rangeStart=start,rangeEnd=end)
            if export['state']=='queued':
                self.peer.request('workflow_download_arm',payload,timeout=10)
                self._action(step,'export_open')
                for attempt in range(40):
                    result=self._action(step,'export_configure',rangeStart=start,rangeEnd=end,exportId=export['id'])
                    if result.get('stage')=='export-configured':break
                    time.sleep(.2)
                else:raise ValidationError('RIS dışa aktarım seçenekleri kesinleştirilemedi.')
                self._export_update(export['id'],state='submitted')
                self._action(step,'export_submit',rangeStart=start,rangeEnd=end,exportId=export['id'])
            deadline=time.monotonic()+self.export_timeout
            while time.monotonic()<deadline:
                self.check()
                download=self.peer.request('workflow_download_status',payload,timeout=10)
                if download.get('state')=='complete':break
                if download.get('state') in ('interrupted','ambiguous','missing'):
                    raise ValidationError(download.get('error','RIS indirmesi kesin olarak eşleştirilemedi; dosyayı/Scopus Export durumunu kontrol edin.'))
                self._action(step,'export_inspect',rangeStart=start,rangeEnd=end,exportId=export['id'])
                time.sleep(1)
            else:raise ValidationError('15 dakika içinde RIS indirmesi tamamlanmadı. Export durumunu kontrol edip devam edin.')
            self.check()
            root=self.downloads_root
            if root is None:
                from win32com.shell import shell
                root=Path(shell.SHGetKnownFolderPath(shell.FOLDERID_Downloads,0,None))/'LiteraturKayit'/self.identity
            data,batch=validate_download(download['filename'],root,end-start+1,parse_ris)
            relative=f"01_HamExport/{run['display_id']}_Scopus_{start:05d}-{end:05d}_{export['id'][:8]}.ris"
            if self.store.path(relative).exists():
                if digest(self.store.path(relative).read_bytes())!=digest(data):raise ValidationError('Aynı adlı RIS dosyası farklı içerik taşıyor; üzerine yazılmadı.')
            else:self.store._atomic_write(relative,data)
            self._export_update(export['id'],state='complete',download_id=download['downloadId'],relative_path=relative,sha256=digest(data),record_count=len(batch))
            records.extend(batch)
            self._note(step,run,f'{len(batch)} künye: {relative}')
        if len(records)!=count:raise ValidationError('Toplam dışa aktarılan kayıt sayısı sonuçla eşleşmiyor.')
        return records

    def run(self, identity, peer):
        self.identity=identity;self.peer=peer;self.clock=ClockGuard();self.epoch=self.capture.desktop.epoch
        started=self.records.get(identity);base_elapsed=started['elapsed'];self.hwnd=None
        with self.capture.binding_lock:
            for hwnd,(window,bound_peer) in self.capture.bindings.items():
                if window==started['context']['windowId'] and bound_peer is peer:self.hwnd=hwnd;break
        self.capture.automation_active=True
        try:
            if self.hwnd is None:raise ValidationError('Scopus Windows penceresi eşleştirilemedi.')
            while True:
                session=self.check()
                step=next((s for s in session['steps'] if s['state']!='done'),None)
                if step is None:break
                if step.get('run_id') and step['detail'].get('evidence_complete'):run=self.store.get_run(step['run_id'])
                else:run=self._capture(step,self._search(step))
                step['count_value']=run['count_value']
                if step['code'].startswith('Q') and run['count_value']:
                    try:self.store.export_excel()
                    except Exception:raise ValidationError('PNG kaydedildi; Excel üretilemedi. Dışa aktarım başlamadı; dosya/disk durumunu kontrol edip devam edin.')
                    records=self._export(step,run)
                    self.records.update_step(step['id'],state='importing')
                    summary=self._writer().import_records(records,identity,run['id'],self.check)
                    detail=self.records.get(identity)['steps'][step['ordinal']]['detail']
                    self.records.update_step(step['id'],detail_json=json_text(dict(detail,zotero=summary)))
                    if summary.get('failed'):raise ValidationError('Bazı künyeler Zotero’ya aktarılamadı. Kalan kayıtlar korunuyor; devam ederek yeniden deneyin.')
                try:excel=self.store.export_excel()
                except Exception:raise ValidationError('Kayıtlar saklandı; Excel üretilemedi. Dosya/disk durumunu kontrol edip devam edin.')
                detail=self.records.get(identity)['steps'][step['ordinal']]['detail']
                self.records.update_step(step['id'],detail_json=json_text(dict(detail,excel=excel)))
                self.check()
                self.records.advance(identity,run['count_value'],step['code'])
                if self.records.get(identity)['state']=='completed':break
        except Exception as error:
            current=self.records.get(identity)
            if current['state']=='running':self.records.set_session(identity,state='paused',error=str(error))
        finally:
            # Elapsed is process time, never an assertion of human reading duration.
            elapsed=max(0,time.monotonic()-self.clock.monotonic)
            self.records.set_session(identity,elapsed=base_elapsed+elapsed)
            self.capture.automation_active=False
            final=self.records.get(identity)
            if final['state'] in ('completed','stopped'):
                try:peer.request('workflow_release',{'sessionId':identity},timeout=3)
                except Exception:pass
            self.notify('Scopus taraması tamamlandı.' if final['state']=='completed' else 'Scopus taraması durakladı: '+final['error'],identity)

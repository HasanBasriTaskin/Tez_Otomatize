import threading
import uuid

from .storage import utcnow


class CaptureController:
    def __init__(self,store,desktop,notify):
        self.store,self.desktop,self.notify=store,desktop,notify
        self.bindings={}
        self.binding_lock=threading.Lock()
        self.busy=threading.Lock()
        self.paused=False
        self.last_capture=None
        self.next_action={}

    def bind(self,hwnd,window_id,peer):
        if not hwnd or not self.desktop.chrome_window(hwnd):
            raise ValueError('Chrome pencere kimliği doğrulanamadı.')
        with self.binding_lock:self.bindings[hwnd]=(window_id,peer)

    def unbind(self,hwnd):
        with self.binding_lock:self.bindings.pop(hwnd,None)

    def disconnect(self,peer):
        with self.binding_lock:
            self.bindings={k:v for k,v in self.bindings.items() if v[1] is not peer}

    def capture(self):
        if self.paused:return
        if not self.busy.acquire(blocking=False):
            # A new notification would cover the first screenshot; do not show it until that job ends.
            return
        peer=None
        job_id=str(uuid.uuid4())
        begun=False
        action=dict(self.next_action)
        message=('Yakalama başlatılamadı.','')
        try:
            hwnd=self.desktop.foreground()
            epoch=self.desktop.epoch
            with self.binding_lock:binding=self.bindings.get(hwnd)
            if not self.desktop.chrome_window(hwnd):
                message=('Önce Chrome arama sonuçlarını öne getirin.','');return
            if not binding:
                message=('Chrome bağlantısı hazır değil. Eklenti yönetimini açın.','');return
            window_id,peer=binding
            ready=peer.request('prepare_capture',{'jobId':job_id,'windowId':window_id},timeout=3)
            if not ready.get('ready'):
                message=(ready.get('reason','Sayfa izni veya bağlantısı eksik.'),'');return
            context=ready['context']
            if self.desktop.foreground()!=hwnd or self.desktop.epoch!=epoch:
                message=('Pencere değişti. Sayfa sabitken yeniden Ctrl+M yapın.','');return
            self.store.begin_job(job_id,context)
            begun=True
            if self.desktop.foreground()!=hwnd or self.desktop.epoch!=epoch:
                self.store.mark_incomplete(job_id,'Görüntü alınmadan önce pencere değişti.')
                message=('Pencere değişti; görüntü alınmadı. Yeniden deneyin.',job_id);return
            stamp=utcnow()
            png=self.desktop.grab(hwnd,self.store.settings().get('monitor','active'))
            self.store.save_capture(job_id,png,captured_at=stamp)
            result=peer.request('extract_capture',{'jobId':job_id,'context':context},timeout=4)
            if self.desktop.foreground()!=hwnd or self.desktop.epoch!=epoch:
                self.store.mark_incomplete(job_id,'Yakalama sırasında ön plandaki pencere değişti.',result.get('data'))
                message=('Görüntü korundu; pencere değiştiği için kontrol gerekiyor.',job_id);return
            run=self.store.complete_job(job_id,result['data'],result['context'],new_run=action.get('new_run',False),
                                        attach_to=action.get('attach_to'),role=action.get('role','sonuc'))
            if self.next_action==action:self.next_action={}
            if run.get('state')=='incomplete':
                message=('Görüntü kaydedildi; eksik bilgileri eklentiden tamamlayın.',job_id);return
            self.last_capture=self.store.captures(run['id'])[-1]
            try:
                exported=self.store.export_excel()
                suffix='Excel güncellendi.' if exported['status']=='updated' else 'Excel ayrı sürüme yazıldı.'
                message=(f"{run['display_id']} kaydedildi. {suffix}",run['id'])
            except Exception:
                message=(f"{run['display_id']} kaydedildi; Excel güncellenemedi. Yeniden deneyin.",run['id'])
        except Exception as e:
            if begun:
                self.store.mark_incomplete(job_id,'Yakalama veya DOM bağlantısı tamamlanamadı. Kaydedilmiş görüntüyü kontrol edin.')
            message=('İşlem tamamlanamadı. Eklentide eksik kayıtları kontrol edin.',job_id if begun else '')
        finally:
            if peer:
                try:peer.request('release_capture',{'jobId':job_id},timeout=1)
                except Exception:pass
            self.busy.release()
            self.notify(*message)

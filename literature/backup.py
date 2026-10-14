import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import uuid
import zipfile
from pathlib import Path,PurePosixPath

from .storage import ValidationError,digest,json_text,utcnow


def create_backup(store):
    with store.lock:
        temp=store.path('03_Calisma/Veri/gecici')
        with tempfile.TemporaryDirectory(dir=temp) as scratch:
            snapshot=Path(scratch)/'kayit.sqlite3'
            connection=sqlite3.connect(snapshot)
            try:store.db.backup(connection)
            finally:connection.close()
            archive=Path(scratch)/'project.zip';manifest={}
            with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
                for dirname in ['00_Kilavuz','01_HamExport','02_Ekranlar','03_Calisma','04_PDF_Aday','05_Teslim','Literatur_PDF']:
                    directory=store.path(dirname)
                    if not directory.exists():continue
                    for file in directory.rglob('*'):
                        if not file.is_file():continue
                        if not file.resolve().is_relative_to(store.root):raise ValidationError('Proje dışına yönlenen dosya yedeklenmedi.')
                        relative=file.relative_to(store.root).as_posix()
                        # Excel's owner files are temporary and exclusively locked while a workbook is open.
                        if file.is_relative_to(Path(scratch)) or file.name.startswith(('kayit.sqlite3', '~$')) or file.suffix=='.tmp':continue
                        data=file.read_bytes();z.writestr(relative,data);manifest[relative]=digest(data)
                relative='03_Calisma/Veri/kayit.sqlite3';data=snapshot.read_bytes()
                z.writestr(relative,data);manifest[relative]=digest(data)
                z.writestr('manifest.json',json_text({'version':1,'created_at':utcnow(),'files':manifest,'secrets_included':False}))
            relative='Yedekler/proje_'+utcnow().replace(':','').replace('.','_')+'_'+uuid.uuid4().hex[:6]+'.zip'
            store._atomic_write(relative,archive.read_bytes())
            return str(store.path(relative))


def restore_backup(archive,destination):
    destination=Path(destination).resolve()
    if destination.exists():raise ValidationError('Geri yükleme hedefi yeni bir klasör olmalı; mevcut dosyalar ezilmez.')
    staging=destination.with_name(destination.name+'.restore-'+uuid.uuid4().hex)
    with zipfile.ZipFile(archive) as z:
        names=set();total=0
        for item in z.infolist():
            name=item.filename
            parts=PurePosixPath(name).parts
            if not parts or name.startswith('/') or '\\' in name or ':' in name or '..' in parts or any(p.endswith(('.',' ')) for p in parts):raise ValidationError('Yedekte güvenli olmayan dosya yolu.')
            if name.casefold() in names:raise ValidationError('Yedekte tekrarlı dosya yolu.')
            if (item.external_attr>>16)&0o170000==0o120000:raise ValidationError('Yedekte sembolik bağlantı kabul edilmez.')
            names.add(name.casefold());total+=item.file_size
            if total>5*1024**3:raise ValidationError('Yedek açılmış boyut sınırını aşıyor.')
        if 'manifest.json' not in z.namelist():raise ValidationError('Yedek manifesti eksik.')
        manifest=json.loads(z.read('manifest.json'))
        if manifest.get('version')!=1 or not isinstance(manifest.get('files'),dict):raise ValidationError('Desteklenmeyen yedek sürümü.')
        expected=set(manifest['files'])|{'manifest.json'}
        if set(z.namelist())!=expected:raise ValidationError('Yedek dosya listesi manifest ile eşleşmiyor.')
        staging.mkdir(parents=True)
        try:
            for name,expected_hash in manifest['files'].items():
                target=(staging/name).resolve()
                if not target.is_relative_to(staging):raise ValidationError('Geçersiz geri yükleme yolu.')
                data=z.read(name)
                if digest(data)!=expected_hash:raise ValidationError('Yedek bütünlük kontrolü başarısız.')
                target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
            db_path=staging/'03_Calisma/Veri/kayit.sqlite3'
            if not db_path.exists():raise ValidationError('Yedekte veritabanı eksik.')
            conn=sqlite3.connect(db_path)
            try:
                if conn.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValidationError('Yedekte veritabanı bozuk.')
                if conn.execute('PRAGMA user_version').fetchone()[0]>1:raise ValidationError('Yedek daha yeni uygulama gerektiriyor.')
            finally:conn.close()
            os.rename(staging,destination)
        except Exception:
            if staging.resolve().parent==destination.parent and '.restore-' in staging.name:shutil.rmtree(staging)
            raise
    return str(destination)

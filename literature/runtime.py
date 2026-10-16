import json
import os
import sys
from pathlib import Path


def product_dir():
    return Path(sys.executable).parent.parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[1]


def settings_file():
    return Path(os.environ.get('LOCALAPPDATA',str(Path.home()))) / 'LiteraturKayit' / 'settings.json'


def product():
    return json.loads((product_dir()/'product.json').read_text(encoding='utf-8-sig'))


def configuration():
    file=settings_file()
    return json.loads(file.read_text(encoding='utf-8-sig')) if file.exists() else {'project_root':str(product_dir().parent)}


# Per-installation defaults (who is recording, which Zotero library, its collection roles). They live
# next to the installation, not in the project database, so a fresh project starts with them.
DEFAULT_KEYS=('operator','library','zotero_data_dir','collection_mapping','collection_library')


def user_defaults():
    try:defaults=configuration().get('defaults')
    except (OSError,ValueError):return {}
    return {k:v for k,v in defaults.items() if k in DEFAULT_KEYS} if isinstance(defaults,dict) else {}


def suggested_defaults(config,product_info):
    """What the installer pre-fills: this computer's earlier choice, else the team default in product.json."""
    team=product_info.get('defaults') if isinstance(product_info.get('defaults'),dict) else {}
    mine=config.get('defaults') if isinstance(config.get('defaults'),dict) else {}
    result={k:str(mine.get(k) or team.get(k) or '') for k in ('operator','library')}
    # The data folder is per computer: never taken from the team file; Zotero's own default otherwise.
    result['zotero_data_dir']=str(mine.get('zotero_data_dir') or Path.home()/'Zotero')
    return result


def merge_installer_defaults(config,operator,library,team=None,zotero_data_dir=None):
    """Store the installer's answers. Collection roles stay only while the library is unchanged;
    the team's roles (product.json) are used for the team library when none are saved yet."""
    import re
    operator=(operator or '').strip();library=(library or '').strip()
    if not operator or len(operator)>120:raise ValueError('Kaydı yapan kişinin adını yazın (en çok 120 karakter).')
    if not re.fullmatch(r'(users|groups)/\d+',library):raise ValueError('Zotero kütüphanesi users/0 veya groups/1234567 biçiminde olmalı.')
    defaults=dict(config.get('defaults')) if isinstance(config.get('defaults'),dict) else {}
    if defaults.get('library')!=library:
        defaults.pop('collection_mapping',None);defaults.pop('collection_library',None)
    defaults.update(operator=operator,library=library)
    if zotero_data_dir is not None:
        folder=zotero_data_dir.strip()
        if len(folder)>500:raise ValueError('Zotero veri klasörü yolu çok uzun.')
        if folder:defaults['zotero_data_dir']=folder
        else:defaults.pop('zotero_data_dir',None)
    team=team if isinstance(team,dict) else {}
    if (not defaults.get('collection_mapping') and team.get('library')==library and team.get('collection_library')==library
            and isinstance(team.get('collection_mapping'),dict) and team['collection_mapping']):
        defaults.update(collection_mapping=dict(team['collection_mapping']),collection_library=library)
    return {**config,'defaults':defaults}


def project_folder(path,install_root=None):
    """Validate a project folder typed or pasted by the user (no native dialog needed)."""
    if not isinstance(path,str) or not path.strip() or len(path)>1000:raise ValueError('Proje klasörünün tam yolunu yazın.')
    raw=path.strip().strip('"').strip()
    folder=Path(raw).expanduser()
    if not folder.is_absolute():raise ValueError('Tam yol yazın, ör. D:\\Tez\\Deneme.')
    if not folder.is_dir():raise ValueError('Klasör bulunamadı: '+raw+'. Önce klasörü oluşturun.')
    folder=folder.resolve()
    root=Path(install_root if install_root is not None else settings_file().parent).resolve()
    if folder==root or folder.is_relative_to(root):raise ValueError('Proje klasörü uygulama kurulum klasöründen ayrı olmalı.')
    return folder


def save_user_defaults(updates):
    updates={k:v for k,v in updates.items() if k in DEFAULT_KEYS}
    if not updates:return
    file=settings_file()
    try:config=json.loads(file.read_text(encoding='utf-8-sig')) if file.exists() else {}
    except ValueError:config={}
    defaults=config.get('defaults') if isinstance(config.get('defaults'),dict) else {}
    defaults.update(updates);config['defaults']=defaults
    file.parent.mkdir(parents=True,exist_ok=True)
    temporary=file.with_name(file.name+'.tmp')
    temporary.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
    os.replace(temporary,file)

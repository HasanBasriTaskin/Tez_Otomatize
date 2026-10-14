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

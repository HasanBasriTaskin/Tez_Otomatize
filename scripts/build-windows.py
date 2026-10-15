"""Run with .venv/Scripts/python.exe scripts/build-windows.py from the repository."""
import os
import json
import shutil
import subprocess
import sys
from pathlib import Path

root=Path(__file__).resolve().parents[1]
os.chdir(root)
artifacts=root/'artifacts'
# Never follow a redirected output root when removing generated files.
if artifacts.resolve()!=artifacts:raise ValueError('artifacts başka bir klasöre yönleniyor; temizlik yapılmadı.')
if artifacts.exists():shutil.rmtree(artifacts)
work=artifacts/'work';work.mkdir(parents=True)
os.environ['TEMP']=os.environ['TMP']=str(work/'tmp')
(work/'tmp').mkdir()
windows=artifacts/'windows'
version=json.loads((root/'package.json').read_text(encoding='utf-8'))['version']
release=artifacts/'release'/('LiteraturKayit-'+version);payload=release/'payload'
subprocess.run(['npm.cmd','run','build'],check=True)
for name,entry,windowed in [('LiteraturKayit','run_tray.py',True),('NativeHost','run_host.py',False),('Kurulum','installer.py',True)]:
    args=[sys.executable,'-m','PyInstaller','--noconfirm','--name',name,'--distpath',str(windows),'--workpath',str(work/'pyinstaller'),'--specpath',str(work/'spec')]
    if windowed:args+=['--windowed']
    if name=='Kurulum':args+=['--onefile','--hidden-import','win32timezone']
    if name=='LiteraturKayit':args+=['--hidden-import','pystray._win32','--hidden-import','win32timezone']
    subprocess.run(args+[entry],check=True)
payload.mkdir(parents=True,exist_ok=True)
for name,destination in [('LiteraturKayit','tray'),('NativeHost','host')]:shutil.copytree(windows/name,payload/destination,dirs_exist_ok=True)
shutil.copytree(artifacts/'extension',payload/'extension',dirs_exist_ok=True)
shutil.copy2(root/'product.json',payload/'product.json')
shutil.copy2(windows/'Kurulum.exe',release/'Kurulum.exe')
(release/'default-project.txt').write_text('',encoding='utf-8')
for name in ['README.md','docs/MANUEL_TEST.md','docs/TEST_RAPORU.md']:
    if (root/name).exists():shutil.copy2(root/name,release/Path(name).name)
shutil.make_archive(str(release),'zip',release)
print('PACKAGE:',release)

"""Run with .venv/Scripts/python.exe scripts/build-windows.py from the repository."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

root=Path(__file__).resolve().parents[1]
os.chdir(root)
os.environ['TEMP']=os.environ['TMP']=str(root/'.tmp')
(root/'.tmp').mkdir(exist_ok=True)
release=root/'release'/'LiteraturKayit-0.1.0';payload=release/'payload'
subprocess.run(['npm.cmd','run','build'],check=True)
for name,entry,windowed in [('LiteraturKayit','run_tray.py',True),('NativeHost','run_host.py',False),('Kurulum','installer.py',True)]:
    args=[sys.executable,'-m','PyInstaller','--noconfirm','--name',name,'--distpath',str(root/'dist'),'--workpath',str(root/'build')]
    if windowed:args+=['--windowed']
    if name=='Kurulum':args+=['--onefile','--hidden-import','win32timezone']
    if name=='LiteraturKayit':args+=['--hidden-import','pystray._win32','--hidden-import','win32timezone']
    subprocess.run(args+[entry],check=True)
payload.mkdir(parents=True,exist_ok=True)
for name,destination in [('LiteraturKayit','tray'),('NativeHost','host')]:shutil.copytree(root/'dist'/name,payload/destination,dirs_exist_ok=True)
shutil.copytree(root/'extension'/'dist',payload/'extension',dirs_exist_ok=True)
shutil.copy2(root/'product.json',payload/'product.json')
shutil.copy2(root/'dist'/'Kurulum.exe',release/'Kurulum.exe')
(release/'default-project.txt').write_text(str(root.parent),encoding='utf-8')
for name in ['README.md','docs/MANUEL_TEST.md','docs/TEST_RAPORU.md']:
    if (root/name).exists():shutil.copy2(root/name,release/Path(name).name)
shutil.make_archive(str(release),'zip',release)
print('PACKAGE:',release)

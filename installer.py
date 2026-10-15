"""Per-user setup. Project evidence is never moved or removed by this program."""
import argparse
import json
import os
import shutil
import subprocess
import sys
import winreg
from pathlib import Path

APP='LiteraturKayit'
REG=r'Software\Google\Chrome\NativeMessagingHosts\com.literaturkayit.host'


def install_root():
    return Path(os.environ['LOCALAPPDATA'])/APP


def package_root():
    if getattr(sys,'frozen',False):return Path(sys.executable).parent
    root=Path(__file__).parent
    version=json.loads((root/'package.json').read_text(encoding='utf-8'))['version']
    return root/'release'/('LiteraturKayit-'+version)


def manifest_for(root,product):
    return {'name':product['host_name'],'description':'Literatur Kayit Windows bridge',
            'path':str(root/'host'/'NativeHost.exe'),'type':'stdio',
            'allowed_origins':['chrome-extension://'+product['extension_id']+'/']}


def shortcut(path,target,arguments=''):
    import pythoncom
    from win32com.client import Dispatch
    pythoncom.CoInitialize()
    try:
        path.parent.mkdir(parents=True,exist_ok=True)
        link=Dispatch('WScript.Shell').CreateShortcut(str(path))
        link.TargetPath=str(target);link.Arguments=arguments;link.WorkingDirectory=str(target.parent);link.Save()
    finally:pythoncom.CoUninitialize()


def ensure_stopped():
    import win32event
    from literature.ipc import pipe_name
    try:handle=win32event.OpenMutex(0x100000,False,'Local\\'+pipe_name().split('\\')[-1])
    except Exception:return
    handle.Close()
    raise ValueError('Önce sistem tepsisindeki Literatür Kayıt Asistanı menüsünden Çıkış seçin.')


def install(project,startup=False):
    ensure_stopped()
    source=package_root()/'payload';root=install_root()
    for name in ['host/NativeHost.exe','tray/LiteraturKayit.exe','extension/manifest.json','product.json']:
        if not (source/name).is_file():raise ValueError('Kurulum dosyaları eksik. ZIP’in tamamını bir klasöre çıkarın.')
    project=Path(project).resolve()
    if not project.is_dir():raise ValueError('Mevcut proje klasörünü seçin.')
    if project.is_relative_to(root):raise ValueError('Proje klasörü uygulama kurulumundan ayrı olmalı.')
    root.mkdir(parents=True,exist_ok=True)
    shutil.copytree(source,root,dirs_exist_ok=True)
    product=json.loads((root/'product.json').read_text(encoding='utf-8-sig'))
    config=root/'settings.json'
    settings=json.loads(config.read_text(encoding='utf-8-sig')) if config.exists() else {}
    settings['project_root']=str(project)
    config.write_text(json.dumps(settings,ensure_ascii=False,indent=2),encoding='utf-8')
    manifest=root/'native-host.json'
    manifest.write_text(json.dumps(manifest_for(root,product),ensure_ascii=False,indent=2),encoding='utf-8')
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,REG) as key:winreg.SetValueEx(key,'',0,winreg.REG_SZ,str(manifest))
    executable=root/'tray'/'LiteraturKayit.exe'
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
        if startup:winreg.SetValueEx(key,APP,0,winreg.REG_SZ,'"'+str(executable)+'"')
        else:
            try:winreg.DeleteValue(key,APP)
            except FileNotFoundError:pass
    menu=Path(os.environ['APPDATA'])/'Microsoft/Windows/Start Menu/Programs/Literatur Kayit Asistani'
    shortcut(menu/'Literatür Kayıt Asistanı.lnk',executable)
    if getattr(sys,'frozen',False):
        if Path(sys.executable).resolve()!=root/'Kaldir.exe':shutil.copy2(sys.executable,root/'Kaldir.exe')
        shortcut(menu/'Kaydı kaldır.lnk',root/'Kaldir.exe','--uninstall')
    return root


def uninstall():
    ensure_stopped()
    try:winreg.DeleteKey(winreg.HKEY_CURRENT_USER,REG)
    except FileNotFoundError:pass
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
        try:winreg.DeleteValue(key,APP)
        except FileNotFoundError:pass
    menu=Path(os.environ['APPDATA'])/'Microsoft/Windows/Start Menu/Programs/Literatur Kayit Asistani'
    for name in ['Literatür Kayıt Asistanı.lnk','Kaydı kaldır.lnk']:(menu/name).unlink(missing_ok=True)
    # Keep installed files and project data. An in-use executable cannot remove itself safely.
    return install_root()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--install');parser.add_argument('--uninstall',action='store_true');parser.add_argument('--startup',action='store_true');args=parser.parse_args()
    if args.install:install(args.install,args.startup);return
    import tkinter as tk
    from tkinter import ttk,filedialog,messagebox
    window=tk.Tk();window.title('Literatür Kayıt Asistanı — Kurulum');window.geometry('740x430');window.minsize(640,410)
    frame=ttk.Frame(window,padding=28);frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='Literatür Kayıt Asistanı',font=('Segoe UI',18,'bold')).pack(anchor='w')
    ttk.Label(frame,text='Windows uygulaması + Chrome eklentisi · v0.2.1',padding=(0,8)).pack(anchor='w')
    if args.uninstall:
        ttk.Label(frame,text='Chrome köprü kaydı, başlangıç kaydı ve kısayollar kaldırılır.\nProje verileri ve kurulum dosyaları korunur.\nChrome eklentisini chrome://extensions sayfasından ayrıca kaldırın.',wraplength=650).pack(anchor='w',pady=20)
        def remove():
            try:
                path=uninstall();messagebox.showinfo('Kayıt kaldırıldı','Kayıtlar kaldırıldı. İsterseniz şu uygulama klasörünü daha sonra silebilirsiniz:\n'+str(path));window.destroy()
            except Exception as e:messagebox.showerror('İşlem tamamlanamadı',str(e))
        ttk.Button(frame,text='Uygulama kaydını kaldır',command=remove).pack(anchor='w');window.mainloop();return
    default=package_root()/'default-project.txt'
    initial=(default.read_text(encoding='utf-8').strip() if default.exists() else '') or str(Path.home()/'Documents')
    project=tk.StringVar(value=initial);startup=tk.BooleanVar(value=False)
    ttk.Label(frame,text='Proje ana klasörü').pack(anchor='w',pady=(16,4));ttk.Entry(frame,textvariable=project).pack(fill='x')
    def browse():
        chosen=filedialog.askdirectory(title='Proje ana klasörünü seçin',initialdir=project.get())
        if chosen:project.set(chosen)
    ttk.Button(frame,text='Klasör seç',command=browse).pack(anchor='e',pady=6)
    ttk.Checkbutton(frame,text='Windows oturumu açılınca başlat',variable=startup).pack(anchor='w',pady=8)
    ttk.Label(frame,text='Yönetici hesabı gerekmez. Mevcut tez dosyaları taşınmaz.\nKurulumdan sonra Chrome’a eklentiyi bir kez yüklemeniz gerekir.',wraplength=650).pack(anchor='w',pady=10)
    def run():
        try:
            root=install(project.get(),startup.get())
            subprocess.Popen([str(root/'tray'/'LiteraturKayit.exe')],creationflags=subprocess.CREATE_NO_WINDOW)
            window.clipboard_clear();window.clipboard_append(str(root/'extension'));window.update()
            messagebox.showinfo('Windows kurulumu tamamlandı','Chrome’da chrome://extensions adresini açın.\nGeliştirici modunu açıp Paketlenmemiş öğe yükle seçin.\n\nŞu klasörü seçin (panoya kopyalandı):\n'+str(root/'extension')+'\n\nArdından eklentiyi sabitleyin ve bir sonuç sayfasında Bu sitede etkinleştir seçin.')
        except Exception as e:messagebox.showerror('Kurulum tamamlanamadı',str(e))
    ttk.Button(frame,text='Kur ve başlat',command=run).pack(anchor='w',pady=10)
    window.mainloop()


if __name__=='__main__':main()

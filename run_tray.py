import argparse
import logging
import threading
from pathlib import Path

import pystray
from PIL import Image,ImageDraw
import win32api
import win32event
import winerror

from literature.application import Application
from literature.ipc import PipeServer,pipe_name
from literature.runtime import configuration,settings_file


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--project');args=parser.parse_args()
    mutex=win32event.CreateMutex(None,False,'Local\\'+pipe_name().split('\\')[-1])
    if win32api.GetLastError()==winerror.ERROR_ALREADY_EXISTS:return
    logs=settings_file().parent;logs.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(filename=str(logs/'application.log'),level=logging.WARNING,format='%(asctime)s %(levelname)s %(message)s')
    icon=None
    def notify(message,identity=''):
        if icon:
            try:icon.notify(message,'Literatür Kayıt Asistanı')
            except Exception:pass
    app=Application(args.project or configuration()['project_root'],notify)
    def toggle():
        app.controller.paused=not app.controller.paused
        app.desktop.configure(app.store.settings()['hotkey'],app.controller.paused)
        icon.update_menu()
    def last_image():
        if app.controller.last_capture:app.command('open_capture',{'id':app.controller.last_capture['id']})
        else:app.open_manager()
    def quit_app():app.desktop.stop();icon.stop()
    image=Image.new('RGB',(64,64),'#163d4a');draw=ImageDraw.Draw(image)
    draw.rounded_rectangle((14,12,49,52),radius=3,fill='#fff8ed');draw.line((22,24,41,24),fill='#163d4a',width=4)
    draw.line((22,33,41,33),fill='#163d4a',width=4)
    icon=pystray.Icon('LiteraturKayit',image,'Literatür Kayıt Asistanı',menu=pystray.Menu(
        pystray.MenuItem('Kayıtlar ve ayarlar',lambda:app.open_manager(),default=True),
        pystray.MenuItem('Son görüntüyü aç',last_image),
        pystray.MenuItem('Proje klasörünü aç',lambda:app.command('open_folder',{'folder':'project'})),
        pystray.MenuItem(lambda item:'Yakalamayı sürdür' if app.controller.paused else 'Yakalamayı duraklat',toggle),
        pystray.MenuItem('Çıkış',quit_app)))
    server=PipeServer(app.handle,app.disconnect)
    threading.Thread(target=server.run,daemon=True,name='native-server').start()
    app.start()
    try:icon.run()
    finally:
        app.desktop.stop()
        win32api.CloseHandle(mutex)


if __name__=='__main__':main()

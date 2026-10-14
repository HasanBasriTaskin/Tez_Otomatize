import ctypes
from ctypes import wintypes
import threading
from pathlib import Path

import mss
import mss.tools
import win32api
import win32con
import win32gui
import win32process


user32=ctypes.WinDLL('user32',use_last_error=True)
kernel32=ctypes.WinDLL('kernel32',use_last_error=True)
kernel32.QueryFullProcessImageNameW.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD)]
kernel32.QueryFullProcessImageNameW.restype=wintypes.BOOL
user32.SetProcessDpiAwarenessContext.argtypes=[wintypes.HANDLE]
user32.SetProcessDpiAwarenessContext.restype=wintypes.BOOL
WINEVENTPROC=ctypes.WINFUNCTYPE(None,wintypes.HANDLE,wintypes.DWORD,wintypes.HWND,wintypes.LONG,wintypes.LONG,wintypes.DWORD,wintypes.DWORD)
user32.SetWinEventHook.argtypes=[wintypes.DWORD,wintypes.DWORD,wintypes.HMODULE,WINEVENTPROC,wintypes.DWORD,wintypes.DWORD,wintypes.DWORD]
user32.SetWinEventHook.restype=wintypes.HANDLE
user32.UnhookWinEvent.argtypes=[wintypes.HANDLE]


def enable_dpi():
    user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # Per-monitor aware v2, before creating any windows.


def parse_hotkey(text):
    parts=text.upper().replace(' ','').split('+')
    if len(parts)<2 or len(parts[-1])!=1 or not parts[-1].isalnum() or not parts[-1].isascii():
        raise ValueError('Kısayol CTRL+M veya CTRL+ALT+M biçiminde olmalı.')
    modifiers=0x4000
    for item in parts[:-1]:
        if item not in {'CTRL','ALT','SHIFT'}:raise ValueError('CTRL, ALT veya SHIFT kullanın.')
        modifiers|={'CTRL':2,'ALT':1,'SHIFT':4}[item]
    return modifiers,ord(parts[-1])


class Desktop:
    def __init__(self):
        enable_dpi()
        self.epoch=0
        self.hotkey_error=None
        self.thread_id=None
        self.hotkey='CTRL+M'
        self.paused=False
        self.ready=threading.Event()
        self.on_destroy=lambda hwnd:None
        self.callback=lambda:None

    def foreground(self):return win32gui.GetForegroundWindow()

    def chrome_window(self,hwnd):
        if not hwnd or not win32gui.IsWindow(hwnd):return False
        try:
            _,pid=win32process.GetWindowThreadProcessId(hwnd)
            process=win32api.OpenProcess(0x1000,False,pid)
            try:
                size=wintypes.DWORD(32768);name=ctypes.create_unicode_buffer(size.value)
                if not kernel32.QueryFullProcessImageNameW(int(process),0,name,ctypes.byref(size)):return False
                return Path(name.value).name.lower()=='chrome.exe' and win32gui.GetClassName(hwnd).startswith('Chrome_WidgetWin')
            finally:process.Close()
        except Exception:return False

    def monitors(self):
        with mss.MSS() as capture:return [dict(m) for m in capture.monitors]

    def grab(self,hwnd,monitor='active'):
        with mss.MSS() as capture:
            if monitor=='all':area=capture.monitors[0]
            elif monitor=='active':
                handle=win32api.MonitorFromWindow(hwnd,win32con.MONITOR_DEFAULTTONEAREST)
                left,top,right,bottom=win32api.GetMonitorInfo(handle)['Monitor']
                area=dict(left=left,top=top,width=right-left,height=bottom-top)
            else:
                index=int(monitor)
                if not 1<=index<len(capture.monitors):raise ValueError('Seçilen monitör bağlı değil.')
                area=capture.monitors[index]
            frame=capture.grab(area)
            return mss.tools.to_png(frame.rgb,frame.size)

    def start(self,hotkey,callback,on_destroy):
        self.hotkey,self.callback,self.on_destroy=hotkey,callback,on_destroy
        threading.Thread(target=self._loop,daemon=True,name='windows-events').start()
        self.ready.wait(3)

    def configure(self,hotkey,paused=False):
        parse_hotkey(hotkey)
        self.hotkey,self.paused=hotkey,paused
        if self.thread_id:win32api.PostThreadMessage(self.thread_id,win32con.WM_APP+1,0,0)

    def stop(self):
        if self.thread_id:win32api.PostThreadMessage(self.thread_id,win32con.WM_QUIT,0,0)

    def _register(self):
        try:win32gui.UnregisterHotKey(None,1)
        except Exception:pass
        self.hotkey_error=None
        if self.paused:return
        try:
            mods,key=parse_hotkey(self.hotkey)
            win32gui.RegisterHotKey(None,1,mods,key)
        except Exception:self.hotkey_error='Kısayol kullanılamıyor. CTRL+ALT+M seçebilir veya diğer uygulamadaki kısayolu kapatabilirsiniz.'

    def _loop(self):
        self.thread_id=win32api.GetCurrentThreadId()
        @WINEVENTPROC
        def event(hook,event_id,hwnd,obj,child,thread,time):
            if event_id==3:self.epoch+=1
            elif event_id==0x8001 and obj==0 and child==0:self.on_destroy(hwnd)
        self._event_callback=event
        hooks=[user32.SetWinEventHook(3,3,None,event,0,0,0),user32.SetWinEventHook(0x8001,0x8001,None,event,0,0,0)]
        self._register()
        self.ready.set()
        try:
            msg=wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(msg),None,0,0)>0:
                if msg.message==win32con.WM_HOTKEY:
                    threading.Thread(target=self.callback,daemon=True,name='capture-job').start()
                elif msg.message==win32con.WM_APP+1:self._register()
                user32.TranslateMessage(ctypes.byref(msg));user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            try:win32gui.UnregisterHotKey(None,1)
            except Exception:pass
            for hook in hooks:
                if hook:user32.UnhookWinEvent(hook)

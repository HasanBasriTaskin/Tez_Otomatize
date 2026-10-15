@echo off
setlocal
pushd "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" scripts\build-all.py
    goto result
)
py -3.12 -c "import sys; assert sys.maxsize > 2**32" >nul 2>&1
if not errorlevel 1 (
    py -3.12 scripts\build-all.py
    goto result
)
python -c "import sys; assert sys.version_info[:2] == (3, 12) and sys.maxsize > 2**32" >nul 2>&1
if not errorlevel 1 (
    python scripts\build-all.py
    goto result
)
echo Python 3.12 x64 bulunamadi. README'deki ilk kurulum adimlarini uygulayin.
cmd /c exit 1
:result
set "buildExit=%ERRORLEVEL%"
if "%buildExit%"=="0" (echo BUILD TAMAMLANDI.) else (echo BUILD BASARISIZ. Yukaridaki hata giderilmeden paket kullanmayin.)
if /i not "%~1"=="--no-pause" pause
popd
exit /b %buildExit%

"""One-command local build: dependencies, checks, both bundles and verified ZIP."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    print('\n> ' + subprocess.list2cmdline([str(arg) for arg in args]), flush=True)
    subprocess.run([str(arg) for arg in args], check=True)


def build(python, npm):
    run(python, '-m', 'pip', 'install', '-r', 'requirements.lock')
    run(npm, 'ci')
    run(npm, 'run', 'typecheck')
    run(python, '-m', 'compileall', '-q', 'literature', 'installer.py', 'run_tray.py', 'run_host.py')
    run(npm, 'audit', '--audit-level=high')
    run(npm, 'test')
    run(python, '-m', 'unittest', 'discover', '-s', 'tests', '-v')
    run(python, 'scripts/build-windows.py')
    run(python, 'scripts/check-package.py')


def main():
    if sys.platform != 'win32' or sys.version_info[:2] != (3, 12) or sys.maxsize <= 2**32:
        raise RuntimeError('Windows ve Python 3.12 x64 gerekir. README: Kaynak koddan build.')
    node, npm = shutil.which('node'), shutil.which('npm.cmd')
    if not node or not npm:
        raise RuntimeError('Node.js 24 kurun, sonra build.bat dosyasini yeniden acin.')
    run(node, '-e', 'if (Number(process.versions.node.split(".")[0]) !== 24) { console.error("Node.js 24 gerekir."); process.exit(1); }')
    os.chdir(ROOT)
    scratch = ROOT / '.tmp'
    scratch.mkdir(exist_ok=True)
    os.environ.update(TEMP=str(scratch), TMP=str(scratch), PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    python = ROOT / '.venv/Scripts/python.exe'
    if not python.exists():
        run(sys.executable, '-m', 'venv', ROOT / '.venv')
    run(python, '-c', 'import sys; assert sys.version_info[:2] == (3, 12) and sys.maxsize > 2**32, "Mevcut .venv Python 3.12 x64 olmali."')
    build(python, npm)
    version = json.loads((ROOT / 'package.json').read_text(encoding='utf-8'))['version']
    package = ROOT / 'artifacts' / 'release' / ('LiteraturKayit-' + version)
    print('\n================ CIKTILAR ================')
    print('1) Calistir     : ' + str(package / 'Kurulum.exe'))
    print('2) Chrome       : Kurulumdan sonra chrome://extensions > Paketlenmemis oge yukle >')
    print('                  ' + os.path.join(os.environ.get('LOCALAPPDATA', '%LOCALAPPDATA%'), 'LiteraturKayit', 'extension'))
    print('                  (Kurulum bu yolu panoya kopyalar. Paketteki kopya: ' + str(package / 'payload' / 'extension') + ')')
    print('3) Baskasina ver: ' + str(package) + '.zip')
    print('==========================================')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        print('\nBuild durdu: ' + str(exc), file=sys.stderr)
        sys.exit(1)

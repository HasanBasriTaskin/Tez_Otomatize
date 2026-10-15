"""Validate the distribution and write its checksum; does not install or launch it."""
import hashlib
import json
import zipfile
from pathlib import Path

root=Path(__file__).resolve().parents[1]
version=json.loads((root/'package.json').read_text(encoding='utf-8'))['version']
package=root/'artifacts'/'release'/('LiteraturKayit-'+version)
archive=Path(str(package)+'.zip')
required=['Kurulum.exe','payload/tray/LiteraturKayit.exe','payload/host/NativeHost.exe',
          'payload/extension/manifest.json','payload/extension/worker.js','payload/extension/content.js',
          'payload/extension/manager.html','payload/product.json','README.md','MANUEL_TEST.md','TEST_RAPORU.md']
with zipfile.ZipFile(archive) as packed:
    assert packed.testzip() is None,'ZIP integrity failed'
    for relative in required:
        data=(package/relative).read_bytes()
        assert packed.read(relative)==data,'ZIP differs from package: '+relative
        if relative.endswith('.exe'):assert data.startswith(b'MZ'),'Invalid Windows executable: '+relative
    assert not packed.read('default-project.txt').strip(),'Machine-specific project path leaked into package'
manifest=json.loads((package/'payload/extension/manifest.json').read_text(encoding='utf-8'))
assert manifest['version']==version and manifest['manifest_version']==3,'Extension version differs'
assert not list(package.rglob('*.sqlite3')),'User database must not be shipped'
checksum=hashlib.sha256(archive.read_bytes()).hexdigest()
Path(str(archive)+'.sha256').write_text(checksum+'  '+archive.name+'\n',encoding='utf-8')
print('PASS: installer, tray, bridge, extension, ZIP and SHA-256:',archive.name)

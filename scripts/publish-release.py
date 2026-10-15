"""Publish only a tested tag's verified archive, keeping incomplete uploads draft."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def release_info(root, tag):
    version = json.loads((root / 'package.json').read_text(encoding='utf-8'))['version']
    if not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', version) or tag != 'v' + version:
        raise ValueError('Etiket package.json sürümüyle aynı olmalı: v' + version)
    lock = json.loads((root / 'package-lock.json').read_text(encoding='utf-8'))
    if lock.get('version') != version or lock.get('packages', {}).get('', {}).get('version') != version:
        raise ValueError('package-lock.json sürümü package.json ile uyuşmuyor.')
    preview = json.loads((root / 'release.json').read_text(encoding='utf-8')).get('prerelease')
    if type(preview) is not bool:
        raise ValueError('release.json prerelease alanı true veya false olmalı.')
    notes = root / 'docs/releases' / (tag + '.md')
    if not notes.is_file() or not notes.read_text(encoding='utf-8').strip():
        raise ValueError('Sürüm notu eksik: ' + str(notes))
    return version, preview, notes


def verify_archive(root, version):
    archive = root / 'artifacts/release' / ('LiteraturKayit-' + version + '.zip')
    checksum = archive.with_suffix('.zip.sha256')
    expected = hashlib.sha256(archive.read_bytes()).hexdigest() + '  ' + archive.name
    if checksum.read_text(encoding='utf-8').strip() != expected:
        raise ValueError('Kurulum ZIP dosyasının SHA-256 özeti uyuşmuyor.')
    with zipfile.ZipFile(archive) as packed:
        if packed.testzip() is not None:
            raise ValueError('Kurulum ZIP dosyası bozuk.')
        manifest = json.loads(packed.read('payload/extension/manifest.json'))
        if manifest['version'] != version:
            raise ValueError('Paketteki eklenti sürümü etiketle uyuşmuyor.')
        for path in ('Kurulum.exe', 'payload/tray/LiteraturKayit.exe', 'payload/host/NativeHost.exe'):
            if not packed.read(path).startswith(b'MZ'):
                raise ValueError('Windows programı eksik veya bozuk: ' + path)
        if packed.read('default-project.txt').strip():
            raise ValueError('Pakette kişisel proje yolu var.')
    return archive, checksum


def publish(root, tag, repository):
    version, preview, notes = release_info(root, tag)
    archive, checksum = verify_archive(root, version)
    # A missing release is distinguishable from permission and network failures.
    existing = subprocess.run(['gh', 'api', 'repos/' + repository + '/releases/tags/' + tag], capture_output=True, text=True)
    if existing.returncode:
        try:
            missing = json.loads(existing.stdout).get('status') in (404, '404')
        except (ValueError, AttributeError):
            missing = False
        if not missing:
            raise RuntimeError('Release kontrolü başarısız: ' + existing.stderr.strip())
        args = ['gh', 'release', 'create', tag, '--repo', repository, '--verify-tag', '--draft',
                '--title', version + (' - Ön sürüm' if preview else ''), '--notes-file', str(notes)]
        if preview:
            args.append('--prerelease')
        subprocess.run(args, check=True)
    elif not json.loads(existing.stdout)['draft']:
        raise ValueError('Bu sürüm zaten yayımlanmış. Üzerine yazmak yerine yeni sürüm numarası kullanın.')
    subprocess.run(['gh', 'release', 'upload', tag, str(archive), str(checksum), '--repo', repository, '--clobber'], check=True)
    subprocess.run(['gh', 'release', 'edit', tag, '--repo', repository, '--draft=false',
                    '--prerelease=' + str(preview).lower(), '--latest=' + str(not preview).lower(),
                    '--title', version + (' - Ön sürüm' if preview else ''), '--notes-file', str(notes)], check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['validate', 'publish'])
    args = parser.parse_args()
    tag = os.environ.get('GITHUB_REF_NAME', '')
    version, preview, _ = release_info(ROOT, tag)
    if args.command == 'publish':
        publish(ROOT, tag, os.environ['GITHUB_REPOSITORY'])
    print('PASS:', tag, 'ön sürüm' if preview else 'kararlı sürüm')


if __name__ == '__main__':
    main()

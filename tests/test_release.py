import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

spec = importlib.util.spec_from_file_location('publish_release', Path(__file__).resolve().parents[1] / 'scripts/publish-release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name, data in [('package.json', {'version':'0.3.0'}),
                           ('package-lock.json', {'version':'0.3.0', 'packages':{'':{'version':'0.3.0'}}}),
                           ('release.json', {'prerelease':True})]:
            (self.root/name).write_text(json.dumps(data))
        (self.root/'docs/releases').mkdir(parents=True)
        (self.root/'docs/releases/v0.3.0.md').write_text('Preview release notes')
        (self.root/'artifacts/release').mkdir(parents=True)
        self.archive = self.root/'artifacts/release/LiteraturKayit-0.3.0.zip'
        self.pack('0.3.0')

    def pack(self, version):
        with zipfile.ZipFile(self.archive, 'w') as packed:
            packed.writestr('payload/extension/manifest.json', json.dumps({'version':version}))
            packed.writestr('default-project.txt', '')
            for name in ('Kurulum.exe','payload/tray/LiteraturKayit.exe','payload/host/NativeHost.exe'):
                packed.writestr(name, b'MZtest')
        self.checksum = self.archive.with_suffix('.zip.sha256')
        self.checksum.write_text(hashlib.sha256(self.archive.read_bytes()).hexdigest()+'  '+self.archive.name+'\n')

    def test_mismatched_tag_or_lock_and_missing_notes_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Etiket'):
            release.release_info(self.root, 'v0.3.1')
        (self.root/'package-lock.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'package-lock'):
            release.release_info(self.root, 'v0.3.0')
        (self.root/'package-lock.json').write_text(json.dumps({'version':'0.3.0','packages':{'':{'version':'0.3.0'}}}))
        (self.root/'docs/releases/v0.3.0.md').unlink()
        with self.assertRaisesRegex(ValueError, 'Sürüm notu'):
            release.release_info(self.root, 'v0.3.0')

    def test_invalid_release_channel_and_wrong_package_are_rejected(self):
        (self.root/'release.json').write_text('{"prerelease":"false"}')
        with self.assertRaisesRegex(ValueError, 'prerelease'):
            release.release_info(self.root, 'v0.3.0')
        self.pack('0.2.1')
        with self.assertRaisesRegex(ValueError, 'eklenti sürümü'):
            release.verify_archive(self.root, '0.3.0')
        self.checksum.write_text('invalid')
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            release.verify_archive(self.root, '0.3.0')

    def test_upload_failure_keeps_release_draft(self):
        missing = subprocess.CompletedProcess([], 1, '{"status":"404"}', '')
        with patch.object(release.subprocess, 'run', side_effect=[missing, None, subprocess.CalledProcessError(1,'upload')]) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                release.publish(self.root, 'v0.3.0', 'owner/repo')
        commands = [call.args[0] for call in run.call_args_list]
        self.assertIn('--draft', commands[1])
        self.assertFalse(any('edit' in command for command in commands))

    def test_draft_retry_publishes_verified_preview_without_becoming_latest(self):
        draft = subprocess.CompletedProcess([], 0, '{"draft":true}', '')
        with patch.object(release.subprocess, 'run', side_effect=[draft,None,None]) as run:
            release.publish(self.root, 'v0.3.0', 'owner/repo')
        commands = [call.args[0] for call in run.call_args_list]
        self.assertIn('upload', commands[1])
        self.assertIn('--latest=false', commands[2])
        self.assertIn('--prerelease=true', commands[2])
        self.assertIn('--draft=false', commands[2])

    def test_new_stable_release_becomes_latest_only_after_upload(self):
        (self.root/'release.json').write_text('{"prerelease":false}')
        missing = subprocess.CompletedProcess([], 1, '{"status":"404"}', '')
        with patch.object(release.subprocess, 'run', side_effect=[missing,None,None,None]) as run:
            release.publish(self.root, 'v0.3.0', 'owner/repo')
        commands = [call.args[0] for call in run.call_args_list]
        self.assertIn('--verify-tag', commands[1])
        self.assertIn('--draft', commands[1])
        self.assertIn('upload', commands[2])
        self.assertIn('--latest=true', commands[3])
        self.assertIn('--prerelease=false', commands[3])

    def test_published_release_or_api_failure_cannot_be_overwritten(self):
        for result, error in [(subprocess.CompletedProcess([],0,'{"draft":false}',''),ValueError),
                              (subprocess.CompletedProcess([],1,'{"status":"403"}','denied'),RuntimeError)]:
            with self.subTest(error=error), patch.object(release.subprocess,'run',return_value=result) as run:
                with self.assertRaises(error):
                    release.publish(self.root,'v0.3.0','owner/repo')
                self.assertEqual(run.call_count, 1)

    def test_installer_reads_display_version_from_actual_package(self):
        import installer
        manifest = self.root/'payload/extension/manifest.json'
        manifest.parent.mkdir(parents=True)
        manifest.write_text('{"version":"0.3.7"}')
        with patch.object(installer,'package_root',return_value=self.root):
            self.assertEqual(installer.package_version(),'0.3.7')
            installed = self.root/'extension/manifest.json'
            installed.parent.mkdir()
            manifest.replace(installed)
            self.assertEqual(installer.package_version(),'0.3.7')


class AutoReleaseTest(unittest.TestCase):
    """Branch pushes publish a new package.json version once; the release creates the tag."""
    setUp = ReleaseTest.setUp
    pack = ReleaseTest.pack

    def test_new_version_is_released_from_the_tested_commit(self):
        missing = subprocess.CompletedProcess([], 1, '{"status":"404"}', '')
        with patch.object(release.subprocess, 'run', side_effect=[missing, None, None, None]) as run:
            release.publish(self.root, 'v0.3.0', 'owner/repo', target='abc123')
        create = run.call_args_list[1].args[0]
        self.assertEqual(create[create.index('--target') + 1], 'abc123')
        self.assertNotIn('--verify-tag', create)

    def test_existing_tag_means_nothing_to_publish(self):
        with patch.object(release.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '{}', '')):
            self.assertTrue(release.tag_exists('owner/repo', 'v0.3.0'))
        with patch.object(release.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '{"status":"404"}', '')):
            self.assertFalse(release.tag_exists('owner/repo', 'v0.3.0'))
        with patch.object(release.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '', 'HTTP 403')):
            with self.assertRaises(RuntimeError):
                release.tag_exists('owner/repo', 'v0.3.0')

import json
import os
from pathlib import Path
import runpy
import shutil
import tempfile
import unittest
from unittest.mock import patch

BUILD_SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/build-windows.py'


class BuildOutputTest(unittest.TestCase):
    def setUp(self):
        self.previous = Path.cwd()
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        (self.root/'scripts').mkdir()
        shutil.copy2(BUILD_SCRIPT, self.root/'scripts/build-windows.py')
        (self.root/'package.json').write_text(json.dumps({'version':'0.3.0'}))
        (self.root/'product.json').write_text('{}')
        (self.root/'source.py').write_text('source must survive')
        (self.root/'artifacts').mkdir()
        (self.root/'artifacts/stale.txt').write_text('old build')
        self.commands = []

    def tearDown(self):
        os.chdir(self.previous)
        self.temp.cleanup()

    def fake_build(self, args, **kwargs):
        self.commands.append(args)
        if args[0] == 'npm.cmd':
            folder = self.root/'artifacts/extension'
            folder.mkdir(parents=True)
            (folder/'manifest.json').write_text('{}')
        else:
            name = args[args.index('--name')+1]
            folder = Path(args[args.index('--distpath')+1])
            target = folder/(name+'.exe') if name == 'Kurulum' else folder/name/(name+'.exe')
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(b'MZtest')

    def test_full_build_removes_old_outputs_and_keeps_source(self):
        with patch.dict(os.environ),patch('subprocess.run',side_effect=self.fake_build):
            runpy.run_path(str(self.root/'scripts/build-windows.py'))
        self.assertFalse((self.root/'artifacts/stale.txt').exists())
        self.assertEqual((self.root/'source.py').read_text(),'source must survive')
        self.assertTrue((self.root/'artifacts/release/LiteraturKayit-0.3.0.zip').is_file())
        for args in self.commands[1:]:
            for flag in ('--distpath','--workpath','--specpath'):
                self.assertTrue(Path(args[args.index(flag)+1]).is_relative_to(self.root/'artifacts'))
        self.assertFalse((self.root/'dist').exists())
        self.assertFalse(list(self.root.glob('*.spec')))

    def test_redirected_output_root_stops_before_cleaning_or_building(self):
        original_resolve = Path.resolve
        def redirected(path,*args,**kwargs):
            if path == self.root/'artifacts':return self.root/'source-files'
            return original_resolve(path,*args,**kwargs)
        with patch.object(Path,'resolve',redirected),patch('subprocess.run') as build:
            with self.assertRaisesRegex(ValueError,'temizlik'):
                runpy.run_path(str(self.root/'scripts/build-windows.py'))
            build.assert_not_called()
        self.assertTrue((self.root/'artifacts/stale.txt').exists())
        self.assertEqual((self.root/'source.py').read_text(),'source must survive')

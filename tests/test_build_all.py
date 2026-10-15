import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('build_all', Path(__file__).resolve().parents[1] / 'scripts/build-all.py')
build_all = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_all)


class BuildAllTest(unittest.TestCase):
    def test_build_checks_before_packaging_and_verifies_package_last(self):
        with patch.object(build_all.subprocess, 'run') as run:
            build_all.build('python.exe', 'npm.cmd')
        commands = [call.args[0] for call in run.call_args_list]
        self.assertTrue(all(call.kwargs['check'] for call in run.call_args_list))
        self.assertLess(commands.index(['npm.cmd', 'test']), commands.index(['python.exe', 'scripts/build-windows.py']))
        self.assertIn(['python.exe', '-m', 'unittest', 'discover', '-s', 'tests', '-v'], commands)
        self.assertEqual(commands[-1], ['python.exe', 'scripts/check-package.py'])

    def test_failed_dependency_stops_before_build(self):
        with patch.object(build_all.subprocess, 'run', side_effect=[None, subprocess.CalledProcessError(1, 'npm ci')]) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                build_all.build('python.exe', 'npm.cmd')
        self.assertEqual(run.call_count, 2)

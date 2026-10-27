import json
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import agentcici_cloudcc_class as shared


class SharedCloudccConfigTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.cli = self.root / 'cloudcc-cli'
        self.cli.touch()
        (self.root / 'cloudcc-cli.config.json').write_text('{"use":"dev"}')
        (self.root / '.cloudcc-cache.json').write_text('{"test":"shared-cache"}')
        for name in ('app-a', 'app-b'):
            (self.root / 'applications' / name).mkdir(parents=True)

    def project(self, app='app-a'):
        return self.root / 'applications' / app / 'cloudcc'

    def source(self, app='app-a'):
        directory = self.project(app) / 'backend/classes/AppService'
        directory.mkdir(parents=True)
        (directory / 'AppService.java').write_text('public class AppService {}')
        return directory

    def assert_clean(self, app='app-a'):
        self.assertFalse((self.root / 'backend').exists())
        for name in ('cloudcc-cli.config.json', '.cloudcc-cache.json'):
            path = self.project(app) / name
            self.assertFalse(path.exists() or path.is_symlink())

    def test_create_uses_cloudcc_project_and_only_temporary_config_links(self):
        def create(command, cwd):
            self.assertEqual(Path(cwd), self.project())
            self.assertEqual(command[1:], ['create', 'classes', 'AppService'])
            for name in ('cloudcc-cli.config.json', '.cloudcc-cache.json'):
                self.assertTrue((Path(cwd) / name).is_symlink())
                self.assertEqual((Path(cwd) / name).resolve(), self.root / name)
            self.source()
            return subprocess.CompletedProcess(command, 0)
        with patch.object(shared.subprocess, 'run', side_effect=create):
            self.assertEqual(shared.run_class(self.cli, self.root, 'app-a', 'create', 'AppService'), 0)
        self.assert_clean()

    def test_each_application_keeps_source_and_cli_config_writeback(self):
        for app in ('app-a', 'app-b'):
            source = self.source(app)
            def execute(command, cwd):
                self.assertEqual(Path(command[-1]), self.project(app))
                self.assertEqual(Path(cwd), self.project(app))
                (source / 'config.json').write_text('{"id":"remote-class-id"}')
                (Path(cwd) / '.cloudcc-cache.json').write_text('{"test":"refreshed-cache"}')
                return subprocess.CompletedProcess(command, 0)
            with patch.object(shared.subprocess, 'run', side_effect=execute):
                self.assertEqual(shared.run_class(self.cli, self.root, app, 'publish', 'AppService'), 0)
            self.assertEqual(json.loads((source / 'config.json').read_text())['id'], 'remote-class-id')
            self.assert_clean(app)
        self.assertIn('refreshed-cache', (self.root / '.cloudcc-cache.json').read_text())

    def test_cache_invalidation_and_recreation_updates_root_even_when_cli_fails(self):
        self.source()
        def refresh(command, cwd):
            cache = Path(cwd) / '.cloudcc-cache.json'
            cache.unlink()
            cache.write_text('{"test":"fresh-after-invalidation"}')
            return subprocess.CompletedProcess(command, 7)
        with patch.object(shared.subprocess, 'run', side_effect=refresh):
            self.assertEqual(shared.run_class(self.cli, self.root, 'app-a', 'validate', 'AppService'), 7)
        self.assertIn('fresh-after-invalidation', (self.root / '.cloudcc-cache.json').read_text())
        self.assert_clean()

    def test_cache_invalidation_without_recreation_removes_stale_root_cache(self):
        self.source()
        def reject(command, cwd):
            (Path(cwd) / '.cloudcc-cache.json').unlink()
            raise OSError('process failed')
        with patch.object(shared.subprocess, 'run', side_effect=reject):
            with self.assertRaises(OSError):
                shared.run_class(self.cli, self.root, 'app-a', 'validate', 'AppService')
        self.assertFalse((self.root / '.cloudcc-cache.json').exists())
        self.assert_clean()

    def test_missing_root_cache_is_created_by_cli_without_synthetic_credentials(self):
        self.source()
        (self.root / '.cloudcc-cache.json').unlink()
        def first_run(command, cwd):
            cache = Path(cwd) / '.cloudcc-cache.json'
            self.assertTrue(cache.is_symlink())
            self.assertFalse(cache.exists())
            cache.write_text('{"test":"created-by-cli"}')
            return subprocess.CompletedProcess(command, 0)
        with patch.object(shared.subprocess, 'run', side_effect=first_run):
            shared.run_class(self.cli, self.root, 'app-a', 'validate', 'AppService')
        self.assertIn('created-by-cli', (self.root / '.cloudcc-cache.json').read_text())
        self.assert_clean()

    def test_cli_failure_and_process_exception_cleanup_links(self):
        self.source()
        for result in (subprocess.CompletedProcess([], 9), OSError('process failed')):
            with patch.object(shared.subprocess, 'run', **({'side_effect': result} if isinstance(result, Exception) else {'return_value': result})):
                if isinstance(result, Exception):
                    with self.assertRaises(OSError):
                        shared.run_class(self.cli, self.root, 'app-a', 'validate', 'AppService')
                else:
                    self.assertEqual(shared.run_class(self.cli, self.root, 'app-a', 'validate', 'AppService'), 9)
            self.assert_clean()

    def test_existing_project_configs_and_dangling_links_are_never_overwritten(self):
        self.source()
        for name in ('cloudcc-cli.config.json', '.cloudcc-cache.json'):
            path = self.project() / name
            for linked in (False, True):
                if linked: path.symlink_to(self.root / 'missing.json')
                else: path.write_text('keep')
                with patch.object(shared.subprocess, 'run') as run:
                    with self.assertRaises(RuntimeError):
                        shared.run_class(self.cli, self.root, 'app-a', 'validate', 'AppService')
                    run.assert_not_called()
                self.assertTrue(path.is_symlink() if linked else path.read_text() == 'keep')
                path.unlink()
        self.assert_clean()

    def test_symlink_creation_failure_cleans_first_link(self):
        self.source()
        original = Path.symlink_to
        def link(path, target, **kwargs):
            if path.name == '.cloudcc-cache.json': raise OSError('symlink unavailable')
            original(path, target, **kwargs)
        with patch.object(Path, 'symlink_to', link), patch.object(shared.subprocess, 'run') as run:
            with self.assertRaises(OSError):
                shared.run_class(self.cli, self.root, 'app-a', 'validate', 'AppService')
            run.assert_not_called()
        self.assert_clean()

    def test_legacy_layout_is_not_moved_or_duplicated(self):
        source = self.root / 'applications/app-a/backend/classes/AppService'
        source.mkdir(parents=True)
        (source / 'AppService.java').write_text('keep')
        with patch.object(shared.subprocess, 'run') as run:
            for action in ('validate', 'create'):
                with self.assertRaises(RuntimeError):
                    shared.run_class(self.cli, self.root, 'app-a', action, 'AppService')
            run.assert_not_called()
        self.assertEqual((source / 'AppService.java').read_text(), 'keep')

    def test_platform_backend_is_untouched_and_existing_class_is_not_created_again(self):
        self.source()
        existing = self.root / 'backend/classes/AppService'
        existing.mkdir(parents=True)
        (existing / 'keep.txt').write_text('platform')
        with patch.object(shared.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)):
            shared.run_class(self.cli, self.root, 'app-a', 'validate', 'AppService')
        self.assertEqual((existing / 'keep.txt').read_text(), 'platform')
        with patch.object(shared.subprocess, 'run') as run:
            with self.assertRaises(RuntimeError):
                shared.run_class(self.cli, self.root, 'app-a', 'create', 'AppService')
            run.assert_not_called()

    def test_source_file_and_directory_symlinks_are_rejected(self):
        source = self.source()
        java = source / 'AppService.java'
        java.unlink()
        outside = self.root / 'outside.java'
        outside.write_text('keep')
        java.symlink_to(outside)
        with patch.object(shared.subprocess, 'run') as run:
            with self.assertRaises(RuntimeError):
                shared.run_class(self.cli, self.root, 'app-a', 'validate', 'AppService')
            run.assert_not_called()
        self.assert_clean()
        other = self.project('app-b')
        other.symlink_to(self.project())
        with patch.object(shared.subprocess, 'run') as run:
            with self.assertRaises(RuntimeError):
                shared.run_class(self.cli, self.root, 'app-b', 'validate', 'AppService')
            run.assert_not_called()

    def test_concurrent_application_cannot_share_cache_during_operation(self):
        self.source('app-a')
        self.source('app-b')
        with shared.project_lock(self.root / 'cloudcc-cli.config.json'):
            with patch.object(shared.subprocess, 'run') as run:
                with self.assertRaisesRegex(RuntimeError, '正在使用'):
                    shared.run_class(self.cli, self.root, 'app-b', 'validate', 'AppService')
                run.assert_not_called()
        self.assert_clean('app-b')

    def test_format_arguments_and_invalid_inputs(self):
        self.source()
        with patch.object(shared.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run:
            shared.run_class(self.cli, self.root, 'app-a', 'format', 'AppService', '--check')
            self.assertEqual(run.call_args.args[0][-2:], [str(self.project()), '--check'])
            run.reset_mock()
            for app in ('../outside', 'missing'):
                with self.assertRaises(RuntimeError): shared.run_class(self.cli, self.root, app, 'create', 'AppService')
            with self.assertRaises(RuntimeError): shared.run_class(self.cli, self.root, 'app-a', 'validate', 'AppService', '--write')
            (self.root / 'cloudcc-cli.config.json').unlink()
            with self.assertRaises(RuntimeError): shared.run_class(self.cli, self.root, 'app-a', 'create', 'AppService')
            run.assert_not_called()

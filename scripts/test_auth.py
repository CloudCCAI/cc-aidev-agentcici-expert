import base64
import contextlib
import io
import json
import os
from pathlib import Path
import shlex
import tempfile
import unittest
from unittest.mock import patch
import agentcici_auth as auth
from agentcici_manage import Client


def encoded(secret="test'中文$HOME", url='https://cici.example.test'):
    values = (url, 'client', secret)
    return base64.b64encode('\n'.join('export '+k+'='+shlex.quote(v) for k,v in zip(auth.NAMES, values)).encode()).decode()


class AuthTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / auth.CONFIG_NAME
        self.env_patch = patch.dict(os.environ, {'AGENTCICI_CONFIG_PATH': str(self.path)}, clear=True)
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.exchange = patch.object(Client, 'exchange', return_value='ephemeral-token').start()
        self.addCleanup(patch.stopall)

    def save(self, env='dev', secret="test'中文$HOME"):
        return auth.login(encoded(secret), env)

    def test_decode_without_shell_execution(self):
        self.assertEqual(auth.decode_login(encoded())[auth.NAMES[2]], "test'中文$HOME")

    def test_reject_invalid_and_extra_commands(self):
        for text in ['invalid!', base64.b64encode(b'export X=y; whoami').decode()]:
            with self.assertRaises(RuntimeError):
                auth.decode_login(text)

    def test_reject_remote_http(self):
        with self.assertRaises(RuntimeError):
            auth.decode_login(encoded(url='http://cici.example.test'))

    def test_save_plain_credentials_and_reload_without_token(self):
        self.save()
        saved = json.loads(self.path.read_text())
        self.assertEqual(saved['use'], 'dev')
        self.assertEqual(set(saved['dev']), {'baseUrl', 'clientId', 'clientSecret'})
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertIn('/' + auth.CONFIG_NAME, (self.path.parent / '.gitignore').read_text())
        client = Client()
        self.assertEqual(client.client_secret, "test'中文$HOME")
        self.assertEqual(client.token, '')
        self.assertNotIn('ephemeral-token', self.path.read_text())

    def test_failed_login_keeps_existing_configuration(self):
        self.save()
        previous = self.path.read_bytes()
        self.exchange.side_effect = RuntimeError('secret error')
        with self.assertRaisesRegex(RuntimeError, '登录验证失败'):
            self.save('prod', 'replacement')
        self.assertEqual(self.path.read_bytes(), previous)

    def test_switch_and_login_preserve_other_environments(self):
        self.save('dev', 'dev-secret')
        self.save('prod', 'prod-secret')
        self.assertEqual(Client().client_secret, 'prod-secret')
        auth.local_command('use', 'dev')
        self.assertEqual(Client().client_secret, 'dev-secret')
        self.save(secret='rotated')
        self.assertEqual(json.loads(self.path.read_text())['prod']['clientSecret'], 'prod-secret')
        self.assertEqual(Client().client_secret, 'rotated')

    def test_profile_override_does_not_change_use(self):
        self.save('dev', 'dev-secret')
        self.save('prod', 'prod-secret')
        with patch.dict(os.environ, {'AGENTCICI_LOGIN_PROFILE': 'dev'}):
            self.assertEqual(Client().client_secret, 'dev-secret')
            self.assertEqual(auth.local_command('status', 'prod')['env'], 'prod')
        self.assertEqual(json.loads(self.path.read_text())['use'], 'prod')

    def test_unknown_environment_never_falls_back(self):
        self.save()
        previous = self.path.read_bytes()
        for command in ('use', 'status', 'logout'):
            with self.assertRaises(RuntimeError):
                auth.local_command(command, 'missing')
        self.assertEqual(self.path.read_bytes(), previous)

    def test_invalid_environment_rejected_before_request(self):
        for name in ('../prod', 'use'):
            with self.assertRaises(RuntimeError):
                self.save(name)
        self.exchange.assert_not_called()

    def test_logout_only_removes_selected_environment(self):
        self.save('dev', 'dev-secret')
        self.save('prod', 'prod-secret')
        auth.local_command('logout', 'dev')
        self.assertEqual(Client().client_secret, 'prod-secret')
        self.assertNotIn('dev', json.loads(self.path.read_text()))
        auth.local_command('logout')
        self.assertFalse(self.path.exists())

    def test_logout_active_environment_selects_remaining(self):
        self.save('dev', 'dev-secret')
        self.save('prod', 'prod-secret')
        auth.local_command('logout')
        self.assertEqual(Client().client_secret, 'dev-secret')

    def test_status_and_login_output_omit_secret(self):
        result = self.save(secret='private-secret')
        self.assertNotIn('private-secret', json.dumps(result))
        output = io.StringIO()
        with patch('sys.argv', ['auth', 'status']), contextlib.redirect_stdout(output):
            self.assertEqual(auth.main(), 0)
        self.assertEqual(json.loads(output.getvalue())['env'], 'dev')
        self.assertNotIn('private-secret', output.getvalue())
        self.assertNotIn('clientSecret', output.getvalue())

    def test_partial_environment_does_not_mix_identities(self):
        self.save()
        with patch.dict(os.environ, {auth.NAMES[0]: 'https://other.example.test'}):
            with self.assertRaisesRegex(RuntimeError, '不与已保存身份混用'):
                Client()

    def test_full_environment_needs_no_file(self):
        with patch.dict(os.environ, dict(zip(auth.NAMES, ['https://cici.example.test', 'client', 'secret']))):
            self.assertEqual(Client().client_secret, 'secret')
        self.assertFalse(self.path.exists())

    def test_child_directory_discovers_project_config(self):
        self.save()
        child = self.path.parent / 'application' / 'src'
        child.mkdir(parents=True)
        with patch.dict(os.environ, {}, clear=True), patch.object(Path, 'cwd', return_value=child):
            self.assertEqual(auth.config_path(), self.path)
            self.assertEqual(Client().client_id, 'client')

    def test_application_login_creates_shared_root_config_from_nested_working_directory(self):
        child = self.path.parent / 'applications' / 'test-app' / 'cloudcc'
        child.mkdir(parents=True)
        with patch.dict(os.environ, {}, clear=True), patch.object(Path, 'cwd', return_value=child):
            self.assertEqual(auth.config_path(), self.path)
            self.save()
        self.assertTrue(self.path.is_file())
        self.assertFalse((child / auth.CONFIG_NAME).exists())
        self.assertFalse((child.parent / auth.CONFIG_NAME).exists())

    def test_legacy_application_identity_is_not_silently_selected(self):
        child = self.path.parent / 'applications' / 'test-app' / 'src'
        child.mkdir(parents=True)
        old = child.parent / auth.CONFIG_NAME
        old.write_text('{}')
        with patch.dict(os.environ, {}, clear=True), patch.object(Path, 'cwd', return_value=child):
            with self.assertRaisesRegex(RuntimeError, '应用内旧登录配置'):
                auth.config_path()
        with patch.dict(os.environ, {'AGENTCICI_CONFIG_PATH': str(old)}, clear=True):
            self.assertEqual(auth.config_path(), old.resolve())
        self.assertEqual(old.read_text(), '{}')

    def test_new_project_uses_current_directory_and_dev(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(Path, 'cwd', return_value=self.path.parent):
            self.assertEqual(auth.config_path(), self.path)
            self.assertEqual(auth.login(encoded())['env'], 'dev')

    def test_cli_use_environment(self):
        self.save('dev')
        self.save('prod')
        with patch('sys.argv', ['auth', 'use', 'dev']), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(auth.main(), 0)
        self.assertEqual(json.loads(self.path.read_text())['use'], 'dev')

    def test_corrupt_or_incomplete_config_errors_without_replacing(self):
        for value in ('[]', '{broken', '{"use":"prod"}', '{"use":"prod","prod":{}}'):
            self.path.write_text(value)
            with self.assertRaises(RuntimeError):
                Client()
            self.assertEqual(self.path.read_text(), value)

    def test_unsafe_manually_edited_address_rejected(self):
        self.save()
        root = json.loads(self.path.read_text())
        root['dev']['baseUrl'] = 'http://remote.example.test'
        self.path.write_text(json.dumps(root))
        with self.assertRaises(RuntimeError):
            Client()

    def test_atomic_write_failure_preserves_config_and_cleans_temporary(self):
        self.save()
        previous = self.path.read_bytes()
        with patch.object(auth.os, 'replace', side_effect=OSError('write failed')):
            with self.assertRaisesRegex(RuntimeError, '无法保存'):
                self.save('prod')
        self.assertEqual(self.path.read_bytes(), previous)
        self.assertEqual(list(self.path.parent.glob('.cloudcc-agentcici-*.tmp')), [])


if __name__ == '__main__':
    unittest.main()

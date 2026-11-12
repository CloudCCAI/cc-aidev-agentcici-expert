import unittest
from unittest.mock import Mock
from agentcici_manage import parser, execute

class ManagementTests(unittest.TestCase):
    def run_command(self, *args, client=None):
        client = client or Mock()
        execute(client, parser().parse_args(args))
        return client

    def test_skill_partial_update_preserves_definition(self):
        client = Mock()
        client.request.return_value = {'id': 9, 'skillCode': 'birthday', 'name': 'Old', 'runtimeApis': [], 'enabled': True}
        self.run_command('skills', 'update', '9', '--json', '{"name":"New"}', client=client)
        client.request.assert_called_with('PUT', '/openapi/v1/management/skills/9',
            {'skillCode': 'birthday', 'name': 'New', 'runtimeApis': [], 'enabled': True})

    def test_mcp_update_preserves_other_fields(self):
        client = Mock()
        client.request.return_value = {'id': 3, 'name': 'Existing', 'url': 'https://example.com/mcp',
                                       'transportType': 'streamableHttp', 'enabled': True,
                                       'clientSecretConfigured': True}
        self.run_command('mcp', 'update', '3', '--json', '{"name":"New"}', client=client)
        client.request.assert_called_with('PUT', '/openapi/v1/management/mcp-servers/3',
            {'name': 'New', 'url': 'https://example.com/mcp', 'transportType': 'streamableHttp', 'enabled': True})

    def test_mcp_tool_discovery_and_cached_read(self):
        c = self.run_command('mcp', 'discover', '3')
        c.request.assert_called_once_with('POST', '/openapi/v1/management/mcp-servers/3/discover')
        c = self.run_command('mcp', 'tools', '3')
        c.request.assert_called_once_with('GET', '/openapi/v1/management/mcp-servers/3/tools')

    def test_existing_tool_catalog_is_read_only(self):
        import contextlib
        import io
        c = self.run_command('tools', 'list')
        c.request.assert_called_once_with('GET', '/openapi/v1/management/tools')
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parser().parse_args(('tools', 'create'))

    def test_compile_and_publish_use_explicit_version(self):
        c = self.run_command('agents', 'publish', 'a', '--version-no', '7')
        c.request.assert_called_once_with('POST', '/openapi/v1/management/agents/a/publish', {'versionNo': 7})
        c = self.run_command('skills', 'compile', '9')
        c.request.assert_called_once_with('POST', '/openapi/v1/management/skills/9/compile', {})

    def test_binding_isolated_and_explicit_clear(self):
        c = self.run_command('agents', 'bind-knowledge', 'a', '--json', '{"knowledgeBaseIds":[]}')
        c.request.assert_called_once_with('PATCH', '/openapi/v1/management/agents/a', {'knowledgeBaseIds': []})
        with self.assertRaises(RuntimeError):
            self.run_command('agents', 'bind-tools', 'a', '--json', '{"toolIds":[],"channels":[]}')
        with self.assertRaises(RuntimeError):
            self.run_command('agents', 'bind-skills', 'a', '--json', '{}')

    def test_tool_binding_accepts_runtime_policies(self):
        body = {'toolIds': ['managed_web_search', 'structured_web_search'],
                'toolLoadingModes': {'managed_web_search': 'always-on', 'structured_web_search': 'on-demand'},
                'toolRuntimePolicies': {
                    'managed_web_search': {'policyVersion': 2, 'qualityMode': 'QUICK_PREVIEW', 'preset': 'FAST'},
                    'structured_web_search': {'preset': 'CUSTOM', 'maxCallsPerRun': 1,
                                              'maxAttemptsPerRun': 2, 'singleCallTimeoutMs': 10000,
                                              'maxResults': 10, 'queryRewrite': False}}}
        import json
        client = self.run_command('agents', 'bind-tools', 'a', '--json', json.dumps(body))
        client.request.assert_called_once_with('PATCH', '/openapi/v1/management/agents/a', body)

    def test_knowledge_access_routes_preserve_role_ids_and_version(self):
        path = '/openapi/v1/management/knowledge-bases/30/access'
        client = self.run_command('knowledge', 'get-access', '30')
        client.request.assert_called_once_with('GET', path)
        client = self.run_command('knowledge', 'set-access', '30', '--json',
                                  '{"mode":"ROLE_RESTRICTED","roleIds":["role-a"],"expectedVersion":0}')
        client.request.assert_called_once_with(
            'PUT', path, {'mode': 'ROLE_RESTRICTED', 'roleIds': ['role-a'], 'expectedVersion': 0})

    def test_delete_requires_matching_id(self):
        c = Mock()
        with self.assertRaises(RuntimeError):
            self.run_command('skills', 'delete', '9', '--confirm-id', '8', client=c)
        c.request.assert_not_called()

    def test_invalid_version_never_sent(self):
        c = Mock()
        with self.assertRaises(RuntimeError):
            self.run_command('agents', 'publish', 'a', '--version-no', '0', client=c)
        c.request.assert_not_called()

    def test_export_writes_native_bytes_and_never_overwrites(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'agent.ciciagent'
            client = Mock()
            client.download.return_value = b'native-package-bytes'
            self.run_command('agents', 'export', 'mail', '--output', str(output), client=client)
            self.assertEqual(output.read_bytes(), b'native-package-bytes')
            client.download.assert_called_once_with('GET', '/openapi/v1/management/agents/mail/package', None)
            with self.assertRaises(RuntimeError):
                self.run_command('agents', 'export', 'mail', '--output', str(output), client=client)
            self.assertEqual(client.download.call_count, 1)

    def test_skill_export_explicit_draft(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            client = Mock()
            client.download.return_value = b'zip'
            self.run_command('skills', 'export', '36', '--allow-draft', '--output', str(Path(directory) / 'skill.zip'), client=client)
            client.download.assert_called_once_with('POST', '/openapi/v1/management/skills/36/package', {'allowDraft': True})

    def test_create_key_private_file_and_redacted_result(self):
        import json
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'key.json'
            client = Mock()
            payload = {'credential': {'id': 17}, 'plainKey': 'test-secret'}
            client.request.return_value = payload
            result = execute(client, parser().parse_args(['agents', 'create-api-key', 'a/b', '--json', '{"name":"test"}', '--output', str(output)]))
            client.request.assert_called_once_with('POST', '/openapi/v1/management/agents/a%2Fb/api-keys', {'name': 'test', 'maxPromptChars': 64000, 'maxResponseChars': 128000})
            self.assertEqual(json.loads(output.read_text()), payload)
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            self.assertEqual(result, {'file': str(output.resolve()), 'credentialId': 17})
            with self.assertRaises(RuntimeError):
                self.run_command('agents', 'create-api-key', 'a', '--json', '{"name":"test"}', '--output', str(output), client=client)
            self.assertEqual(client.request.call_count, 1)

    def test_create_key_preserves_explicit_character_limits(self):
        import tempfile
        from pathlib import Path
        for limits, expected in [
            ({'maxPromptChars': 12000}, {'maxPromptChars': 12000, 'maxResponseChars': 128000}),
            ({'maxResponseChars': 32000}, {'maxPromptChars': 64000, 'maxResponseChars': 32000}),
            ({'maxPromptChars': 12000, 'maxResponseChars': 32000}, {'maxPromptChars': 12000, 'maxResponseChars': 32000}),
        ]:
            with self.subTest(limits=limits), tempfile.TemporaryDirectory() as directory:
                import json
                client = Mock()
                client.request.return_value = {'credential': {'id': 17}, 'plainKey': 'test-secret'}
                self.run_command('agents', 'create-api-key', 'a', '--json', json.dumps({'name': 'test', **limits}), '--output', str(Path(directory) / 'key.json'), client=client)
                client.request.assert_called_once_with('POST', '/openapi/v1/management/agents/a/api-keys', {'name': 'test', **expected})

    def test_create_key_unknown_result_not_retried_or_leaked(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            client = Mock()
            client.request.side_effect = RuntimeError('sensitive-server-content')
            with self.assertRaisesRegex(RuntimeError, '结果可能未知') as error:
                self.run_command('agents', 'create-api-key', 'a', '--json', '{"name":"test"}', '--output', str(Path(directory) / 'key.json'), client=client)
            self.assertNotIn('sensitive-server-content', str(error.exception))
            self.assertEqual(client.request.call_count, 1)

    def test_revoke_key_requires_exact_credential_confirmation(self):
        client = self.run_command('agents', 'revoke-api-key', 'a', '17', '--confirm-id', '17')
        client.request.assert_called_once_with('POST', '/openapi/v1/management/agents/a/api-keys/17/revoke', {})
        for credential_id, confirmation in [('17', '18'), ('0', '0'), ('-1', '-1')]:
            client = Mock()
            with self.assertRaises(RuntimeError):
                self.run_command('agents', 'revoke-api-key', 'a', credential_id, '--confirm-id', confirmation, client=client)
            client.request.assert_not_called()

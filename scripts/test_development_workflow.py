import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import agentcici_application as app
from agentcici_manage import Client, NoCredentialRedirect, execute, parser
from test_application import fixture


class KnowledgeCommandsTest(unittest.TestCase):
    def run_command(self, *args, client=None):
        client = client or Mock()
        execute(client, parser().parse_args(('knowledge', *args)))
        return client

    def test_lifecycle_and_partial_update_preserve_name(self):
        client = Mock()
        client.request.return_value = {'id': 3, 'name': 'Docs', 'description': 'Old', 'companyId': 'org'}
        self.run_command('update', '3', '--json', '{"description":"New"}', client=client)
        client.request.assert_called_with('PUT', '/openapi/v1/management/knowledge-bases/3', {'name': 'Docs', 'description': 'New'})
        self.run_command('documents', '3').request.assert_called_once_with('GET', '/openapi/v1/management/knowledge-bases/3/documents')
        self.run_command('publish-document', '9').request.assert_called_once_with('POST', '/openapi/v1/management/knowledge-bases/documents/9/publish', {})
        self.run_command('reindex-document', '9').request.assert_called_once_with('POST', '/openapi/v1/management/knowledge-bases/documents/9/reindex', {})

    def test_upload_uses_multipart_client_and_retrieval_has_separate_body(self):
        client = self.run_command('upload', '3', '--file', '/project/approved.txt')
        client.upload_document.assert_called_once_with('/openapi/v1/management/knowledge-bases/3/documents', '/project/approved.txt')
        client.request.assert_not_called()
        self.run_command('retrieve', '3', '--json', '{"query":"test"}').request.assert_called_once_with(
            'POST', '/openapi/v1/management/knowledge-bases/3/retrieval/test', {'query': 'test'})

    def test_multipart_client_uses_developer_token_and_never_redirects(self):
        with tempfile.TemporaryDirectory() as directory:
            document = Path(directory) / 'guide.txt'
            document.write_text('approved test material')
            client = Client({'AGENTCICI_BASE_URL': 'https://cici.example.test', 'AGENTCICI_CLIENT_ID': 'client', 'AGENTCICI_CLIENT_SECRET': 'secret'})
            client.token = 'short-lived-token'
            response = Mock()
            response.__enter__ = Mock(return_value=io.StringIO('{"success":true,"data":{"id":9}}'))
            response.__exit__ = Mock(return_value=False)
            with patch('agentcici_manage.urllib.request.build_opener') as opener:
                opener.return_value.open.return_value = response
                self.assertEqual(client.upload_document('/upload', document), {'id': 9})
                self.assertIsInstance(opener.call_args.args[0], NoCredentialRedirect)
                request = opener.return_value.open.call_args.args[0]
                self.assertEqual(request.get_header('Authorization'), 'Bearer short-lived-token')
                self.assertIn(b'approved test material', request.data)
                self.assertIn(b'name="file"; filename="guide.txt"', request.data)

    def test_delete_requires_same_document_id(self):
        client = Mock()
        with self.assertRaises(RuntimeError):
            self.run_command('delete-document', '9', '--confirm-id', '8', client=client)
        client.request.assert_not_called()
        self.run_command('delete-document', '9', '--confirm-id', '9').request.assert_called_once_with(
            'DELETE', '/openapi/v1/management/knowledge-bases/documents/9')


class BusinessPackageTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = fixture(self.root)
        self.config['installationManifest'] = {
            'schemaVersion': 1, 'steps': [{'key': 'menu', 'type': 'menu', 'payload': {'pname': 'record_menu'}}],
            'renderConfig': {'renderer': 'iframe', 'entryUrl': 'https://app.test/index.html',
                             'positions': ['home'], 'closeBehavior': 'hide', 'hostLayer': 'content'}}
        (self.root / 'cloudcc/metadata').mkdir(parents=True)
        (self.root / 'cloudcc/backend/classes').mkdir(parents=True)
        (self.root / 'cloudcc/metadata/Record.json').write_text(json.dumps({'apiName': 'Record', 'label': '记录'}))
        (self.root / 'cloudcc/backend/classes/RecordService.java').write_text('public class RecordService {}')
        self.config['cloudccResources'] = [
            {'key': 'record', 'kind': 'object', 'file': 'cloudcc/metadata/Record.json'},
            {'key': 'record-service', 'kind': 'class', 'apiName': 'RecordService', 'label': '记录服务',
             'file': 'cloudcc/backend/classes/RecordService.java', 'dependsOn': ['record']}]

    def build(self, name='release.zip'):
        (self.root / 'application.json').write_text(json.dumps(self.config))
        result = app.package(self.root / 'application.json', self.root / name)
        return app.read_zip(Path(result['path']).read_bytes())

    def test_packages_objects_and_classes_together_with_native_agent_and_skill(self):
        files = self.build()
        manifest = app.validate(files)
        self.assertEqual(manifest['formatVersion'], 2)
        self.assertEqual(manifest['installationManifest']['schemaVersion'], 2)
        self.assertEqual(files['agents/assistant.ciciagent'], (self.root / 'agent.ciciagent').read_bytes())
        self.assertIn('cloudcc/metadata/Record.json', files)

    def test_cycle_missing_dependency_and_source_org_id_rejected(self):
        self.config['cloudccResources'][0]['dependsOn'] = ['record-service']
        with self.assertRaisesRegex(ValueError, '循环'):
            self.build()
        self.config['cloudccResources'][0]['dependsOn'] = ['missing']
        with self.assertRaisesRegex(ValueError, '依赖'):
            self.build()
        self.config['cloudccResources'][0].pop('dependsOn')
        (self.root / 'cloudcc/metadata/Record.json').write_text(json.dumps({'apiName': 'Record', 'label': '记录', 'id': 'source-org-id'}))
        with self.assertRaisesRegex(ValueError, '组织ID'):
            self.build()

    def test_symlink_resource_is_not_followed(self):
        path = self.root / 'cloudcc/metadata/Record.json'
        path.unlink()
        target = self.root / 'private.json'
        target.write_text('{}')
        path.symlink_to(target)
        with self.assertRaisesRegex(ValueError, '符号链接'):
            self.build()

    def test_credentials_cannot_be_copied_into_site(self):
        for filename in ('cloudcc-agentcici.config.json', 'cloudcc-cli.config.json', '.cloudcc-cache.json'):
            target = self.root / 'web/dist' / filename
            target.write_text('{"clientSecret":"test-secret"}')
            with self.assertRaisesRegex(ValueError, '禁止发布'):
                self.build()
            target.unlink()

    def test_mcp_dependencies_keep_endpoints_but_reject_developer_credentials(self):
        installation = self.config['installationManifest']
        installation['mcpServers'] = [{'ref': 'crm', 'name': 'CRM', 'description': '业务数据',
                                     'transportType': 'streamableHttp', 'url': 'https://mcp.cloudcc.cn/crm'}]
        installation['tools'] = [{'ref': 'query', 'name': 'actual_discovered_tool', 'source': 'mcp', 'mcpRef': 'crm'}]
        self.assertEqual(app.validate(self.build())['installationManifest']['tools'][0]['mcpRef'], 'crm')
        installation['mcpServers'][0]['headers'] = '{"Authorization":"test-secret"}'
        with self.assertRaisesRegex(ValueError, '凭据'):
            self.build('invalid.zip')

    def test_business_file_tamper_is_rejected(self):
        files = self.build()
        files['cloudcc/metadata/Record.json'] = b'{}'
        with self.assertRaisesRegex(ValueError, '摘要'):
            app.validate(files)

    def test_organization_publish_uses_new_endpoint(self):
        with patch.object(app, 'Client') as factory, patch('sys.argv', ['app', 'publish', 'record-app', '--version', '1.0.0']), contextlib.redirect_stdout(io.StringIO()):
            factory.return_value.request.return_value = {'versions': []}
            self.assertEqual(app.main(), 0)
            factory.return_value.request.assert_called_once_with('POST', '/openapi/v1/management/ai-applications/record-app/versions/1.0.0/publish', {})

    def test_delete_requires_matching_application_confirmation(self):
        for confirm, expected in [('other-app', 1), ('record-app', 0)]:
            with patch.object(app, 'Client') as factory, patch('sys.argv', ['app', 'delete', 'record-app', '--confirm-id', confirm]), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                factory.return_value.request.return_value = {'appCode': 'record-app', 'deleted': True}
                self.assertEqual(app.main(), expected)
                if expected:
                    factory.assert_not_called()
                else:
                    factory.return_value.request.assert_called_once_with('DELETE', '/openapi/v1/management/ai-applications/record-app')

    def test_delete_requires_confirmation_argument_and_does_not_retry_conflict(self):
        with patch.object(app, 'Client') as factory, patch('sys.argv', ['app', 'delete', 'record-app']), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit): app.main()
            factory.assert_not_called()
        with patch.object(app, 'Client') as factory, patch('sys.argv', ['app', 'delete', 'record-app', '--confirm-id', 'record-app']), contextlib.redirect_stderr(io.StringIO()):
            factory.return_value.request.side_effect = RuntimeError('版本被市场或安装引用，不能删除')
            self.assertEqual(app.main(), 1)
            factory.return_value.request.assert_called_once()

    def test_release_builds_uploads_drafts_and_publishes_in_order(self):
        (self.root / 'application.json').write_text(json.dumps(self.config))
        request_id = '11111111-1111-4111-8111-111111111111'
        response = Mock()
        response.read.return_value = b''
        response.__enter__ = Mock(return_value=io.StringIO(json.dumps({'success': True, 'data': {'id': request_id}})))
        response.__exit__ = Mock(return_value=False)
        with patch.object(app, 'Client') as factory, patch.object(app.urllib.request, 'build_opener') as opener, patch('sys.argv',
                ['app', 'release', '--manifest', str(self.root / 'application.json'), '--output', str(self.root / 'release.zip')]), contextlib.redirect_stdout(io.StringIO()):
            opener.return_value.open.return_value = response
            factory.return_value.base_url = 'https://cici.example.test'
            factory.return_value.exchange.return_value = 'ephemeral-test-token'
            factory.return_value.request.side_effect = [{'status': 'DRAFT'}, {'versions': [{'orgStatus': 'PUBLISHED'}]}]
            self.assertEqual(app.main(), 0)
            calls = factory.return_value.request.call_args_list
            self.assertEqual(calls[0].args[1], '/openapi/v1/management/application-requests/' + request_id + '/draft')
            self.assertEqual(calls[1].args[1], '/openapi/v1/management/ai-applications/birthday-mail/versions/1.0.0/publish')

import json
import pathlib
import tempfile
import unittest
import zipfile
from unittest.mock import patch
import agentcici_application as app


def fixture(root):
    (root / 'web/dist').mkdir(parents=True)
    (root / 'web/dist/index.html').write_text('<html>生日邮件</html>')
    payload = app.encode({'agent': {'name': '生日助手'}, 'skills': [{'ref': 'skill-1'}], 'knowledge': [], 'tools': [], 'agentToolRefs': []})
    agent = app.zip_bytes({'manifest.json': app.encode({'format': 'agentcici-agent-package', 'formatVersion': 1, 'snapshot': 'SAVED_DRAFT', 'sha256': app.digest(payload)}), 'agent.json': payload})
    skill = app.zip_bytes({'manifest.json': app.encode({'format': 'universal-skill-package', 'formatVersion': '1.0'}), 'SKILL.md': b'# Birthday'})
    (root / 'agent.ciciagent').write_bytes(agent)
    (root / 'skill.zip').write_bytes(skill)
    config = {'appCode': 'birthday-mail', 'name': '生日邮件', 'version': '1.0.0', 'web': {'directory': 'web/dist'}, 'skills': [{'ref': 'writer', 'file': 'skill.zip'}], 'agents': [{'ref': 'assistant', 'file': 'agent.ciciagent', 'skillBindings': {'skill-1': 'writer'}, 'knowledgeBindings': {}}], 'knowledgeBases': [], 'menu': {'tabName': '生日邮件', 'pname': 'birthdaymail', 'type': 'script', 'sdkUrl': 'https://service.example.test/sdk/agentcici-app@1.1.0.js'}}
    (root / 'application.json').write_text(json.dumps(config))
    return config


class PackageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.config = fixture(self.root)

    def build(self):
        return app.package(self.root / 'application.json', self.root / 'release.zip')

    def test_installation_render_config_roundtrip(self):
        self.config['installationManifest'] = {'schemaVersion': 1, 'steps': [{'key': 'sisi', 'type': 'clientScript', 'label': '思思', 'payload': {'scriptName': '思思', 'scriptContent': 'void 0'}}], 'renderConfig': {'renderer': 'shadow-dom', 'entryUrl': 'https://app.test/widget.js', 'positions': ['float', 'right'], 'closeBehavior': 'hide', 'hostLayer': 'assistant'}}
        (self.root / 'application.json').write_text(json.dumps(self.config))
        self.build()
        with zipfile.ZipFile(self.root / 'release.zip') as z:
            self.assertEqual(json.loads(z.read('application.json'))['installationManifest'], self.config['installationManifest'])

    def test_rejects_invalid_render_position(self):
        self.config['installationManifest'] = {'schemaVersion': 1, 'steps': [{}], 'renderConfig': {'renderer': 'iframe', 'positions': ['left'], 'closeBehavior': 'hide', 'hostLayer': 'content'}}
        (self.root / 'application.json').write_text(json.dumps(self.config))
        with self.assertRaisesRegex(ValueError, '展示位置'):
            self.build()

    def test_rejects_multiple_agents(self):
        self.config["agents"].append({**self.config["agents"][0], "ref": "second"})
        (self.root / "application.json").write_text(json.dumps(self.config))
        with self.assertRaisesRegex(ValueError, "只能包含一个智能体"):
            self.build()

    def test_roundtrip_preserves_originals_and_is_deterministic(self):
        result = self.build()
        files = app.read_zip((self.root / 'release.zip').read_bytes())
        self.assertEqual(app.validate(files)['appCode'], 'birthday-mail')
        self.assertEqual(files['agents/assistant.ciciagent'], (self.root / 'agent.ciciagent').read_bytes())
        self.assertEqual(set(app.read_zip(files['site.zip'])), {'index.html'})
        other = app.package(self.root / 'application.json', self.root / 'second.zip')
        self.assertEqual(result['sha256'], other['sha256'])

    def test_does_not_overwrite(self):
        self.build()
        with self.assertRaises(FileExistsError): self.build()

    def test_default_menu_is_short_sdk_loader(self):
        self.build()
        files = app.read_zip((self.root / 'release.zip').read_bytes())
        script = json.loads(files['cloudcc/menu.json'])['functioncode']
        self.assertLess(len(script), 500)
        self.assertIn('AgentCiCiApp.mount', script)
        self.assertIn('"birthday-mail"', script)
        self.assertIn('__AGENTCICI_SITE_URL__', script)
        self.assertNotIn('__SDK_URL__', script)
        self.assertNotIn('fetch(', script)

    def test_sdk_url_override(self):
        self.config['menu']['sdkUrl'] = 'https://example.test/sdk/agentcici-app.js'
        (self.root / 'application.json').write_text(json.dumps(self.config))
        self.build()
        files = app.read_zip((self.root / 'release.zip').read_bytes())
        self.assertIn(self.config['menu']['sdkUrl'], json.loads(files['cloudcc/menu.json'])['functioncode'])

    def test_legacy_menu_requires_explicit_sdk_and_rejects_credential_urls(self):
        self.config['menu'].pop('sdkUrl')
        (self.root / 'application.json').write_text(json.dumps(self.config))
        with self.assertRaisesRegex(ValueError, '显式sdkUrl'):
            self.build()
        for url in ('https://user:secret@example.test/sdk.js', 'https://example.test/sdk.js?token=secret', 'http://remote.test/sdk.js'):
            self.config['menu']['sdkUrl'] = url
            (self.root / 'application.json').write_text(json.dumps(self.config))
            with self.assertRaisesRegex(ValueError, 'SDK地址'):
                self.build()
        self.assertFalse((self.root / 'release.zip').exists())

    def test_rejects_tampering_and_unlisted_file(self):
        self.build()
        files = app.read_zip((self.root / 'release.zip').read_bytes())
        files['site.zip'] += b'tampered'
        with self.assertRaises(ValueError): app.validate(files)
        files['extra.txt'] = b'bad'
        with self.assertRaises(ValueError): app.validate(files)

    def test_missing_mapping(self):
        self.config['agents'][0]['skillBindings'] = {}
        (self.root / 'application.json').write_text(json.dumps(self.config))
        with self.assertRaises(ValueError): self.build()
        self.assertFalse((self.root / 'release.zip').exists())

    def test_secret_file_and_missing_entry(self):
        (self.root / 'web/dist/.env').write_text('secret')
        with self.assertRaises(ValueError): self.build()
        (self.root / 'web/dist/.env').unlink()
        (self.root / 'web/dist/index.html').unlink()
        with self.assertRaises(ValueError): self.build()

    def test_path_traversal_and_zip_limit(self):
        with self.assertRaises(ValueError): app.read_zip(app.zip_bytes({'../escape': b'bad'}))
        data = app.zip_bytes({'large': b'x' * 1000})
        with patch.object(app, 'LIMIT', 200):
            with self.assertRaises(ValueError): app.read_zip(data)

    def test_symlink(self):
        (self.root / 'web/dist/linked').symlink_to(self.root / 'skill.zip')
        with self.assertRaises(ValueError): self.build()


class ResourceManifestTest(unittest.TestCase):
    def setUp(self):
        import application_manifest
        self.compiler = application_manifest
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        (self.root/'dist').mkdir()
        (self.root/'dist/index.html').write_text('<html>思思</html>')
        (self.root/'dist/widget.js').write_text('void 0;')
        self.config = {'schemaVersion': 2, 'appCode': 'sisi', 'name': '思思', 'version': '1.0.7', 'summary': 'AI助手',
            'appType': 'web', 'outputDir': 'dist', 'entry': 'widget.js', 'renderer': 'shadow-dom',
            'host': {'closeBehavior': 'hide', 'hostLayer': 'assistant'},
            'connectedApplications': True, 'agent': {'type': 'platform', 'ref': 'cici-system'},
            'launchers': [{'id': 'sisi_launcher', 'name': '思思', 'trigger': 'global-floating',
                'positions': ['global-floating', 'global-right'], 'payload': {'event': 'onLoad'}}]}

    def build(self):
        (self.root/'application.json').write_text(json.dumps(self.config))
        app.package(self.root/'application.json', self.root/'release.zip')
        return app.read_zip((self.root/'release.zip').read_bytes())

    def test_platform_package_needs_no_exports_and_generates_installation(self):
        files = self.build(); manifest = app.validate(files)
        self.assertEqual(set(files), {'site.zip', 'application.json'})
        self.assertEqual(manifest['agents'], [])
        self.assertEqual(manifest['platformAgent'], {'ref': 'cici-system'})
        install = manifest['installationManifest']
        self.assertEqual(install['renderConfig'], {'renderer': 'shadow-dom', 'entryPath': 'widget.js', 'positions': ['float', 'right'], 'closeBehavior': 'hide', 'hostLayer': 'assistant'})
        self.assertTrue(install['requiresConnectedApplication'])
        self.assertEqual(install['agentRuntime']['agentId'], 'cici-system')
        self.assertEqual(install['agentRuntime']['keyType'], 'cloudcc')
        script = install['steps'][0]['payload']['scriptContent']
        self.assertIn('AgentCiCiApp.start({ appCode, launcherId: "sisi_launcher" })', script)
        self.assertNotIn('name:', script)
        self.assertNotIn('position:', script)
        self.assertEqual(install['application']['name'], '思思')
        self.assertEqual(install['launchers'][0]['name'], '思思')
        self.assertNotIn('file', install['launchers'][0])

    def test_agent_optional(self):
        del self.config['agent']
        manifest = app.validate(self.build())
        self.assertNotIn('agentRuntime', manifest['installationManifest'])
        self.assertNotIn('platformAgent', manifest)

    def test_custom_agent_can_request_standard_runtime_key(self):
        self.config['agent'] = {'type': 'custom', 'ref': 'mail-agent', 'file': 'agent.ciciagent',
            'keyType': 'standard', 'skills': [], 'knowledges': []}
        install = self.compiler.compile_manifest(self.config, self.root)['installationManifest']
        self.assertEqual(install['agentRuntime'], {'agentId': 'mail-agent', 'keyType': 'standard'})

    def test_rejects_invalid_agent_runtime_key_type(self):
        self.config['agent']['keyType'] = 'invalid'
        with self.assertRaisesRegex(ValueError, '密钥类型'): self.compiler.compile_manifest(self.config, self.root)

    def test_missing_fields_are_reported_for_questionnaire(self):
        self.config['summary'] = ''; del self.config['connectedApplications']
        self.assertEqual(self.compiler.missing(self.config), ['summary'])
        with self.assertRaisesRegex(ValueError, 'summary'): self.build()

    def test_connected_application_defaults_to_required(self):
        del self.config['connectedApplications']
        manifest = app.validate(self.build())
        self.assertTrue(manifest['installationManifest']['requiresConnectedApplication'])

    def test_web_application_defaults_to_menu_launcher(self):
        del self.config['launchers']
        self.assertNotIn('launchers', self.compiler.missing(self.config))
        install = app.validate(self.build())['installationManifest']
        self.assertEqual(len(install['launchers']), 1)
        self.assertEqual({k: install['launchers'][0][k] for k in ('id', 'name', 'trigger', 'positions')}, {
            'id': 'default-menu', 'name': '思思', 'trigger': 'menu', 'positions': ['page-content']
        })
        self.assertEqual(install['launchers'][0]['renderConfig']['positions'], ['home'])
        self.assertEqual(install['renderConfig']['positions'], ['home'])
        self.assertEqual(install['steps'][0]['type'], 'menu')
        self.assertEqual(install['steps'][0]['payload']['pname'], 'sisi')
        self.assertIn('AgentCiCiApp.mount({ appCode, launcherId: "default-menu" })', install['steps'][0]['payload']['functioncode'])

    def test_explicit_empty_launchers_remain_invalid(self):
        self.config['launchers'] = []
        self.assertIn('launchers', self.compiler.missing(self.config))

    def test_connected_application_can_be_explicitly_disabled(self):
        self.config['connectedApplications'] = False
        manifest = app.validate(self.build())
        self.assertFalse(manifest['installationManifest']['requiresConnectedApplication'])

    def test_platform_bindings_cannot_be_silently_dropped(self):
        self.config['agent']['skills'] = [{'ref': 'managed'}]
        with self.assertRaisesRegex(ValueError, '不导出或重绑'): self.build()

    def test_entry_must_exist(self):
        self.config['entry'] = 'missing.js'
        with self.assertRaisesRegex(ValueError, '入口不存在'): self.build()

    def test_entry_cannot_escape_or_mix_url(self):
        self.config['entry'] = '../widget.js'
        with self.assertRaisesRegex(ValueError, '相对文件'): self.build()

    def test_button_script_uses_crm_field_and_keeps_layout_assignment(self):
        self.config['launchers'][0].update(trigger='detail-button', objects=['Account'],
            placement='allObjectDetailLayouts', payload={'objid': 'account',
                'tpSysButtonVO': {'btnType': 'detailBtn', 'category': 'CustomButton', 'functioncode': 'obsolete'}})
        step = app.validate(self.build())['installationManifest']['steps'][0]
        button = step['payload']['tpSysButtonVO']
        self.assertIn('AgentCiCiApp.mount({ appCode, launcherId: "sisi_launcher" })', button['functionCode'])
        self.assertNotIn('functioncode', button)
        self.assertEqual(step['payload']['objid'], 'account')
        self.assertEqual(step['placement'], 'allObjectDetailLayouts')

    def test_four_layer_rejects_position_outside_trigger(self):
        self.config['layoutVersion'] = 2
        self.config['launchers'][0]['positions'] = ['detail-right']
        with self.assertRaisesRegex(ValueError, '位置与入口类型不匹配'): self.build()

    def test_four_layer_requires_entry_when_renderer_changes(self):
        self.config['layoutVersion'] = 2
        self.config['launchers'][0]['renderer'] = 'iframe'
        with self.assertRaisesRegex(ValueError, '独立加载地址'): self.build()
        self.config['launchers'][0]['entry'] = 'index.html'
        launcher = app.validate(self.build())['installationManifest']['launchers'][0]
        self.assertEqual(launcher['renderConfig']['renderer'], 'iframe')
        self.assertEqual(launcher['renderConfig']['entryPath'], 'index.html')

    def test_four_layer_list_button_keeps_supplied_object(self):
        self.config['layoutVersion'] = 2
        self.config['launchers'][0].update(trigger='list-button', positions=['list-right'], objects=['Opportunity'],
            payload={'objid': 'opportunity', 'tpSysButtonVO': {'btnType': 'listBtn', 'category': 'CustomButton', 'event': 'lightning-script'}})
        install = app.validate(self.build())['installationManifest']
        self.assertEqual(install['steps'][0]['payload']['objid'], 'opportunity')
        self.assertEqual(install['launchers'][0]['objects'], ['Opportunity'])
        self.assertIn('launcherId: "sisi_launcher"', install['steps'][0]['payload']['tpSysButtonVO']['functionCode'])
        self.assertEqual(install['launchers'][0]['renderConfig']['positions'], ['list-right'])

    def test_page_trigger_requires_customer_object_selection(self):
        self.config['launchers'][0]['trigger'] = 'detail-button'
        with self.assertRaisesRegex(ValueError, '客户选择'): self.build()


    def test_fullscreen_roundtrip_preserves_default_position_order(self):
        self.config['launchers'][0]['positions'] = ['fullscreen', 'global-floating']
        install = app.validate(self.build())['installationManifest']
        self.assertEqual(install['launchers'][0]['positions'], ['fullscreen', 'global-floating'])
        self.assertEqual(install['renderConfig']['positions'], ['fullscreen', 'float'])

    def test_duplicate_trigger_with_distinct_ids_is_rejected(self):
        self.config['launchers'].append({**self.config['launchers'][0], 'id': 'another_launcher'})
        with self.assertRaisesRegex(ValueError, '每种trigger只能配置一项'): self.build()

    def test_duplicate_positions_are_rejected(self):
        self.config['launchers'][0]['positions'] = ['fullscreen', 'fullscreen']
        with self.assertRaisesRegex(ValueError, '展示位置'): self.build()


if __name__ == '__main__': unittest.main()

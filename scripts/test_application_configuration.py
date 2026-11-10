import json
import pathlib
import unittest
import tempfile
import agentcici_application as app
from application_business_resources import validate_resources


class ConfigurationContractTest(unittest.TestCase):
    def test_shared_contract(self):
        fixtures = pathlib.Path(__file__).resolve().parents[1] / 'tests/fixtures/resource-configuration-cases.json'
        for example in json.loads(fixtures.read_text()):
            with self.subTest(example=example):
                declaration = {'key': 'resource', 'kind': example['kind'], 'file': 'cloudcc/metadata/sample.json'}
                def validate():
                    validate_resources([declaration], {declaration['file']: json.dumps(example['payload']).encode()}, {'steps': []})
                if example['valid']:
                    validate()
                else:
                    with self.assertRaises(ValueError):
                        validate()

    def test_existing_server_resource_types(self):
        for kind, directory in [('trigger', 'triggers'), ('timer', 'timers')]:
            path = 'cloudcc/backend/' + directory + '/Sample.java'
            declaration = {'key': 'resource', 'kind': kind, 'file': path, 'apiName': 'Sample', 'label': '业务代码'}
            if kind == 'trigger':
                declaration.update(targetObjectApiName='work', triggerTime='beforeInsert')
            validate_resources([declaration], {path: b'// platform SOURCE'}, {'steps': []})
        path = 'cloudcc/metadata/rule.json'
        validate_resources([{'key': 'rule', 'kind': 'validationRule', 'file': path}],
                           {path: json.dumps({'apiName': 'AmountCheck', 'objectApiName': 'work', 'label': '金额检查', 'formulaText': 'amount < 0', 'errorMessage': '金额不能为负数'}).encode()}, {'steps': []})

    def test_new_configuration_survives_package_roundtrip(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            (root / 'dist').mkdir(); (root / 'dist/index.html').write_text('<html>配置协议</html>')
            (root / 'cloudcc/metadata').mkdir(parents=True)
            definitions = {
                'model': {'apiName': 'work', 'label': '工单', 'accessable': '0', 'quickCreate': True},
                'default-model': {'apiName': 'work_history', 'label': '工单历史'},
                'key': {'apiName': 'request_key', 'objectApiName': 'work', 'label': '请求键', 'fieldType': 'S', 'allowDuplicates': False, 'required': False, 'caseSensitive': True},
                'status': {'apiName': 'status', 'objectApiName': 'work', 'label': '状态', 'fieldType': 'L', 'options': ['待处理', '完成'], 'defaultFirstOption': True},
                'rule': {'apiName': 'AmountCheck', 'objectApiName': 'work', 'label': '金额检查', 'formulaText': 'amount < 0', 'errorMessage': '金额不能为负数'},
            }
            resources = []
            for name, definition in definitions.items():
                file = 'cloudcc/metadata/' + name + '.json'
                (root / file).write_bytes(app.encode(definition))
                resources.append({'key': name, 'kind': 'object' if name in ('model', 'default-model') else 'validationRule' if name == 'rule' else 'field', 'file': file})
            manifest = {'schemaVersion': 2, 'appCode': 'configuration-test', 'name': '配置协议', 'version': '1.0.0', 'summary': '资源配置', 'appType': 'web', 'outputDir': 'dist', 'entry': 'index.html', 'renderer': 'iframe', 'host': {'closeBehavior': 'hide', 'hostLayer': 'content'}, 'cloudccResources': resources}
            (root / 'application.json').write_bytes(app.encode(manifest))
            app.package(root / 'application.json', root / 'package.zip')
            files = app.read_zip((root / 'package.zip').read_bytes()); app.validate(files)
            for resource in resources:
                expected = definitions[resource['key']].copy()
                if resource['key'] == 'default-model':
                    expected['accessable'] = '2'
                    self.assertNotIn('accessable', json.loads((root / resource['file']).read_bytes()))
                self.assertEqual(expected, json.loads(files[resource['file']]))

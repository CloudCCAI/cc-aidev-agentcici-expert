import json
import pathlib
import tempfile
import unittest
import agentcici_application as app
from application_business_resources import validate_resources


class ExtendedFieldsTest(unittest.TestCase):
    def validate(self, payload):
        path = 'cloudcc/metadata/sample.json'
        return validate_resources([{'key': 'sample', 'kind': 'field', 'file': path}],
                                  {path: app.encode(payload)}, {'steps': []})

    def field(self, kind):
        return {'apiName': 'sample', 'objectApiName': 'sample_object', 'label': '测试', 'fieldType': kind}

    def test_type_specific_length_boundaries(self):
        for kind in ['F', 'X', 'J', 'A', 'H', 'IMG', 'FL']:
            maximum = 32000 if kind in ['J', 'A'] else 4000
            self.validate(self.field(kind))
            for value in [1, maximum]:
                self.validate({**self.field(kind), 'length': value})
            for value in [0, maximum + 1, '32000', 1.5, True, None]:
                with self.subTest(kind=kind, value=value), self.assertRaises(ValueError):
                    self.validate({**self.field(kind), 'length': value})

    def test_media_options_and_wrong_type_rejected(self):
        for kind in ['IMG', 'FL']:
            for count in [1, 10]:
                self.validate({**self.field(kind), 'maxFiles': count})
            for count in [0, 11, '1', True, 1.5]:
                with self.subTest(kind=kind, count=count), self.assertRaises(ValueError):
                    self.validate({**self.field(kind), 'maxFiles': count})
        for mode in ['input', 'url']:
            self.validate({**self.field('IMG'), 'imageInputMode': mode})
        for payload in [{**self.field('S'), 'maxFiles': 1},
                        {**self.field('FL'), 'imageInputMode': 'input'},
                        {**self.field('IMG'), 'imageInputMode': 'ref'}]:
            with self.assertRaises(ValueError):
                self.validate(payload)

    def test_package_roundtrip_keeps_extended_definitions_and_digests(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root/'dist').mkdir(); (root/'dist/index.html').write_text('<html>字段测试</html>')
            (root/'cloudcc/metadata').mkdir(parents=True)
            resources = []
            definitions = {}
            for kind in ['F', 'X', 'J', 'A', 'H', 'IMG', 'FL']:
                payload = {**self.field(kind), 'apiName': 'field_' + kind.lower()}
                if kind in ['J', 'A']: payload['length'] = 16000
                if kind in ['IMG', 'FL']: payload['maxFiles'] = 5
                path = 'cloudcc/metadata/' + kind + '.json'
                (root/path).write_bytes(app.encode(payload)); definitions[path] = payload
                resources.append({'key': 'field-' + kind.lower(), 'kind': 'field', 'file': path})
            config = {'schemaVersion': 2, 'appCode': 'field-test', 'name': '字段测试', 'version': '1.0.0',
                      'summary': '扩展字段', 'appType': 'web', 'outputDir': 'dist', 'entry': 'index.html',
                      'renderer': 'iframe', 'host': {'closeBehavior': 'hide', 'hostLayer': 'content'},
                      'cloudccResources': resources}
            (root/'application.json').write_bytes(app.encode(config))
            app.package(root/'application.json', root/'release.zip')
            files = app.read_zip((root/'release.zip').read_bytes()); manifest = app.validate(files)
            self.assertEqual(2, manifest['formatVersion'])
            self.assertEqual(2, manifest['installationManifest']['schemaVersion'])
            for path, payload in definitions.items():
                self.assertEqual(payload, json.loads(files[path]))
                self.assertEqual(app.digest(files[path]), manifest['sha256'][path])


class LargeV2PackageTest(unittest.TestCase):
    def test_large_package_roundtrip_and_dependency_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root/'dist').mkdir(); (root/'dist/index.html').write_text('<html>大清单</html>')
            (root/'cloudcc/metadata').mkdir(parents=True)
            resources = []
            for index in range(180):
                path = 'cloudcc/metadata/model_' + str(index) + '.json'
                (root/path).write_bytes(app.encode({'apiName': 'model_' + str(index), 'label': '对象' + str(index)}))
                resources.append({'key': 'model-' + str(index), 'kind': 'object', 'file': path})
            config = {'schemaVersion': 2, 'appCode': 'large-test', 'name': '大清单', 'version': '1.0.0',
                      'summary': '大清单验收', 'appType': 'web', 'outputDir': 'dist', 'entry': 'index.html',
                      'renderer': 'iframe', 'host': {'closeBehavior': 'hide', 'hostLayer': 'content'},
                      'cloudccResources': resources}
            (root/'application.json').write_bytes(app.encode(config))
            app.package(root/'application.json', root/'release.zip')
            manifest = app.validate(app.read_zip((root/'release.zip').read_bytes()))
            self.assertEqual(180, len(manifest['cloudccResources']))
            config['cloudccResources'][-1]['dependsOn'] = ['missing']
            (root/'application.json').write_bytes(app.encode(config))
            with self.assertRaises(ValueError):
                app.package(root/'application.json', root/'invalid.zip')

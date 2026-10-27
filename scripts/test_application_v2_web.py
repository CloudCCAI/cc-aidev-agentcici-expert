"""验证纯Web/MCP应用可显式选择V2，不产生虚假CRM资源。"""
import json,tempfile,unittest
from pathlib import Path
import agentcici_application as app

class V2WebPackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        (self.root/'dist').mkdir();(self.root/'dist/index.html').write_text('<html></html>');(self.root/'dist/app.js').write_text('void 0;')
        self.config={'schemaVersion':2,'layoutVersion':2,'formatVersion':2,'cloudccResources':[], 'appCode':'analytics-test','name':'分析','version':'0.3.0','summary':'测试','appType':'web','outputDir':'dist','entry':'app.js','renderer':'shadow-dom','host':{'closeBehavior':'confirm-destroy','hostLayer':'content'}}
    def build(self):
        (self.root/'application.json').write_text(json.dumps(self.config));app.package(self.root/'application.json',self.root/'out.zip')
        return app.validate(app.read_zip((self.root/'out.zip').read_bytes()))
    def test_explicit_v2_with_no_business_resources(self):
        m=self.build();self.assertEqual(m['formatVersion'],2);self.assertEqual(m['cloudccResources'],[]);self.assertEqual(m['installationManifest']['schemaVersion'],2)
        self.assertEqual([x['type'] for x in m['installationManifest']['steps']],['menu'])
    def test_legacy_web_still_defaults_to_v1(self):
        del self.config['formatVersion'];del self.config['cloudccResources'];self.assertEqual(self.build()['formatVersion'],1)
    def test_v2_missing_resource_declaration_normalizes_to_empty(self):
        del self.config['cloudccResources'];self.assertEqual(self.build()['cloudccResources'],[])
    def test_v2_rejects_invalid_resource_type(self):
        self.config['cloudccResources']={}
        with self.assertRaises(ValueError):self.build()
    def test_version_must_be_supported_integer(self):
        for version in [True,'2',3]:
            self.config['formatVersion']=version
            with self.assertRaises(ValueError):self.build()

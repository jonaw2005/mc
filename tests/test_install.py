import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('installer', Path(__file__).resolve().parents[1] / 'scripts' / 'install.py')
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.release = {'id': '1.21.1', 'type': 'release', 'url': 'https://example.test/version'}
        self.snapshot = {'id': 'test-snapshot', 'type': 'snapshot'}
        self.manifest = {'versions': [self.release, self.snapshot, {'id': 'old', 'type': 'old_alpha'}]}
        self.metadata = {'id': '1.21.1', 'javaVersion': {'majorVersion': 21}, 'downloads': {'server': {}}}

    def test_release_filter(self):
        self.assertEqual(installer.available_versions(self.manifest), [self.release])

    def test_snapshot_filter(self):
        self.assertEqual(installer.available_versions(self.manifest, True), [self.release, self.snapshot])

    def test_java_tags(self):
        for major, tag in [(8, 'java8'), (16, 'java17'), (17, 'java17'), (21, 'java21'), (25, 'java25')]:
            self.metadata['javaVersion']['majorVersion'] = major
            self.assertEqual(installer.java_tag(self.metadata), tag)

    def test_legacy_java(self):
        self.assertEqual(installer.java_tag({'downloads': {'server': {}}}), 'java8')

    def test_unsupported_java(self):
        self.metadata['javaVersion']['majorVersion'] = 999
        with self.assertRaises(ValueError):
            installer.java_tag(self.metadata)

    def test_no_server(self):
        with self.assertRaises(ValueError):
            installer.java_tag({'downloads': {}})

    def test_invalid_settings(self):
        for values in [('../escape', '2G', 25565, '0.0.0.0'), ('1.21.1', '0G', 25565, '0.0.0.0'),
                       ('1.21.1', '2G\nEULA=TRUE', 25565, '0.0.0.0'),
                       ('1.21.1', '2G', 65536, '0.0.0.0'), ('1.21.1', '2G', 25565, 'invalid')]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                installer.validate_settings(*values)

    def test_menu(self):
        with patch('builtins.input', side_effect=['invalid', '1']), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(installer.select_version([self.release]), self.release)

    def test_menu_id(self):
        with patch('builtins.input', return_value='1.21.1'), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(installer.select_version([self.release]), self.release)

    def test_menu_pagination(self):
        versions = [{'id': f'v{i}', 'type': 'release'} for i in range(25)]
        with patch('builtins.input', side_effect=['n', 'p', 'n', '21']), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(installer.select_version(versions), versions[20])

    def test_configure_and_launch(self):
        for configure_only in (True, False):
            with self.subTest(configure_only=configure_only), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                with patch.object(installer, 'ROOT', root), patch.object(installer, 'fetch_json', side_effect=[self.manifest, self.metadata]), patch.object(installer, 'compose') as compose, contextlib.redirect_stdout(io.StringIO()):
                    args = ['--version', '1.21.1', '--accept-eula']
                    installer.main(args + (['--configure-only'] if configure_only else []))
                    self.assertIn('MC_VERSION=1.21.1\nJAVA_TAG=java21', (root / '.env').read_text())
                    self.assertFalse((root / '.env.tmp').exists())
                    self.assertEqual(compose.call_count, 0 if configure_only else 3)

    def test_eula_declined_preserves_config(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.env').write_text('existing config')
            with patch.object(installer, 'ROOT', root), patch.object(installer, 'fetch_json', side_effect=[self.manifest, self.metadata]), patch('builtins.input', return_value='nein'), contextlib.redirect_stdout(io.StringIO()), self.assertRaises(ValueError):
                installer.main(['--version', '1.21.1'])
            self.assertEqual((root / '.env').read_text(), 'existing config')

    def test_unknown_version(self):
        with patch.object(installer, 'fetch_json', return_value=self.manifest), self.assertRaises(ValueError):
            installer.main(['--version', 'does-not-exist'])

    def test_metadata_mismatch(self):
        self.metadata['id'] = 'other'
        with patch.object(installer, 'fetch_json', side_effect=[self.manifest, self.metadata]), self.assertRaises(ValueError):
            installer.main(['--version', '1.21.1'])


if __name__ == '__main__':
    unittest.main()
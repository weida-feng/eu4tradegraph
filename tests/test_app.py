from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


class AppTests(unittest.TestCase):
    def test_demo_and_source_switch(self):
        app = AppTest.from_file(str(ROOT / 'app.py')).run(timeout=30)
        self.assertFalse(app.exception)
        self.assertFalse(app.warning)
        self.assertEqual([metric.value for metric in app.metric][1:], ['80', '153'])
        app.radio[0].set_value('上传存档').run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.metric), 0)

    @unittest.skipUnless(shutil.which('dot'), 'Graphviz system executable is not installed')
    def test_demo_graph_and_downloads(self):
        app = AppTest.from_file(str(ROOT / 'app.py')).run(timeout=30)
        app.checkbox[0].uncheck()
        app.button[0].click().run(timeout=60)
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        self.assertEqual(len(app.get('download_button')), 4)
        self.assertTrue(app.session_state['rendered'][1].startswith(b'\x89PNG'))

    @unittest.skipUnless(shutil.which('dot'), 'Graphviz system executable is not installed')
    def test_unverified_version_warns_and_can_render(self):
        demo = ROOT / 'examples/trade_snapshot_1.34.4.eu4'
        # Synthetic metadata checks the warning path, not real 1.35 compatibility.
        data = demo.read_bytes().replace(b'second=34', b'second=35')
        read_bytes = Path.read_bytes

        def read_fixture(path):
            return data if path == demo else read_bytes(path)

        with patch.object(Path, 'read_bytes', read_fixture):
            app = AppTest.from_file(str(ROOT / 'app.py')).run(timeout=30)
            self.assertFalse(app.exception)
            self.assertEqual(app.metric[0].value, '1.35.4.0 / 1444.12.1')
            self.assertEqual(len(app.warning), 1)
            self.assertIn('不保证结果正确', app.warning[0].value)
            app.checkbox[0].uncheck()
            app.button[0].click().run(timeout=60)
            self.assertFalse(app.exception)
            self.assertFalse(app.error)
            self.assertEqual(len(app.get('download_button')), 4)
            self.assertTrue(app.session_state['rendered'][1].startswith(b'\x89PNG'))


if __name__ == '__main__':
    unittest.main()

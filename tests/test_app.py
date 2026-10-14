from pathlib import Path
import shutil
import unittest

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


class AppTests(unittest.TestCase):
    def test_demo_and_source_switch(self):
        app = AppTest.from_file(str(ROOT / 'app.py')).run(timeout=30)
        self.assertFalse(app.exception)
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


if __name__ == '__main__':
    unittest.main()

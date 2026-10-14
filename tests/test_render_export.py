import csv
from io import BytesIO, StringIO
import shutil
import unittest
import xml.etree.ElementTree as ET

from PIL import Image

from eu4tradegraph import parse_save
from eu4tradegraph.export import node_rows, route_rows, to_csv
from eu4tradegraph.render import GraphSettings, build_graph, render_graph, scale

DATA = b'''EU4txt
savegame_version={ first=1 second=34 third=4 forth=0 }
trade={
 node={ definitions="kongo" current=0 local_value=0 }
 node={ definitions="zambezi" current=0 local_value=0 incoming={ from=1 value=0 } }
}'''


class RenderExportTests(unittest.TestCase):
    def test_constant_ranges_and_zero_routes(self):
        self.assertEqual(scale(0, 0, 0, (1, 6)), 3.5)
        self.assertEqual(scale(5, 0, 10, (1, 6)), 3.5)
        dot = build_graph(parse_save(DATA)).source
        self.assertIn('style=dashed', dot)
        self.assertIn('penwidth=3.5', dot)
        self.assertIn('0 -> 1', dot)

    def test_no_routes(self):
        snapshot = parse_save(DATA.replace(b'incoming={ from=1 value=0 }', b''))
        self.assertNotIn(' -> ', build_graph(snapshot).source)

    def test_tabular_exports_match_graph_data(self):
        snapshot = parse_save(DATA)
        rows = node_rows(snapshot)
        csv_bytes = to_csv(rows, tuple(rows[0]))
        self.assertTrue(csv_bytes.startswith(b'\xef\xbb\xbf'))
        table = list(csv.DictReader(StringIO(csv_bytes.decode('utf-8-sig'))))
        self.assertEqual(table[0]['node_id'], 'kongo')
        self.assertEqual(table[0]['label_zh'], '刚果')
        self.assertEqual(route_rows(snapshot), [{'source': 'kongo', 'target': 'zambezi', 'value': 0.0}])
        self.assertEqual(to_csv([], ('source', 'target', 'value')).decode('utf-8-sig'), 'source,target,value\r\n')

    @unittest.skipUnless(shutil.which('dot'), 'Graphviz system executable is not installed')
    def test_png_and_svg_rendering(self):
        snapshot = parse_save(DATA)
        # English labels make this test independent of installed CJK fonts.
        settings = GraphSettings(chinese_labels=False)
        png = render_graph(snapshot, settings, 'png')
        with Image.open(BytesIO(png)) as image:
            self.assertEqual(image.format, 'PNG')
            self.assertGreater(image.width, 100)
        svg = ET.fromstring(render_graph(snapshot, settings, 'svg'))
        self.assertEqual(svg.tag, '{http://www.w3.org/2000/svg}svg')
        text = ''.join(svg.itertext())
        self.assertIn('Kongo', text)
        self.assertIn('Zambezi', text)


if __name__ == '__main__':
    unittest.main()

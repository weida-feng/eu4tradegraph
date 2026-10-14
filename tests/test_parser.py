from pathlib import Path
import unittest
from unittest.mock import patch

from eu4tradegraph import SaveError, parse_save

ROOT = Path(__file__).resolve().parents[1]
VERSION = "savegame_version={ first=1 second=34 third=4 forth=0 }"


def save(trade: str, extra: str = "", version: str = VERSION) -> bytes:
    return f"EU4txt\ndate=1444.12.1\n{version}\n{extra}\ntrade={{ {trade} }}".encode()


class ParserTests(unittest.TestCase):
    def test_reference_snapshot(self):
        snapshot = parse_save((ROOT / "examples/trade_snapshot_1.34.4.eu4").read_bytes())
        self.assertEqual((snapshot.version, snapshot.date), ("1.34.4.0", "1444.12.1"))
        self.assertEqual((len(snapshot.nodes), len(snapshot.routes)), (80, 153))
        self.assertEqual(snapshot.nodes[0].name, "african_great_lakes")
        self.assertEqual(snapshot.nodes[0].current, 0.923)
        self.assertEqual(snapshot.nodes[0].local_value, 1.653)
        self.assertEqual(snapshot.routes[0].source, 0)
        self.assertEqual(snapshot.routes[0].target, 1)
        self.assertEqual(snapshot.routes[0].value, 0.335)

    def test_whitespace_comments_quotes_and_forward_reference(self):
        data = save('''
            # A } in a comment is not a block end.
            node = { definitions = "kongo" current = 0
                     country = { note = "escaped \\" { }" current = 999 }
                     incoming = { from = 2 value = 1.25 } }
            node = { definitions = "zambezi" local_value = 2 }
        ''', extra='map_area_data{ ignored={ value=3 } }')
        snapshot = parse_save(data)
        self.assertEqual(snapshot.nodes[0].current, 0)
        self.assertEqual(snapshot.routes[0].source, 1)
        self.assertEqual(snapshot.routes[0].target, 0)

    def test_omitted_zero_fields_do_not_read_country_values(self):
        snapshot = parse_save(save('node={ definitions="kongo" KON={ current=99 outgoing=8 } }'))
        self.assertEqual((snapshot.nodes[0].current, snapshot.nodes[0].outgoing), (0, 0))
        self.assertEqual(snapshot.routes, ())

    def test_other_versions_are_not_blocked(self):
        for second in (33, 35, 37):
            with self.subTest(second=second):
                snapshot = parse_save(save('node={ definitions="kongo" }', version=VERSION.replace("second=34", f"second={second}")))
                self.assertEqual(snapshot.version, f"1.{second}.4.0")
                self.assertEqual(snapshot.nodes[0].name, "kongo")
        snapshot = parse_save(save('node={ definitions="kongo" }', version=VERSION.replace("third=4", "third=3")))
        self.assertEqual(snapshot.version, "1.34.3.0")

    def test_malformed_version_metadata(self):
        for version in ("", "savegame_version={ first=1 }", "savegame_version=1.34", VERSION + VERSION):
            with self.subTest(version=version), self.assertRaises(SaveError):
                parse_save(save('node={ definitions="kongo" }', version=version))

    def test_mods_and_ironman(self):
        node = 'node={ definitions="kongo" }'
        for extra in ('mods_enabled={ "mod/test.mod" }', 'mod_enabled={ "test" }', 'ironman=yes'):
            with self.subTest(extra=extra), self.assertRaises(SaveError):
                parse_save(save(node, extra=extra))
        parse_save(save(node, extra='mods_enabled={ # empty\n } ironman=no'))

    def test_bad_headers(self):
        for data in (b"PK\x03\x04", b"EU4bin", b"EU4txt\x00", b"random", b"EU4txtfake"):
            with self.subTest(data=data), self.assertRaises(SaveError):
                parse_save(data)

    def test_size_limit(self):
        with patch("eu4tradegraph.parser.MAX_SAVE_BYTES", 4), self.assertRaisesRegex(SaveError, "200 MB"):
            parse_save(b"EU4txt")

    def test_utf8_bom_and_windows_encoding(self):
        data = save('node={ definitions="kongo" }')
        self.assertEqual(parse_save(b"\xef\xbb\xbf" + data), parse_save(data))
        self.assertEqual(parse_save(data + b'\n# caf\xe9\n'), parse_save(data))

    def test_invalid_trade_fields(self):
        cases = [
            'node={ definitions="unknown_mod_node" }',
            'node={ definitions="kongo" } node={ definitions="kongo" }',
            'node={ definitions="kongo" incoming={ from=0 } }',
            'node={ definitions="kongo" incoming={ from=-1 } }',
            'node={ definitions="kongo" incoming={ from=1.5 } }',
            'node={ definitions="kongo" incoming={ from=2 } }',
            'node={ definitions="kongo" incoming={ value=1 } }',
            'node={ definitions="kongo" current=-1 }',
            'node={ definitions="kongo" current=NaN }',
            'node={ definitions="kongo" current=1e9999 }',
            'node={ definitions="kongo" current=1+2 }',
            'node={ definitions="kongo" current=1 current=2 }',
            'node={ definitions="kongo" incoming=1 }',
            'node=1', '',
        ]
        for trade in cases:
            with self.subTest(trade=trade), self.assertRaises(SaveError):
                parse_save(save(trade))

    def test_missing_or_malformed_trade_block(self):
        for data in (f"EU4txt\n{VERSION}".encode(),
                     save('node={ definitions="kongo" }')[:-1],
                     save('node={ definitions="kongo" }') + b' trade={}',
                     save('node={ definitions="kongo" }') + b' }'):
            with self.subTest(data=data), self.assertRaises(SaveError):
                parse_save(data)


if __name__ == "__main__":
    unittest.main()

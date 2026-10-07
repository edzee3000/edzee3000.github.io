"""Regression checks for stable-ID imports, validation and graph centrality."""
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import io

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_music_atlas import ROOT, build, page_rank, read_json, validate
from import_music_tracks import merge, fetch_playlist


class AtlasDataTests(unittest.TestCase):
    def setUp(self):
        self.raw = read_json(ROOT / '_data/music.json')
        self.analysis = read_json(ROOT / '_data/music_atlas.json')

    def test_page_rank_symmetry_and_dangling_mass(self):
        cycle = [dict(source=1, target=2), dict(source=2, target=3), dict(source=3, target=1)]
        scores = page_rank([1, 2, 3], cycle)
        for score in scores.values():
            self.assertAlmostEqual(score['pageRank'], 1 / 3)
        with_isolate = page_rank([1, 2, 3, 4], cycle)
        self.assertAlmostEqual(sum(v['pageRank'] for v in with_isolate.values()), 1)
        self.assertLess(with_isolate[4]['pageRank'], with_isolate[1]['pageRank'])

    def test_import_preserves_annotations_and_is_idempotent(self):
        incoming = copy.deepcopy(self.raw[0])
        incoming['id'] = 999999999001
        incoming['name'] = 'Temporary import test'
        raw, analysis, report = merge(self.raw, self.analysis, [incoming])
        self.assertEqual(report['added'], [incoming['id']])
        self.assertEqual(analysis['nodes'][:-1], self.analysis['nodes'])
        self.assertEqual(analysis['edges'], self.analysis['edges'])
        self.assertEqual(analysis['nodes'][-1]['group'], 'unclassified')
        again, again_analysis, report = merge(raw, analysis, [incoming])
        self.assertEqual(report['added'], [])
        self.assertEqual(again, raw)
        self.assertEqual(again_analysis, analysis)

    def test_duplicate_import_and_dangling_annotation_rejected(self):
        with self.assertRaises(ValueError):
            merge(self.raw, self.analysis, [self.raw[0], self.raw[0]])
        invalid = copy.deepcopy(self.analysis)
        invalid['nodes'][0]['id'] = 999999999001
        with self.assertRaises(ValueError):
            validate(self.raw, invalid)

    def test_partial_public_playlist_response_aborts(self):
        metadata = dict(code=200, playlist=dict(trackCount=2, trackIds=[dict(id=1), dict(id=2)]))
        partial = dict(code=200, songs=[dict(id=1)])
        responses = [io.BytesIO(json.dumps(data).encode()) for data in [metadata, partial]]
        with patch('urllib.request.urlopen', side_effect=responses):
            with self.assertRaisesRegex(ValueError, 'no metadata'):
                fetch_playlist(8114560070)

    def test_reordering_and_new_song_build_preserve_editorial_data(self):
        test_parent = ROOT / 'local/music-atlas'
        test_parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=test_parent) as temp:
            root = Path(temp).resolve()
            self.assertTrue(root.is_relative_to((ROOT / 'local').resolve()))
            (root / '_data').mkdir()
            shutil.copytree(ROOT / 'assets/music', root / 'assets/music',ignore=shutil.ignore_patterns('covers','covers-small'))
            (root / '_data/music.json').write_text(json.dumps(self.raw), encoding='utf-8')
            (root / '_data/music_atlas.json').write_text(json.dumps(self.analysis), encoding='utf-8')
            _, first = build(root)
            (root / '_data/music.json').write_text(json.dumps(list(reversed(self.raw))), encoding='utf-8')
            _, reordered = build(root)
            self.assertEqual(first, reordered)
            incoming = copy.deepcopy(self.raw[0])
            incoming['id'] = 999999999001
            raw, analysis, _ = merge(self.raw, self.analysis, [incoming])
            (root / '_data/music.json').write_text(json.dumps(raw), encoding='utf-8')
            (root / '_data/music_atlas.json').write_text(json.dumps(analysis), encoding='utf-8')
            catalog, updated = build(root)
            # A rebuild/import must never repopulate media in the GitHub tree.
            self.assertFalse((root/'assets/music/covers').exists())
            self.assertFalse((root/'assets/music/covers-small').exists())
            self.assertEqual(len(catalog), len(self.raw) + 1)
            self.assertEqual(len(updated['nodes']), len(first['nodes']) + 1)
            old_notes = {n['id']: n['note'] for n in first['nodes']}
            self.assertEqual(old_notes, {n['id']: n['note'] for n in updated['nodes'] if n['id'] in old_notes})
            self.assertTrue(all(e['kind'] == 'album' for e in updated['edges'] if incoming['id'] in [e['source'], e['target']]))

    def test_generated_catalog_uses_verified_external_artwork(self):
        media=read_json(ROOT/'_data/music_artwork.json')
        catalog=read_json(ROOT/'assets/music/catalog.json')
        prefix=f"https://huggingface.co/datasets/{media['repo']}/resolve/{media['revision']}/"
        self.assertEqual(media['originalCount'],len(media['assets']))
        self.assertEqual(media['verifiedFiles'],len(media['assets'])*3)
        for song in catalog:
            source=media['assets'][song['coverSource']]
            self.assertEqual(song['coverOriginal'],prefix+source['original'])
            self.assertEqual(song['cover'],prefix+source['preview'])
            self.assertEqual(song['coverSmall'],prefix+source['small'])


if __name__ == '__main__':
    unittest.main()

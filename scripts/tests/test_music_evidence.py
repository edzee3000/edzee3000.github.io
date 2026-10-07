"""Evidence boundaries: never turn missing data or samples into conclusions."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_music_atlas import ROOT, validate
from collect_music_evidence import lyric_summary, measure_pcm
import numpy as np


class EvidenceBoundaryTests(unittest.TestCase):
    def test_missing_lyrics_are_not_instrumental(self):
        empty = lyric_summary({'code': 200, '_song_id': 1})
        self.assertEqual(empty['status'], 'insufficient')
        self.assertFalse(empty['themes'])
        marked = lyric_summary({'code': 200, 'pureMusic': True, '_song_id': 1})
        self.assertEqual(marked['status'], 'instrumental-platform-label')

    def test_one_ambiguous_word_is_not_a_theme(self):
        result = lyric_summary({'lrc': {'lyric': '[00:00]爱\n[00:01]爱\n[00:02]爱'}, '_song_id': 1})
        self.assertFalse(result['themes'])

    def test_sine_centroid_is_close_to_known_frequency(self):
        sr = 16000
        signal = (.5 * np.sin(2 * np.pi * 440 * np.arange(sr * 10) / sr)).astype('<f4')
        features = measure_pcm(signal.tobytes())
        self.assertAlmostEqual(features['centroidHz'], 440, delta=10)
        self.assertGreater(features['seconds'], 9)

    def test_generated_full_graph_respects_evidence_boundaries(self):
        graph = json.loads((ROOT / 'assets/music/network.json').read_text(encoding='utf8'))
        raw = json.loads((ROOT / '_data/music.json').read_text(encoding='utf8'))
        validate(raw, graph)
        self.assertEqual({n['id'] for n in graph['nodes']}, {s['id'] for s in raw})
        self.assertEqual(graph['coverage']['fullTrackListeningReviewed'], 0)
        measured = {n['id'] for n in graph['nodes'] if n['evidence']['audioStatus'] == 'measured'}
        for edge in graph['edges']:
            if edge['kind'] == 'acoustic':
                self.assertIn(edge['source'], measured)
                self.assertIn(edge['target'], measured)
                self.assertEqual(edge['status'], 'measured')
            if edge['kind'] in ['emotion', 'structure', 'sound', 'lyrics']:
                self.assertEqual(edge['status'], 'candidate')
        for node in graph['nodes']:
            self.assertTrue(all(np.isfinite(node['position'])))
            if node['editorialStatus'] == 'pending':
                self.assertEqual(node['group'], 'unclassified')


if __name__ == '__main__':
    unittest.main()

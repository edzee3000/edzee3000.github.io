"""Check style evidence, multi-label hierarchy and whole-library navigation."""
import json
from collections import Counter
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from music_styles import apply_styles, canonical
from build_music_atlas import ROOT


class StyleEvidenceTests(unittest.TestCase):
    def test_genre_hierarchy_does_not_invent_sibling_styles(self):
        raw=[dict(id=1,artists=[dict(name='Band')],album=dict(name='Album')),
             dict(id=2,artists=[dict(name='Unknown')],album=dict(name='Other'))]
        graph=dict(nodes=[dict(id=1,artistIds=[1]),dict(id=2,artistIds=[2])],edges=[])
        sources={'Band':dict(source='https://example.org/band',tags=[dict(name='midwest emo',count=5),
            dict(name='psytrance',count=1),dict(name='american',count=20)])}
        apply_styles(graph,raw,sources,{})
        labels=graph['nodes'][0]['styles']
        self.assertIn('midwest-emo',labels)
        self.assertIn('emo',labels)
        self.assertIn('rock',labels)
        self.assertNotIn('math-rock',labels)
        self.assertNotIn('psytrance',labels)
        self.assertIsNone(canonical('american'))
        self.assertEqual(canonical('instrumental rock'),'rock')
        self.assertEqual(graph['nodes'][1]['styles'],['pending'])
        self.assertFalse(graph['nodes'][1]['styleEvidence'])

    def test_release_and_track_evidence_keep_their_scope(self):
        raw=[dict(id=i,artists=[dict(name='Band')],album=dict(name=name)) for i,name in [(1,'Specific'),(2,'Other')]]
        graph=dict(nodes=[dict(id=i,artistIds=[1]) for i in [1,2]],edges=[])
        overrides=dict(artists={'Band':[dict(labels=['post-rock'],albums=['Specific'],
            url='https://example.org/release',title='Release')]},tracks={'2':dict(exclude=['post-rock'],
            labels=[dict(id='math-rock',url='https://example.org/track',title='Track',basis='Track analysis')],primary='math-rock')})
        apply_styles(graph,raw,{},overrides)
        self.assertEqual(next(r['scope'] for r in graph['nodes'][0]['styleEvidence'] if r['id']=='post-rock'),'release')
        self.assertNotIn('post-rock',graph['nodes'][1]['styles'])
        self.assertEqual(next(r['scope'] for r in graph['nodes'][1]['styleEvidence'] if r['id']=='math-rock'),'track')

    def test_full_library_has_evidence_and_bounded_style_edges(self):
        graph=json.loads((ROOT/'assets/music/network.json').read_text(encoding='utf8'))
        raw=json.loads((ROOT/'_data/music.json').read_text(encoding='utf8'))
        by_id={n['id']:n for n in graph['nodes']}
        self.assertEqual(set(by_id),{s['id'] for s in raw})
        degrees=Counter()
        for node in by_id.values():
            self.assertTrue(node['styles'])
            self.assertEqual(len(node['styles']),len(set(node['styles'])))
            self.assertEqual(len(node['stylePosition']),2)
            for evidence in node['styleEvidence']:
                self.assertTrue(evidence['source'].startswith('https://'))
                self.assertIn(evidence['scope'],['artist-context','release','track'])
        for edge in graph['edges']:
            if edge['kind']!='style':continue
            self.assertTrue(edge['styles'])
            for endpoint in ['source','target']:
                ident=edge[endpoint];degrees[ident]+=1
                direct={r['id'] for r in by_id[ident]['styleEvidence'] if not r['inherited']}
                self.assertTrue(set(edge['styles'])<=direct)
                self.assertNotIn('pending',by_id[ident]['styles'])
        self.assertLessEqual(max(degrees.values()),3)
        nirvana=next(n for n in by_id.values() if any('Nirvana' in r['sourceTitle'] for r in n['styleEvidence']))
        self.assertNotIn('psytrance',nirvana['styles'])
        self.assertNotIn('hip-hop',nirvana['styles'])


if __name__=='__main__':unittest.main()

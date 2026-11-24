import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from app.catalog import Plan, compile_plan, rule_plan
from app.main import Ask, compare, fingerprint
from tools.dataset import prepare, sha256
from tools.portable import export, restore


class CatalogTests(unittest.TestCase):
    def test_spanish_and_bounds(self):
        self.assertEqual(rule_plan('¿Qué países tienen más entidades?').intent, 'countries')
        self.assertEqual(rule_plan('Alcance a 3 saltos del nodo 10000001').hops, 3)
        with self.assertRaises(ValueError):
            Plan(intent='reach', hops=99)
        with self.assertRaises(ValueError):
            rule_plan('Borra todo')
        with self.assertRaises(ValueError):
            compile_plan(Plan(intent='unsupported'))
        with self.assertRaises(ValueError):
            rule_plan('Alcance a 4 saltos del nodo 10000001')

    def test_parameter_injection_is_only_a_value(self):
        plan = Plan(intent='search', term="x' DELETE n //")
        query, params = compile_plan(plan)
        self.assertNotIn('DELETE', query)
        self.assertIn('delete', params['term'])

    def test_comparison_preserves_duplicates(self):
        self.assertNotEqual(fingerprint([{'a': 1}]), fingerprint([{'a': 1}, {'a': 1}]))
        self.assertEqual(fingerprint([{'a': 1}, {'a': 2}]), fingerprint([{'a': 2}, {'a': 1}]))


class DatasetTests(unittest.TestCase):
    def test_real_format_fixture_normalizes_and_filters_dangling_edges(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / 'fixture.zip'
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr('nodes-entities.csv', 'node_id,name,countries,sourceID\n1001,ACME,Spain,fixture\n1002,Órbita,France,fixture\n')
                z.writestr('relationships.csv', 'node_id_start,node_id_end,rel_type\n1001,1002,officer_of\n1001,9999,unknown\n')
            prepare(root, 'full', archive)
            manifest = json.loads((root / 'canonical/manifest.json').read_text())
            rows = [json.loads(x) for x in (root / 'canonical/graph.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual((manifest['nodes'], manifest['edges'], manifest['excluded_edges']), (2, 1, 1))
            self.assertEqual(rows[1]['properties']['name_search'], 'orbita')
            self.assertEqual(manifest['graph_sha256'], sha256(root / 'canonical/graph.jsonl'))
            package = root / 'portable.zip'
            export(root, package)
            restore(root / 'another-machine', package)
            self.assertEqual(sha256(root / 'another-machine/canonical/graph.jsonl'), manifest['graph_sha256'])
            with self.assertRaises(ValueError):
                prepare(root, 'full', archive)


class ComparisonTests(unittest.TestCase):
    def test_measurement_equality_and_warmup(self):
        calls = []
        class Engine:
            def __init__(self, dataset='full'):
                pass
            def query(self, q, params):
                calls.append(q)
                return [{'total': 12}]
            def close(self):
                pass
        with patch('app.main.NeoEngine', Engine), patch('app.main.TuringEngine', Engine):
            result = compare(Ask(question='¿Cuántos nodos hay?', repetitions=3, warmups=1))
        self.assertTrue(result['equivalent'])
        self.assertEqual(len(calls), 8)
        self.assertEqual(len(result['engines']['Neo4j']['samples_ms']), 3)

    def test_failure_never_becomes_a_speed_result(self):
        def fail(**kwargs):
            raise ConnectionError('offline')
        with patch('app.main.NeoEngine', fail), patch('app.main.TuringEngine', fail):
            result = compare(Ask(question='¿Cuántos nodos hay?'))
        self.assertIsNone(result['equivalent'])
        self.assertNotIn('median_ms', result['engines']['Neo4j'])


if __name__ == '__main__':
    unittest.main()

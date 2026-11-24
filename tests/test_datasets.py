import gzip
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.catalog import Plan, compile_plan, rule_plan, dataset_examples
from app.datasets import dataset_config
from app.main import app, Ask, compare
from tools.epinions import prepare


class DatasetRoutingTests(unittest.TestCase):
    def test_invalid_selector_is_rejected(self):
        with self.assertRaises(ValueError):
            dataset_config('../canonical')
        with self.assertRaises(ValueError):
            Ask(question='Cuenta nodos', dataset='other')
        with TestClient(app) as client:
            self.assertEqual(client.get('/api/status?dataset=other').status_code, 422)

    def test_comparison_routes_both_engines_and_report(self):
        selected = []
        class Engine:
            def __init__(self, dataset='full'):
                selected.append(dataset)
            def query(self, query, params):
                return [{'total': 75879}]
            def close(self):
                pass
        with patch('app.main.NeoEngine', Engine), patch('app.main.TuringEngine', Engine), patch('app.main.interpret', return_value=(Plan(intent='nodes'), 'rules')):
            report = compare(Ask(question='¿Cuántos nodos hay?', dataset='small', repetitions=1, warmups=0))
        self.assertEqual(selected, ['small', 'small'])
        self.assertEqual(report['dataset_id'], 'small')
        self.assertTrue(report['equivalent'])

    def test_zero_id_and_dataset_semantics(self):
        plan = rule_plan('Alcance del nodo 0 a 2 saltos')
        self.assertEqual(plan.node_id, '0')
        small, params = compile_plan(plan, 'small')
        full, _ = compile_plan(plan, 'full')
        self.assertIn(']->', small)
        self.assertNotEqual(small, full)
        self.assertEqual(params['id'], '0')
        with self.assertRaises(ValueError):
            compile_plan(Plan(intent='countries'), 'small')
        self.assertEqual(rule_plan(dataset_examples('small')[2]).intent, 'trusted')

    def test_complete_network_preserves_ids_directions_and_counts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = root / 'test.gz'
            with gzip.open(raw, 'wt') as f:
                f.write('# fixture\n0\t2\n2\t1\n')
            prepare(root, raw, expected=(3, 2))
            rows = [json.loads(line) for line in (root / 'small/graph.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual([r['id'] for r in rows[:3]], ['0', '1', '2'])
            self.assertEqual(rows[3]['start']['id'], '0')
            self.assertEqual(rows[3]['end']['id'], '2')
            self.assertEqual(rows[0]['properties']['name'], 'Usuario 0')
            self.assertEqual(rows[0]['properties']['country'], '')
            with self.assertRaises(ValueError):
                prepare(root, raw, expected=(3, 2))

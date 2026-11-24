"""Run the presentation catalogue through the same API used by the frontend."""
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path
import httpx
from app.catalog import EXAMPLES


def main(dataset='full'):
    reports = []
    with httpx.Client(base_url='http://localhost:8000', timeout=600) as client:
        state = client.get('/api/status', params={'dataset': dataset}).raise_for_status().json()
        intents = ['nodes', 'edges', 'countries', 'hubs', 'search', 'neighbors', 'reach']
        if dataset == 'small':
            intents[2] = 'trusted'
        for question, intent in zip(state['examples'], intents):
            print(question, flush=True)
            response = client.post('/api/compare', json={'dataset': dataset, 'question': question, 'repetitions': 3, 'warmups': 1})
            response.raise_for_status()
            report = response.json()
            report['expected_intent'] = intent
            report['intent_correct'] = report['plan']['intent'] == intent
            reports.append(report)
            print(json.dumps({'equivalent': report['equivalent'], 'engines': {
                name: {k: v for k, v in value.items() if k != 'rows'}
                for name, value in report['engines'].items()}}, ensure_ascii=False), flush=True)
    result = {'created_utc': datetime.now(timezone.utc).isoformat(), 'state': state, 'queries': reports}
    Path('reports').mkdir(exist_ok=True)
    filename = 'benchmark.json' if dataset == 'full' else 'benchmark-small.json'
    (Path('reports') / filename).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    if not all(r['equivalent'] is True and r['intent_correct'] for r in reports):
        raise SystemExit('Hay consultas incompatibles o resultados distintos; consulta reports/benchmark.json.')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--dataset', choices=['full', 'small'], default='full')
    main(p.parse_args().dataset)

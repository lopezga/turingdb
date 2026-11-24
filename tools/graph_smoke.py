"""Integration check of actual per-engine graph results, expansion and aggregates."""
import json
from pathlib import Path
import httpx


def signature(graph):
    return json.dumps({'nodes': graph['nodes'], 'edges': graph['edges']}, sort_keys=True, ensure_ascii=False)


def main():
    results=[]
    with httpx.Client(base_url='http://localhost:8000',timeout=180) as client:
        def graph(report,engine,action='result',node_id=''):
            response=client.post('/api/visualize',json={'comparison_id':report['comparison_id'],'engine':engine,'action':action,'node_id':node_id})
            response.raise_for_status()
            return response.json()
        for dataset,seed in [('full','10000001'),('small','0')]:
            report=client.post('/api/compare',json={'dataset':dataset,'question':f'Vecinos del nodo {seed}','repetitions':1,'warmups':0}).raise_for_status().json()
            assert report['plan']['intent']=='neighbors' and report['equivalent'], report
            graphs={name:graph(report,name) for name in ['Neo4j','TuringDB']}
            for name,g in graphs.items():
                assert g['dataset_id']==dataset
                assert {e['id'] for e in g['edges']}=={row['edge_id'] for row in report['engines'][name]['rows']}
                assert all(e['source'] in {n['id'] for n in g['nodes']} and e['target'] in {n['id'] for n in g['nodes']} for e in g['edges'])
            assert signature(graphs['Neo4j'])==signature(graphs['TuringDB'])
            selected=next(n['id'] for n in graphs['Neo4j']['nodes'] if n['id']!=seed)
            expanded={name:graph(report,name,'expand',selected) for name in graphs}
            assert signature(expanded['Neo4j'])==signature(expanded['TuringDB'])
            assert all(g['scope']=='exploration' for g in expanded.values())
            for name in graphs:
                assert signature(graph(report,name,'reset'))==signature(graphs[name])
            aggregate=client.post('/api/compare',json={'dataset':dataset,'question':'¿Cuántos nodos hay?','repetitions':1,'warmups':0}).raise_for_status().json()
            for name in graphs:
                g=graph(aggregate,name)
                assert not g['available'] and not g['nodes'] and not g['edges']
            results.append({'dataset':dataset,'result_nodes':len(graphs['Neo4j']['nodes']),
                'result_edges':len(graphs['Neo4j']['edges']), 'expanded_nodes':len(expanded['Neo4j']['nodes']),
                'expanded_edges':len(expanded['Neo4j']['edges']), 'equal':True,'aggregates_without_fabricated_nodes':True})
            print(json.dumps(results[-1]),flush=True)
    Path('reports').mkdir(exist_ok=True)
    Path('reports/graph-smoke.json').write_text(json.dumps(results,indent=2),encoding='utf-8')


if __name__=='__main__':
    main()

import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.catalog import Plan
from app.graph import ComparisonStore, result_graph, expand_graph, merge_graph, MAX_NODES, MAX_EDGES, GraphRequestError, store
from app.main import app, lock


class GraphTests(unittest.TestCase):
    def entry(self, intent='neighbors', rows=None):
        return {'dataset': 'small', 'plan': Plan(intent=intent, node_id='0'),
                'results': {'Neo4j': {'rows': rows or []}}, 'graphs': {}}

    def test_exact_neighbors_fetch_only_returned_edges_with_real_direction(self):
        queries = []
        class Engine:
            def query(self, query, params):
                queries.append((query, params))
                if 'edge_ids' in params:
                    return [{'id':'7','source':'0','target':'1','role':'trusts','origin':'SNAP'}]
                return [{'id':i,'name':'Usuario '+i,'kind':'User','country':'','jurisdiction':'','source':'SNAP'} for i in ['0','1']]
        entry=self.entry(rows=[{'id':'1','edge_id':'7','role':'trusts'}])
        graph=result_graph(entry,'Neo4j',Engine())
        self.assertEqual(queries[0][1], {'edge_ids':['7']})
        self.assertEqual(graph['edges'][0]['source'], '0')
        self.assertEqual(graph['edges'][0]['target'], '1')
        self.assertEqual({n['id'] for n in graph['nodes']}, {'0','1'})
        self.assertEqual(graph['scope'], 'result')

    def test_aggregates_never_fabricate_nodes_or_query_database(self):
        class Engine:
            def query(self,*_):
                raise AssertionError('Aggregates must not need graph data')
        graph=result_graph(self.entry('nodes',[{'total':75879}]),'Neo4j',Engine())
        self.assertFalse(graph['available'])
        self.assertEqual(graph['nodes'], [])
        self.assertEqual(graph['edges'], [])

    def test_expand_requires_a_node_from_the_server_held_graph(self):
        entry=self.entry()
        entry['graphs']['Neo4j']={'nodes':[{'id':'0'}],'edges':[],'anchor':'0'}
        with self.assertRaises(GraphRequestError):
            expand_graph(entry,'Neo4j',None,'999')

    def test_merge_preserves_parallel_edges_and_enforces_caps(self):
        nodes=[{'id':str(i)} for i in range(MAX_NODES+1)]
        edges=[{'id':str(i),'source':'0','target':'1','role':'trusts'} for i in range(MAX_EDGES+1)]
        graph=merge_graph({'nodes':[],'edges':[],'limited':False},nodes,edges)
        self.assertEqual(len(graph['nodes']),MAX_NODES)
        self.assertEqual(len(graph['edges']),MAX_EDGES)
        self.assertTrue(graph['limited'])

    def test_expired_and_evicted_reports_are_rejected(self):
        cache=ComparisonStore(capacity=1,ttl=10)
        with patch('app.graph.time.monotonic',return_value=1):
            first=cache.add('small',Plan(intent='nodes'),{})
            second=cache.add('full',Plan(intent='nodes'),{})
        with patch('app.graph.time.monotonic',return_value=2):
            with self.assertRaises(KeyError):cache.get(first)
        with patch('app.graph.time.monotonic',return_value=11):
            with self.assertRaises(KeyError):cache.get(second)

    def test_visual_api_validates_engine_and_does_not_overlap_measurements(self):
        with TestClient(app) as client:
            self.assertEqual(client.post('/api/visualize',json={'comparison_id':'a'*32,'engine':'other'}).status_code,422)
            self.assertEqual(client.post('/api/visualize',json={'comparison_id':'a'*32,'engine':'Neo4j'}).status_code,410)
            lock.acquire()
            try:
                self.assertEqual(client.post('/api/visualize',json={'comparison_id':'a'*32,'engine':'Neo4j'}).status_code,409)
            finally:lock.release()

    def test_visual_api_uses_the_cached_dataset_not_a_client_selector(self):
        selected=[]
        class Engine:
            def __init__(self,dataset):selected.append(dataset)
            def close(self):pass
        key=store.add('small',Plan(intent='nodes'),{'Neo4j':{'rows':[{'total':75879}]}})
        with patch('app.main.NeoEngine',Engine), TestClient(app) as client:
            graph=client.post('/api/visualize',json={'comparison_id':key,'engine':'Neo4j'}).json()
        self.assertEqual(selected,['small'])
        self.assertEqual(graph['dataset_id'],'small')

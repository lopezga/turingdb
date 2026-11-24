import os
import time
from app.datasets import dataset_config


class NeoEngine:
    def __init__(self, dataset='full'):
        from neo4j import GraphDatabase
        config = dataset_config(dataset)
        self.driver = GraphDatabase.driver(os.getenv(config['neo_env'], config['neo_default']),
            auth=('neo4j', os.getenv('NEO4J_PASSWORD', '')), connection_timeout=10)
        self.driver.verify_connectivity()

    def query(self, cypher, params=None):
        from neo4j import Query
        with self.driver.session(database='neo4j') as session:
            return session.run(Query(cypher, timeout=30), params or {}).data()

    def close(self):
        self.driver.close()


class TuringEngine:
    def __init__(self, graph=True, dataset='full'):
        from turingdb import TuringDB
        config = dataset_config(dataset)
        self.client = TuringDB(host=os.getenv(config['turing_env'], config['turing_default']), port=6666)
        if graph:
            self.client.impl._inner.set_timeout(30000)
            self.client.load_graph(config['graph'], raise_if_loaded=False)
            self.client.set_graph(config['graph'])

    def query(self, cypher, params=None):
        return self.client.query(cypher, params or {}).to_dict(orient='records')

    def close(self):
        # The facade has no public close() in 3.1; release the underlying socket.
        try:
            self.client.impl._inner.disconnect()
        except RuntimeError:
            pass  # A transport failure may already have closed the socket.


def measure(engine, cypher, params):
    started = time.perf_counter_ns()
    rows = engine.query(cypher, params)
    return {'ms': (time.perf_counter_ns() - started) / 1e6, 'rows': rows}

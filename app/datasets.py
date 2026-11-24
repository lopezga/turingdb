"""Allowlisted dataset routing. Each dataset has its own pair of database services."""
from pathlib import Path
from typing import Literal

DatasetId = Literal['full', 'small']


def dataset_config(dataset='full'):
    if dataset not in ('full', 'small'):
        raise ValueError('Dataset desconocido')
    return {'id': dataset, 'directory': Path('data/canonical' if dataset == 'full' else 'data/small'),
            'graph': 'offshore', 'neo_env': 'NEO4J_URI' if dataset == 'full' else 'NEO4J_SMALL_URI',
            'turing_env': 'TURING_HOST' if dataset == 'full' else 'TURING_SMALL_HOST',
            'neo_default': 'bolt://localhost:7687' if dataset == 'full' else 'bolt://localhost:7690',
            'turing_default': 'localhost' if dataset == 'full' else 'turingdb-small'}

"""Convert the complete Stanford SNAP Epinions network; no node sampling."""
import argparse
import gzip
import json
import httpx
from datetime import datetime, timezone
from pathlib import Path
from tools.dataset import sha256

URL = 'https://snap.stanford.edu/data/soc-Epinions1.txt.gz'
SOURCE = 'https://snap.stanford.edu/data/soc-Epinions1.html'


def prepare(root='data', archive=None, expected=(75879, 508837)):
    root = Path(root)
    target = root / 'small'
    target.mkdir(parents=True, exist_ok=True)
    graph, manifest_path = target / 'graph.jsonl', target / 'manifest.json'
    if graph.exists() or manifest_path.exists():
        raise ValueError('Epinions ya está preparado o hay una preparación parcial; no se sobrescribe.')
    archive = Path(archive) if archive else root / 'raw' / 'epinions.txt.gz'
    archive.parent.mkdir(parents=True, exist_ok=True)
    if not archive.exists():
        temp = archive.with_suffix('.partial')
        with httpx.stream('GET', URL, timeout=120, follow_redirects=True) as response, temp.open('wb') as out:
            response.raise_for_status()
            for block in response.iter_bytes():
                out.write(block)
        temp.replace(archive)
    nodes, edges = set(), []
    with gzip.open(archive, 'rt', encoding='utf-8') as file:
        for line in file:
            if not line.strip() or line.startswith('#'):
                continue
            a, b = (int(value) for value in line.split())
            if a < 0 or b < 0:
                raise ValueError('Identificador negativo en el origen')
            nodes.update((a, b))
            edges.append((a, b))
    if (len(nodes), len(edges)) != expected:
        raise ValueError(f'El origen no coincide con los conteos esperados: {len(nodes)} nodos y {len(edges)} relaciones')
    temporary = target / 'graph.partial'
    with temporary.open('w', encoding='utf-8', newline='\n') as out:
        for uid in sorted(nodes):
            name = f'Usuario {uid}'
            row = {'type': 'node', 'id': str(uid), 'labels': ['Record'], 'properties': {
                'uid': str(uid), 'name': name, 'name_search': name.lower(), 'kind': 'User',
                'country': '', 'jurisdiction': '', 'source': 'SNAP Epinions'}}
            out.write(json.dumps(row, ensure_ascii=False) + '\n')
        for index, (a, b) in enumerate(edges):
            row = {'type': 'relationship', 'id': str(index), 'label': 'LINK', 'start': {'id': str(a)},
                'end': {'id': str(b)}, 'properties': {'uid': str(index), 'role': 'trusts', 'source': 'SNAP Epinions'}}
            out.write(json.dumps(row) + '\n')
    temporary.replace(graph)
    manifest = {'name': 'Epinions · red de confianza', 'source': SOURCE, 'download': URL,
        'attribution': 'Stanford SNAP; M. Richardson, R. Agrawal y P. Domingos, ISWC 2003',
        'license_note': 'La página del dataset no declara una licencia específica. Consultar al proveedor antes de redistribuir o reutilizar comercialmente.',
        'created_utc': datetime.now(timezone.utc).isoformat(), 'nodes': len(nodes), 'edges': len(edges),
        'profile': 'complete', 'sampling': 'Ninguno: todos los nodos y enlaces del archivo oficial.',
        'semantics': 'A -> B significa que A confía en B. Sin nombres reales, países, reseñas ni puntuaciones. Usuario N es una etiqueta derivada del ID.',
        'archive_sha256': sha256(archive), 'graph_sha256': sha256(graph)}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--root', default='data')
    prepare(p.parse_args().root)

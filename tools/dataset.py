"""Download ICIJ once; normalize to a canonical portable graph, never synthetic data."""
import argparse
import csv
import hashlib
import io
import json
import os
import sqlite3
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from app.catalog import normalize

URL = 'https://offshoreleaks-data.icij.org/offshoreleaks/csv/full-oldb.LATEST.zip'
KINDS = {'entities': 'Entity', 'officers': 'Officer', 'intermediaries': 'Intermediary',
         'addresses': 'Address', 'others': 'Other'}


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def prepare(root, profile, archive=None):
    root = Path(root)
    raw, target = root / 'raw', root / 'canonical'
    raw.mkdir(parents=True, exist_ok=True)
    target.mkdir(parents=True, exist_ok=True)
    if (target / 'manifest.json').exists():
        raise ValueError('Ya hay un dataset preparado. Usa otro DATA_DIR para conservar su identidad.')
    archive = Path(archive) if archive else raw / 'icij.zip'
    if not archive.exists():
        print('Descargando ICIJ (puede tardar varios minutos)...', flush=True)
        temporary = archive.with_suffix('.partial')
        req = urllib.request.Request(URL, headers={'User-Agent': 'GraphScope educational benchmark'})
        with urllib.request.urlopen(req, timeout=120) as response, open(temporary, 'wb') as f:
            while block := response.read(1024 * 1024):
                f.write(block)
        temporary.replace(archive)
    max_nodes = {'small': 100_000, 'medium': 500_000, 'full': None}[profile]
    dbpath = raw / 'selected.sqlite'
    db = sqlite3.connect(dbpath)
    db.execute('CREATE TABLE IF NOT EXISTS ids (id TEXT PRIMARY KEY)')
    db.execute('DELETE FROM ids')
    nodes = edges = skipped = 0
    graphpath = target / 'graph.jsonl'
    with zipfile.ZipFile(archive) as z, open(graphpath, 'w', encoding='utf-8', newline='\n') as out:
        files = sorted(n for n in z.namelist() if n.lower().endswith('.csv') and not n.startswith('__MACOSX'))
        nodefiles = [(n, kind) for n in files for key, kind in KINDS.items()
                     if Path(n).stem.lower().endswith('nodes-' + key) or Path(n).stem.lower() == key]
        relfiles = [n for n in files if 'relationship' in Path(n).stem.lower()]
        if not nodefiles or not relfiles:
            raise ValueError(f'Formato ICIJ no reconocido: {files}')
        def records(name):
            with z.open(name) as stream:
                reader = csv.DictReader(io.TextIOWrapper(stream, encoding='utf-8-sig'))
                for row in reader:
                    yield {k.strip().lower(): (v or '').strip() for k, v in row.items() if k}
        for filename, kind in nodefiles:
            # Same deterministic fraction per node type; full profile includes every row.
            for row in records(filename):
                uid = row.get('node_id', '')
                if not uid.isdigit():
                    raise ValueError('node_id ausente o no numérico')
                fraction = int(hashlib.sha256(uid.encode()).hexdigest()[:8], 16) / 2**32
                threshold = {'small': .03, 'medium': .20, 'full': 1}[profile]
                if fraction >= threshold or (max_nodes and nodes >= max_nodes):
                    continue
                inserted = db.execute('INSERT OR IGNORE INTO ids VALUES (?)', (uid,)).rowcount
                if not inserted:
                    continue
                name = row.get('name') or row.get('address') or ''
                props = {'uid': uid, 'name': name, 'name_search': normalize(name), 'kind': kind,
                    'country': row.get('countries') or row.get('country_codes') or 'Unknown',
                    'jurisdiction': row.get('jurisdiction_description') or row.get('jurisdiction') or '',
                    'source': row.get('sourceid', '')}
                out.write(json.dumps({'type': 'node', 'id': uid, 'labels': ['Record'], 'properties': props}, ensure_ascii=False) + '\n')
                nodes += 1
            db.commit()
            print(f'{kind}: {nodes:,} nodos acumulados', flush=True)
        for filename in relfiles:
            for row in records(filename):
                a, b = row.get('node_id_start'), row.get('node_id_end')
                if not a or not b:
                    raise ValueError('Columnas de relaciones ICIJ no reconocidas')
                if db.execute('SELECT count(*) FROM ids WHERE id IN (?,?)', (a, b)).fetchone()[0] != (1 if a == b else 2):
                    skipped += 1
                    continue
                out.write(json.dumps({'type': 'relationship', 'id': str(edges), 'label': 'LINK',
                    'start': {'id': a}, 'end': {'id': b}, 'properties': {'uid': str(edges),
                    'role': row.get('rel_type') or row.get('type') or row.get('link') or '',
                    'source': row.get('sourceid', '')}}, ensure_ascii=False) + '\n')
                edges += 1
    db.close()
    manifest = {'source': URL, 'attribution': 'International Consortium of Investigative Journalists (ICIJ)',
        'license_database': 'ODbL 1.0', 'license_contents': 'CC BY-SA',
        'created_utc': datetime.now(timezone.utc).isoformat(), 'profile': profile,
        'nodes': nodes, 'edges': edges, 'excluded_edges': skipped,
        'sampling': 'Deterministic ID hash, induced subgraph; full keeps all recognized nodes.',
        'archive_sha256': sha256(archive), 'graph_sha256': sha256(graphpath)}
    (target / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', choices=['small', 'medium', 'full'], default='full')
    parser.add_argument('--root', default=os.getenv('DATA_DIR', 'data'))
    parser.add_argument('--archive')
    args = parser.parse_args()
    prepare(args.root, args.profile, args.archive)

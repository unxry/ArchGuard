"""Rebuild only the authored, offline mini-repository artifacts. No provider or Settings."""
import json
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[3]
fixtures = Path('design/archguard-signature-v2/tests/fixtures')
mini = fixtures / 'architecture-mini'
env = {**os.environ, 'PYTHONPATH': str(root / 'src')}

def run(args, name, expected=0):
    command = [sys.executable, '-m', 'archguard.cli', *args, str(mini), '--namespace', 'archguard:signature-v2-fixture', '--output', str(fixtures / name)]
    result = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True)
    if result.returncode != expected:
        raise RuntimeError(f'{name}: {result.returncode}: {result.stderr[-1500:]}')
    print(name, result.returncode)

run(['iam', 'build'], 'architecture-iam.json')
run(['architecture', 'discover'], 'architecture-discovery.json')
run(['hybrid', 'analyze', '--without-ai', '--spec', str(mini / 'architecture.yaml')], 'architecture-hybrid.json')
iam = json.loads((root / fixtures / 'architecture-iam.json').read_text())
node = next(n['id'] for n in iam['nodes'] if n['name'] == 'DemoController') if any(n['name'] == 'DemoController' for n in iam['nodes']) else iam['nodes'][0]['id']
run(['ai', 'context', '--node', node], 'architecture-context.json')
config = fixtures / 'graph-thresholds.json'
(root / config).write_text(json.dumps({'projection': {'projection': 'file', 'included_relations': ['IMPORTS']}, 'candidates': {'excessive_coupling': 1}}, indent=2)+'\n')
run(['graph', 'analyze', '--config', str(config)], 'architecture-candidates.json')
cycle_spec = fixtures / 'architecture-cycles.yaml'
(root / cycle_spec).write_text((root / mini / 'architecture.yaml').read_text()+'  - id: ARCH003\n    type: circular_dependency\n    projection: file\n    severity: HIGH\n    relations: [IMPORTS]\n')
run(['architecture', 'check', '--spec', str(cycle_spec)], 'architecture-composite.json', 1)

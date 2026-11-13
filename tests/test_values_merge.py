"""Run the actual promotion workflow's merge step against persisted-value regressions."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

workflow = json.loads(Path(sys.argv[1]).read_text())
assert workflow['on']['workflow_call']['inputs']['merge_existing_values']['default'] is True
step = next(s for s in workflow['jobs']['argocd-promote-helm']['steps'] if s.get('id') == 'merge_values')
assert step['env']['MERGE_EXISTING_VALUES'] == '${{ inputs.merge_existing_values }}'

cases = [
    ('default merge preserves older overrides', True, {'env': {'OLD': 'keep', 'SAME': 'before'}}, {'env': {'SAME': 'after'}}, {'env': {'OLD': 'keep', 'SAME': 'after'}}, True),
    ('replacement removes omitted override', False, {'env': {'SMOKE': 'remove', 'SAME': 'before'}}, {'env': {'SAME': 'after'}}, {'env': {'SAME': 'after'}}, True),
    ('replacement clears all values', False, {'env': {'SMOKE': 'remove'}}, {}, {}, True),
    ('empty default merge stays a no-op', True, {}, {}, {}, False),
]
for name, merge, before, new, expected, has_values in cases:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / 'existing_values.yaml').write_text(json.dumps(before))
        (root / 'new_values.yaml').write_text(json.dumps(new))
        output = root / 'outputs'
        subprocess.run(['bash', '-e', '-c', step['run']], cwd=root,
                       env=dict(os.environ, MERGE_EXISTING_VALUES=str(merge).lower(), GITHUB_OUTPUT=str(output)),
                       check=True, capture_output=True, text=True)
        rendered = json.loads(subprocess.check_output(['yq', '-o=json', '.', 'merged_values.yaml'], cwd=root))
        assert rendered == expected, (name, rendered)
        assert f'has_values={str(has_values).lower()}' in output.read_text(), name
        print('PASS:', name)

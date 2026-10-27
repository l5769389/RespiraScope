"""Keep reusable algorithms and models independent of transport and startup."""
import ast
from pathlib import Path

import ct_breath
import pytest


@pytest.mark.parametrize('package', ['models', 'processing', 'binning'])
def test_reusable_packages_do_not_import_application_adapters(package):
    root = Path(ct_breath.__file__).parent
    forbidden = ('ct_breath.api', 'ct_breath.application', 'ct_breath.runtime')
    for source in (root / package).glob('*.py'):
        tree = ast.parse(source.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                if node.level:
                    parents = ['ct_breath', package]
                    module = '.'.join(parents[:len(parents) - node.level + 1] + [module]).rstrip('.')
                names = [module, *(f'{module}.{alias.name}' for alias in node.names)]
            assert not any(name == prefix or name.startswith(prefix + '.')
                           for name in names for prefix in forbidden), source

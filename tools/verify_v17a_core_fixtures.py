"""Optional read-only verification against a pinned Core source checkout.

Run in a development environment with Core's Pydantic dependency installed:
python tools/verify_v17a_core_fixtures.py --core-source /path/to/core
No Core package initialization, API calls, SQL or writes are performed.
"""
import argparse
import ast
import importlib.util
import json
from pathlib import Path
from typing import Literal


def main():
    from pydantic import Field  # Core development dependency, never HA runtime

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core-source',type=Path,required=True)
    args = parser.parse_args()
    source = args.core_source
    spec = importlib.util.spec_from_file_location('v17a_upstream_schemas',source / 'src/pec/schemas.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    namespace = dict(Literal=Literal,Field=Field,Contract=module.Contract,Gear=module.Gear,
                     Opportunity=module.Opportunity,PublicLocation=module.PublicLocation)
    # Importing patterns.api would initialize its database dependencies. Compile
    # only its actual response model definitions, unchanged, against real bases.
    tree = ast.parse((source / 'src/pec/patterns/api.py').read_text(encoding='utf-8'))
    models = ast.Module(body=[n for n in tree.body if isinstance(n,ast.ClassDef)],type_ignores=[])
    exec(compile(models,'upstream_pattern_models','exec'),namespace)
    fixtures = Path(__file__).resolve().parents[1] / 'tests/fixtures/v17a'
    count = 0
    for path in sorted(fixtures.glob('*.json')):
        model = (namespace['PatternResponse'] if path.stem == 'shadow_patterns'
                 else module.SourceHealthList if path.stem == 'source_health' else module.OpportunityList)
        model.model_validate(json.loads(path.read_text(encoding='utf-8')))
        print(f'{path.name}: {model.__name__} valid')
        count += 1
    print(f'{count} fixtures validated against actual Core model classes.')
    print('API incompatibility is a deliberate string-level compatibility failure; it is rejected by the HA tests, not by Core Version typing.')


if __name__ == '__main__':
    main()

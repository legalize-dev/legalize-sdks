# legalize

[![python-ci](https://github.com/legalize-dev/legalize-sdks/actions/workflows/python-ci.yml/badge.svg)](https://github.com/legalize-dev/legalize-sdks/actions/workflows/python-ci.yml)
[![PyPI](https://img.shields.io/pypi/v/legalize.svg)](https://pypi.org/project/legalize/)
[![Python versions](https://img.shields.io/pypi/pyversions/legalize.svg)](https://pypi.org/project/legalize/)

Official Python client for the [Legalize API](https://legalize.dev/api).

```bash
pip install legalize
```

```python
from legalize import Legalize

client = Legalize(api_key="leg_...")

for law in client.laws.list(country="es", law_type="ley_organica"):
    print(law.id, law.title)
```

See the [monorepo README](../README.md) for the full SDK design and
language matrix.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

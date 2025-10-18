#!/bin/bash

echo "🚀 Installation de la CI/CD pour OSM-GPX-Uploader"
echo "=================================================="
echo ""

# Créer les dossiers
echo "📁 Création des dossiers..."
mkdir -p .github/workflows
mkdir -p .github/ISSUE_TEMPLATE
mkdir -p tests

# 1. tests/test_osm_gpx_uploader.py
echo "📝 Création de tests/test_osm_gpx_uploader.py..."
cat > tests/test_osm_gpx_uploader.py << 'TESTEOF'
#!/usr/bin/env python3
"""Tests unitaires pour OSM-GPX-Uploader"""
import pytest
import json
import tempfile
import os
import importlib.util
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, mock_open

# Importer le module avec des tirets dans le nom
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location(
    "uploader",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "OSM-GPX-Uploader.py")
)
uploader = importlib.util.module_from_spec(spec)
with patch('webbrowser.open'), patch('http.server.HTTPServer'):
    spec.loader.exec_module(uploader)

class TestConfiguration:
    def test_default_config_values(self):
        assert uploader.DEFAULT_CONFIG['visibility'] == 'identifiable'
        assert uploader.DEFAULT_CONFIG['tags'] == 'survey'

class TestGPXParsing:
    def test_format_trace_name(self):
        dt = datetime(2023, 11, 22, 14, 4, 30)
        trace_name = uploader.format_trace_name(dt)
        assert trace_name == "20231122 - 14:04"

class TestTraceManagement:
    @patch('requests.get')
    def test_get_existing_traces(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'traces': [
                {'id': 1, 'description': '20231122 - 14:04 - Test'},
            ]
        }
        mock_get.return_value = mock_response
        traces = uploader.get_existing_traces('test_token')
        assert len(traces) == 1

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
TESTEOF

# 2. .github/workflows/tests.yml
echo "📝 Création de .github/workflows/tests.yml..."
cat > .github/workflows/tests.yml << 'WORKFLOWEOF'
name: Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        python-version: ['3.8', '3.9', '3.10', '3.11', '3.12']
    steps:
    - uses: actions/checkout@v4
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v5
      with:
        python-version: ${{ matrix.python-version }}
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install pytest pytest-cov pytest-mock requests
    - name: Run tests
      run: pytest tests/ --cov=. --cov-report=xml --cov-report=term-missing
    - name: Upload coverage
      uses: codecov/codecov-action@v4
      with:
        file: ./coverage.xml
      env:
        CODECOV_TOKEN: ${{ secrets.CODECOV_TOKEN }}

  lint:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.11'
    - name: Install tools
      run: |
        python -m pip install --upgrade pip
        pip install flake8 black
    - name: Lint
      run: |
        flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
        flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
    - name: Check format
      run: black --check .
WORKFLOWEOF

# 3. pytest.ini
echo "📝 Création de pytest.ini..."
cat > pytest.ini << 'PYTESTEOF'
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = --verbose --strict-markers --tb=short
PYTESTEOF

# 4. .codecov.yml
echo "📝 Création de .codecov.yml..."
cat > .codecov.yml << 'CODECOVEOF'
codecov:
  require_ci_to_pass: yes

coverage:
  precision: 2
  range: "70...100"
  status:
    project:
      default:
        target: 80%
    patch:
      default:
        target: 80%

ignore:
  - "tests/"
  - "**/__pycache__"
CODECOVEOF

# 5. requirements-dev.txt
echo "📝 Création de requirements-dev.txt..."
cat > requirements-dev.txt << 'REQEOF'
requests>=2.28.0
pytest>=7.0.0
pytest-cov>=4.0.0
pytest-mock>=3.10.0
flake8>=6.0.0
black>=23.0.0
REQEOF

# 6. Makefile avec TABS
echo "📝 Création de Makefile..."
cat > Makefile << 'MAKEEOF'
.PHONY: help test install

help:
  @echo 'Available targets:'
  @echo '  install      Install dependencies'
  @echo '  test         Run tests'
  @echo '  test-cov     Run tests with coverage'
  @echo '  lint         Lint code'
  @echo '  format       Format code'

install:
  pip install -r requirements-dev.txt

test:
  pytest tests/ -v

test-cov:
  pytest tests/ --cov=. --cov-report=html --cov-report=term-missing

lint:
  flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127

format:
  black .

clean:
  rm -rf __pycache__ .pytest_cache .coverage htmlcov
  find . -type d -name __pycache__ -exec rm -rf {} +
MAKEEOF

# 7. Bug report template
echo "📝 Création de .github/ISSUE_TEMPLATE/bug_report.md..."
cat > .github/ISSUE_TEMPLATE/bug_report.md << 'BUGEOF'
---
name: Bug Report
about: Create a report to help us improve
title: '[BUG] '
labels: bug
---

## Bug Description
<!-- Clear description -->

## Steps to Reproduce
1. 
2. 

## Environment
- OS: 
- Python: 
BUGEOF

# 8. Feature request template
echo "📝 Création de .github/ISSUE_TEMPLATE/feature_request.md..."
cat > .github/ISSUE_TEMPLATE/feature_request.md << 'FEATUREEOF'
---
name: Feature Request
about: Suggest an idea
title: '[FEATURE] '
labels: enhancement
---

## Feature Description
<!-- What feature would you like? -->

## Motivation
<!-- Why is this needed? -->

## Use Cases
1. 
2. 
FEATUREEOF

# 9. PR template
echo "📝 Création de .github/PULL_REQUEST_TEMPLATE.md..."
cat > .github/PULL_REQUEST_TEMPLATE.md << 'PREOF'
## Description
<!-- What does this PR do? -->

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation

## Testing
- [ ] Tests pass
- [ ] Added new tests

## Checklist
- [ ] Code follows style
- [ ] Updated docs
PREOF

# 10. CONTRIBUTING.md
echo "📝 Création de CONTRIBUTING.md..."
cat > CONTRIBUTING.md << 'CONTRIBEOF'
# Contributing

## Getting Started
1. Fork the repository
2. Clone: `git clone https://github.com/YOUR_USERNAME/OSM-GPX-Uploader.git`
3. Install: `pip install -r requirements-dev.txt`

## Running Tests
```bash
make test
make test-cov
```

## Code Style
```bash
make format
make lint
```

## Pull Requests
1. Create a branch
2. Make changes
3. Run tests
4. Submit PR

Thank you! ❤️
CONTRIBEOF

echo ""
echo "✅ Installation terminée!"
echo ""
echo "📋 Fichiers créés avec succès"
echo ""
echo "🎯 Prochaines étapes:"
echo "  1. make install"
echo "  2. make test"
echo "  3. git add . && git commit -m 'Add CI/CD'"
echo "  4. git push"
echo ""
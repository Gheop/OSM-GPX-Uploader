.PHONY: help test install

help:
	@echo 'Targets: install, test, test-cov, lint, format, clean'

install:
	pip install -r requirements-dev.txt

test:
	pytest tests/ -v

test-cov:
	pytest tests/ --cov=. --cov-report=html

lint:
	flake8 .

format:
	black .

clean:
	rm -rf __pycache__ .pytest_cache .coverage htmlcov

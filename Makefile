.PHONY: install test demo demo-orallexa demo-generic clean

PY ?= python3

install:
	$(PY) -m pip install -r requirements.txt

test:
	PYTHONPATH=. $(PY) -m pytest tests/ -v

demo: demo-generic

demo-generic:
	@echo "── Generic project demo (no API keys required) ──"
	PYTHONPATH=. $(PY) examples/generic_demo.py

demo-orallexa:
	@echo "── Orallexa as test project (no API keys required) ──"
	PYTHONPATH=. $(PY) examples/orallexa_demo.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	rm -rf .coverage htmlcov dist build *.egg-info

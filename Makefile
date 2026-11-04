.PHONY: install run fast test data

install:
	pip install -e ".[dev]"

run:            ## full pipeline: models, scenarios, robustness, figures (~1 min)
	python -m oilinfl

fast:           ## quick check: fewer draws, no robustness suite (~5 s)
	python -m oilinfl --fast --skip-robustness

test:
	python -m pytest -q

data:           ## refresh FRED series and crack spread (needs internet)
	python scripts/update_data.py

# Viaggio backend — dev/CI helper (Linux/macOS; on Windows use dev.ps1)
# Spatial (PostGIS) tests require the docker-compose PostGIS service running.
PY ?= python
export USE_SQLITE ?= True

.PHONY: check test migrate run
check:
	$(PY) manage.py check
test:
	$(PY) -m pytest
migrate:
	$(PY) manage.py makemigrations
	$(PY) manage.py migrate
run:
	$(PY) manage.py runserver 0.0.0.0:8000

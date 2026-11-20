PYTHON ?= python3
BROKER_DIR = meross_local_broker/rootfs/opt/custom_broker

.PHONY: install test lint-profiles reports

install:
	$(PYTHON) -m pip install -r $(BROKER_DIR)/requirements_ci.txt

test:
	cd $(BROKER_DIR) && $(PYTHON) -m pytest -q

lint-profiles:
	cd $(BROKER_DIR) && $(PYTHON) profile_lint.py

reports:
	@mkdir -p reports
	cd $(BROKER_DIR) && $(PYTHON) -m pytest -q \
		--junitxml=../../../../reports/broker.xml

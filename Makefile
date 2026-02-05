SHELL=/bin/bash
export PYTHON_VERSION := python3

DEFAULT_CONFIG_FILES := $(wildcard default_config/*.yml)
CONFIG_FILES := $(DEFAULT_CONFIG_FILES:default_config/%=config/%)

all: config msg
.PHONY: all

msg:
	@echo
	@echo
	@echo ---------------------------------------------------
	@echo type '`make about`' for a description of the project
	@echo ---------------------------------------------------
	@echo
	@echo
.PHONY: msg

about:
	less readme.md
.PHONY: about

config: setup-venv setup-config
.PHONY: config

fake-sentry: setup-venv
	.venv/bin/python -m fake_sentry.fake_sentry
.PHONY: fake-sentry

check-test:
ifndef TEST
	$(error TEST is undefined. Please specify a test name such as `make TEST=simple load-test` or `make TEST=kafka_consumers load-test`)
endif
.PHONY: check-test

load-test: check-test setup-venv
	./bin/start_locust.sh $(TEST)_locustfile.py

.PHONY: load-test

setup-brew:
	brew bundle
.PHONY: setup-brew


setup-config: $(CONFIG_FILES)
.PHONY: setup-config

config/%.yml: default_config/%.yml
	@mkdir -p config
	cp $< $@

setup-venv: .venv/bin/python
.PHONY: setup-venv

.venv/bin/python:
	@rm -rf .venv
	python3 -m venv --copies .venv
	.venv/bin/pip install -U pip wheel
	.venv/bin/pip install -U -r requirements.txt

format: setup-venv
	.venv/bin/black .

style: setup-venv
	.venv/bin/black --check .

generate-javascript-stack-traces:
	cd javascript-stack-trace-generator && make all

# Ansible targets
ANSIBLE_DIR := ansible
ANSIBLE_PLAYBOOK := ansible-playbook -i $(ANSIBLE_DIR)/inventory/hosts.yml
TAGS ?=

# Run ansible against all hosts
ansible-all:
	cd $(ANSIBLE_DIR) && ansible-playbook site.yml $(if $(TAGS),--tags $(TAGS),)
.PHONY: ansible-all

# Run ansible against master only
ansible-master:
	cd $(ANSIBLE_DIR) && ansible-playbook site.yml --limit master $(if $(TAGS),--tags $(TAGS),)
.PHONY: ansible-master

# Run ansible against workers only
ansible-workers:
	cd $(ANSIBLE_DIR) && ansible-playbook site.yml --limit workers $(if $(TAGS),--tags $(TAGS),)
.PHONY: ansible-workers

# Test ansible connectivity
ansible-ping:
	cd $(ANSIBLE_DIR) && ansible all -m ping
.PHONY: ansible-ping

# List ansible hosts
ansible-list:
	cd $(ANSIBLE_DIR) && ansible all --list-hosts
.PHONY: ansible-list

# Show available ansible tags
ansible-tags:
	@echo "Available tags:"
	@echo "  packages  - Install system packages"
	@echo "  python    - Python and pip setup"
	@echo "  deploy    - Deploy application files"
	@echo "  config    - Configure services"
	@echo "  service   - Manage systemd services"
	@echo "  master    - Master-specific tasks"
	@echo "  worker    - Worker-specific tasks"
	@echo ""
	@echo "Usage: make ansible-all TAGS=deploy,config"
.PHONY: ansible-tags

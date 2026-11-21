# Developer conveniences. Deployment steps are plain scripts documented in
# docs/installation/; they are intentionally not hidden behind make targets.

SHELL := /usr/bin/env bash
SHELL_SCRIPTS := $(shell find scripts tests -name '*.sh')
TERRAFORM ?= terraform

.PHONY: help lint lint-shell lint-yaml lint-python lint-terraform lint-templates lint-markdown

help: ## Show this help
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-16s %s\n", $$1, $$2}'

lint: lint-shell lint-yaml lint-python lint-templates lint-terraform ## Run all linters

lint-shell: ## ShellCheck on every script
	shellcheck -x $(SHELL_SCRIPTS)

lint-yaml: ## yamllint on static YAML files
	yamllint -c .yamllint .

lint-python: ## ruff on Python helpers
	ruff check scripts
	ruff format --check scripts

lint-templates: ## Render manifest templates with sample values and validate them
	tests/render-templates.sh

lint-terraform: ## terraform fmt and validate
	$(TERRAFORM) -chdir=deployment/infrastructure fmt -check -recursive
	$(TERRAFORM) -chdir=deployment/infrastructure init -backend=false -input=false >/dev/null
	$(TERRAFORM) -chdir=deployment/infrastructure validate

lint-markdown: ## markdownlint on the documentation (requires Node.js)
	npx --yes markdownlint-cli2 "**/*.md"

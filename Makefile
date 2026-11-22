# Build and check the documentation portal. Details: tools/site/README.md.
#
# The portal of OzarLand Academy is one site per available module or release
# of academy.toml, published under its own URL prefix (site/<path>/: lab/,
# day2/2024.1/ ...), plus the root of the portal (the learning path, the home
# of the day-2 module, the not-found page, one page per planned module or
# release).
#
#   make docs-deps      install the pinned build dependencies, fetch the vendored Mermaid
#   make docs-check     check the Markdown sources (no build needed)
#   make docs-content   content conventions of the OzarLand hub, for the
#                       modules that follow them (HUB=<checkout of OzarLand/ozarland>)
#   make docs-build     unit tests, strict build into site/, checks on the built portal
#   make docs-test      unit tests of tools/site only
#   make docs-serve     live preview of one site, rebuilt on change
#   make docs-preview   serve the built portal as GitHub Pages publishes it
#   make docs-clean     remove what the build generates
#
# Python: `python3` from PATH by default, which is what CI uses. When the
# virtual environment .venv exists it is used instead, without activation:
#
#   python3 -m venv .venv
#   make docs-deps
#   make docs-check docs-build
#
# Variables:
#   RELEASE=<path>      docs-check, docs-build: that site only, such as
#                       day2/2024.1 (docs-build also rebuilds the root);
#                       docs-serve: the site to preview (default: the
#                       default release of the day-2 module)
#   SITE_DOMAIN=<domain>  build and check the portal for https://<domain>/
#                       (default: academy.ozarland.com, the domain of the
#                       published portal; SITE_DOMAIN= builds for site_url of
#                       zensical.base.toml, the github.io address). CI sets it
#                       from the repository variable of the same name
#   STRICT=1            the warnings of the checks are errors (CI runs
#                       docs-check and docs-build with STRICT=1)
#   PYTHON=<interpreter>
#   DEV_ADDR=<ip:port>  address of docs-serve and docs-preview

VENV ?= .venv
ifneq ($(wildcard $(VENV)/bin/python),)
PYTHON ?= $(VENV)/bin/python
else
PYTHON ?= python3
endif

# Must match SITE_DIR in tools/site/releases.py.
SITE_DIR := site
DEV_ADDR ?= localhost:8000
# Read by tools/site/releases.py (portal_root_url): the address of the portal.
# The default is the domain of the published portal, the value of the
# repository variable SITE_DOMAIN that CI uses: a local check sees the address
# that README.md writes. An empty value given on the command line or in the
# environment (CI, when the variable is empty) is kept.
SITE_DOMAIN ?= academy.ozarland.com
export SITE_DOMAIN
STRICT ?=
RELEASE ?=
CHECK_FLAGS := $(if $(filter-out 0,$(STRICT)),--strict)
RELEASE_FLAG := $(if $(RELEASE),--release $(RELEASE))

# tools/site holds the local Markdown extension (portal_mdx) that
# zensical.base.toml enables: the unit tests must be able to import it
# (build.py sets the same path for Zensical).
SITE_ENV := PYTHONPATH="$(CURDIR)/tools/site$(if $(PYTHONPATH),:$(PYTHONPATH))"

.DEFAULT_GOAL := help
.PHONY: help docs-deps docs-check docs-content docs-test docs-build docs-serve docs-preview docs-clean

help:
	@echo "make docs-deps      install the pinned build dependencies, fetch the vendored Mermaid"
	@echo "make docs-check     check the Markdown sources (no build needed)"
	@echo "make docs-content   content conventions of the OzarLand hub (HUB=<checkout of OzarLand/ozarland>)"
	@echo "make docs-build     unit tests, strict build into $(SITE_DIR)/, checks on the built portal"
	@echo "make docs-test      unit tests of tools/site only"
	@echo "make docs-serve     live preview of one site on http://$(DEV_ADDR)"
	@echo "make docs-preview   serve the built portal on http://$(DEV_ADDR), as GitHub Pages publishes it"
	@echo "make docs-clean     remove what the build generates"
	@echo "Python: $(PYTHON)   (RELEASE=<path>: one site; STRICT=1: warnings of the checks are errors)"
	@echo "Address:         $$($(PYTHON) tools/site/releases.py url)"
	@echo "Available sites: $$($(PYTHON) tools/site/releases.py list --status available | tr '\n' ' ')"
	@echo "Planned:         $$($(PYTHON) tools/site/releases.py list --status planned | tr '\n' ' ')"

# The only target that needs the network: PyPI, then the pinned Mermaid bundle
# (not committed; fetch_vendor.py verifies its checksum).
docs-deps:
	$(PYTHON) -m pip install -r requirements-docs.txt
	$(PYTHON) tools/site/fetch_vendor.py

docs-check:
	$(PYTHON) tools/site/check_docs.py $(CHECK_FLAGS) $(RELEASE_FLAG)
	$(PYTHON) tools/site/check_learning.py $(CHECK_FLAGS) $(RELEASE_FLAG)
	$(PYTHON) tools/site/runbook_categories.py --check

HUB ?=
docs-content:
	$(if $(HUB),,$(error docs-content: set HUB to a checkout of OzarLand/ozarland))
	$(PYTHON) tools/site/check_content.py --hub $(HUB)

docs-test:
ifneq ($(wildcard tools/site/tests),)
	$(SITE_ENV) $(PYTHON) -m unittest discover -s tools/site/tests
else
	@echo "docs-test: no tools/site/tests directory, nothing to run"
endif

# --strict: any warning of Zensical (broken link or anchor, ...) fails the build.
docs-build: docs-test
	$(PYTHON) tools/site/build.py --strict $(RELEASE_FLAG)
	$(PYTHON) tools/site/check_site.py $(SITE_DIR) $(CHECK_FLAGS) $(RELEASE_FLAG)

# One site at a time: links to the other sites do not work in this preview.
# For the whole portal: docs-preview.
docs-serve:
	$(PYTHON) tools/site/build.py --serve --dev-addr $(DEV_ADDR) $(RELEASE_FLAG)

docs-preview:
	$(PYTHON) tools/site/serve_site.py $(SITE_DIR) --addr $(DEV_ADDR)

# The downloaded Mermaid bundle is a dependency, not a build product: it stays.
docs-clean:
	rm -rf $(SITE_DIR) .cache .build .zensical.*.toml docs/*/assets/data/*.json docs/*/*/assets/data/*.json
	find tools -type d -name __pycache__ -prune -exec rm -rf {} +

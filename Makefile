.RECIPEPREFIX := >
SHELL := /bin/bash

PYTHON ?= python3
VERSION ?= $(shell $(PYTHON) scripts/release.py next-version)
TAG := v$(VERSION)

.PHONY: version next-version test check bump-version changelog release

version next-version:
>printf '%s\n' "$(VERSION)"

test:
>$(PYTHON) -m unittest discover -s tests -q

check:
>$(PYTHON) -m unittest discover -s tests -q
>$(PYTHON) -m py_compile app.py
>git diff --check

bump-version:
>$(PYTHON) scripts/release.py bump-version --version "$(VERSION)"

changelog:
>$(PYTHON) scripts/release.py changelog --version "$(VERSION)"

release:
>$(MAKE) check
>$(MAKE) bump-version VERSION="$(VERSION)"
>$(MAKE) changelog VERSION="$(VERSION)"
>$(MAKE) check

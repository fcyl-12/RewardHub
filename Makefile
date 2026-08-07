.RECIPEPREFIX := >
.ONESHELL:
SHELL := /bin/bash

PYTHON ?= python3
CURRENT_VERSION := $(shell sed -nE 's/^APP_VERSION = "([^"]+)"/\1/p' app.py | head -n 1)
LATEST_TAG := $(shell git tag --sort=-v:refname | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$$' | head -n 1)
VERSION ?= $(shell $(PYTHON) -c 'import re, subprocess; tags=subprocess.check_output(["git","tag","--sort=-v:refname"], text=True).split(); current="$(CURRENT_VERSION)"; tag=next((t for t in tags if re.fullmatch(r"v\d+\.\d+\.\d+", t)), ""); m=re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", tag); print(f"{m.group(1)}.{m.group(2)}.{int(m.group(3))+1}" if m else current)')
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
>set -e
>sed -i -E 's/^APP_VERSION = ".*"/APP_VERSION = "$(VERSION)"/' app.py
>sed -i -E 's/(org.opencontainers.image.version=")[^"]+/\1$(VERSION)/' Dockerfile
>sed -i -E 's/[0-9]+\.[0-9]+\.[0-9]+/$(VERSION)/g' templates/index.html
>sed -i -E '0,/[0-9]+\.[0-9]+\.[0-9]+/s//$(VERSION)/' README.md
>sed -i -E 's/[0-9]+\.[0-9]+\.[0-9]+/$(VERSION)/g' tests/test_app.py
>sed -i -E 's/v[0-9]+\.[0-9]+\.[0-9]+: child branding/v$(VERSION): child branding/' static/style.css

changelog:
>set -e
>tmp="$$(mktemp)"
>{
>  printf '# Changelog\n\n'
>  printf '## $(TAG) - %s\n\n' "$$(date -u +%Y-%m-%d)"
>  if [ -n "$(LATEST_TAG)" ]; then
>    git log --pretty=format:'- %s (%h)' "$(LATEST_TAG)..HEAD"
>  else
>    git log --reverse --pretty=format:'- %s (%h)'
>  fi
>  printf '\n\n'
>  if [ -f CHANGELOG.md ]; then
>    if grep -q '^# Changelog' CHANGELOG.md; then
>      tail -n +2 CHANGELOG.md
>    else
>      cat CHANGELOG.md
>    fi
>  fi
>} > "$$tmp"
>mv "$$tmp" CHANGELOG.md

release:
>$(MAKE) check
>$(MAKE) bump-version VERSION="$(VERSION)"
>$(MAKE) changelog VERSION="$(VERSION)"
>$(MAKE) check

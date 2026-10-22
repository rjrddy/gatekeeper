CARGO := $(if $(wildcard .cache/cargo/bin/cargo),$(CURDIR)/.cache/cargo/bin/cargo,cargo)
ifneq ($(wildcard .cache/rustup),)
export CARGO_HOME := $(CURDIR)/.cache/cargo
export RUSTUP_HOME := $(CURDIR)/.cache/rustup
endif
.PHONY: setup build lint test bench demo scan
setup:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip==26.2.2 setuptools==84.0.0
	.venv/bin/pip install -e '.[dev]'
	npm --prefix apps/web ci
build:
	$(CARGO) build --release --locked --manifest-path agent/Cargo.toml
	mkdir -p bin
	cp agent/target/release/gatekeeper-agent bin/
	npm --prefix apps/web run build
lint:
	.venv/bin/ruff check gatekeeper scripts tests
	.venv/bin/ruff format --check gatekeeper scripts tests
	$(CARGO) fmt --manifest-path agent/Cargo.toml --check
	$(CARGO) clippy --locked --manifest-path agent/Cargo.toml --all-targets -- -D warnings
	npm --prefix apps/web run lint
test:
	.venv/bin/python -m pytest -q
	$(CARGO) test --locked --manifest-path agent/Cargo.toml
bench: build
	.venv/bin/python scripts/bench_analysis.py
	.venv/bin/python scripts/bench_canary.py
	.venv/bin/python scripts/bench_supply.py

demo:
	docker compose up --build
scan:
	.venv/bin/pip-audit --progress-spinner off
	npm --prefix apps/web audit --audit-level=high
	$(CARGO) audit --file agent/Cargo.lock

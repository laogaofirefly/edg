CC ?= cc
CFLAGS ?= -std=c17 -O2 -Wall -Wextra -Wpedantic
CPPFLAGS ?= -Iinclude
RUST_DIR := rust
RUST_LIB := $(RUST_DIR)/target/release/libedg_hot.so

.PHONY: rust rust-debug host host-python edgc smoke smoke-rust value-smoke clean test

rust:
	cargo build --manifest-path $(RUST_DIR)/Cargo.toml --release

rust-debug:
	cargo build --manifest-path $(RUST_DIR)/Cargo.toml

host:
	$(CC) $(CFLAGS) $(CPPFLAGS) c/edg_host.c c/python_embed.c -o edg-host

host-python:
	$(CC) $(CFLAGS) $(CPPFLAGS) -DEDG_WITH_PYTHON c/edg_host.c c/python_embed.c $$(python3-config --cflags --ldflags) -o edg-host-python

edgc:
	$(CC) $(CFLAGS) $(CPPFLAGS) c/edgc.c -o edgc

smoke: host
	./edg-host eval "print('Python disabled')" || test $$? -eq 1

smoke-rust: rust
	$(CC) $(CFLAGS) $(CPPFLAGS) c/edg_hot_smoke.c -L$(RUST_DIR)/target/release -ledg_hot -Wl,-rpath,'$$ORIGIN/$(RUST_DIR)/target/release' -o edg-hot-smoke

value-smoke:
	$(CC) $(CFLAGS) $(CPPFLAGS) c/edg_value.c c/edg_value_smoke.c -o edg-value-smoke
	./edg-value-smoke


test: rust
	python3 edg.py test

clean:
	cargo clean --manifest-path $(RUST_DIR)/Cargo.toml

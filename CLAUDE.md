# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Boom is a Linux boot manager that creates and manages bootable snapshots using the Boot Loader Specification (BLS). It supports LVM2, Stratis, and BTRFS snapshots and works with systemd-boot and BLS-enabled GRUB 2. Written in Python (>=3.9), licensed Apache-2.0.

## Build and Development

Install in editable mode:
```bash
python3 -m venv .venv && source .venv/bin/activate
python3 -m pip install -e .
```

Or run directly from the repo:
```bash
export PATH="$PWD/bin:$PATH" PYTHONPATH="$PWD:$PYTHONPATH"
```

## Testing

Run full test suite with coverage:
```bash
coverage run -m pytest -v --log-level=debug tests
coverage report -m --include "./boom/*"
```

Run a specific test:
```bash
python3 -m pytest -v --log-level=debug tests -k <test_name_pattern>
```

Tests use a sandbox directory (`tests/sandbox/`) created and torn down per-test. The `tests/__init__.py` module provides `reset_sandbox()`, `reset_boom_paths()`, `set_mock_path()`, and a `MockArgs` class used across all test files. Tests redirect boom's boot path to `tests/` so they never touch the real `/boot`.

Some tests require root or LVM — these are guarded by `have_root()` and `have_lvm()` predicates in `tests/__init__.py`.

## Linting

```bash
pycodestyle boom --ignore E501,E203,W503
```

Python source in `boom/` is formatted with `black` (tests are excluded from auto-formatting). A pre-commit hook is available via `pre-commit install`.

pylint is configured in `.pylintrc` with disabled checks: `C0302,R0902,R0903,R0913,R0801,R0917`.

## Architecture

**CLI entrypoint**: `bin/boom` calls `boom.command.main()`.

**Core modules** (all under `boom/`):

- `_boom.py` — Package-level constants (format keys like `FMT_VERSION`, `FMT_ROOT_DEVICE`), path configuration (`set_boot_path()`, `get_boom_path()`), the `Selection` class for filtering objects, `BoomError` base exception, and logging setup.
- `bootloader.py` — `BootEntry` and `BootParams` classes. Reads/writes BLS entries from `/boot/loader/entries`. Entries are identified by SHA1-based IDs. `BootParams` encapsulates kernel version, root device, and storage-specific options.
- `osprofile.py` — `OsProfile` class. Templates for generating boot entries per OS (kernel/initramfs patterns, root options per storage type). Stored in `/boot/boom/profiles/`. Identified by `os_id` (SHA1 of name + short name + version + version ID).
- `hostprofile.py` — `HostProfile` class. Per-host overrides of `OsProfile` defaults (e.g. custom kernel options). Stored in `/boot/boom/hosts/`.
- `command.py` — CLI argument parsing, the procedural API (functions like `create_entry()`, `create_profile()` etc.), and report field definitions. Largest module (~4800 lines).
- `report.py` — Tabular text reporting engine modeled after the device-mapper reporting engine. Supports custom field selection, multi-column sorting, and JSON output.
- `cache.py` — Boot image cache: backs up kernel/initramfs images so snapshot entries remain bootable.
- `config.py` — Reads/writes `boom.conf` persistent configuration.
- `legacy.py` — Read-only support for legacy (non-BLS) bootloader configs. **Deprecated since 1.6.7**.
- `lvm2.py` — LVM2 integration: queries VGs/LVs via `lvs` subprocess calls.
- `stratis.py` — Stratis integration: queries pool UUIDs via D-Bus (`dbus-python`).
- `mounts.py` — Parses systemd-style command-line mount specifications.

**Key design patterns**:
- Profile/entry classes are dict-like containers (support `[]` indexing) with named properties for each key.
- Objects are identified by truncated SHA1 hashes with a configurable minimum width (`MIN_ID_WIDTH = 7`).
- All on-disk writes use atomic rename (`mkstemp` + `fdatasync` + `rename`) to avoid corruption.
- The `Selection` class provides uniform filtering across profiles, entries, and params.

## Commit Message Format

Use `subsystem: description` format for the subject line. Common subsystems: `boom`, `bootloader`, `osprofile`, `hostprofile`, `command`, `cache`, `tests`, `doc`, `dist`, `ci`. Reference issues with `Related: #N` or `Resolves: #N`.

## AI-Assisted Contributions

When AI tools generate meaningful code, include in the commit message:
```
Assisted-by: Tool Name <https://tool.example.com>
```

## Dependencies

Runtime: `dbus-python >= 1.2.16`. Dev: `pycodestyle`, `coverage`, `pytest`, `Sphinx`.

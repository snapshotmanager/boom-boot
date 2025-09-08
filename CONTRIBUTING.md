# Contributing to boom-boot

Contributions, whether features or bug fixes, are welcome. We aim to be
responsive and helpful in project issues and feature requests. For
larger changes, consider discussing the change first by filing an issue;
the maintainers can then add to or create a GitHub project to track the
work. This also gives us a chance to provide feedback on the feasibility
and suitability of your proposal, which helps ensure your hard work
aligns with the project's direction.

-----

Following these guidelines will help you get up to speed quickly,
enabling you to develop and test changes for `boom-boot` and facilitating
a smooth review and merge process. This document provides instructions for
setting up your development environment, our coding style, and how to
run the test suite.

-----

## Writing and Submitting Changes

We use a standard **GitHub pull request workflow**. Here are the basic steps:

1.  **Fork** the repository on GitHub.
2.  **Clone** your fork to your local machine.
3.  Create a **new branch** for your changes.
4.  Make your changes and **commit** them with a clear, concise message.
5.  **Push** your changes to your fork on GitHub.
6.  Create a **pull request** from your fork to the main boom-boot repository.
7.  A committer will **review** your pull request. You may be asked to
    make changes.
8.  Once your pull request is approved and all tests pass, it will be
    **merged**.

-----

## Setting up a Dev Environment

To get started with development on a **RHEL, Fedora, or CentOS-based
system**, you'll need to install the necessary build and runtime
dependencies.

Install the build dependencies with this command:

```bash
dnf builddep boom-boot
```

Create a venv to isolate the installation (optionally add
``--system-site-packages`` to use the installed packages, rather than building
from source):

```bash
python3 -m venv .venv && source .venv/bin/activate
```

Install in editable mode:

```bash
git clone https://github.com/snapshotmanager/boom-boot.git
cd boom-boot
python3 -m pip install -e .
```

Or run from a git clone:

```bash
git clone https://github.com/snapshotmanager/boom-boot.git
cd boom-boot
export PATH="$PWD/bin:$PATH" PYTHONPATH="$PWD:$PYTHONPATH"
boom <type> <command> ...
```

-----

## Coding Style

To maintain a consistent coding style, we use a few tools to format and
lint our code.

* **black**: All Python code in the `boom-boot` package should be
  formatted with `black` (tests are currently excluded from automatic
  formatting).
  * Optional: install pre-commit and enable the Black hook:
    ```bash
    python3 -m pip install pre-commit
    pre-commit install
    ```
* **Sphinx Docstrings**: All functions and methods should have a
  docstring in Sphinx format. You can find a good guide
[here](https://sphinx-rtd-tutorial.readthedocs.io/en/latest/docstrings.html).

-----

## Running Tests

We have a comprehensive test suite to ensure the quality of our code. We
**strongly** recommend running the tests in a virtual machine or other
isolated environment.

### Requirements

* The test suite requires `pytest` (and optionally `coverage`). You can
  install them with `pip` or `dnf` (on RHEL/Fedora/CentOS systems these
  packages are named `python3-pytest` and `python3-coverage`).
* A full test run typically completes in a few minutes, depending on system
  performance.

### Suggested Commands

To run the entire test suite with coverage checking, use the following
commands:

```bash
coverage run -m pytest -v --log-level=debug tests
coverage report -m --include "./boom/*"
```

To run a specific test, you can use the `-k` flag with `pytest`:

```bash
python3 -m pytest -v --log-level=debug tests -k <test_name_pattern>
```

## Building the Documentation

We use Sphinx. To build the HTML docs locally:

```bash
python3 -m pip install -r requirements.txt
make -C doc html
xdg-open doc/_build/html/index.html
```

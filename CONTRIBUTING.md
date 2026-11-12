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

## Commit message formatting

We use a consistent format for commit messages and we expect all contributors
to follow this pattern. If your commits are not formatted in the expected way
you may be asked to change or re-write them before your changes can be merged.
You can do this easily using the ``git commit --amend`` or ``git rebase
--interactive`` commands. If you are not familiar with these and you receive a
request to amend a commit please ask—we are always happy to help new
contributors get the hang of the workflow!

The commit subject (first line) should be in the format:

```text
subsystem: description of change
```

Where "subsystem" is free-form text that should succinctly describe the area of
the codebase that your patch touches. There are no really hard rules here, but
we encourage the use of the module name if changing a single Python file (minus
any dot-separated prefix needed to uniquely identify the module to Python). If
your changes touch several files in the same package you should use the package
name (that would be "plugins" to continue with the previous example). Changes
that are either tree-wide, or that affect several packages (such as a
refactoring that lifts functionality upwards in the package tree) typically use
the top-level "boom" package as the subsystem. Occasionally a comma-separated
list may make sense: for example "lvm2,stratis" but this easily gets unwieldy
so it is not routinely encouraged.

The remainder of the subject should be a brief description of the change or
what it achieves. Again there are few strict rules but it should be possible
for a reviewer to get a rough idea of what to expect in the patch. We do not
enforce a hard limit on the length of the subject but wherever possible it is
good to keep it to fewer than 80 characters (sometimes this is difficult,
especially when naming particular functions or class names—that's fine, and we
review these on a case-by-case basis).

Some examples of common subsystem strings used in the project are:

  * **boom**: the top-level "catch all" subsystem
  * **bootloader**: the ``bootloader`` module, including ``BootEntry`` and
    ``BootParams``
  * **osprofile**: the ``osprofile`` module.
  * **doc**: documentation (including all MarkDown files in the root, as well
    as the Sphinx documentation in doc/, and the groff formatted man pages in
    the man/ directory).
  * **tests**: changes to any of the test suites.
  * **dist**: package and distribution metadata: RPM spec file, Python project
    and build metadata etc.

The commit body (the main text of the commit which follows the subject,
separated by a single empty line) should contain a description of the change if
necessary (often the subject is sufficient, especially for simple changes).

Most changes (even simple fixes or refactors) should be accompanied by an issue
(whether for a fix, or a new feature). Please reference the issue in the commit
using the standard GitHub tags:

```text
Related: #123
Resolves: #232
```

In most cases it's best to have a one-to-one relationship between commits and
issues, but if the problem you are working on is complicated it is perfectly
fine (and encouraged) to break it up into smaller chunks. You can file
sub-issues on GitHub for these if you wish (and it can be helpful when working
on large or complex features/fixes) but it is also acceptable to tag the series
with the "Related:" keyword, and then use "Resolves:" for the final commit that
ends the series.

You are welcome to include tool output, code snippets, and diff output in your
commit message if it provides helpful context. If you do so please indent such
text by at least two characters. This makes the message more readable and
helps to prevent the content being mis-interpreted by programs like
``patch(1)`` which other developers or the maintainers may use to process your
changes.

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
python3 -m coverage run /usr/bin/pytest -v --log-level=debug tests
python3 -m coverage report -m --include "./boom/*"
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

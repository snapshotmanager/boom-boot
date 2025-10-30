%global summary A set of libraries and tools for managing boot loader entries
%global sphinx_docs 1

Name:		boom-boot
Version:	1.6.8
Release:	1%{?dist}
Summary:	%{summary}

License:	Apache-2.0
URL:		https://github.com/snapshotmanager/boom-boot
Source0:	%{url}/archive/%{version}/%{name}-%{version}.tar.gz

BuildArch:	noarch

BuildRequires:	make
BuildRequires:	python3-setuptools
BuildRequires:	python3-devel
BuildRequires:  python3-pip
BuildRequires:  python3-wheel
BuildRequires:  python3-pytest
%if 0%{?sphinx_docs}
BuildRequires:	python3-dbus
BuildRequires:	python3-sphinx
%endif
BuildRequires: make

Requires: python3-boom = %{version}-%{release}
Requires: %{name}-conf = %{version}-%{release}
Requires: python3-dbus
%if 0%{?rhel} == 9
Requires: systemd >= 252-18
%else
Requires: systemd >= 254
%endif

Obsoletes: boom-boot-grub2 <= 1.3
# boom-grub2 was not an official name of subpackage in fedora, but was used upstream:
Obsoletes: boom-grub2 <= 1.3

%package -n python3-boom
Summary: %{summary}
%{?python_provide:%python_provide python3-boom}
Requires: %{__python3}
Recommends: (lvm2 or brtfs-progs)
Recommends: %{name}-conf = %{version}-%{release}

# There used to be a boom package in fedora, and there is boom packaged in
# copr. How to tell which one is installed? We need python3-boom and no boom
# only.
Conflicts: boom

%package conf
Summary: %{summary}

%description
Boom is a boot manager for Linux systems using boot loaders that support
the BootLoader Specification for boot entry configuration.

Boom requires a BLS compatible boot loader to function: either the
systemd-boot project, or Grub2 with the BLS patch (Red Hat Grub2 builds
include this support in both Red Hat Enterprise Linux 7 and Fedora).

%description -n python3-boom
Boom is a boot manager for Linux systems using boot loaders that support
the BootLoader Specification for boot entry configuration.

Boom requires a BLS compatible boot loader to function: either the
systemd-boot project, or Grub2 with the BLS patch (Red Hat Grub2 builds
include this support in both Red Hat Enterprise Linux 7 and Fedora).

This package provides python3 boom module.

%description conf
Boom is a boot manager for Linux systems using boot loaders that support
the BootLoader Specification for boot entry configuration.

Boom requires a BLS compatible boot loader to function: either the
systemd-boot project, or Grub2 with the BLS patch (Red Hat Grub2 builds
include this support in both Red Hat Enterprise Linux 7 and Fedora).

This package provides configuration files for boom.

%prep
%autosetup -p1 -n %{name}-%{version}

%build
%if 0%{?sphinx_docs}
make %{?_smp_mflags} -C doc html
rm doc/_build/html/.buildinfo
mv doc/_build/html doc/html
rm -r doc/_build
%endif

%if 0%{?centos} || 0%{?rhel}
%py3_build
%else
%pyproject_wheel
%endif

%install
%if 0%{?centos} || 0%{?rhel}
%py3_install
%else
%pyproject_install
%endif

# Make configuration directories
# mode 0700 - in line with /boot/grub2 directory:
install -d -m 700 ${RPM_BUILD_ROOT}/boot/boom/profiles
install -d -m 700 ${RPM_BUILD_ROOT}/boot/boom/hosts
install -d -m 700 ${RPM_BUILD_ROOT}/boot/loader/entries
install -d -m 700 ${RPM_BUILD_ROOT}/boot/boom/cache
install -m 644 examples/boom.conf ${RPM_BUILD_ROOT}/boot/boom

mkdir -p ${RPM_BUILD_ROOT}/%{_mandir}/man8
mkdir -p ${RPM_BUILD_ROOT}/%{_mandir}/man5
install -m 644 man/man8/boom.8 ${RPM_BUILD_ROOT}/%{_mandir}/man8
install -m 644 man/man5/boom.5 ${RPM_BUILD_ROOT}/%{_mandir}/man5

rm doc/Makefile
rm doc/conf.py

%check
pytest-3 --log-level=debug -v

%files
%license LICENSE
%doc README.md
%{_bindir}/boom
%doc %{_mandir}/man*/boom.*

%files -n python3-boom
%license LICENSE
%doc README.md
%{python3_sitelib}/boom/*
%if 0%{?centos} || 0%{?rhel}
%{python3_sitelib}/boom*.egg-info/
%else
%{python3_sitelib}/boom*.dist-info/
%endif
%doc doc
%doc examples
%doc tests

%files conf
%license LICENSE
%doc README.md
%dir /boot/boom
%config(noreplace) /boot/boom/boom.conf
%dir /boot/boom/profiles
%dir /boot/boom/hosts
%dir /boot/boom/cache
%dir /boot/loader/entries


%changelog
* Thu Oct 30 2025 Bryn M. Reeves <bmr@redhat.com> - 1.6.8-1
- tests: convert test_command.py from * to explicit imports
- command: avoid list mutation in _apply_no_fstab()
- osprofile: enforce absolute kernel/initramfs patterns
- config: use ConfigParser.getboolean instead of substring tests
- config: docstring nit: “read” → “write” for path param
- hostprofile: fix deletion removing all labels for the same machine_id
- hostprofile: normalize label to empty str if None passed to setter
- hostprofile: guard against None in HostProfile._generate_id()
- profiles: factor out common code from {Os,Host}Profile.__setitem__
- hostprofile: add missing docstrings for property setters
- hostprofile: drop obsolete FIXME comment
- dist: update and drop files in examples/
- command: use abspath() for boot_path normalzaiton
- mounts: add timeout and log decoded blkid output
- command: have create_config() report actual path in fail log
- hostprofile: duplicate symbol in __all__
- boom: fix docstring typo ("ath" → "path")
- doc: Mention BOOM_BOOT_PATH alongside --boot-dir in boom.8
- doc: Clarify config overwrite semantics and idempotency in boom.8
- config: raise BoomConfigError exception on parse failure
- config: make permissions atomic: chmod temp file before rename
- command: harden machine-id read: catch OSError from open too
- command: avoid duplicate logging in _cache_image()
- boom: bump required python to 3.9
- boom: fix type hints to use typing imports
- command: profile edit guard checks the wrong OS version option
- tests: remove unused local BoomConfig in setUp (confusing no-op).
- boom: drop annoying --verbose field selection
- boom.mounts: allow swap entries with create_entry(mounts=...)
- boom: wire up new debug log filttering in boom.command.setup_logging()
- boom: convert modules to new log filtering interface
- boom: replace BoomLogger Logging class with SubsystemFilter Filter class
- boom: use "boom" rather than __name__ (boom._boom) for getLogger()
- boom: add string constants for new name-based subsystem log filtering

Mon Sep 15 2025 Bryn M. Reeves <bmr@redhat.com> - 1.6.7-1
- boom: bump release to 1.6.7
- legacy: add deprecation notices to boom.legacy docstrings
- doc: note legacy bootloader deprecation status in boom.8
- boom: emit warning on legacy_enable == True or 'boom legacy <cmd>' use
- boom add boom/py.typed and add to MANIFEST.in
- doc: fix typo in boom.8 (re-use -> reuse)
- command: fix typos in boom.command
- doc: Update README.md, add CONTRIBUTING.md, move detailed guide to doc/
- osprofile: make 'options must include root=' formatting consistent
- boom: replace (OSError, IOError) with OSError
- tests: refactor test_boom_main_*` cases for better isolation
- tests: assert exit satus in CommandTests.test__create_cmd()
- boom: fix typo OsError for OSError
- legacy: handle IO errors, close tmp_fd and unlink to avoid leaks
- boom: set encoding="utf8" consistently when calling fdopen()
- config: flush f_tmp before calling fdatasync()
- osprofile: fix BoomProfile._delete_profile() docstring
- legacy: stray apostrophe in error messages
- cache: use context manager when creating the dot-file
- boom: docstring fixes for set_boot_path()
- boom: docstring mismatch for get_cache_path()
- boom: ensure errors go to stderr
- boom: fix optional_keys help text typo ("allows")
- boom: fix typo 'identiry'
- boom: call fsync() on containing directory after rename()
- boom: create_config idempotency and boot_path validation
- boom: fix overly broad excpetions and exception variable use
- tests: replace NotEqual(r, 1) with Equal(r, 0) for exit status tests
- tests: cover OsProfile.__setitem__()
- bootloader: mark BootEntry.write_entry() exception branch no cover
- tests: cover missing boom/hosts directory
- boom: mark _{clone,create,edit}_cmd() exception branches no cover
- tests: cover boom create --grub-user with profile missing grub_user optional key
- tests: cover clone_entry() with --backup
- tests: cover boom edit with non-existent root device and allow_no_dev=False
- command: improve _lv_from_device_string() validation and add tests
- tests: add test data for /dev/mapper/vg-lv case
- tests: delete duplicate test__clone_profile_cmd
- tests: delete duplicate test__delete_cmd_verbose
- tests: delete duplicate test__delete_cmd_no_selection()
- tests: delete duplicate test_edit_entry_del_opts()
- tests: fix test case name (s/no_debug_arg/bad_debug_arg/)
- tests: assert result in test__{list,show}_cache_cmd
- tests: set boot_path=tests/sandbox in tests/boom/boom.conf
- tests: add test for 'boom config create --boot-dir=...'
- tests: add test to cover --root-device=/dev/mapper/.. case
- tests: add test data for machine_id_from_filename()
- stratis: mark pool_name_to_pool_uuid() no cover
- tests: additional coverage for boom.mounts
- tests: add coverage for boom.mounts
- mounts: additional validation of swap and mount units
- tests: add coverage for boom.command._apply_no_fstab()
- tests: add coverage for boom.command._apply_btrfs_subvol_exclusive()
- tests: add coverage for main() with invalid --root-device
- boom: mark legacy integration hooks no cover
- tests: add coverage for missing/broken configuration
- boom: add tests to cover --root-lv/--root-device combinations
- boom: ensure set_boom_path() called when --boot-dir/BOOM_BOOT_PATH
- tests: add CommandTests.test_boom_main_bad_arg()
- tests: add test_boom_main_bad_debug()
- tests: add CommandTests for bad type and unknown command
- command: mark _cache_path() error path as no cover
- tests: add test__create_cmd_backup()
- tests: drop_cache() when tearing down CommandTests
- tests: add test_create_config()
- command: accept boot_path arg to boom.command.create_config()
- tests: add test for add_opts/del_opts conflict
- command: don't cover __write_legacy() body
- command: add 'no cover' to fallback get_machine_id() branches
- tests: cover more _int_if_val() cases
- tests: cover _bool_to_yes_no() helper
- command: clarify exception types in _int_if_val() docstring
- doc: fix typo "classed" -> "classes" in boom.8
- doc: fix stray '.' in CMD_HOST_LIST macro usage
- doc: fix typo "prorile" in boom.8
- doc: update man page date in boom.8
- doc: fix typo "optiona" in boom.8
- doc: add man pages and Stratis links to SEE ALSO
- doc: add EXIT STATUS, FILES, and BUGS sections to boom.8
- doc: convert URLs to .UR/.UE markup
- doc: normalize references to BLS in boom.8
- doc: fix quoted font command mistaken for macro and boom cache list typo
- doc: fix broken font commands (\fp for \fP) in boom.8
- doc: convert examples to .EX/.EE in boom.8
- doc: convert COMMANDS .HP use to .TP 6/.IP
- doc: convert OPTIONS .HP usage to .TP
- doc: fix command and argument formatting
- doc: add "Command types" and "Subcommands" subsections to boom.8
- doc: remove deprecated .HP / .PD usage
- doc: remove manual . ad l / . ad b formatting commands from boom.8
- doc: replace missuse of .P/.B for subsections with .SS Section Name
- doc: add missing .SH COMMANDS to boom.8
- doc: fix blank lines in boom.8
- boom: remove redundant BOOM_OS_OPTIONS default in OsProfile._from_data()
- command: fix return type for print_* functions
- boom: avoid duplicating no_fstab / ro / rw option changes
- bootloader: run grub2-editenv with a timeout
- osprofile: check self._profile_data in BoomProfile._dirty()
- bootloader: fix boom_entries_path() docstring
- tests: fix duplicate test name (masks 2nd instance)
- boom: simplify btrfs_subvol_* mutex checks in clone_entry(), edit_entry()
- boom: fix typo in user-facing help --rows ("columnes")
- osprofile: avoid duplicates and leading spaces when adding optional keys
- osprofile: fix error messages to reference the correct property name
- osprofile: harden _is_null_profile() for uninitialized profile list
- boom: remove redundant special-casing in _transform_key()
- boom: guard Stratis check when root_device may be None
- osprofile: mark profile dirty in BoomProfile.__setitem__()
- bootloader: be.delete_entry(): avoid TypeError if self._entry_path is unset
- bootloader: make OsIdentifier: parsing more robust
- bootloader: fix missing self._dirty() calls in optional-key setters
- osprofile: Redundant BOOM_OS_OPTIONS presence check after defaults
- osprofile: Avoid fdatasync() per-key in _write_profile()
- bootloader: handle missing version more gracefully in from_entry()
- bootloader: Split os_id comment only once in __os_id_from_comment()
- boom: Guard against writing entries with empty machine_id/version
- boom: Fix inverted env-expansion check in BootEntry.from_entry()
- File descriptor leak and encoding issue in BootEntry.write_entry()
- boom: clean up and simplify BootParams checks in edit_entry()
- boom: Honor the expand parameter in from_entry()
- osprofile: fix definition of OS_ROOT_KEYS list
- boom: make BootEntry._have_optional_key() check more strict
- boom: Type check bug: uses is instead of isinstance
- boom: Fix "use before assign” and enforce NEEDS correctly in _apply_format
- boom: fix docstring rtype mismatch ('str' vs. 'Optional[str]')
- boom: propagate missing command arguments in edit_entry()
- osprofile: add type annotations to OsProfile.write_profile()
- osprofile: add type annotations to OsProfile.from_*os_release*()
- osprofile: add type annotations to OsProfile string methods
- osprofile: add type annotations to BoomProfile._{write,delete}_profile
- osprofile: add type annotations to BoomProfile optional key methods
- osprofile: add type annotations to BoomProfile.title
- osprofile: add type annotations to BoomProfile.options
- osprofile: add type annotations to BoomProfile.root_opts_btrfs
- osprofile: add type annotations to BoomProfile.root_opts_lvm2
- osprofile: add type annotations to {kernel,initramfs}_pattern
- osprofile: add type annotations to BoomProfile.uname_pattern
- osprofile: add type annotations to BoomProfile match_* methods
- osprofile: add type annotations to BoomProfile._from_file()
- osprofile: add type annotations to BoomProfile.{keys,values,items}()
- osprofile: add type annotations to BoomProfile.__{get,set}item__()
- osprofile: add type annotations to BoomProfile string methods
- osprofile: add type annotations to BoomProfile defaults
- osprofile: add type annotations to key_from_key_name()
- osprofile: add type annotations to match_os_profile()
- osprofile: fix select_profile() formatting
- osprofile: add type annotations to write_profiles()
- osprofile: add type annotations to _profile_exists()/_is_null_profile()
- osprofile: add type annotations to module constants
- boom: fix another star import
- boom: more type fixes
- boom: create_entry() error should reflect OsProfile|HostProfile
- boom: raise error in edit_entry() if !be.bp and {add,del}_opts used
- boom: fix profile clone error message
- boom: fix incorrect exception string in edit_host()
- boom: fix machine_id fallback in edit_host()
- boom: propagate --update to clone image caching
- boom: Fix incorrect user-facing message
- boom: fix Hostprofile.optional_keys() setter NameError
- boom: fix handling of missing values for create_host()
- boom: fix create_host() arg validation
- command: add type annotations to set_debug()
- command: add type annotations to command handlers
- command: handle optional values in edit_entry()
- command: handle optional values in clone_entry()
- command: handle optional values in create_entry()
- bootloader: add type annotations to BootEntry.update_entry()
- bootloader: add type annotations to BootEntry.entry_path
- bootloader: add type annotations to BootEntry optional keys
- bootloader: add type annotations to BootEntry.architecture
- bootloader: add type annotations to BootEntry.devicetree
- bootloader: add type annotations to BootEntry.efi
- bootloader: add type annotations to BootEntry.{linux,initrd}
- bootloader: add type annotations to BootEntry.options helpers
- bootloader: add type annotations to BootEntry.version
- bootloader: add type annotations to BootEntry.machine_id
- bootloader: add type annotations to BootEntry.title
- bootloader: add type annotations to BootEntry.bp
- bootloader: add type annotations to BootEntry.expanded()
- bootloader: add type annotations too BootEntry._have_optional_key()
- bootloader: add type annotations to BootEntry.__generate_boot_id()
- bootloader: add type annotations to BootEntry._apply_format() helpers
- bootloader: add type annotations to __os_id_from_comment()
- bootloader: add type hints and rewrite BootEntry.{items,keys,values}()
- bootloader: add type annotations to BootEntry.__{get,set}item__()
- bootloader: add type annotations to BootEntry.__eq__()
- bootloader: add type annotations to BootEntry defaults
- bootloader: add type annotations to select_{params,entry}()
- bootloader: add type annotations to load_entries()
- bootloader: add type annotations to BootParams.from_entry()
- bootloader: add type annotations to BootParams properties
- bootloader: add type annotations to BootParams initialiser
- bootloader: add type annotations to BootParams string methods
- bootloader: add type annotations to BootParams defaults
- boom: add type annotations to _grub2_get_env()
- bootloader: add type annotations to _match_root_lv()
- bootloader: add type annotations to check_root_device()
- bootloader: add type annotations to module constants
- boom: remove stray debug print()s
- boom: remove more star imports
- boom: fix type for osprofile.select_profile()
- doc: set language = 'en' in doc/conf.py
- doc: apply CSS workaround for Sphinx docs sidebar overflow
- doc: add DeepWiki badge to README.md
- tests: additional coverage for 'boom list' with implicit type
- boom: special-case --help in arg pre-validation
- boom: document additional types and commands in help text
- boom: separate out "unknown type" from "unknown command"
- boom: make command type matching strict
- tests: additional coverage for boom.command.main() error paths
- boom: make "Unknown command" etc. match "unrecognised argument"
- boom: get rid of try/except handling around parser.parse_args()
- boom: include PATH in command environment when calling lvm2
- boom: add .pylintrc
- command: initial type annotations for command module
- report: make title and output_fields Optional[str]
- cache: mark find_cache_paths() selection arg as Optional[Selection]
- bootloader: mark optional BootParams() args as Optional[str]
- bootloader: accept HostProfile in BootEntry()
- command: replace wildcard imports with explicit lists
- hostprofile: initial type annotations for hostprofile module
- hostprofile: add missing uname_pattern/optional_keys setters
- hostprofile: replace wildcard imports with explicit lists
- osprofile: initial type annotations for osprofile module
- osprofile: replace wildcard imports with explicit lists
- bootloader: fix BootEntry.initrd property method ordering
- bootloader: fix missing ROOT_OPTS_STRATIS import
- bootloader: re-order comments in BootEntry._apply_format()
- bootloader: add type hint for format_key_specs table
- bootloader: rename 'get_key_attr()' -> 'get_key_value()'
- bootloader: initial type annotations for bootloader module
- boom: add global MIN_ID_WIDTH constant
- bootloader: replace wildcard imports with explicit lists
- report: initial type annotations for report module
- stratis: initial type annotations for stratis module
- stratis: replace wildcard imports with explicit lists
- config: initial type annotations for config module
- config: test config._cfg before calling config._cfg.write()
- config: drop obsolete hasattr() check for BoomConfig._cfg
- config: replace wildcard imports with explicit lists
- boom: add type hint for BoomConfig._cfg: ConfigParser
- cache: initial type annotations for cache module
- cache: replace wildcard imports with explicit lists
- boom: initial type annotations for boom
- boom: make environment helpers public
- osprofile: make btrfs rootflags=subvol{,id}= regexes more precise [WIP]
- bootlader: don't apply {add,del}_opts to BootEntry.options overrides
- boom: automatically set BootParams.lvm_root_lv from root_device
- bootloader: set stratis_pool_uuid in BootParams.__init__()
- stratis: check for path presence in is_stratis_device_path()
- Do not require wheel for building
- boom: simplify fixed/formatted option membership tests
- boom: avoid unnecessary 'else'/'elif' after 'return' pattern
- boom: clean up unused variables
- boom: always specify encoding when opening files in text mode
- command: avoid redefining 'string' in _str_indent()
- cache: avoid shadowing 'cache_path()' function with local vars
- boom: convert to python3-style super() usage
- osprofile: use None instead of empty dict as default profile_data
- boom: drop unnecessary 'elif' after 'raise'
- boom: fix unused argument warnings
- command: fix missing add_opts/del_opts propagation in edit_host()
- boom: fix inconsistent return statements
- boom: replace list comprehensions with generators
- boom: fix implicit string concatenation
- boom: stop inheriting from object
- boom: don't use .keys() when iterating dictionaries
- cache: fix missing CACHE_UNKNOWN CacheEntry state constant
- boom: fix missing errno.ENOENT import
- config: fix missing os.unlink import
- boom: remove unnecessary 'global' use
- boom: drop obsolete use of from __future__ import print_function
- boom: f-string conversion for mounts module
- boom: f-string conversion for legacy module
- boom: f-string conversion for config module
- boom: f-string conversion for stratis module
- boom: f-string conversion for cache module
- boom: f-string conversion for hostprofile module
- boom: f-string conversion for command module
- boom: f-string conversion for osprofile module
- boom: f-string conversion for bootloader module
- boom: f-string conversion for boom module
- command: fix missing update param in create_entry() docstring
- tests: use log.info() for test log messages instead of log.debug()
- tests: uncouple BadConfigTests from ConfigTests
- tests: rename BadConfigTests.test_load_boom_config_default
- dist: change boom-boot license from GPL-2.0-only to Apache-2.0
- report: Report - stop misusing class vars
- report: Row - stop misusing class vars
- report: Field - stop misusing class vars
- report: FieldType - stop misusing class vars
- report: ReportObjType - stop misusing class vars
- report: ReportOpts - stop misusing class vars
- report: FieldProperties - stop misusing class vars and add initialiser
- doc: update BLS specification URL in README.md
- dist: avoid Python packaging warnings
- dist: fix RPM changelog version string

* Mon Mar 31 2025 Bryn M. Reeves <bmr@redhat.com> - 1.6.6-1
- tests: drop remaining Python2 compat handling
- boom.config: drop Python2 compat handling for ConfigParser
- dist: update example boom.conf
- boom: use correct option names in BoomConfig.__str__()
- boom: use write_boom_config() in boom.command.create_config()
- config: add missing [cache] section to boom.config.__make_config()
- config: add missing [cache] section handling to boom.config._sync_config()
- config: treat {boom,boot}_root and {boom,boot}_path as synonyms
- dist: enable check in boom-boot.spec
- dist: replace license classifier with SPDX expressions
- boom: replace __make_map_key() function with dictionary comprehension
- dist: clean up copyright statements and convert to SPDX license headers
- dist: update GPLv2 text in COPYING
- boom: use lazy printf formatting when logging
- boom: fix report argument formatting
- tests: drop separate coverage runs and split out reporting step
- tests: switch Fedora tests to fedora:latest
- tests: bracket test cases with log messages
- tests: fix duplicate log handlers in test suite
- report: strip trailing whitespace from report output
- legacy: use 'is' instead of explicit type comparison
- boom: clean up new OsProfile if setting uname_pattern fails
- boom: add CentOS Stream to uname heuristics table
- boom: fix license headers across tree
- dist: update spec file changelog and release
- dist: drop unused systemd-rpm-macros BuildRequires
- dist: fix Source URL and autosetup invocation

* Fri Sep 27 2024 Bryn M. Reeves <bmr@redhat.com> - 1.6.5-2
- dist: drop unused systemd-rpm-macros BuildRequires
- dist: fix Source URL and autosetup invocation

* Tue Sep 17 2024 Bryn M. Reeves <bmr@redhat.com> - 1.6.5-1
- doc: add --update to boom.8
- doc: add --backup to boom.8
- boom: add --update to enable updating of backup images
- boom.cache: default to re-using cached images
- boom: fix --backup of modified images
- tests: add json to MockArgs
- doc: add --json and JSON examples to README.md
- doc: update README.md
- doc: add report options to list commands and document --json
- boom: add --json support to list commands
- tests: add JSON report output test
- report: merge comparisons in Report.{__get_field,__key_match}()
- report: replace open coded comparison with max() in  __recalculate_fields()
- report: use .items() to iterate over SHAs in  __recalculate_sha_width()
- snapm.report: only import dumps from json
- report: fix setting of ReportOpts.json in ReportOpts()
- report: allow sort keys to use optional prefix
- report: handle $PREFIX_all when parsing field list
- report: add support for JSON output
- report: add title argument to Report()
- report: remove unused 'private' Report argument
- report: fix field prefix handling and drop hardcoded prefix
- report: fix comment typos
- report: add REP_SIZE field type for human readable size strings
- tests: fix up tests for boom.report renames
- report: sync boom.report with snapm and drop Boom prefix
- dist: make setup.cfg package name consistent with pyproject.toml
- dist: extend CentOS py3_build/py3_install conditionals to RHEL
- dist: Require correct systemd version on RHEL9

* Wed Jun 19 2024 Bryn M. Reeves <bmr@redhat.com> - 1.6.4-1
- dist: add epel-9, centos-stream-9 and centos-stream-10 to Packit
- doc: add 'boom config create' command to boom.8
- tests: fix broken test for config file section name
- boom: advise user to run 'boom config create' if no config found
- boom: fix configuration file section name in BoomConfig.__str__()
- boom: add 'boom config create' command
- boom: add missing comment to _show_legacy_cmd()
- dist: add license_file to setup.cfg
- dist: update repository URL in boom-boot.spec
- dist: add install dependency on dbus-python >= 1.2.16

* Tue Jun 18 2024 Bryn M. Reeves <bmr@redhat.com> - 1.6.3-1
- boom: ensure root is mounted rw when --no-fstab is used
- dist: drop snapshot-remount-fs generator
- tests: check for device node presence in get_root_lv()

* Thu May 30 2024 Bryn M. Reeves <bmr@redhat.com> - 1.6.2-1
- dist: require python3-dbus
- dist: add dependency on systemd >= v254
- Update snapm.spec source to use URL with name and version macros
- boom: Change interpreter to /usr/bin/python3
- dist: Use _smp_mflags make flags in snapm.spec docs build
- dist: Fix use of python3_sitelib wildcard in snapm.spec
- dist: Fix SPDX license identifier in setup.cfg

* Tue May 14 2024 Bryn M. Reeves <bmr@redhat.com> - 1.6.1-1
- boom.bootloader: repair boom entries with mismatched boot_id
- boom.bootloader: make BOOM_ENTRIES_PATTERN more strict
- Revert "boom.cache: ignore foreign boot entries when reference counting"
- command: fix docstring typo ('or``OsError``')
- doc: update Grub2 docs to add removal of submenu support in 1.4
- snapshot-remount-fs: use correct systemd unit path
- snapshot-remount-fs: limit maxsplit when splitting kernel arguments
- dist: Use systemd-rpm-macros for the path to the generator directory

* Thu Nov 23 2023 Bryn M. Reeves <bmr@redhat.com> - 1.6.0-2
- Update spec file

* Mon Nov 20 2023 Bryn M. Reeves <bmr@redhat.com> - 1.6.0
- Bump release

* Fri Nov 17 2023 Bryn M. Reeves <bmr@redhat.com> - 1.5.1-4.20231117175234813485.bmr.add.snapshot.remount.fs.29.ga48ccf9
- dist: add build notifications to .packit.yaml (Bryn M. Reeves)
- dist: make packit copr_build job run on pull_request (Bryn M. Reeves)
- dist: add jobs to .packit.yaml (Bryn M. Reeves)
- dist: add .packit.yaml (Bryn M. Reeves)
- dist: update spec file for packit builds (Bryn M. Reeves)
- tests: fix filenames in unit test comments (Bryn M. Reeves)
- tests: add missing test_mounts.py to git (Bryn M. Reeves)
- dist: update boom-boot.spec from Fedora dist-git spec file (Bryn M. Reeves)
- dist: rename boom.spec -> boom-boot.spec to match Fedora packaging (Bryn M. Reeves)
- doc: Add readthedocs configuration file (Bryn M. Reeves)
- boom: concatenate strings in argument definitions (Bryn M. Reeves)
- tests: skip test__get_machine_id (Bryn M. Reeves)
- boom: use correct machine_id path in error string (Bryn M. Reeves)
- docs: document --no-fstab, --mount, and --swap in boom.8 (Bryn M. Reeves)
- boom: support command line swap unit syntax (Bryn M. Reeves)
- boom: add missing param docstring to clone_entry() (Bryn M. Reeves)
- boom: support command line mount unit syntax (Bryn M. Reeves)
- Add --no-fstab command line argument (Bryn M. Reeves)
- Ignore pycodestyle E501,E203,W503 (Bryn M. Reeves)
- Convert GitHub workflow to "pip install" (Bryn M. Reeves)
- Use black for formatting (Bryn M. Reeves)
- boom: fix unclosed file warning for /proc/cmdline (Bryn M. Reeves)
- tests: add coverage to CI test runs (Bryn M. Reeves)
- Update CI environment to Fedora 38 (Bryn M. Reeves)
- tests: switch from nose to pytest (Bryn M. Reeves)
- Rename tests to comply with unittest expectations (Bryn M. Reeves)
- Fix system vs. project import ordering (Bryn M. Reeves)
- Fix typos across tree (Bryn M. Reeves)
- Switch setuptools config to setup.cfg (Bryn M. Reeves)

* Thu Nov 16 2023 Bryn M. Reeves <bmr@redhat.com> - 1.5.1-4.20231116180940293550.main.24.g1b2fd45
- Update spec file for packit builds
- tests: fix filenames in unit test comments (Bryn M. Reeves)
- tests: add missing test_mounts.py to git (Bryn M. Reeves)
- dist: update boom-boot.spec from Fedora dist-git spec file (Bryn M. Reeves)
- dist: rename boom.spec -> boom-boot.spec to match Fedora packaging (Bryn M. Reeves)
- doc: Add readthedocs configuration file (Bryn M. Reeves)
- boom: concatenate strings in argument definitions (Bryn M. Reeves)
- tests: skip test__get_machine_id (Bryn M. Reeves)
- boom: use correct machine_id path in error string (Bryn M. Reeves)
- docs: document --no-fstab, --mount, and --swap in boom.8 (Bryn M. Reeves)
- boom: support command line swap unit syntax (Bryn M. Reeves)
- boom: add missing param docstring to clone_entry() (Bryn M. Reeves)
- boom: support command line mount unit syntax (Bryn M. Reeves)
- Add --no-fstab command line argument (Bryn M. Reeves)
- Ignore pycodestyle E501,E203,W503 (Bryn M. Reeves)
- Convert GitHub workflow to "pip install" (Bryn M. Reeves)
- Use black for formatting (Bryn M. Reeves)
- boom: fix unclosed file warning for /proc/cmdline (Bryn M. Reeves)
- tests: add coverage to CI test runs (Bryn M. Reeves)
- Update CI environment to Fedora 38 (Bryn M. Reeves)
- tests: switch from nose to pytest (Bryn M. Reeves)
- Rename tests to comply with unittest expectations (Bryn M. Reeves)
- Fix system vs. project import ordering (Bryn M. Reeves)
- Fix typos across tree (Bryn M. Reeves)
- Switch setuptools config to setup.cfg (Bryn M. Reeves)

* Thu Nov 16 2023 Bryn M. Reeves <bmr@redhat.com> - 1.5.1-4.20231116180027713828.main.20.gad7e78a
- Update spec file for packit builds
- doc: Add readthedocs configuration file (Bryn M. Reeves)
- boom: concatenate strings in argument definitions (Bryn M. Reeves)
- tests: skip test__get_machine_id (Bryn M. Reeves)
- boom: use correct machine_id path in error string (Bryn M. Reeves)
- docs: document --no-fstab, --mount, and --swap in boom.8 (Bryn M. Reeves)
- boom: support command line swap unit syntax (Bryn M. Reeves)
- boom: add missing param docstring to clone_entry() (Bryn M. Reeves)
- boom: support command line mount unit syntax (Bryn M. Reeves)
- Add --no-fstab command line argument (Bryn M. Reeves)
- Ignore pycodestyle E501,E203,W503 (Bryn M. Reeves)
- Convert GitHub workflow to "pip install" (Bryn M. Reeves)
- Use black for formatting (Bryn M. Reeves)
- boom: fix unclosed file warning for /proc/cmdline (Bryn M. Reeves)
- tests: add coverage to CI test runs (Bryn M. Reeves)
- Update CI environment to Fedora 38 (Bryn M. Reeves)
- tests: switch from nose to pytest (Bryn M. Reeves)
- Rename tests to comply with unittest expectations (Bryn M. Reeves)
- Fix system vs. project import ordering (Bryn M. Reeves)
- Fix typos across tree (Bryn M. Reeves)
- Switch setuptools config to setup.cfg (Bryn M. Reeves)

* Thu May 4 2023 Bryn M. Reeves <bmr@redhat.com> = 1.5.1
- Bump release

* Thu May 19 2022 Bryn M. Reeves <bmr@redhat.com> = 1.4
- Fix boom.spec ChangeLog date
- Drop Grub2 integration scripts and defaults file
- Simplify bootloader integration checks
- Add stratis_tests.py
- Fix workflow name in CI status badge URL
- Update build status badge in README.md
- Ensure have_lvm() returns False if lvs does not exist
- Rewrite .travis.yml CI checks as GHA
- Fix parsing of btrfs subvolumes
- Fix uname heuristic for Fedora >=35
- Generate Stratis syntax in BootEntry.root_opts()
- Add Stratis format keys to make_format_regexes()
- Add FMT_STRATIS_POOL_UUID to BootEntry string formatting table
- Add ROOT_OPTS_STRATIS template
- Add stratis_pool_uuid property to BootParams
- Add BootParams.has_stratis()
- Add is_stratis_device_path()
- Update travis configuration for DBus
- Add stratis sub-module
- Add debug mask for boom.stratis
- Add FMT_STRATIS_ROOT_OPTS
- Add FMT_STRATIS_POOL_UUID format specifier
- Add constants for btrfs path and ID volume syntax
- Add constants for btrfs path and ID volume syntax
- Fix missing line break in HostProfile.__str__()
- Fix test_match_host_profile boot_id
- Remove BOOM_ENTRY_OPTIONS hack from BootEntry.__from_data()
- Sort legacy boot entries by (version, title)
- Fix typo when initialising BootEntry with explicit BootParams
- Change references to "master" locations to "main" locations
- Rename toctree document to "main_doc"
- Remove references to 'master' branch from README.md
- Fix optional BLS key to command line argument decoding
- Fix invalid date string in boom.spec
- Fix docstring typo ('or``OsError``')
- Add new submodules to README.md
- Fix docstring typo ('objecct')

* Thu Jan 28 2021 Bryn M. Reeves <bmr@redhat.com> = 1.3
- Check for duplicates consistently in the clone and edit commands
- Apply correct command line precedence to --add-opts and --del-opts
- Correctly merge multiple --add/del-opts when editing or cloning
- Correctly propagate --add/del-opts in boom edit commands
- Enhanced logging of --add/del-opts merge logic
- The default Python interpreter is now /usr/bin/python
- Fixed re-ordering of options modifications when read from disk
- Do not set BootParams attributes for anonymous option words
- Make lvm_root_lv validation checks more strict
- Improve BootParams.from_entry() parameter recovery debug logging
- Include sample OsProfile for Fedora 32
- Re-set sandbox state in test suite to ensure run-to-run consistency
- Improve compatibility with Red Hat BLS implementation
- Allow non-boom managed entries to be listed and displayed
- Handle quirks in Red Hat's use of the BLS machine_id key
- Allow grub2 bootloader variables to be expanded when cloning entries
- Simplify clone_entry logic and make consistent with edit_entry
- Ensure stable ordering of legacy boot entry configuration

* Wed May 13 2020 Bryn M. Reeves <bmr@redhat.com> = 1.1
- Bump release

* Tue May 12 2020 Bryn M. Reeves <bmr@redhat.com> = 1.1-0.1.beta
- Bump release

* Mon May 11 2020 Bryn M. Reeves <bmr@redhat.com> - 1.0-2
- Include boom/cache directory in package

* Wed Nov 27 2019 Bryn M. Reeves <bmr@redhat.com> - 1.0-1
- Bump release for boom-1.0

* Thu Oct 03 2019 Miro Hrončok <mhroncok@redhat.com> - 1.0-0.5.20190329git6ff3e08
- Rebuilt for Python 3.8.0rc1 (#1748018)

* Mon Aug 19 2019 Miro Hrončok <mhroncok@redhat.com> - 1.0-0.4.20190329git6ff3e08
- Rebuilt for Python 3.8

* Wed Jul 24 2019 Fedora Release Engineering <releng@fedoraproject.org> - 1.0-0.3.20190329git6ff3e08
- Rebuilt for https://fedoraproject.org/wiki/Fedora_31_Mass_Rebuild

* Thu May 09 2019 Marian Csontos <mcsontos@redhat.com> 1.0-0.2.20190329git6ff3e08
- Fix packaging issues.

* Thu May 09 2019 Marian Csontos <mcsontos@redhat.com> 1.0-0.1.20190329git6ff3e08
- Pre-release of new version.

* Thu Jan 31 2019 Fedora Release Engineering <releng@fedoraproject.org> - 0.9-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_30_Mass_Rebuild

* Tue Jul 17 2018 Marian Csontos <mcsontos@redhat.com> 0.9-4
- Change dependencies.

* Mon Jul 16 2018 Marian Csontos <mcsontos@redhat.com> 0.9-3
- Split executable, python module and configuration.

* Wed Jun 27 2018 Marian Csontos <mcsontos@redhat.com> 0.9-2
- Spin off grub2 into subpackage

* Wed Jun 27 2018 Marian Csontos <mcsontos@redhat.com> 0.9-1
- Update to new upstream 0.9.
- Fix boot_id caching.

* Fri Jun 08 2018 Marian Csontos <mcsontos@redhat.com> 0.8.5-6.2
- Remove example files from /boot/boom/profiles.

* Fri May 11 2018 Marian Csontos <mcsontos@redhat.com> 0.8.5-6.1
- Files in /boot are treated as configuration files.

* Thu Apr 26 2018 Marian Csontos <mcsontos@redhat.com> 0.8.5-6
- Package upstream version 0.8-5.6


%global summary A set of libraries and tools for managing boot loader entries
%global sphinx_docs 1

Name:		boom-boot
Version:	1.6.6
Release:	1%{?dist}
Summary:	%{summary}

License:	GPL-2.0-only
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
%license COPYING
%doc README.md
%{_bindir}/boom
%doc %{_mandir}/man*/boom.*

%files -n python3-boom
%license COPYING
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
%license COPYING
%doc README.md
%dir /boot/boom
%config(noreplace) /boot/boom/boom.conf
%dir /boot/boom/profiles
%dir /boot/boom/hosts
%dir /boot/boom/cache
%dir /boot/loader/entries


%changelog
* Mon Mar 31 2025 Bryn M. Reeves <bmr@redhat.com> - 1.6.5-1
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


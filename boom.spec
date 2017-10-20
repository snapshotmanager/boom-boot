%{!?python_sitelib: %define python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}
%global summary A set of libraries and tools for managing boot loader entries
Name: boom	
Version: 0.1
Release: 1%{?dist}
Summary: %{summary}

Group: Applications/System
License: GPLv2
URL: https://github.com/bmr-cymru/boom	
Source0: boom-0.1.tar.gz

BuildRequires: python2-devel
BuildRequires: python3-devel
BuildRequires: python2-sphinx
BuildRequires: python3-sphinx

BuildArch: noarch

%description
Boom is a boot manager for Linux systems using boot loaders that support
the BootLoader Specification for boot entry configuration.

Boom requires a BLS compatible boot loader to function: either the
systemd-boot project, or Grub2 with the bls patch (Red Hat Grub2 builds
include this support in both Red Hat Enterprise Linux 7 and Fedora).

%package -n python2-boom
Summary: %{summary}
%{?python_provide:%python_provide python2-boom}

%description -n python2-boom
Boom is a boot manager for Linux systems using boot loaders that support
the BootLoader Specification for boot entry configuration.

Boom requires a BLS compatible boot loader to function: either the
systemd-boot project, or Grub2 with the bls patch (Red Hat Grub2 builds
include this support in both Red Hat Enterprise Linux 7 and Fedora).

This package provides the python2 version of boom.


%package -n python3-boom
Summary: %{summary}
%{?python_provide:%python_provide python3-boom}

%description -n python3-boom
Boom is a boot manager for Linux systems using boot loaders that support
the BootLoader Specification for boot entry configuration.

Boom requires a BLS compatible boot loader to function: either the
systemd-boot project, or Grub2 with the bls patch (Red Hat Grub2 builds
include this support in both Red Hat Enterprise Linux 7 and Fedora).

This package provides the python3 version of boom.


%prep
%autosetup -n boom-%{version}

%build
%py2_build
%py3_build

%install
%py2_install
%py3_install

make -C ${RPM_BUILD_DIR}/%{name}-%{version}/doc html BUILDDIR=../doc

# Install Grub2 integration scripts
mkdir -p ${RPM_BUILD_ROOT}/etc/grub.d
mkdir -p ${RPM_BUILD_ROOT}/etc/default
install -m 755 ${RPM_BUILD_DIR}/%{name}-%{version}/etc/grub.d/42_boom ${RPM_BUILD_ROOT}/etc/grub.d
install -m 644 ${RPM_BUILD_DIR}/%{name}-%{version}/etc/default/boom ${RPM_BUILD_ROOT}/etc/default

%check
%{__python2} setup.py test
%{__python3} setup.py test

%files -n python2-boom
%license COPYING
%doc README.md
%doc doc/html/
%doc examples/*
%{python2_sitelib}/*
%{_bindir}/boom
/etc/grub.d/42_boom
/etc/default/boom

%files -n python3-boom
%license COPYING
%doc README.md
%doc doc/html/
%doc examples/*
%{python3_sitelib}/*
/etc/grub.d/42_boom
/etc/default/boom

%changelog
* Thu Oct 19 2017 Bryn M. Reeves <bmr@redhat.com> = 0.1-1
- Initial RPM spec

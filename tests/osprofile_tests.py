# Copyright (C) 2017 Red Hat, Inc., Bryn M. Reeves <bmr@redhat.com>
#
# osprofile_tests.py - Boom OS profile tests.
#
# This file is part of the boom project.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions
# of the GNU General Public License v.2.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
import unittest
import logging
from sys import stdout

log = logging.getLogger()
log.level = logging.DEBUG
log.addHandler(logging.FileHandler("test.log"))

from os import listdir

import boom
BOOM_ROOT_TEST = "./tests/boom"
# Override default BOOM_ROOT.
boom.BOOM_ROOT = BOOM_ROOT_TEST
from boom.osprofile import *


class OsProfileTests(unittest.TestCase):
    # Module tests
    def test_import(self):
        import boom.osprofile

    # Profile store tests

    def test_load_profiles(self):
        # Test that loading the test profiles succeeds.
        boom.osprofile.load_profiles()

        # Add profile content tests

    # OsProfile tests

    def test_OsProfile__str__(self):
        osp = OsProfile(name="Distribution", short_name="distro",
                        version="1 (Workstation)", version_id="1")

        xstr = ('OS ID: "d279248249d12dd3d115e77e81afac1cb6a00ebd",\n'
                'Name: "Distribution", Short name: "distro",\n'
                'Version: "1 (Workstation)", Version ID: "1"')

        self.assertEqual(str(osp), xstr)

    def test_OsProfile__repr__(self):
        osp = OsProfile(name="Distribution", short_name="distro",
                        version="1 (Workstation)", version_id="1")

        xrepr = ('OsProfile(profile_data={'
                 'BOOM_OS_ID:"d279248249d12dd3d115e77e81afac1cb6a00ebd", '
                 'BOOM_OS_NAME:"Distribution", BOOM_OS_SHORT_NAME:"distro", '
                 'BOOM_OS_VERSION:"1 (Workstation)", BOOM_OS_VERSION_ID:"1"})')

        self.assertEqual(repr(osp), xrepr)

    def test_OsProfile(self):
        # Test OsProfile init from kwargs
        with self.assertRaises(ValueError) as cm:
            osp = OsProfile(name="Fedora", short_name="fedora",
                            version="24 (Workstation Edition)")
        with self.assertRaises(ValueError) as cm:
            osp = OsProfile(name="Fedora", short_name="fedora",
                            version_id="24")
        with self.assertRaises(ValueError) as cm:
            osp = OsProfile(name="Fedora", version="24 (Workstation Edition)",
                            version_id="24")

        osp = OsProfile(name="Fedora", short_name="fedora",
                        version="24 (Workstation Edition)", version_id="24")

        self.assertTrue(osp)

        # os_id for fedora24
        self.assertEqual(osp.os_id, "9cb53ddda889d6285fd9ab985a4c47025884999f")

    def test_OsProfile_from_profile_data(self):
        # Pull in all the BOOM_OS_* constants to the local namespace.
        from boom.osprofile import (
            BOOM_OS_ID, BOOM_OS_NAME, BOOM_OS_SHORT_NAME,
            BOOM_OS_VERSION, BOOM_OS_VERSION_ID,
            BOOM_OS_UNAME_PATTERN, BOOM_OS_KERNEL_PATTERN,
            BOOM_OS_INITRAMFS_PATTERN, BOOM_OS_ROOT_OPTS_LVM2,
            BOOM_OS_ROOT_OPTS_BTRFS, BOOM_OS_OPTIONS
        )
        profile_data = {
            BOOM_OS_ID: "3fc389bba581e5b20c6a46c7fc31b04be465e973",
            BOOM_OS_NAME: "Red Hat Enterprise Linux Server",
            BOOM_OS_SHORT_NAME: "rhel",
            BOOM_OS_VERSION: "7.2 (Maipo)",
            BOOM_OS_VERSION_ID: "7.2",
            BOOM_OS_UNAME_PATTERN: "el7",
            BOOM_OS_KERNEL_PATTERN: "vmlinuz-%{version}",
            BOOM_OS_INITRAMFS_PATTERN: "initramfs-%{version}.img",
            BOOM_OS_ROOT_OPTS_LVM2: "rd.lvm.lv=%{lvm_root_lv}",
            BOOM_OS_ROOT_OPTS_BTRFS: "rootflags=%{btrfs_subvolume}",
            BOOM_OS_OPTIONS: "root=%{root_device} %{root_opts} rhgb quiet"
        }

        osp = OsProfile(profile_data=profile_data)
        self.assertTrue(osp)

        # Remove the root options keys.
        profile_data.pop(BOOM_OS_ROOT_OPTS_LVM2, None)
        profile_data.pop(BOOM_OS_ROOT_OPTS_BTRFS, None)
        with self.assertRaises(ValueError) as cm:
            osp = OsProfile(profile_data=profile_data)

        # Remove the name key.
        profile_data.pop(BOOM_OS_NAME, None)
        with self.assertRaises(ValueError) as cm:
            osp = OsProfile(profile_data=profile_data)

    def test_OsProfile_properties(self):
        osp = OsProfile(name="Fedora", short_name="fedora",
                        version="24 (Workstation Edition)", version_id="24")
        osp.kernel_pattern = "vmlinuz-%{version}"
        osp.initramfs_pattern = "initramfs-%{version}.img"
        osp.root_opts_lvm2 = "rd.lvm.lv=%{lvm_root_lv}"
        osp.root_opts_btrfs = "rootflags=%{btrfs_subvolume}"
        osp.options = "root=%{root_device} %{root_opts} rhgb quiet"
        self.assertEqual(osp.name, "Fedora")
        self.assertEqual(osp.short_name, "fedora")
        self.assertEqual(osp.version, "24 (Workstation Edition)")
        self.assertEqual(osp.version_id, "24")
        self.assertEqual(osp.kernel_pattern, "vmlinuz-%{version}")
        self.assertEqual(osp.initramfs_pattern,
                         "initramfs-%{version}.img")
        self.assertEqual(osp.root_opts_lvm2, "rd.lvm.lv=%{lvm_root_lv}")
        self.assertEqual(osp.root_opts_btrfs,
                         "rootflags=%{btrfs_subvolume}")
        self.assertEqual(osp.options,
                         "root=%{root_device} %{root_opts} rhgb quiet")

    def test_OsProfile_no_lvm(self):
        osp = OsProfile(name="NoLVM", short_name="nolvm",
                        version="1 (Server)", version_id="1")
        osp.kernel_pattern = "vmlinux-%{version}"
        osp.initramfs_pattern = "initramfs-%{version}.img"
        osp.root_opts_btrfs = "rootflags=%{btrfs_subvolume}"

        self.assertEqual(osp.root_opts_lvm2, None)

    def test_OsProfile_no_btrfs(self):
        osp = OsProfile(name="NoBTRFS", short_name="nobtrfs",
                        version="1 (Server)", version_id="1")
        osp.kernel_pattern = "/"
        osp.kernel_pattern = "vmlinux-%{version}"
        osp.initramfs_pattern = "initramfs-%{version}.img"
        osp.root_opts_lvm2 = "rd.lvm.lv=%{lvm_root_lv}"

        self.assertEqual(osp.root_opts_btrfs, None)

    def test_OsProfile_from_os_release(self):
        osp = OsProfile.from_os_release([
            '# Fedora 24 Workstation Edition\n',
            'NAME=Fedora\n', 'VERSION="24 (Workstation Edition)\n',
            'ID=fedora\n', 'VERSION_ID=24\n',
            'PRETTY_NAME="Fedora 24 (Workstation Edition)"\n',
            'ANSI_COLOR="0;34"\n',
            'CPE_NAME="cpe:/o:fedoraproject:fedora:24"\n',
            'HOME_URL="https://fedoraproject.org/"\n',
            'BUG_REPORT_URL="https://bugzilla.redhat.com/"\n',
            'VARIANT="Workstation Edition"\n',
            'VARIANT_ID=workstation\n'
        ])

    def test_OsProfile_from_file(self):
        osp = OsProfile.from_os_release_file("/etc/os-release")
        self.assertTrue(osp)

    def test_OsProfile_from_host(self):
        osp = OsProfile.from_host_os_release()
        self.assertTrue(osp)

    def test_OsProfile_write(self):
        from os.path import exists, join
        osp = OsProfile(name="Fedora", short_name="fedora",
                        version="24 (Workstation Edition)", version_id="24")
        osp.uname_pattern = "fc24"
        osp.kernel_pattern = "vmlinuz-%{version}"
        osp.initramfs_pattern = "initramfs-%{version}.img"
        osp.root_opts_lvm2 = "rd.lvm.lv=%{lvm_root_lv}"
        osp.root_opts_btrfs = "rootflags=%{btrfs_subvolume}"
        osp.options = "root=%{root_device} ro %{root_opts} rhgb quiet"
        osp.write_profile()
        profile_path = join(boom.osprofile.BOOM_PROFILES_PATH,
                            "%s-fedora24.profile" % osp.os_id)
        self.assertTrue(exists(profile_path))

    def test_osprofile_write_profiles(self):
        boom.osprofile.load_profiles()
        boom.osprofile.write_profiles()

    def test_osprofile_find_profiles_by_id(self):
        rhel72_os_id = "9736c347ccb724368be04e51bb25687a361e535c"
        osp_list = find_profiles(os_id=rhel72_os_id)
        self.assertEqual(len(osp_list), 1)
        self.assertEqual(osp_list[0].os_id, rhel72_os_id)

    def test_osprofile_find_profiles_by_name(self):
        os_name = "Fedora"
        os_short_name = "fedora"
        osp_list = find_profiles(name=os_name)
        nr_profiles = 0
        for f in listdir(boom.osprofile.BOOM_PROFILES_PATH):
            if os_short_name in f:
                nr_profiles += 1
        self.assertTrue(len(osp_list), nr_profiles)

# vim: set et ts=4 sw=4 :

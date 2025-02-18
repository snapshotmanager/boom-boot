# Copyright Red Hat
#
# tests/osprofile_tests.py - Boom OS profile tests.
#
# This file is part of the boom project.
#
# SPDX-License-Identifier: GPL-2.0-only
import unittest
import logging
from sys import stdout
from os import listdir, makedirs
from os.path import abspath, join
import shutil

log = logging.getLogger()

from boom.osprofile import *
from boom import *

BOOT_ROOT_TEST = abspath("./tests")
set_boot_path(BOOT_ROOT_TEST)

from tests import *

class OsProfileTests(unittest.TestCase):
    """Test OsProfile basic methods
    """

    # Main boom configuration path for sandbox
    boom_path = join(BOOT_ROOT_TEST, "boom")

    def setUp(self):
        log.debug("Preparing %s", self._testMethodName)

        reset_sandbox()

        # Sandbox paths
        boot_sandbox = join(SANDBOX_PATH, "boot")
        boom_sandbox = join(SANDBOX_PATH, "boot/boom")

        makedirs(boot_sandbox)
        shutil.copytree(self.boom_path, boom_sandbox)

        set_boot_path(boot_sandbox)

        drop_profiles()

    def tearDown(self):
        log.debug("Tearing down %s", self._testMethodName)

        drop_profiles()
        rm_sandbox()
        reset_boom_paths()

    # Module tests
    def test_import(self):
        import boom.osprofile

    # Profile store tests

    def test_load_profiles(self):
        # Test that loading the test profiles succeeds.
        load_profiles()

        # Add profile content tests

    # OsProfile tests

    def test_OsProfile__str__(self):
        osp = OsProfile(name="Distribution", short_name="distro",
                        version="1 (Workstation)", version_id="1")

        xstr = ('OS ID: "d279248249d12dd3d115e77e81afac1cb6a00ebd",\n'
                'Name: "Distribution", Short name: "distro",\n'
                'Version: "1 (Workstation)", Version ID: "1",\n'
                'Kernel pattern: "/vmlinuz-%{version}", '
                'Initramfs pattern: "/initramfs-%{version}.img",\n'
                'Root options (LVM2): "rd.lvm.lv=%{lvm_root_lv}",\n'
                'Root options (BTRFS): "rootflags=%{btrfs_subvolume}",\n'
                'Options: "root=%{root_device} ro %{root_opts}",\n'
                'Title: "%{os_name} %{os_version_id} (%{version})",\n'
                'UTS release pattern: ""')

        self.assertEqual(str(osp), xstr)
        osp.delete_profile()

    def test_OsProfile__repr__(self):
        osp = OsProfile(name="Distribution", short_name="distro",
                        version="1 (Workstation)", version_id="1")

        xrepr = ('OsProfile(profile_data={'
                 'BOOM_OS_ID:"d279248249d12dd3d115e77e81afac1cb6a00ebd", '
                 'BOOM_OS_NAME:"Distribution", BOOM_OS_SHORT_NAME:"distro", '
                 'BOOM_OS_VERSION:"1 (Workstation)", BOOM_OS_VERSION_ID:"1", '
                 'BOOM_OS_KERNEL_PATTERN:"/vmlinuz-%{version}", '
                 'BOOM_OS_INITRAMFS_PATTERN:"/initramfs-%{version}.img", '
                 'BOOM_OS_ROOT_OPTS_LVM2:"rd.lvm.lv=%{lvm_root_lv}", '
                 'BOOM_OS_ROOT_OPTS_BTRFS:"rootflags=%{btrfs_subvolume}", '
                 'BOOM_OS_OPTIONS:"root=%{root_device} ro %{root_opts}", '
                 'BOOM_OS_TITLE:"%{os_name} %{os_version_id} (%{version})", '
                 'BOOM_OS_UNAME_PATTERN:""})')

        self.assertEqual(repr(osp), xrepr)
        osp.delete_profile()

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

    def test_OsProfile__profile_exists(self):
        import boom
        osp = OsProfile(name="Fedora", short_name="fedora",
                        version="24 (Workstation Edition)", version_id="24")

        self.assertTrue(osp)

        # os_id for fedora24
        self.assertEqual(osp.os_id, "9cb53ddda889d6285fd9ab985a4c47025884999f")
        self.assertTrue(boom.osprofile._profile_exists(osp.os_id))

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
            BOOM_OS_KERNEL_PATTERN: "/vmlinuz-%{version}",
            BOOM_OS_INITRAMFS_PATTERN: "/initramfs-%{version}.img",
            BOOM_OS_ROOT_OPTS_LVM2: "rd.lvm.lv=%{lvm_root_lv} rh",
            BOOM_OS_ROOT_OPTS_BTRFS: "rootflags=%{btrfs_subvolume} rh",
            BOOM_OS_OPTIONS: "root=%{root_device} %{root_opts} rhgb quiet"
        }

        osp = OsProfile(profile_data=profile_data)
        self.assertTrue(osp)

        # Cleanup
        osp.delete_profile()

        # Remove the root options keys.
        profile_data.pop(BOOM_OS_ROOT_OPTS_LVM2, None)
        profile_data.pop(BOOM_OS_ROOT_OPTS_BTRFS, None)
        osp = OsProfile(profile_data=profile_data)

        # Assert that defaults are restored
        self.assertEqual(osp.root_opts_lvm2, "rd.lvm.lv=%{lvm_root_lv}")
        self.assertEqual(osp.root_opts_btrfs, "rootflags=%{btrfs_subvolume}")

        # Cleanup
        osp.delete_profile()

        # Remove the name key.
        profile_data.pop(BOOM_OS_NAME, None)
        with self.assertRaises(ValueError) as cm:
            osp = OsProfile(profile_data=profile_data)

    def test_OsProfile_properties(self):
        osp = OsProfile(name="Fedora Core", short_name="fedora",
                        version="1 (Workstation Edition)", version_id="1")
        osp.kernel_pattern = "/vmlinuz-%{version}"
        osp.initramfs_pattern = "/initramfs-%{version}.img"
        osp.root_opts_lvm2 = "rd.lvm.lv=%{lvm_root_lv}"
        osp.root_opts_btrfs = "rootflags=%{btrfs_subvolume}"
        osp.options = "root=%{root_device} %{root_opts} rhgb quiet"
        self.assertEqual(osp.os_name, "Fedora Core")
        self.assertEqual(osp.os_short_name, "fedora")
        self.assertEqual(osp.os_version, "1 (Workstation Edition)")
        self.assertEqual(osp.os_version_id, "1")
        self.assertEqual(osp.kernel_pattern, "/vmlinuz-%{version}")
        self.assertEqual(osp.initramfs_pattern,
                         "/initramfs-%{version}.img")
        self.assertEqual(osp.root_opts_lvm2, "rd.lvm.lv=%{lvm_root_lv}")
        self.assertEqual(osp.root_opts_btrfs,
                         "rootflags=%{btrfs_subvolume}")
        self.assertEqual(osp.options,
                         "root=%{root_device} %{root_opts} rhgb quiet")
        osp.delete_profile()

    def test_OsProfile_no_lvm(self):
        osp = OsProfile(name="NoLVM", short_name="nolvm",
                        version="1 (Server)", version_id="1")
        osp.kernel_pattern = "/vmlinux-%{version}"
        osp.initramfs_pattern = "/initramfs-%{version}.img"
        osp.root_opts_btrfs = "rootflags=%{btrfs_subvolume}"

        self.assertEqual(osp.root_opts_lvm2, "rd.lvm.lv=%{lvm_root_lv}")

    def test_OsProfile_no_btrfs(self):
        osp = OsProfile(name="NoBTRFS", short_name="nobtrfs",
                        version="1 (Server)", version_id="1")
        osp.kernel_pattern = "/"
        osp.kernel_pattern = "/vmlinux-%{version}"
        osp.initramfs_pattern = "/initramfs-%{version}.img"
        osp.root_opts_lvm2 = "rd.lvm.lv=%{lvm_root_lv}"

        self.assertEqual(osp.root_opts_btrfs, "rootflags=%{btrfs_subvolume}")

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
        osp = OsProfile(name="Fedora Core", short_name="fedora",
                        version="1 (Workstation Edition)", version_id="1")
        osp.uname_pattern = "fc1"
        osp.kernel_pattern = "/vmlinuz-%{version}"
        osp.initramfs_pattern = "/initramfs-%{version}.img"
        osp.root_opts_lvm2 = "rd.lvm.lv=%{lvm_root_lv}"
        osp.root_opts_btrfs = "rootflags=%{btrfs_subvolume}"
        osp.options = "root=%{root_device} ro %{root_opts} rhgb quiet"
        osp.write_profile()
        profile_path = join(boom_profiles_path(),
                            "%s-fedora1.profile" % osp.os_id)
        self.assertTrue(exists(profile_path))

    def test_OsProfile_set_optional_keys(self):
        osp = OsProfile(name="Fedora Core", short_name="fedora",
                        version="1 (Workstation Edition)", version_id="1")
        osp.uname_pattern = "fc1"
        osp.kernel_pattern = "/vmlinuz-%{version}"
        osp.initramfs_pattern = "/initramfs-%{version}.img"
        osp.root_opts_lvm2 = "rd.lvm.lv=%{lvm_root_lv}"
        osp.root_opts_btrfs = "rootflags=%{btrfs_subvolume}"
        osp.options = "root=%{root_device} ro %{root_opts} rhgb quiet"
        osp.optional_keys = "grub_users grub_arg"

    def test_OsProfile_bad_optional_key_raises(self):
        osp = OsProfile(name="Fedora Core", short_name="fedora",
                        version="1 (Workstation Edition)", version_id="1")
        osp.uname_pattern = "fc1"
        osp.kernel_pattern = "/vmlinuz-%{version}"
        osp.initramfs_pattern = "/initramfs-%{version}.img"
        osp.root_opts_lvm2 = "rd.lvm.lv=%{lvm_root_lv}"
        osp.root_opts_btrfs = "rootflags=%{btrfs_subvolume}"
        osp.options = "root=%{root_device} ro %{root_opts} rhgb quiet"
        with self.assertRaises(ValueError) as cm:
            osp.optional_keys = "no_such_option"

    def test_OsProfile_add_optional_keys(self):
        osp = OsProfile(name="Fedora Core", short_name="fedora",
                        version="1 (Workstation Edition)", version_id="1")
        osp.uname_pattern = "fc1"
        osp.kernel_pattern = "/vmlinuz-%{version}"
        osp.initramfs_pattern = "/initramfs-%{version}.img"
        osp.root_opts_lvm2 = "rd.lvm.lv=%{lvm_root_lv}"
        osp.root_opts_btrfs = "rootflags=%{btrfs_subvolume}"
        osp.options = "root=%{root_device} ro %{root_opts} rhgb quiet"
        osp.add_optional_key("grub_class")
        osp.optional_keys = "grub_users grub_arg"
        osp.add_optional_key("grub_class")

    def test_OsProfile_add_bad_optional_keys(self):
        osp = OsProfile(name="Fedora Core", short_name="fedora",
                        version="1 (Workstation Edition)", version_id="1")
        osp.uname_pattern = "fc1"
        osp.kernel_pattern = "/vmlinuz-%{version}"
        osp.initramfs_pattern = "/initramfs-%{version}.img"
        osp.root_opts_lvm2 = "rd.lvm.lv=%{lvm_root_lv}"
        osp.root_opts_btrfs = "rootflags=%{btrfs_subvolume}"
        osp.options = "root=%{root_device} ro %{root_opts} rhgb quiet"
        osp.optional_keys = "grub_users grub_arg"
        with self.assertRaises(ValueError) as cm:
            osp.add_optional_key("no_such_key")

    def test_OsProfile_del_optional_keys(self):
        osp = OsProfile(name="Fedora Core", short_name="fedora",
                        version="1 (Workstation Edition)", version_id="1")
        osp.uname_pattern = "fc1"
        osp.kernel_pattern = "/vmlinuz-%{version}"
        osp.initramfs_pattern = "/initramfs-%{version}.img"
        osp.root_opts_lvm2 = "rd.lvm.lv=%{lvm_root_lv}"
        osp.root_opts_btrfs = "rootflags=%{btrfs_subvolume}"
        osp.options = "root=%{root_device} ro %{root_opts} rhgb quiet"
        osp.optional_keys = "grub_users grub_arg"
        osp.del_optional_key("grub_arg")

    def test_OsProfile_del_bad_optional_keys(self):
        osp = OsProfile(name="Fedora Core", short_name="fedora",
                        version="1 (Workstation Edition)", version_id="1")
        osp.uname_pattern = "fc1"
        osp.kernel_pattern = "/vmlinuz-%{version}"
        osp.initramfs_pattern = "/initramfs-%{version}.img"
        osp.root_opts_lvm2 = "rd.lvm.lv=%{lvm_root_lv}"
        osp.root_opts_btrfs = "rootflags=%{btrfs_subvolume}"
        osp.options = "root=%{root_device} ro %{root_opts} rhgb quiet"
        osp.optional_keys = "grub_users grub_arg"
        with self.assertRaises(ValueError) as cm:
            osp.del_optional_key("no_such_key")

    def test_osprofile_write_profiles(self):
        import boom
        boom.osprofile.load_profiles()
        boom.osprofile.write_profiles()

    def test_osprofile_find_profiles_by_id(self):
        rhel72_os_id = "9736c347ccb724368be04e51bb25687a361e535c"
        osp_list = find_profiles(selection=Selection(os_id=rhel72_os_id))
        self.assertEqual(len(osp_list), 1)
        self.assertEqual(osp_list[0].os_id, rhel72_os_id)

    def test_osprofile_find_profiles_by_name(self):
        os_name = "Fedora"
        os_short_name = "fedora"
        osp_list = find_profiles(selection=Selection(os_name=os_name))
        nr_profiles = 0
        for f in listdir(boom_profiles_path()):
            if os_short_name in f:
                nr_profiles += 1
        self.assertTrue(len(osp_list), nr_profiles)

    def test_no_select_null_profile(self):
        import boom
        osps = find_profiles(Selection(os_id=boom.osprofile._profiles[0].os_id))
        self.assertFalse(osps)

    def test_find_os_short_name(self):
        osps = find_profiles(Selection(os_short_name="fedora"))
        self.assertTrue(osps)

    def test_find_os_version(self):
        osps = find_profiles(Selection(os_version="26 (Workstation Edition)"))
        self.assertTrue(osps)

    def test_find_os_version_id(self):
        osps = find_profiles(Selection(os_version_id="26"))
        self.assertTrue(osps)

    def test_find_os_uname_pattern(self):
        osps = find_profiles(Selection(os_uname_pattern="el7"))
        self.assertTrue(osps)

    def test_find_os_kernel_pattern(self):
        pattern = "/vmlinuz-%{version}"
        osps = find_profiles(Selection(os_kernel_pattern=pattern))
        self.assertTrue(osps)

    def test_find_os_initramfs_pattern(self):
        osps = find_profiles(Selection(os_initramfs_pattern="/initramfs-%{version}.img"))
        self.assertTrue(osps)

# vim: set et ts=4 sw=4 :

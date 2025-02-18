# Copyright Red Hat
#
# tests/test_hostprofile.py - Boom OS profile tests.
#
# This file is part of the boom project.
#
# SPDX-License-Identifier: GPL-2.0-only
import unittest
import logging
from sys import stdout
from os import listdir, makedirs
from os.path import abspath, exists, join
import shutil

log = logging.getLogger()

from boom.osprofile import *
from boom.hostprofile import *
from boom.bootloader import *
from boom import *

# For private member validation checks
import boom.hostprofile

from tests import *

BOOT_ROOT_TEST = abspath("./tests")
set_boot_path(BOOT_ROOT_TEST)

BOOM_ENTRY_MACHINE_ID="BOOM_ENTRY_MACHINE_ID"

def _count_value_in_key(dir_path, ext, key_name, xvalue,
                        exact=False, default=False):
    """Helper function to count the number of times ``xvalue`` appears
        as the value of key ``key_name`` in the set of files found in
        ``dir_path`` having file extension ``ext`.

        If ``exact`` is true the value is compared for equality.
        Otherwise the value is counted if the string ``value`` appears
        anywhere within the named key value.

        If ``default`` is ``True``, and the key is not found in a
        profile, it is assumed that ``xvalue`` is the default value,
        and that the relevant profile has inherited this value from
        the embedded ``OsProfile`` defaults.

        This is used to count profiles by property independently of
        the ``boom`` library modules for comparison of results
        returned from the API.
    """
    count = 0
    filecount = 1
    for f_name in listdir(dir_path):
        if not f_name.endswith(ext):
            continue
        f_path = join(dir_path, f_name)
        found_in_file = False
        with open(f_path, "r") as f:
            for line in f.readlines():
                (key, value) = parse_name_value(line)
                if key not in HOST_PROFILE_KEYS:
                    continue
                if key == key_name:
                    found_in_file = True
                    if not exact:
                        count += 1 if xvalue in value else 0
                    else:
                        count += 1 if xvalue == value else 0
            if default and not found_in_file:
                count += 1
            filecount += 1
    return count


class HostProfileTests(unittest.TestCase):
    # Main boom configuration path for sandbox
    boom_path = join(BOOT_ROOT_TEST, "boom")

    # Main BLS loader directory for sandbox
    loader_path = join(BOOT_ROOT_TEST, "loader")

    def setUp(self):
        log.debug("Preparing %s", self._testMethodName)

        reset_sandbox()

        # Sandbox paths
        boot_sandbox = join(SANDBOX_PATH, "boot")
        boom_sandbox = join(SANDBOX_PATH, "boot/boom")
        loader_sandbox = join(SANDBOX_PATH, "boot/loader")

        makedirs(boot_sandbox)
        shutil.copytree(self.boom_path, boom_sandbox)
        shutil.copytree(self.loader_path, loader_sandbox)

        set_boot_path(boot_sandbox)

        drop_host_profiles()
        drop_profiles()

    def tearDown(self):
        log.debug("Tearing down %s", self._testMethodName)

        drop_host_profiles()
        drop_profiles()
        rm_sandbox()
        reset_boom_paths()

    # Module tests
    def test_import(self):
        import boom.hostprofile

    # Profile store tests

    def test_load_profiles(self):
        # Test that loading the test profiles succeeds.
        load_host_profiles()

    # HostProfile tests

    def test_HostProfile__str__(self):
        load_profiles()
        load_host_profiles()
        hp = HostProfile(machine_id="ffffffffffffffff", host_name="localhost",
                         label='', os_id="3fc389b")

        xstr = (
                'Host ID: "83fb23b393d6460e18e3694a8766b06ade021c3f",\n'
                'Host name: "localhost",\nMachine ID: "ffffffffffffffff",\n'
                'OS ID: "3fc389bba581e5b20c6a46c7fc31b04be465e973",\n'
                'Host label: "",\nName: "Red Hat Enterprise Linux Server", '
                'Short name: "rhel", Version: "7.2 (Maipo)",\n'
                'Version ID: "7.2", UTS release pattern: "el7",\n'
                'Kernel pattern: "/vmlinuz-%{version}", '
                'Initramfs pattern: "/initramfs-%{version}.img",\n'
                'Root options (LVM2): "rd.lvm.lv=%{lvm_root_lv}",\n'
                'Root options (BTRFS): "rootflags=%{btrfs_subvolume}",\n'
                'Options: "root=%{root_device} ro %{root_opts} rhgb quiet"'
        )

        self.assertEqual(str(hp), xstr)
        hp.delete_profile()

    def test_HostProfile__repr__(self):
        load_profiles()
        load_host_profiles()
        hp = HostProfile(machine_id="ffffffffffffffff", host_name="localhost",
                         label='', os_id="3fc389b")

        xrepr = ('HostProfile(profile_data={'
                 'BOOM_HOST_ID:"83fb23b393d6460e18e3694a8766b06ade021c3f", '
                 'BOOM_HOST_NAME:"localhost", '
                 'BOOM_ENTRY_MACHINE_ID:"ffffffffffffffff", '
                 'BOOM_OS_ID:"3fc389bba581e5b20c6a46c7fc31b04be465e973", '
                 'BOOM_HOST_LABEL:"", '
                 'BOOM_OS_NAME:"Red Hat Enterprise Linux Server", '
                 'BOOM_OS_SHORT_NAME:"rhel", BOOM_OS_VERSION:"7.2 (Maipo)", '
                 'BOOM_OS_VERSION_ID:"7.2", BOOM_OS_UNAME_PATTERN:"el7", '
                 'BOOM_OS_KERNEL_PATTERN:"/vmlinuz-%{version}", '
                 'BOOM_OS_INITRAMFS_PATTERN:"/initramfs-%{version}.img", '
                 'BOOM_OS_ROOT_OPTS_LVM2:"rd.lvm.lv=%{lvm_root_lv}", '
                 'BOOM_OS_ROOT_OPTS_BTRFS:"rootflags=%{btrfs_subvolume}", '
                 'BOOM_OS_OPTIONS:"root=%{root_device} ro %{root_opts} rhgb '
                 'quiet"})'
        )

        self.assertEqual(repr(hp), xrepr)
        hp.delete_profile()

    def test_HostProfile(self):
        # Test HostProfile init from kwargs
        with self.assertRaises(ValueError) as cm:
            hp = HostProfile(host_name="localhost", os_id="3fc389b")
        with self.assertRaises(ValueError) as cm:
            hp = HostProfile(machine_id="ffffffffffffffff", host_name="localhost")
        with self.assertRaises(ValueError) as cm:
            hp = HostProfile(machine_id="ffffffffffffffff", os_id="3fc389b")

        hp = HostProfile(machine_id="ffffffffffffffff", host_name="localhost",
                         os_id="3fc389b", label='')

        self.assertTrue(hp)

        # os_id for RHEL-7.2
        self.assertEqual(hp.os_id, "3fc389bba581e5b20c6a46c7fc31b04be465e973")

        hp.delete_profile()

    def test_HostProfile_from_profile_data(self):
        profile_data = {
            BOOM_ENTRY_MACHINE_ID: "fffffffffffffff",
            BOOM_HOST_NAME: "localhost",
            BOOM_OS_ID: "3fc389bba581e5b20c6a46c7fc31b04be465e973",
            BOOM_OS_KERNEL_PATTERN: "/vmlinuz-%{version}",
            BOOM_OS_INITRAMFS_PATTERN: "/initramfs-%{version}.img",
            BOOM_OS_ROOT_OPTS_LVM2: "rd.lvm.lv=%{lvm_root_lv} rh",
            BOOM_OS_ROOT_OPTS_BTRFS: "rootflags=%{btrfs_subvolume} rh",
            BOOM_OS_OPTIONS: "root=%{root_device} %{root_opts} rhgb quiet"
        }

        hp = HostProfile(profile_data=profile_data)
        self.assertTrue(hp)

        # Assert that overrides are present
        self.assertEqual(hp.root_opts_lvm2, "rd.lvm.lv=%{lvm_root_lv} rh")
        self.assertEqual(hp.root_opts_btrfs, "rootflags=%{btrfs_subvolume} rh")

        hp.delete_profile()

        # Remove the root options keys.
        profile_data.pop(BOOM_OS_ROOT_OPTS_LVM2, None)
        profile_data.pop(BOOM_OS_ROOT_OPTS_BTRFS, None)
        hp = HostProfile(profile_data=profile_data)

        # Assert that defaults are restored
        self.assertEqual(hp.root_opts_lvm2, "rd.lvm.lv=%{lvm_root_lv}")
        self.assertEqual(hp.root_opts_btrfs, "rootflags=%{btrfs_subvolume}")

        hp.delete_profile()

        # Remove the name key.
        profile_data.pop(BOOM_HOST_NAME, None)
        with self.assertRaises(ValueError) as cm:
            hp = HostProfile(profile_data=profile_data)

    def test_HostProfile_properties(self):
        hp = HostProfile(machine_id="fffffffffffffff", host_name="localhost",
                         os_id="3fc389b", label="")
        hp.kernel_pattern = "/vmlinuz-%{version}"
        hp.initramfs_pattern = "/initramfs-%{version}.img"
        hp.root_opts_lvm2 = "rd.lvm.lv=%{lvm_root_lv}"
        hp.root_opts_btrfs = "rootflags=%{btrfs_subvolume}"
        hp.options = "root=%{root_device} %{root_opts} rhgb quiet"

        self.assertEqual(hp.host_name, "localhost")
        self.assertEqual(hp.machine_id, "fffffffffffffff")
        self.assertEqual(hp.kernel_pattern, "/vmlinuz-%{version}")
        self.assertEqual(hp.initramfs_pattern,
                         "/initramfs-%{version}.img")
        self.assertEqual(hp.root_opts_lvm2, "rd.lvm.lv=%{lvm_root_lv}")
        self.assertEqual(hp.root_opts_btrfs,
                         "rootflags=%{btrfs_subvolume}")
        self.assertEqual(hp.options,
                         "root=%{root_device} %{root_opts} rhgb quiet")
        hp.delete_profile()

    def test_HostProfile_write(self):
        hp = HostProfile(machine_id="fffffffffffffff", host_name="localhost",
                         os_id="3fc389b", label="")
        hp.write_profile()
        profile_path = join(boom_host_profiles_path(),
                            "%s-%s.host" % (hp.host_id, hp.host_name))
        self.assertTrue(exists(profile_path))
        hp.delete_profile()

    @unittest.skipIf(have_root(), "DAC controls do not apply to root")
    def test_load_host_profiles_no_read(self):
        # Set the /boot path to a non-writable path for the test user.
        set_boot_path("/boot")
        with self.assertRaises(OSError) as cm:
            load_host_profiles()
        # Re-set test /boot
        set_boot_path(BOOT_ROOT_TEST)

    @unittest.skipIf(have_root(), "DAC controls do not apply to root")
    def test_write_host_profiles_fail(self):
        load_host_profiles()
        # Set the /boot path to a non-writable path for the test user.
        set_boot_path("/boot")
        # Create a dirty profile to write
        hp = HostProfile(machine_id="ffffffffffffff1", host_name="localhost",
                         os_id="3fc389b", label="")
        write_host_profiles()

        # Clean up dummy profile
        hp.delete_profile()
        # Re-set test /boot
        set_boot_path(BOOT_ROOT_TEST)

    def test_osprofile_write_profiles(self):
        load_host_profiles()
        write_host_profiles()

    def test_hostprofile_find_profiles_by_id(self):
        # Reload host profiles from disk: a failure to clean up in an
        # earlier test may have left the profile list in an inconsistent
        # state.
        host_id = "6af0980a6607b20cda34a45d2869c9be020914b4"
        load_host_profiles()
        hp = HostProfile(machine_id="fffffffffffffff", host_name="localhost",
                         os_id="3fc389b", label="testhp")
        hp.write_profile()
        hp_list = find_host_profiles(selection=Selection(host_id=host_id))
        self.assertEqual(len(hp_list), 1)
        self.assertEqual(hp_list[0].host_id, host_id)
        hp.delete_profile()

    def test_hostprofile_find_profiles_by_host_name(self):
        host_name = "localhost"
        hp_list = find_host_profiles(selection=Selection(host_name=host_name))
        nr_profiles = 0
        for f in listdir(boom_profiles_path()):
            if f.endswith(host_name + ".host"):
                nr_profiles += 1
        self.assertTrue(len(hp_list), nr_profiles)

    def test_hostprofile_find_profiles_by_add_opts(self):
        add_opts = "debug"
        select = Selection(host_add_opts=add_opts)
        hp_list = find_host_profiles(selection=select)
        # Adjusted to current test data
        self.assertEqual(1, len(hp_list))
        self.assertEqual(add_opts, hp_list[0].add_opts)

    def test_hostprofile_find_profiles_by_del_opts(self):
        del_opts = "rhgb quiet"
        select = Selection(host_del_opts=del_opts)
        hp_list = find_host_profiles(selection=select)
        nr_hps = 0
        for hp in boom.hostprofile._host_profiles:
            if hp.del_opts == del_opts:
                nr_hps += 1
        self.assertEqual(nr_hps, len(hp_list))
        self.assertEqual(del_opts, hp_list[0].del_opts)

    def test_hostprofile_find_profiles_by_os_id(self):
        os_id = "3fc389b"
        hp_list = find_host_profiles(selection=Selection(os_id=os_id))
        nr_hps = 0
        for hp in boom.hostprofile._host_profiles:
            if hp.os_id.startswith(os_id):
                nr_hps += 1
        self.assertEqual(nr_hps, len(hp_list))
        self.assertTrue(hp_list[0].os_id.startswith(os_id))

    def test_hostprofile_find_profiles_by_os_name(self):
        os_name = "Fedora"
        hp_list = find_host_profiles(selection=Selection(os_name=os_name))
        nr_hps = 0
        for hp in boom.hostprofile._host_profiles:
            if hp.os_name == os_name:
                nr_hps += 1
        self.assertEqual(nr_hps, len(hp_list))
        self.assertEqual(os_name, hp_list[0].os_name)

    def test_hostprofile_find_profiles_by_os_short_name(self):
        os_short_name = "fedora"
        select = Selection(os_short_name=os_short_name)
        hp_list = find_host_profiles(selection=select)
        nr_hps = 0
        for hp in boom.hostprofile._host_profiles:
            if hp.os_short_name == os_short_name:
                nr_hps += 1
        self.assertEqual(nr_hps, len(hp_list))
        self.assertEqual(os_short_name, hp_list[0].os_short_name)

    def test_hostprofile_find_profiles_by_os_version(self):
        os_version = "7.2 (Maipo)"
        select = Selection(os_version=os_version)
        hp_list = find_host_profiles(selection=select)
        # Adjusted to current test data
        self.assertEqual(2, len(hp_list))
        self.assertEqual(os_version, hp_list[0].os_version)

    def test_hostprofile_find_profiles_by_os_version_id(self):
        os_version_id = "7.2"
        select = Selection(os_version_id=os_version_id)
        hp_list = find_host_profiles(selection=select)
        nr_hps = 0
        for hp in boom.hostprofile._host_profiles:
            if hp.os_version_id == os_version_id:
                nr_hps += 1
        self.assertEqual(nr_hps, len(hp_list))
        self.assertEqual(os_version_id, hp_list[0].os_version_id)

    def test_hostprofile_find_profiles_by_uname_pattern(self):
        uname_pattern = "el7"
        select = Selection(os_uname_pattern=uname_pattern)
        hp_list = find_host_profiles(selection=select)
        nr_hps = 0
        for hp in boom.hostprofile._host_profiles:
            if hp.uname_pattern == uname_pattern:
                nr_hps += 1
        self.assertEqual(nr_hps, len(hp_list))
        self.assertEqual(uname_pattern, hp_list[0].uname_pattern)

    def test_hostprofile_find_profiles_by_kernel_pattern(self):
        kernel_pattern = "/vmlinuz-%{version}"
        select = Selection(os_kernel_pattern=kernel_pattern)
        hp_list = find_host_profiles(selection=select)

        nr_hps = 0
        for hp in boom.hostprofile._host_profiles:
            if hp.kernel_pattern == kernel_pattern:
                nr_hps += 1
        self.assertEqual(nr_hps, len(hp_list))
        self.assertEqual(kernel_pattern, hp_list[0].kernel_pattern)

        # Non-matching
        kernel_pattern = "NOTAREALKERNELPATTERN"
        select = Selection(os_kernel_pattern=kernel_pattern)
        hp_list = find_host_profiles(selection=select)
        self.assertFalse(hp_list)

    def test_hostprofile_find_profiles_by_initramfs_pattern(self):
        initramfs_pattern = "/initramfs-%{version}.img"
        select = Selection(os_initramfs_pattern=initramfs_pattern)
        hp_list = find_host_profiles(selection=select)

        host_path = boom_host_profiles_path()
        profile_count = _count_value_in_key(host_path, ".host",
                                            BOOM_OS_INITRAMFS_PATTERN,
                                            initramfs_pattern,
                                            exact=True, default=True)

        self.assertEqual(profile_count, len(hp_list))
        self.assertEqual(initramfs_pattern, hp_list[0].initramfs_pattern)

        # Non-matching
        initramfs_pattern = "NOTAREALINITRAMFSPATTERN"
        select = Selection(os_initramfs_pattern=initramfs_pattern)
        hp_list = find_host_profiles(selection=select)
        # Adjusted to current test data
        self.assertFalse(hp_list)

    def test_hostprofile_find_profiles_by_options(self):
        options = "root=%{root_device} ro %{root_opts} rhgb quiet"
        select = Selection(os_options=options)
        hp_list = find_host_profiles(selection=select)
        nr_hps = 0
        for hp in boom.hostprofile._host_profiles:
            if hp.options == options:
                nr_hps += 1
        self.assertEqual(nr_hps, len(hp_list))
        self.assertEqual(options, hp_list[0].options)

        # Non-matching
        options = "root=/dev/nodev ro rhgb quiet"
        select = Selection(os_options=options)
        hp_list = find_host_profiles(selection=select)
        # Adjusted to current test data
        self.assertFalse(hp_list)

    def test_hostprofile_find_host_profiles_not_loaded(self):
        # Find with automatic load
        hps = find_host_profiles()
        self.assertTrue(hps)

    def test_host_min_id_width(self):
        import boom.hostprofile
        xwidth = 7 # Adjusted to current test data
        load_host_profiles()
        width = boom.hostprofile.min_host_id_width()
        self.assertEqual(xwidth, width)

    def test_machine_min_id_width(self):
        import boom.hostprofile
        xwidth = 13 # Adjusted to current test data
        load_host_profiles()
        width = boom.hostprofile.min_machine_id_width()
        self.assertEqual(xwidth, width)

    def test_find_host_host_id(self):
        # Non-existent host_id
        hps = find_host_profiles(Selection(host_id="fffffff"))
        self.assertFalse(hps)

        host_id1 = "373ccd1"
        # Valid single host_id
        hps = find_host_profiles(Selection(host_id=host_id1))
        self.assertTrue(hps)

        nr_hps = 0
        for hp in boom.hostprofile._host_profiles:
            if hp.host_id.startswith(host_id1):
                nr_hps += 1
        self.assertEqual(nr_hps, len(hps))

        # Two host profiles exist for this host_id (and with no label).
        # This is because this host is used for "hand edited host"
        # testing. Although this is not a valid configuratio that can
        # be reached using the Boom CLI it is still expected to work
        # and to produce consistent API behaviour.
        host_id2 = "5ebcb1f"
        hps = find_host_profiles(Selection(host_id=host_id2))
        self.assertTrue(hps)

        nr_hps = 0
        for hp in boom.hostprofile._host_profiles:
            if hp.host_id.startswith(host_id2):
                nr_hps += 1
        self.assertEqual(nr_hps, len(hps))

        # Valid host_id scoped by label
        host_label = "ALABEL"
        hps = find_host_profiles(Selection(host_id=host_id1,
                                           host_label=host_label))
        nr_hps = 0
        for hp in boom.hostprofile._host_profiles:
            if hp.host_id.startswith(host_id1):
                if hp.label == host_label:
                    nr_hps += 1
        self.assertTrue(hps)
        self.assertEqual(nr_hps, len(hps))

    def test_find_host_host_name(self):
        host_name = "localhost.localdomain"
        hps = find_host_profiles(Selection(host_name=host_name))
        self.assertTrue(hps)
        nr_hps = 0
        for hp in boom.hostprofile._host_profiles:
            if hp.host_name == host_name:
                nr_hps += 1
        self.assertEqual(nr_hps, len(hps))

    def test_find_host_host_short_name(self):
        load_host_profiles()
        host_name = "localhost"
        hps = find_host_profiles(Selection(host_short_name=host_name))
        self.assertTrue(hps)

        host_path = boom_host_profiles_path()
        profile_count = _count_value_in_key(host_path, ".host",
                                            BOOM_HOST_NAME, host_name)
        # Adjusted to current test data
        self.assertEqual(profile_count, len(hps))

    def test_find_host_host_label(self):
        hps = find_host_profiles(Selection(host_label="ALABEL"))
        self.assertTrue(hps)
        # Adjusted to current test data
        self.assertEqual(1, len(hps))

    def test_get_host_profile_by_id(self):
        load_host_profiles()
        m_id1 = "fffffffffffffff"
        hp = get_host_profile_by_id(m_id1)
        self.assertEqual(m_id1, hp.machine_id)

    def test_get_host_profile_by_id_not_loaded(self):
        m_id1 = "fffffffffffffff"


        hp = get_host_profile_by_id(m_id1)
        self.assertEqual(m_id1, hp.machine_id)

    def test_get_host_profile_by_id_and_label(self):
        m_id1 = "611f38fd887d41dea7ffffffffffff"
        label = "ALABEL"
        hp = get_host_profile_by_id(m_id1, label=label)
        self.assertEqual(m_id1, hp.machine_id)
        self.assertEqual(label, hp.label)

    def test_get_host_profile_by_id_no_match(self):
        m_id1 = "bazquxfoo"
        hp = get_host_profile_by_id(m_id1)
        self.assertFalse(hp)

    def test_match_host_profile(self):
        bes = find_entries(Selection(boot_id="dc5f44d"))
        self.assertTrue(bes)
        be = bes[0]
        self.assertTrue(be)
        machine_id = be.machine_id
        hp = match_host_profile(be)
        self.assertTrue(hp)
        self.assertEqual(be.machine_id, hp.machine_id)

# vim: set et ts=4 sw=4 :

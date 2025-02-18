# Copyright Red Hat
#
# tests/test_osprofile.py - Boom OS profile tests.
#
# This file is part of the boom project.
#
# SPDX-License-Identifier: GPL-2.0-only
import unittest
import logging
from sys import stdout
from os import listdir, makedirs, mknod, unlink
from os.path import abspath, exists, join
from stat import S_IFBLK, S_IFCHR
import shutil

# Test suite paths
from tests import *

import boom
from boom.bootloader import *
from boom.osprofile import *
from boom.hostprofile import *
from boom import Selection

# Override default BOOM_ROOT and BOOT_ROOT
# NOTE: with test fixtures that use the sandbox, this path is further
# overridden by the class setUp() method to point to the appropriate
# sandbox location.
boom.set_boot_path(BOOT_ROOT_TEST)

log = logging.getLogger()

_test_osp = None

class BootParamsTests(unittest.TestCase):
    def setUp(self):
        log.debug("Preparing %s", self._testMethodName)

    def tearDown(self):
        log.debug("Tearing down %s", self._testMethodName)

    def test_BootParams_no_version_raises(self):
        with self.assertRaises(ValueError) as cm:
            # A version string is required
            bp = BootParams(None)

    def test_BootParams_conflicting_btrfs_raises(self):
        with self.assertRaises(ValueError) as cm:
            # Only one of subvol_id or subvol_path is allowed
            bp = BootParams("1.1.1.x86_64", root_device="/dev/sda5",
                            btrfs_subvol_path="/snapshots/snap-1",
                            btrfs_subvol_id="232")

    def test_BootParams_plain__str__and__repr__(self):
        # Plain root_device
        bp = BootParams(version="1.1.1.x86_64", root_device="/dev/sda5")
        xstr = "1.1.1.x86_64, root_device=/dev/sda5"
        xrepr = 'BootParams("1.1.1.x86_64", root_device="/dev/sda5")'
        self.assertEqual(str(bp), xstr)
        self.assertEqual(repr(bp), xrepr)

    def test_BootParams_lvm__str__and__repr__(self):
        # LVM logical volume and no root_device
        bp = BootParams(version="1.1.1.x86_64", lvm_root_lv="vg00/lvol0")
        xstr = ("1.1.1.x86_64, root_device=/dev/vg00/lvol0, "
                "lvm_root_lv=vg00/lvol0")
        xrepr = ('BootParams("1.1.1.x86_64", root_device="/dev/vg00/lvol0", '
                 'lvm_root_lv="vg00/lvol0")')
        self.assertEqual(str(bp), xstr)
        self.assertEqual(repr(bp), xrepr)

        # LVM logical volume and root_device override
        bp = BootParams(version="1.1.1.x86_64",
                        root_device="/dev/mapper/vg00-lvol0",
                        lvm_root_lv="vg00/lvol0")
        xstr = ("1.1.1.x86_64, root_device=/dev/mapper/vg00-lvol0, "
                "lvm_root_lv=vg00/lvol0")
        xrepr = ('BootParams("1.1.1.x86_64", '
                 'root_device="/dev/mapper/vg00-lvol0", '
                 'lvm_root_lv="vg00/lvol0")')

        self.assertFalse(bp.has_btrfs())
        self.assertTrue(bp.has_lvm2())
        self.assertEqual(str(bp), xstr)
        self.assertEqual(repr(bp), xrepr)

    def test_BootParams_btrfs__str__and__repr__(self):
        # BTRFS subvol path and root_device
        bp = BootParams(version="1.1.1.x86_64",
                        root_device="/dev/sda5",
                        btrfs_subvol_path="/snapshots/snap-1")
        xstr = ("1.1.1.x86_64, root_device=/dev/sda5, "
                "btrfs_subvol_path=/snapshots/snap-1")
        xrepr = ('BootParams("1.1.1.x86_64", root_device="/dev/sda5", '
                 'btrfs_subvol_path="/snapshots/snap-1")')
        self.assertEqual(str(bp), xstr)
        self.assertEqual(repr(bp), xrepr)

        # BTRFS subvol ID and root_device
        bp = BootParams(version="1.1.1.x86_64",
                        root_device="/dev/sda5",
                        btrfs_subvol_id="232")
        xstr = ("1.1.1.x86_64, root_device=/dev/sda5, "
                "btrfs_subvol_id=232")
        xrepr = ('BootParams("1.1.1.x86_64", root_device="/dev/sda5", '
                 'btrfs_subvol_id="232")')

        self.assertTrue(bp.has_btrfs())
        self.assertFalse(bp.has_lvm2())
        self.assertEqual(str(bp), xstr)
        self.assertEqual(repr(bp), xrepr)

    def test_BootParams_lvm_btrfs__str__and__repr__(self):
        # BTRFS subvol path and LVM root_device
        bp = BootParams(version="1.1.1.x86_64", lvm_root_lv="vg00/lvol0",
                        btrfs_subvol_path="/snapshots/snap-1")
        xstr = ("1.1.1.x86_64, root_device=/dev/vg00/lvol0, "
                "lvm_root_lv=vg00/lvol0, "
                "btrfs_subvol_path=/snapshots/snap-1")
        xrepr = ('BootParams("1.1.1.x86_64", root_device="/dev/vg00/lvol0", '
                 'lvm_root_lv="vg00/lvol0", '
                 'btrfs_subvol_path="/snapshots/snap-1")')
        self.assertEqual(str(bp), xstr)
        self.assertEqual(repr(bp), xrepr)

        # BTRFS subvol id and LVM root_device
        bp = BootParams(version="1.1.1.x86_64", lvm_root_lv="vg00/lvol0",
                        btrfs_subvol_id="232")
        xstr = ("1.1.1.x86_64, root_device=/dev/vg00/lvol0, "
                "lvm_root_lv=vg00/lvol0, btrfs_subvol_id=232")
        xrepr = ('BootParams("1.1.1.x86_64", root_device="/dev/vg00/lvol0", '
                 'lvm_root_lv="vg00/lvol0", btrfs_subvol_id="232")')
        self.assertEqual(str(bp), xstr)
        self.assertEqual(repr(bp), xrepr)


def _reset_test_osprofile():
    global _test_osp
    # Some tests modify the OsProfile: recycle it each time it is used
    if _test_osp:
        _test_osp.delete_profile()
    osp = OsProfile(name="Distribution", short_name="distro",
                    version="1 (Workstation Edition)", version_id="1")
    osp.uname_pattern = "di1"
    osp.kernel_pattern = "/vmlinuz-%{version}"
    osp.initramfs_pattern = "/initramfs-%{version}.img"
    osp.root_opts_lvm2 = "rd.lvm.lv=%{lvm_root_lv}"
    osp.root_opts_btrfs = "rootflags=%{btrfs_subvolume}"
    osp.options = "root=%{root_device} %{root_opts} rhgb quiet"
    _test_osp = osp


class MockBootEntry(object):
    boot_id = "1234567890abcdef"
    version = "1.1.1"
    expand_options = "root=/dev/mapper/rhel-root ro rhgb quiet"
    _osp = None
    _entry_data = {}
    _last_path = "/some/path/to/somewhere"


class BootEntryBasicTests(unittest.TestCase):
    """Tests for the BootEntry class that do not depend on external
        test data.
    """
    # DELETEME
    test_version = "1.1.1-1.qux.x86_64"
    test_lvm2_root_device = "/dev/vg00/lvol0"
    test_lvm_root_lv = "vg00/lvol0"
    test_btrfs_root_device = "/dev/sda5"
    test_btrfs_subvol_path = "/snapshots/snap1"
    test_btrfs_subvol_id = "232"

    # Sandbox paths

    # Main BLS loader directory for sandbox
    loader_path = join(BOOT_ROOT_TEST, "loader")

    # Main boom configuration path for sandbox
    boom_path = join(BOOT_ROOT_TEST, "boom")

    def setUp(self):
        log.debug("Preparing %s", self._testMethodName)
        reset_sandbox()

        # Sandbox paths
        boot_sandbox = join(SANDBOX_PATH, "boot")
        boom_sandbox = join(SANDBOX_PATH, "boot/boom")
        loader_sandbox = join(SANDBOX_PATH, "boot/loader")

        # Initialise sandbox from main
        makedirs(boot_sandbox)
        shutil.copytree(self.boom_path, boom_sandbox)
        shutil.copytree(self.loader_path, loader_sandbox)

        # Set boom paths
        boom.set_boot_path(boot_sandbox)

        # Reset profiles, entries, and host profiles to known state.
        load_profiles()
        load_entries()
        load_host_profiles()

    def tearDown(self):
        log.debug("Tearing down %s", self._testMethodName)
        # Drop any in-memory entries and profiles modified by tests
        drop_entries()
        drop_profiles()
        drop_host_profiles()

        # Clear sandbox data
        rm_sandbox()
        reset_boom_paths()

    # BootEntry tests

    def test_BootEntry__str__(self):
        be = BootEntry(title="title", machine_id="ffffffff", osprofile=None,
                       allow_no_dev=True)
        xstr = ('title title\nmachine-id ffffffff\n'
                'linux /vmlinuz-%{version}\n'
                'initrd /initramfs-%{version}.img')
        self.assertEqual(str(be), xstr)

    def test_BootEntry__repr__(self):
        be = BootEntry(title="title", machine_id="ffffffff", osprofile=None,
                       allow_no_dev=True)
        xrepr = ('BootEntry(entry_data={BOOM_ENTRY_TITLE: "title", '
                 'BOOM_ENTRY_MACHINE_ID: "ffffffff", '
                 'BOOM_ENTRY_LINUX: "/vmlinuz-%{version}", '
                 'BOOM_ENTRY_INITRD: "/initramfs-%{version}.img", '
                 'BOOM_ENTRY_BOOT_ID: '
                 '"40c7c3158e626ed25cc2066b7c308fca0cb57be2"})')
        self.assertEqual(repr(be), xrepr)

    def test_BootEntry(self):
        # Test BootEntry init from kwargs
        with self.assertRaises(ValueError) as cm:
            be = BootEntry(title=None, machine_id="ffffffff", osprofile=None,
                           allow_no_dev=True)

        # Empty machine-id is now allowed for Red Hat BLS entries...
        #with self.assertRaises(ValueError) as cm:
        #    be = BootEntry(title="title", machine_id=None, osprofile=None,
        #                   allow_no_dev=True)

        with self.assertRaises(ValueError) as cm:
            be = BootEntry(title=None, machine_id=None, osprofile=None,
                           allow_no_dev=True)

        be = BootEntry(title="title", machine_id="ffffffff")

        self.assertTrue(be)

    def test_BootEntry_from_entry_data(self):
        # Pull in all the BOOM_ENTRY_* constants to the local namespace.
        from boom.bootloader import (
            BOOM_ENTRY_TITLE, BOOM_ENTRY_MACHINE_ID, BOOM_ENTRY_VERSION,
            BOOM_ENTRY_LINUX, BOOM_ENTRY_EFI, BOOM_ENTRY_INITRD,
            BOOM_ENTRY_OPTIONS
        )
        with self.assertRaises(ValueError) as cm:
            # Missing BOOM_ENTRY_TITLE
            be = BootEntry(entry_data={BOOM_ENTRY_MACHINE_ID: "ffffffff",
                           BOOM_ENTRY_VERSION: "1.1.1",
                           BOOM_ENTRY_LINUX: "/vmlinuz-1.1.1",
                           BOOM_ENTRY_INITRD: "/initramfs-1.1.1.img",
                           BOOM_ENTRY_OPTIONS: "root=/dev/sda5 ro"})

        # Valid entry
        be = BootEntry(entry_data={BOOM_ENTRY_TITLE: "title",
                       BOOM_ENTRY_MACHINE_ID: "ffffffff",
                       BOOM_ENTRY_VERSION: "1.1.1",
                       BOOM_ENTRY_LINUX: "/vmlinuz-1.1.1",
                       BOOM_ENTRY_INITRD: "/initramfs-1.1.1.img",
                       BOOM_ENTRY_OPTIONS: "root=/dev/sda5 ro"})

        with self.assertRaises(ValueError) as cm:
            # Missing BOOM_ENTRY_LINUX or BOOM_ENTRY_EFI
            be = BootEntry(entry_data={BOOM_ENTRY_TITLE: "title",
                           BOOM_ENTRY_MACHINE_ID: "ffffffff",
                           BOOM_ENTRY_VERSION: "1.1.1",
                           BOOM_ENTRY_INITRD: "/initramfs-1.1.1.img",
                           BOOM_ENTRY_OPTIONS: "root=/dev/sda5 ro"})

        # Valid Linux entry
        be = BootEntry(entry_data={BOOM_ENTRY_TITLE: "title",
                       BOOM_ENTRY_LINUX: "/vmlinuz",
                       BOOM_ENTRY_MACHINE_ID: "ffffffff",
                       BOOM_ENTRY_VERSION: "1.1.1",
                       BOOM_ENTRY_OPTIONS: "root=/dev/sda5 ro"})

        # Valid EFI entry
        be = BootEntry(entry_data={BOOM_ENTRY_TITLE: "title",
                       BOOM_ENTRY_EFI: "/some.efi.thing",
                       BOOM_ENTRY_MACHINE_ID: "ffffffff",
                       BOOM_ENTRY_VERSION: "1.1.1",
                       BOOM_ENTRY_OPTIONS: "root=/dev/sda5 ro"})

    def test_BootEntry_with_boot_params(self):
        from boom.bootloader import (
            BOOM_ENTRY_TITLE, BOOM_ENTRY_MACHINE_ID, BOOM_ENTRY_VERSION,
            BOOM_ENTRY_LINUX, BOOM_ENTRY_EFI, BOOM_ENTRY_INITRD,
            BOOM_ENTRY_OPTIONS
        )
        bp = BootParams(version="2.2.2", lvm_root_lv="vg00/lvol0")
        be = BootEntry(entry_data={BOOM_ENTRY_TITLE: "title",
                       BOOM_ENTRY_MACHINE_ID: "ffffffff",
                       BOOM_ENTRY_VERSION: "1.1.1",
                       BOOM_ENTRY_LINUX: "/vmlinuz-1.1.1",
                       BOOM_ENTRY_INITRD: "/initramfs-1.1.1.img",
                       BOOM_ENTRY_OPTIONS: "root=/dev/vg_root/root "
                                     "rd.lvm.lv=vg_root/root"},
                       boot_params=bp, allow_no_dev=True)
        # boot_params overrides BootEntry
        self.assertEqual(be.version, bp.version)
        self.assertNotEqual(be.version, "1.1.1")

    def test_BootEntry_empty_osprofile(self):
        # Assert that key properties of a BootEntry with no attached osprofile
        # return None.
        from boom.bootloader import (
            BOOM_ENTRY_TITLE, BOOM_ENTRY_MACHINE_ID, BOOM_ENTRY_VERSION,
            BOOM_ENTRY_LINUX, BOOM_ENTRY_EFI, BOOM_ENTRY_INITRD,
            BOOM_ENTRY_OPTIONS
        )
        bp = BootParams(version="2.2.2", lvm_root_lv="vg00/lvol0")
        be = BootEntry(entry_data={BOOM_ENTRY_TITLE: "title",
                       BOOM_ENTRY_MACHINE_ID: "ffffffff",
                       BOOM_ENTRY_LINUX: "/vmlinuz",
                       BOOM_ENTRY_VERSION: "1.1.1"}, boot_params=bp,
                       allow_no_dev=True)

        xoptions = "root=/dev/vg00/lvol0 ro rd.lvm.lv=vg00/lvol0"
        self.assertEqual(be.options, xoptions)


class BootEntryTests(unittest.TestCase):
    """Tests for the BootEntry class using on-disk entry and profile
        data.
    """
    test_version = "1.1.1-1.qux.x86_64"
    test_lvm2_root_device = "/dev/vg00/lvol0"
    test_lvm_root_lv = "vg00/lvol0"
    test_btrfs_root_device = "/dev/sda5"
    test_btrfs_subvol_path = "/snapshots/snap1"
    test_btrfs_subvol_id = "232"

    # Standard test OsProfile. Tests must not modify this.
    test_osp = None

    # Standard test BootParams. Tests must not modify this.
    test_bp = None

    # Standard test BootEntry. Tests must not modify this.
    test_be = None

    # Main BLS loader directory for sandbox
    loader_path = join(BOOT_ROOT_TEST, "loader")

    # Main boom configuration path for sandbox
    boom_path = join(BOOT_ROOT_TEST, "boom")

    # Test fixture init/cleanup
    def setUp(self):
        """Set up a test fixture for the BootEntryTests class.

            Defines standard OsProfile, BootParams, and BootEntry
            objects for use in these tests.
        """
        log.debug("Preparing %s", self._testMethodName)

        reset_sandbox()

        # Sandbox paths
        boot_sandbox = join(SANDBOX_PATH, "boot")
        boom_sandbox = join(SANDBOX_PATH, "boot/boom")
        loader_sandbox = join(SANDBOX_PATH, "boot/loader")

        # Initialise sandbox from main
        makedirs(boot_sandbox)
        shutil.copytree(self.boom_path, boom_sandbox)
        shutil.copytree(self.loader_path, loader_sandbox)

        # Set PATH environment variable
        set_mock_path()

        # Set boom paths
        boom.set_boot_path(boot_sandbox)

        # Load test OsProfile and BootEntry data
        load_profiles()
        load_entries()

        # Define a new, test OsProfile that is never included in the
        # standard set distributed with boom. To be used only for
        # formatting BootEntry objects for testing.
        osp = OsProfile(name="Distribution", short_name="distro",
                        version="1 (Workstation Edition)", version_id="1")
        osp.uname_pattern = "di1"
        osp.kernel_pattern = "/vmlinuz-%{version}"
        osp.initramfs_pattern = "/initramfs-%{version}.img"
        osp.root_opts_lvm2 = "rd.lvm.lv=%{lvm_root_lv}"
        osp.root_opts_btrfs = "rootflags=%{btrfs_subvolume}"
        osp.options = "root=%{root_device} %{root_opts} rhgb quiet"
        self.test_osp = osp

        # Define a standard set of test BootParams
        bp = BootParams("1.1.1.fc24", root_device="/dev/vg/lv",
                        lvm_root_lv="vg/lv")
        self.test_bp = bp

        # Define a synthetic BootEntry for testing
        be = BootEntry(title="title", machine_id="ffffffff",
                       boot_params=bp, osprofile=osp, allow_no_dev=True)
        self.test_be = be

    def tearDown(self):
        """Tear down the standard test profiles and entries used by the
            BootEntryTests class.
        """
        log.debug("Tearing down %s", self._testMethodName)

        # Drop any in-memory entries and profiles modified by tests
        drop_entries()
        drop_profiles()

        # Clear sandbox data
        rm_sandbox()
        reset_boom_paths()

        self.test_osp = None
        self.test_bp = None

    # BootParams recovery tests
    def test_BootParams_from_entry_no_opts(self):
        osp = self.test_osp
        osp.options = "root=%{root_device}"

        be = MockBootEntry()
        be.options = ""
        be.expand_options = ""
        be._osp = osp

        # Logs warning (no root_device)
        bp = BootParams.from_entry(be)

        # Assert that root_device is empty and that other parameters
        # are still recovered.
        self.assertEqual(bp.root_device, "")
        self.assertEqual(bp.version, "1.1.1")

    def test_BootParams_from_entry_no_root_device(self):
        osp = self.test_osp

        be = MockBootEntry()
        be.options = "ro rd.lvm.lv=vg00/lvol0 rhgb quiet"
        be._osp = osp

        self.assertTrue(BootParams.from_entry(be))

    def test_BootEntry_fixed_options_string(self):
        # Assert that key properties of a BootEntry with empty format keys
        # return the empty string.
        from boom.bootloader import (
            BOOM_ENTRY_TITLE, BOOM_ENTRY_MACHINE_ID, BOOM_ENTRY_VERSION,
            BOOM_ENTRY_LINUX, BOOM_ENTRY_EFI, BOOM_ENTRY_INITRD,
            BOOM_ENTRY_OPTIONS
        )

        osp = self.test_osp
        # Clear the OsProfile.options format key
        osp.options = "root=/dev/myroot"

        bp = BootParams(version="2.2.2", lvm_root_lv="vg00/lvol0")
        be = BootEntry(entry_data={BOOM_ENTRY_TITLE: "title",
                       BOOM_ENTRY_MACHINE_ID: "ffffffff",
                       BOOM_ENTRY_VERSION: "1.1.1",
                       BOOM_ENTRY_LINUX: "/vmlinuz-1.1.1",
                       BOOM_ENTRY_INITRD: "/initramfs-1.1.1.img"},
                       osprofile=osp, boot_params=bp, allow_no_dev=True)

        self.assertEqual(be.options, "root=/dev/myroot")

    def test_BootEntry_write(self):
        # Use a real OsProfile here: the entry will be written to disk, and
        # may be seen during entry loading (to avoid the entry being moved
        # to the Null profile).
        osp = find_profiles(Selection(os_id="d4439b7"))[0]
        bp = BootParams("1.1.1-1.fc26", root_device="/dev/vg00/lvol0",
                        lvm_root_lv="vg00/lvol0")
        be = BootEntry(title="title", machine_id="ffffffff", boot_params=bp,
                       osprofile=osp, allow_no_dev=True)

        boot_id = be.boot_id
        be.write_entry()
        load_entries()
        be2 = find_entries(Selection(boot_id=boot_id))[0]
        self.assertEqual(be.title, be2.title)
        self.assertEqual(be.boot_id, be2.boot_id)
        self.assertEqual(be.version, be2.version)
        ## Create on-disk entry and add to list of known entries
        #be.write_entry()
        # Profile and entry are non-persistent
        be2.delete_entry()

    def test_BootEntry_profile_kernel_version(self):
        osp = self.test_osp
        be = BootEntry(title="title", machine_id="ffffffff", osprofile=osp)
        be.version = "1.1.1-17.qux.x86_64"
        self.assertEqual(be.linux, "/vmlinuz-1.1.1-17.qux.x86_64")
        self.assertEqual(be.initrd, "/initramfs-1.1.1-17.qux.x86_64.img")

    def test_BootEntry_profile_root_lvm2(self):
        osp = self.test_osp
        bp = BootParams("1.1", lvm_root_lv="vg00/lvol0")
        be = BootEntry(title="title", machine_id="ffffffff",
                       osprofile=osp, boot_params=bp, allow_no_dev=True)
        self.assertEqual(be.root_opts, "rd.lvm.lv=vg00/lvol0")
        self.assertEqual(be.options, "root=/dev/vg00/lvol0 "
                         "rd.lvm.lv=vg00/lvol0 rhgb quiet")

    def test_BootEntry_profile_root_btrfs_id(self):
        osp = self.test_osp
        bp = BootParams("1.1", root_device="/dev/sda5", btrfs_subvol_id="232")
        be = BootEntry(title="title", machine_id="ffffffff",
                       osprofile=osp, boot_params=bp, allow_no_dev=True)
        self.assertEqual(be.root_opts, "rootflags=subvolid=232")
        self.assertEqual(be.options, "root=/dev/sda5 "
                         "rootflags=subvolid=232 rhgb quiet")

    def test_BootEntry_profile_root_btrfs_path(self):
        osp = self.test_osp
        bp = BootParams("1.1", root_device="/dev/sda5",
                        btrfs_subvol_path="/snapshots/20170523-1")
        be = BootEntry(title="title", machine_id="ffffffff",
                       osprofile=osp, boot_params=bp, allow_no_dev=True)
        self.assertEqual(be.root_opts,
                         "rootflags=subvol=/snapshots/20170523-1")
        self.assertEqual(be.options, "root=/dev/sda5 "
                         "rootflags=subvol=/snapshots/20170523-1 rhgb quiet")

    def test_BootEntry_boot_id(self):
        xboot_id = 'f0a46b7a6e982cab4163af6b45087e87691a0c43'
        bp = BootParams("1.1.1.x86_64", root_device="/dev/sda5")
        be = BootEntry(title="title", machine_id="ffffffff", boot_params=bp,
                       allow_no_dev=True)
        self.assertEqual(xboot_id, be.boot_id)

    def test_BootEntry_root_opts_no_values(self):
        from boom.bootloader import (
            BOOM_ENTRY_TITLE, BOOM_ENTRY_MACHINE_ID, BOOM_ENTRY_VERSION,
            BOOM_ENTRY_LINUX, BOOM_ENTRY_EFI, BOOM_ENTRY_INITRD,
            BOOM_ENTRY_OPTIONS
        )
        osp = self.test_osp
        xroot_opts = ""

        be = BootEntry(entry_data={BOOM_ENTRY_TITLE: "title",
                                   BOOM_ENTRY_LINUX: "/vmlinuz",
                                   BOOM_ENTRY_MACHINE_ID: "ffffffff",
                                   BOOM_ENTRY_VERSION: "1.1.1",
                                   BOOM_ENTRY_OPTIONS: "root=/dev/sda5 ro"
                       }, allow_no_dev=True)

        self.assertEqual(xroot_opts, be.root_opts)

        bp = BootParams("1.1.1.x86_64", root_device="/dev/sda5")
        be = BootEntry(entry_data={BOOM_ENTRY_TITLE: "title",
                       BOOM_ENTRY_LINUX: "/vmlinuz",
                       BOOM_ENTRY_MACHINE_ID: "ffffffff",
                       BOOM_ENTRY_VERSION: "1.1.1",
                       BOOM_ENTRY_OPTIONS: "root=%{root_device} %{root_opts}"},
                       osprofile=osp, boot_params=bp, allow_no_dev=True)
        self.assertEqual(xroot_opts, be.root_opts)

    # BootEntry properties get/set tests
    # Simple properties: direct set to self._entry_data.
    def test_BootEntry_options_set_get(self):
        bp = BootParams("1.1.1.x86_64", root_device="/dev/sda5")
        be = BootEntry(title="title", machine_id="ffffffff", boot_params=bp,
                       allow_no_dev=True)
        xoptions = "testoptions root=%{root_device}"
        be.options = xoptions
        self.assertEqual(xoptions, be.options)

    def test_BootEntry_linux_set_get(self):
        bp = BootParams("1.1.1.x86_64", root_device="/dev/sda5")
        be = BootEntry(title="title", machine_id="ffffffff", boot_params=bp,
                       allow_no_dev=True)
        xlinux = "/vmlinuz"
        be.linux = xlinux
        self.assertEqual(xlinux, be.linux)

    def test_BootEntry_initrd_set_get(self):
        bp = BootParams("1.1.1.x86_64", root_device="/dev/sda5")
        be = BootEntry(title="title", machine_id="ffffffff", boot_params=bp,
                       allow_no_dev=True)
        xinitrd = "/initrd.img"
        be.initrd = xinitrd
        self.assertEqual(xinitrd, be.initrd)

    def test_BootEntry_efi_set_get(self):
        bp = BootParams("1.1.1.x86_64", root_device="/dev/sda5")
        be = BootEntry(title="title", machine_id="ffffffff", boot_params=bp,
                       allow_no_dev=True)
        xefi = "/some.efi.img"
        be.efi = xefi
        self.assertEqual(xefi, be.efi)

    def test_BootEntry_devicetree_set_get(self):
        bp = BootParams("1.1.1.x86_64", root_device="/dev/sda5")
        be = BootEntry(title="title", machine_id="ffffffff", boot_params=bp,
                       allow_no_dev=True)
        xdevicetree = "/tegra20-paz00.dtb"
        be.devicetree = xdevicetree
        self.assertEqual(xdevicetree, be.devicetree)

    def test_BootEntry_optional_keys(self):
        osp = self.test_osp
        osp.optional_keys = "grub_users grub_arg grub_class"

        bp = BootParams("1.1", lvm_root_lv="vg00/lvol0")
        be = BootEntry(title="title", machine_id="ffffffff",
                       osprofile=osp, boot_params=bp, allow_no_dev=True)
        self.assertEqual(be.root_opts, "rd.lvm.lv=vg00/lvol0")
        self.assertEqual(be.options, "root=/dev/vg00/lvol0 "
                         "rd.lvm.lv=vg00/lvol0 rhgb quiet")

        be.grub_users = "test_user"
        be.grub_arg = "--test-arg"
        be.grub_class = "test_class"

    def test_BootEntry_optional_keys_not_set(self):
        osp = self.test_osp
        osp.optional_keys = ""

        bp = BootParams("1.1", lvm_root_lv="vg00/lvol0")
        be = BootEntry(title="title", machine_id="ffffffff",
                       osprofile=osp, boot_params=bp, allow_no_dev=True)
        self.assertEqual(be.root_opts, "rd.lvm.lv=vg00/lvol0")
        self.assertEqual(be.options, "root=/dev/vg00/lvol0 "
                         "rd.lvm.lv=vg00/lvol0 rhgb quiet")

        with self.assertRaises(ValueError) as cm:
            be.grub_users = "test_user"

    def test_match_OsProfile_to_BootEntry(self):
        from boom.osprofile import OsProfile, load_profiles
        load_profiles()

        xos_id = "6bf746bb7231693b2903585f171e4290ff0602b5"
        bp = BootParams("4.11.5-100.fc24.x86_64", root_device="/dev/sda5")
        be = BootEntry(title="title", machine_id="ffffffff", boot_params=bp,
                       allow_no_dev=True)
        self.assertEqual(be._osp.os_id, xos_id)

    def test_BootEntry__getitem__(self):
        from boom.osprofile import OsProfile, load_profiles
        load_profiles()

        from boom.bootloader import (BOOM_ENTRY_VERSION, BOOM_ENTRY_TITLE,
                                     BOOM_ENTRY_MACHINE_ID, BOOM_ENTRY_LINUX,
                                     BOOM_ENTRY_INITRD, BOOM_ENTRY_OPTIONS,
                                     BOOM_ENTRY_DEVICETREE)
        xtitle = "title"
        xmachine_id = "ffffffff"
        xversion = "4.11.5-100.fc24.x86_64"
        xlinux = "/vmlinuz-4.11.5-100.fc24.x86_64"
        xinitrd = "/initramfs-4.11.5-100.fc24.x86_64.img"
        xoptions = "root=/dev/sda5 ro rhgb quiet"
        xdevicetree = "device.tree"

        bp = BootParams(xversion, root_device="/dev/sda5")
        be = BootEntry(title=xtitle, machine_id=xmachine_id, boot_params=bp,
                       allow_no_dev=True)
        be.devicetree = xdevicetree

        self.assertEqual(be[BOOM_ENTRY_VERSION], "4.11.5-100.fc24.x86_64")
        self.assertEqual(be[BOOM_ENTRY_TITLE], "title")
        self.assertEqual(be[BOOM_ENTRY_MACHINE_ID], "ffffffff")
        self.assertEqual(be[BOOM_ENTRY_LINUX], xlinux)
        self.assertEqual(be[BOOM_ENTRY_INITRD], xinitrd)
        self.assertEqual(be[BOOM_ENTRY_OPTIONS], xoptions)
        self.assertEqual(be[BOOM_ENTRY_DEVICETREE], xdevicetree)

    def test_BootEntry__getitem__bad_key_raises(self):
        from boom.osprofile import OsProfile, load_profiles
        load_profiles()

        bp = BootParams("4.11.5-100.fc24.x86_64", root_device="/dev/sda5")
        be = BootEntry(title="title", machine_id="ffffffff", boot_params=bp)
        with self.assertRaises(TypeError) as cm:
            be[123]

    def test_BootEntry__setitem__(self):
        from boom.osprofile import OsProfile, load_profiles
        load_profiles()

        from boom.bootloader import (BOOM_ENTRY_VERSION, BOOM_ENTRY_TITLE,
                                     BOOM_ENTRY_MACHINE_ID, BOOM_ENTRY_LINUX,
                                     BOOM_ENTRY_INITRD, BOOM_ENTRY_OPTIONS,
                                     BOOM_ENTRY_DEVICETREE)

        xtitle = "title"
        xmachine_id = "ffffffff"
        xversion = "4.11.5-100.fc24.x86_64"
        xlinux = "/vmlinuz-4.11.5-100.fc24.x86_64"
        xinitrd = "/initramfs-4.11.5-100.fc24.x86_64.img"
        xoptions = "root=/dev/sda5 ro rhgb quiet"
        xdevicetree = "device.tree"

        bp = BootParams(xversion, root_device="/dev/sda5")
        be = BootEntry(title="qux", machine_id="11111111", boot_params=bp,
                       allow_no_dev=True)
        be.devicetree = xdevicetree

        be[BOOM_ENTRY_VERSION] = xversion
        be[BOOM_ENTRY_TITLE] = xtitle
        be[BOOM_ENTRY_MACHINE_ID] = xmachine_id
        be[BOOM_ENTRY_LINUX] = xlinux
        be[BOOM_ENTRY_INITRD] = xinitrd
        be[BOOM_ENTRY_DEVICETREE] = xdevicetree

        self.assertEqual(be.version, "4.11.5-100.fc24.x86_64")
        self.assertEqual(be.title, "title")
        self.assertEqual(be.machine_id, "ffffffff")
        self.assertEqual(be.linux, xlinux)
        self.assertEqual(be.initrd, xinitrd)
        self.assertEqual(be.options, xoptions)
        self.assertEqual(be.devicetree, xdevicetree)

    def test_BootEntry__getitem__bad_key_raises(self):
        from boom.osprofile import OsProfile, load_profiles
        load_profiles()

        bp = BootParams("4.11.5-100.fc24.x86_64", root_device="/dev/sda5")
        be = BootEntry(title="title", machine_id="ffffffff", boot_params=bp,
                       allow_no_dev=True)
        with self.assertRaises(TypeError) as cm:
            be[123] = "qux"

    def test_BootEntry_keys(self):
        from boom.osprofile import OsProfile, load_profiles
        load_profiles()

        xkeys = [
            'BOOM_ENTRY_TITLE', 'BOOM_ENTRY_MACHINE_ID',
            'BOOM_ENTRY_ARCHITECTURE', 'BOOM_ENTRY_LINUX', 'BOOM_ENTRY_INITRD',
            'BOOM_ENTRY_OPTIONS', 'BOOM_ENTRY_VERSION'
        ]

        bp = BootParams("4.11.5-100.fc24.x86_64", root_device="/dev/sda5")
        be = BootEntry(title="title", machine_id="ffffffff", boot_params=bp,
                       allow_no_dev=True)

        self.assertEqual(be.keys(), xkeys)

    def test_BootEntry_values(self):
        from boom.osprofile import OsProfile, load_profiles
        load_profiles()

        xvalues = [
            'title',
            'ffffffff',
            'x64',
            '/vmlinuz-4.11.5-100.fc24.x86_64',
            '/initramfs-4.11.5-100.fc24.x86_64.img',
            'root=/dev/sda5 ro rhgb quiet',
            '4.11.5-100.fc24.x86_64'
        ]

        bp = BootParams("4.11.5-100.fc24.x86_64", root_device="/dev/sda5")
        be = BootEntry(title="title", machine_id="ffffffff", boot_params=bp,
                       architecture='x64', allow_no_dev=True)

        # Ignore ordering
        be_set = set(be.values())
        xvalues_set = set(xvalues)
        self.assertEqual(be_set, xvalues_set)

    def test_BootEntry_items(self):
        from boom.osprofile import OsProfile, load_profiles
        load_profiles()

        os_id = "9cb53ddda889d6285fd9ab985a4c47025884999f"
        osp = boom.osprofile.get_os_profile_by_id(os_id)

        xkeys = [
            'BOOM_ENTRY_TITLE', 'BOOM_ENTRY_MACHINE_ID',
            'BOOM_ENTRY_ARCHITECTURE', 'BOOM_ENTRY_LINUX',
            'BOOM_ENTRY_INITRD', 'BOOM_ENTRY_OPTIONS', 'BOOM_ENTRY_VERSION'
        ]

        xvalues = [
            'title',
            'ffffffff',
            '',
            '/vmlinuz-4.11.5-100.fc24.x86_64',
            '/initramfs-4.11.5-100.fc24.x86_64.img',
            'root=/dev/sda5 ro rhgb quiet',
            '4.11.5-100.fc24.x86_64'
        ]

        xitems = list(zip(xkeys, xvalues))
        bp = BootParams("4.11.5-100.fc24.x86_64", root_device="/dev/sda5")
        be = BootEntry(title="title", machine_id="ffffffff", boot_params=bp,
                       osprofile=osp, allow_no_dev=True)

        be_set = set(be.items())
        xitems_set = set(xitems)
        self.assertEqual(be_set, xitems_set)

    def test_BootEntry_eq_no_boot_id(self):
        class NotABootEntry(object):
            i_have_no_boot_id = True
        osp = self.test_osp
        be = self.test_be
        self.assertFalse(be == NotABootEntry())

    def test__add_entry_loads_entries(self):
        boom.bootloader._entries = None
        osp = self.test_osp
        be = self.test_be
        boom.bootloader._add_entry(be)
        self.assertTrue(boom.bootloader._entries)
        self.assertTrue(boom.osprofile._profiles)

    def test__del_entry_deletes_entry(self):
        boom.bootloader.load_entries()
        be = boom.bootloader._entries[0]
        self.assertTrue(be in boom.bootloader._entries)
        boom.bootloader._del_entry(be)
        self.assertFalse(be in boom.bootloader._entries)

    def test_load_entries_loads_profiles(self):
        import boom.osprofile
        boom.osprofile._profiles = []
        boom.osprofile._profiles_by_id = {}
        boom.osprofile._profiles = [boom.osprofile.OsProfile("","","","","")]
        boom.osprofile._profiles_loaded = False
        boom.bootloader.load_entries()
        self.assertTrue(boom.osprofile._profiles)
        self.assertTrue(boom.bootloader._entries)

    def test_find_entries_loads_entries(self):
        boom.bootloader._entries = None
        boom.bootloader.find_entries()
        self.assertTrue(boom.osprofile._profiles)
        self.assertTrue(boom.bootloader._entries)

    def test_find_entries_by_boot_id(self):
        boot_id = "12a2696bf85cc33f42f0449fab5da64dac7aa10a"
        boom.bootloader._entries = None
        bes = boom.bootloader.find_entries(Selection(boot_id=boot_id))
        self.assertEqual(len(bes), 1)

    def test_find_entries_by_title(self):
        title = "Red Hat Enterprise Linux 7.2 (Maipo) 3.10-23.el7"
        boom.bootloader._entries = None
        bes = boom.bootloader.find_entries(Selection(title=title))
        self.assertEqual(len(bes), 1)

    def test_find_entries_by_version(self):
        version = "4.10.17-100.fc24.x86_64"
        boom.bootloader._entries = None
        bes = boom.bootloader.find_entries(Selection(version=version))
        path = boom_entries_path()
        nr = len([p for p in listdir(path) if version in p])
        self.assertEqual(len(bes), nr)

    def test_find_entries_by_root_device(self):
        entries_path = boom_entries_path()
        root_device = "/dev/vg_root/root"
        boom.bootloader._entries = None
        bes = boom.bootloader.find_entries(Selection(root_device=root_device))
        xentries = 0
        for e in listdir(entries_path):
            if e.endswith(".conf"):
                with open(join(entries_path, e)) as f:
                    for l in f.readlines():
                        if root_device in l:
                            xentries +=1
        self.assertEqual(len(bes), xentries)

    def test_find_entries_by_lvm_root_lv(self):
        entries_path = boom_entries_path()
        boom.bootloader._entries = None
        lvm_root_lv = "vg_root/root"
        bes = boom.bootloader.find_entries(Selection(lvm_root_lv=lvm_root_lv))
        xentries = 0
        for e in listdir(entries_path):
            if e.endswith(".conf"):
                with open(join(entries_path, e)) as f:
                    for l in f.readlines():
                        if "rd.lvm.lv=" + lvm_root_lv in l:
                            xentries +=1
        self.assertEqual(len(bes), xentries)

    def test_find_entries_by_btrfs_subvol_id(self):
        entries_path = boom_entries_path()
        boom.bootloader._entries = None
        btrfs_subvol_id = "23"
        nr = 0

        # count entries
        for p in listdir(entries_path):
            with open(join(entries_path, p), "r") as f:
                for l in f.readlines():
                    if "subvolid=23" in l:
                        nr += 1

        select = Selection(btrfs_subvol_id=btrfs_subvol_id)
        bes = boom.bootloader.find_entries(select)
        self.assertEqual(len(bes), nr)

    def test_find_entries_by_btrfs_subvol_path(self):
        entries_path = boom_entries_path()
        btrfs_subvol_path = "/snapshot/today"
        boom.bootloader._entries = None
        select = Selection(btrfs_subvol_path=btrfs_subvol_path)
        bes = boom.bootloader.find_entries(select)
        nr = 0

        # count entries
        for p in listdir(entries_path):
            with open(join(entries_path, p), "r") as f:
                for l in f.readlines():
                    if "/snapshot/today" in l:
                        nr += 1

        self.assertEqual(len(bes), nr)

    def test_delete_unwritten_BootEntry_raises(self):
        bp = BootParams("4.11.5-100.fc24.x86_64", root_device="/dev/sda5")
        be = BootEntry(title="title", machine_id="ffffffff", boot_params=bp,
                      allow_no_dev=True)
        with self.assertRaises(ValueError) as cm:
            be.delete_entry()

    def test_delete_BootEntry_deletes(self):
        bp = BootParams("4.11.5-100.fc24.x86_64", root_device="/dev/sda5")
        be = BootEntry(title="title", machine_id="ffffffff", boot_params=bp,
                       allow_no_dev=True)
        be.write_entry()
        be.delete_entry()
        self.assertFalse(exists(be._entry_path))

    def test_BootEntry_expanded_vars(self):
        # A boot entry with Grub2 environment variable references
        be = find_entries(Selection(boot_id="526f54a"))[0]
        xstr = ("title grub args\n" +
                "machine-id 653b444d513a43239c37deae4f5fe644\n" +
                "version 5.4.7-100.fc30.x86_64\n" +
                "linux /vmlinuz-5.4.7-100.fc30.x86_64\n" +
                "initrd /initramfs-5.4.7-100.fc30.x86_64.img\n" +
                "options root=/dev/vg_hex/root ro rd.lvm.lv=vg_hex/root\n" +
                "grub_users root\n"
                "grub_arg kernel\n"
                "grub_class --unrestricted")
        self.assertEqual(xstr, be.expanded())

    def test_BootEntry_expanded_no_vars(self):
        # A boot entry with no Grub2 environment variable references
        be = find_entries(Selection(boot_id="b3389d2"))[0]
        xstr = str(be)
        self.assertEqual(xstr, be.expanded())

class BootLoaderBasicTests(unittest.TestCase):
    def setUp(self):
        log.debug("Preparing %s", self._testMethodName)

    def tearDown(self):
        log.debug("Tearing down %s", self._testMethodName)

    def test_import(self):
        import boom.bootloader


class BootLoaderTests(unittest.TestCase):
    """Class for bootloader module-level tests.
    """

    # Main BLS loader directory for sandbox
    loader_path = join(BOOT_ROOT_TEST, "loader")

    # Main boom configuration path for sandbox
    boom_path = join(BOOT_ROOT_TEST, "boom")

    # Test fixture init/cleanup
    def setUp(self):
        """setUp()
            Set up a test fixture for the BootEntryTests class.

            Defines standard OsProfile, BootParams, and BootEntry
            objects for use in these tests.
        """
        log.debug("Preparing %s", self._testMethodName)

        reset_sandbox()

        # Sandbox paths
        boot_sandbox = join(SANDBOX_PATH, "boot")
        boom_sandbox = join(SANDBOX_PATH, "boot/boom")
        loader_sandbox = join(SANDBOX_PATH, "boot/loader")

        # Initialise sandbox from main
        makedirs(boot_sandbox)
        shutil.copytree(self.boom_path, boom_sandbox)
        shutil.copytree(self.loader_path, loader_sandbox)

        # Set boom paths
        boom.set_boot_path(boot_sandbox)

        # Load test OsProfile and BootEntry data
        load_profiles()
        load_entries()

    def tearDown(self):
        """tearDown()
            Tear down the standard test profiles and entries used by the
            BootEntryTests class.
        """
        log.debug("Tearing down %s", self._testMethodName)

        # Drop any in-memory entries and profiles modified by tests
        drop_entries()
        drop_profiles()

        # Clear sandbox data
        rm_sandbox()
        reset_boom_paths()

    # Module tests

    def _nr_machine_id(self, machine_id):
        entries = boom.bootloader._entries
        match = [e for e in entries if e.machine_id == machine_id]
        return len(match)

    # Profile store tests

    def test_load_entries(self):
        # Test that loading the test entries succeeds.
        boom.bootloader.load_entries()
        entry_count = 0
        for entry in listdir(boom_entries_path()):
            if entry.endswith(".conf"):
                entry_count += 1
        self.assertEqual(len(boom.bootloader._entries), entry_count)

    def test_load_entries_with_machine_id(self):
        # Test that loading the test entries by machine_id succeeds,
        # and returns the expected number of profiles.
        machine_id = "ffffffff"
        boom.bootloader.load_entries(machine_id=machine_id)
        entry_count = 0
        for entry in listdir(boom_entries_path()):
            if entry.startswith(machine_id) and entry.endswith(".conf"):
                entry_count += 1
        self.assertEqual(len(boom.bootloader._entries), entry_count)

    def test_write_entries(self):
        boom.bootloader.load_entries()
        boom.bootloader.write_entries()

    def test_find_boot_entries(self):
        boom.bootloader.load_entries()

        find_entries = boom.bootloader.find_entries

        entries = find_entries()
        self.assertEqual(len(entries), len(boom.bootloader._entries))

        entries = find_entries(Selection(machine_id="ffffffff"))
        self.assertEqual(len(entries), self._nr_machine_id("ffffffff"))

    def test_Selection_no_osp_match(self):
        s = Selection(os_id="12345")
        self.assertFalse(find_entries(s))

@unittest.skipIf(not have_root(), "requires root privileges")
class BootLoaderTestsCheckRoot(unittest.TestCase):
    """Base class for BootLoaderTests that validate a chosen root
        device.

        Subclasses define the lists of devices that must be present
        or absent, and the superclass initialises these in the setUp()
        and tearDown() methods.

        The format of the ``add_dev`` and ``del_dev`` lists is a
        tuple ``(devname, type)``, where ``type`` is a string type
        containing the character 'c' (char), or 'b' (block).

        Device types in the del_devs list are currently ignored.

        Tests using this base class require root privileges in order
        to manipulate device nodes in the test sandbox. These tests
        are automatically skipped if the suite is run as a normal
        user.
    """

    add_devs = []
    del_devs = []

    def setUp(self):
        log.debug("Preparing %s", self._testMethodName)
        reset_sandbox()
        dev_path = join(SANDBOX_PATH, "dev")
        makedirs(dev_path)
        for dev in self.add_devs:
            mode = 0o600
            if dev[1] == 'b':
                mode |= S_IFBLK
            if dev[1] == 'c':
                mode |= S_IFCHR
            mknod(join(dev_path, dev[0]), mode)
        for dev in self.del_devs:
            try:
                unlink(join(dev_path, dev[0]))
            except OSError as e:
                if e.errno != 2:
                    raise

    def tearDown(self):
        log.debug("Tearing down %s", self._testMethodName)

        rm_sandbox()


class BootLoaderTestsCheckRootReal(BootLoaderTestsCheckRoot):
    """Check root device with valid block device node.
    """
    add_devs = [("sda", "b")]
    def test_check_root_device_real(self):
        # Real block device node
        boom.bootloader.check_root_device("tests/sandbox/dev/sda")


class BootLoaderTestsCheckRootNonex(BootLoaderTestsCheckRoot):
    """Check root device with invalid block device node.
    """
    del_devs = [("sdb", "b")]
    def test_check_root_device_nonex(self):
        # Non-existent device node
        with self.assertRaises(BoomRootDeviceError) as cm:
            boom.bootloader.check_root_device("tests/dev/sdb")


class BootLoaderTestsCheckRootNonblock(BootLoaderTestsCheckRoot):
    """Check root device with non-block device node.
    """
    add_devs = [("null", "c")]
    def test_check_root_device_nonblock(self):
        # Non-existent device node
        with self.assertRaises(BoomRootDeviceError) as cm:
            boom.bootloader.check_root_device("tests/dev/null")


# vim: set et ts=4 sw=4 :

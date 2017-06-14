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
from os import listdir
from os.path import exists, join

log = logging.getLogger()
log.level = logging.DEBUG
log.addHandler(logging.FileHandler("test.log"))

# Override default BOOM_ROOT and BOOT_ROOT
import boom
BOOT_ROOT_TEST = "./tests"
BOOM_ROOT_TEST = BOOT_ROOT_TEST + "/boom"
boom.BOOM_ROOT = BOOM_ROOT_TEST
boom.BOOT_ROOT = BOOT_ROOT_TEST

import boom.bootloader
from boom.osprofile import OsProfile

BootEntry = boom.bootloader.BootEntry
BootParams = boom.bootloader.BootParams


class BootParamsTests(unittest.TestCase):
    def test_BootParams_no_version_raises(self):
        with self.assertRaises(ValueError) as cm:
            # A version string is required
            bp = BootParams(None)

    def test_BootParams_no_root_device_raises(self):
        with self.assertRaises(ValueError) as cm:
            # An implicit or explicit root_device is required
            bp = BootParams("1.1.1.x86_64")

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


class BootEntryTests(unittest.TestCase):

    test_version = "1.1.1-1.qux.x86_64"
    test_lvm2_root_device = "/dev/vg00/lvol0"
    test_lvm_root_lv = "vg00/lvol0"
    test_btrfs_root_device = "/dev/sda5"
    test_btrfs_subvol_path = "/snapshots/snap1"
    test_btrfs_subvol_id = "232"

    # Helper routines

    def _get_test_OsProfile(self):
        osp = OsProfile(name="Distribution", short_name="distro",
                        version="1 (Workstation Edition)", version_id="1")
        osp.kernel_path = "/"
        osp.initramfs_path = "/"
        osp.uname_pattern = "di1"
        osp.kernel_pattern = "vmlinuz-%{version}"
        osp.initramfs_pattern = "initramfs-%{version}.img"
        osp.root_opts_lvm2 = "rd.lvm.lv=%{lvm_root_lv}"
        osp.root_opts_btrfs = "rootflags=%{btrfs_subvolume}"
        osp.options = "root=%{root_device} %{root_opts} rhgb quiet"
        return osp

    def _get_test_BootEntry(self, osp):
        return BootEntry(title="title", machine_id="ffffffff", osprofile=osp)

    def get_test_lvm2_BootEntry(self, osp):
        be = self._get_test_BootEntry(osp)
        be.version = self.test_version
        be.root_device = self.test_lvm2_root_device
        be.lvm_root_lv = self.test_lvm_root_lv
        return be

    def get_test_btrfs_path_BootEntry(self):
        be = self._get_test_BootEntry(osp)
        be.version = self.test_version
        be.root_device = self.test_btrfs_root_device
        be.btrfs_subvol_path = self.test_btrfs_subvol_path
        return be

    def get_test_btrfs_id_BootEntry(self):
        be = self._get_test_BootEntry(osp)
        be.version = self.test_version
        be.root_device = self.test_btrfs_root_device
        be.btrfs_subvol_id = self.test_btrfs_subvol_id
        return be

    # BootEntry tests

    def test_BootEntry__str__(self):
        be = BootEntry(title="title", machine_id="ffffffff", osprofile=None)
        xstr = 'title title\nmachine-id ffffffff'
        self.assertEqual(str(be), xstr)

    def test_BootEntry__repr__(self):
        be = BootEntry(title="title", machine_id="ffffffff", osprofile=None)
        xrepr = ('BootEntry(entry_data={BOOT_TITLE: "title", '
                 'BOOT_MACHINE_ID: "ffffffff"})')
        self.assertEqual(repr(be), xrepr)

    def test_BootEntry(self):
        # Test BootEntry init from kwargs
        with self.assertRaises(ValueError) as cm:
            be = BootEntry(title=None, machine_id="ffffffff", osprofile=None)

        with self.assertRaises(ValueError) as cm:
            be = BootEntry(title="title", machine_id=None, osprofile=None)

        with self.assertRaises(ValueError) as cm:
            be = BootEntry(title=None, machine_id=None, osprofile=None)

        be = BootEntry(title="title", machine_id="ffffffff")

        self.assertTrue(be)

    def test_BootEntry_from_entry_data(self):
        # Pull in all the BOOT_* constants to the local namespace.
        from boom.bootloader import (
            BOOT_TITLE, BOOT_MACHINE_ID, BOOT_VERSION,
            BOOT_LINUX, BOOT_EFI, BOOT_INITRD, BOOT_OPTIONS
        )
        with self.assertRaises(ValueError) as cm:
            # Missing BOOT_TITLE
            be = BootEntry(entry_data={BOOT_MACHINE_ID: "ffffffff",
                           BOOT_VERSION: "1.1.1", BOOT_LINUX: "/vmlinuz-1.1.1",
                           BOOT_INITRD: "/initramfs-1.1.1.img",
                           BOOT_OPTIONS: "root=%{root_device} %{root_opts}"})

        # Valid entry
        be = BootEntry(entry_data={BOOT_TITLE: "title",
                       BOOT_MACHINE_ID: "ffffffff",
                       BOOT_VERSION: "1.1.1", BOOT_LINUX: "/vmlinuz-1.1.1",
                       BOOT_INITRD: "/initramfs-1.1.1.img",
                       BOOT_OPTIONS: "root=%{root_device} %{root_opts}"})

        with self.assertRaises(ValueError) as cm:
            # Missing BOOT_LINUX or BOOT_EFI
            be = BootEntry(entry_data={BOOT_TITLE: "title",
                           BOOT_MACHINE_ID: "ffffffff", BOOT_VERSION: "1.1.1",
                           BOOT_INITRD: "/initramfs-1.1.1.img",
                           BOOT_OPTIONS: "root=%{root_device} %{root_opts}"})

        # Valid Linux entry
        be = BootEntry(entry_data={BOOT_TITLE: "title",
                       BOOT_LINUX: "/vmlinuz",
                       BOOT_MACHINE_ID: "ffffffff", BOOT_VERSION: "1.1.1",
                       BOOT_OPTIONS: "root=%{root_device} %{root_opts}"})

        # Valid EFI entry
        be = BootEntry(entry_data={BOOT_TITLE: "title",
                       BOOT_EFI: "/some.efi.thing",
                       BOOT_MACHINE_ID: "ffffffff", BOOT_VERSION: "1.1.1",
                       BOOT_OPTIONS: "root=%{root_device} %{root_opts}"})

    def test_BootEntry_with_boot_params(self):
        from boom.bootloader import (
            BOOT_TITLE, BOOT_MACHINE_ID, BOOT_VERSION,
            BOOT_LINUX, BOOT_EFI, BOOT_INITRD, BOOT_OPTIONS
        )
        bp = BootParams(version="2.2.2", lvm_root_lv="vg00/lvol0")
        be = BootEntry(entry_data={BOOT_TITLE: "title",
                       BOOT_MACHINE_ID: "ffffffff",
                       BOOT_VERSION: "1.1.1", BOOT_LINUX: "/vmlinuz-1.1.1",
                       BOOT_INITRD: "/initramfs-1.1.1.img",
                       BOOT_OPTIONS: "root=%{root_device} %{root_opts}"},
                       boot_params=bp)
        # boot_params overrides BootEntry
        self.assertEqual(be.version, bp.version)
        self.assertNotEqual(be.version, "1.1.1")

    def test_BootEntry_empty_osprofile(self):
        # Assert that key properties of a BootEntry with no attached osprofile
        # return None.
        from boom.bootloader import (
            BOOT_TITLE, BOOT_MACHINE_ID, BOOT_VERSION,
            BOOT_LINUX, BOOT_EFI, BOOT_INITRD, BOOT_OPTIONS
        )
        bp = BootParams(version="2.2.2", lvm_root_lv="vg00/lvol0")
        be = BootEntry(entry_data={BOOT_TITLE: "title",
                       BOOT_MACHINE_ID: "ffffffff",
                       BOOT_LINUX: "/vmlinuz",
                       BOOT_VERSION: "1.1.1"}, boot_params=bp)

        self.assertEqual(be.options, None)

    def test_BootEntry_empty_format_key(self):
        # Assert that key properties of a BootEntry with empty format keys
        # return the empty string.
        from boom.bootloader import (
            BOOT_TITLE, BOOT_MACHINE_ID, BOOT_VERSION,
            BOOT_LINUX, BOOT_EFI, BOOT_INITRD, BOOT_OPTIONS
        )

        osp = self._get_test_OsProfile()
        # Clear the OsProfile.options format key
        osp.options = ""

        bp = BootParams(version="2.2.2", lvm_root_lv="vg00/lvol0")
        be = BootEntry(entry_data={BOOT_TITLE: "title",
                       BOOT_MACHINE_ID: "ffffffff",
                       BOOT_VERSION: "1.1.1", BOOT_LINUX: "/vmlinuz-1.1.1",
                       BOOT_INITRD: "/initramfs-1.1.1.img"},
                       osprofile=osp, boot_params=bp)

        self.assertEqual(be.options, "")

    def test_BootEntry_write(self):
        osp = self._get_test_OsProfile()
        be = BootEntry(title="title", machine_id="ffffffff", osprofile=osp)
        be.version = "1.1.1"
        be.lvm_root_lv = "vg00/lvol0"
        be.root_device = "/dev/vg00/lvol0"

        # write entry (FIXME: and verify by re-loading)
        be.write_entry()

    def test_BootEntry_profile_kernel_version(self):
        osp = self._get_test_OsProfile()
        be = BootEntry(title="title", machine_id="ffffffff", osprofile=osp)
        be.version = "1.1.1-17.qux.x86_64"
        self.assertEqual(be.linux, "/vmlinuz-1.1.1-17.qux.x86_64")
        self.assertEqual(be.initrd, "/initramfs-1.1.1-17.qux.x86_64.img")

    def test_BootEntry_profile_root_lvm2(self):
        osp = self._get_test_OsProfile()
        bp = BootParams("1.1", lvm_root_lv="vg00/lvol0")
        be = BootEntry(title="title", machine_id="ffffffff",
                       osprofile=osp, boot_params=bp)
        self.assertEqual(be.root_opts, "rd.lvm.lv=vg00/lvol0")
        self.assertEqual(be.options, "root=/dev/vg00/lvol0 "
                         "rd.lvm.lv=vg00/lvol0 rhgb quiet")

    def test_BootEntry_profile_root_btrfs_id(self):
        osp = self._get_test_OsProfile()
        bp = BootParams("1.1", root_device="/dev/sda5", btrfs_subvol_id="232")
        be = BootEntry(title="title", machine_id="ffffffff",
                       osprofile=osp, boot_params=bp)
        self.assertEqual(be.root_opts, "rootflags=subvolid=232")
        self.assertEqual(be.options, "root=/dev/sda5 "
                         "rootflags=subvolid=232 rhgb quiet")

    def test_BootEntry_profile_root_btrfs_path(self):
        osp = self._get_test_OsProfile()
        bp = BootParams("1.1", root_device="/dev/sda5",
                        btrfs_subvol_path="/snapshots/20170523-1")
        be = BootEntry(title="title", machine_id="ffffffff",
                       osprofile=osp, boot_params=bp)
        self.assertEqual(be.root_opts,
                         "rootflags=subvol=/snapshots/20170523-1")
        self.assertEqual(be.options, "root=/dev/sda5 "
                         "rootflags=subvol=/snapshots/20170523-1 rhgb quiet")

    def test_BootEntry_boot_id(self):
        xboot_id = '043eddada5e0e59986e979f5930a4ee2c2a94eb4'
        bp = BootParams("1.1.1.x86_64", root_device="/dev/sda5")
        be = BootEntry(title="title", machine_id="ffffffff", boot_params=bp)
        self.assertEqual(xboot_id, be.boot_id)

    def test_BootEntry_root_opts_no_values(self):
        from boom.bootloader import (
            BOOT_TITLE, BOOT_MACHINE_ID, BOOT_VERSION,
            BOOT_LINUX, BOOT_EFI, BOOT_INITRD, BOOT_OPTIONS
        )
        osp = self._get_test_OsProfile()
        xroot_opts = ""

        be = BootEntry(entry_data={BOOT_TITLE: "title",
                       BOOT_LINUX: "/vmlinuz",
                       BOOT_MACHINE_ID: "ffffffff", BOOT_VERSION: "1.1.1",
                       BOOT_OPTIONS: "root=%{root_device} %{root_opts}"})
        self.assertEqual(xroot_opts, be.root_opts)

        bp = BootParams("1.1.1.x86_64", root_device="/dev/sda5")
        be = BootEntry(entry_data={BOOT_TITLE: "title",
                       BOOT_LINUX: "/vmlinuz",
                       BOOT_MACHINE_ID: "ffffffff", BOOT_VERSION: "1.1.1",
                       BOOT_OPTIONS: "root=%{root_device} %{root_opts}"},
                       osprofile=osp, boot_params=bp)
        self.assertEqual(xroot_opts, be.root_opts)

    # BootEntry properties get/set tests
    # Simple properties: direct set to self._entry_data.
    def test_BootEntry_options_set_get(self):
        bp = BootParams("1.1.1.x86_64", root_device="/dev/sda5")
        be = BootEntry(title="title", machine_id="ffffffff", boot_params=bp)
        xoptions = "testoptions root=%{root_device}"
        be.options = xoptions
        self.assertEqual(xoptions, be.options)

    def test_BootEntry_linux_set_get(self):
        bp = BootParams("1.1.1.x86_64", root_device="/dev/sda5")
        be = BootEntry(title="title", machine_id="ffffffff", boot_params=bp)
        xlinux = "/vmlinuz"
        be.linux = xlinux
        self.assertEqual(xlinux, be.linux)

    def test_BootEntry_initrd_set_get(self):
        bp = BootParams("1.1.1.x86_64", root_device="/dev/sda5")
        be = BootEntry(title="title", machine_id="ffffffff", boot_params=bp)
        xinitrd = "/initrd.img"
        be.initrd = xinitrd
        self.assertEqual(xinitrd, be.initrd)

    def test_BootEntry_efi_set_get(self):
        bp = BootParams("1.1.1.x86_64", root_device="/dev/sda5")
        be = BootEntry(title="title", machine_id="ffffffff", boot_params=bp)
        xefi = "/some.efi.img"
        be.efi = xefi
        self.assertEqual(xefi, be.efi)

    def test_BootEntry_devicetree_set_get(self):
        bp = BootParams("1.1.1.x86_64", root_device="/dev/sda5")
        be = BootEntry(title="title", machine_id="ffffffff", boot_params=bp)
        xdevicetree = "/tegra20-paz00.dtb"
        be.devicetree = xdevicetree
        self.assertEqual(xdevicetree, be.devicetree)

    def test_match_OsProfile_to_BootEntry(self):
        from boom.osprofile import OsProfile, load_profiles
        load_profiles()

        bp = BootParams("4.11.5-100.fc24.x86_64", root_device="/dev/sda5")
        be = BootEntry(title="title", machine_id="ffffffff", boot_params=bp)
        self.assertEqual(be._osp.os_id, "6bf746bb7231693b2903585f171e4290ff0602b5")

    def test_BootEntry__getitem__(self):
        from boom.osprofile import OsProfile, load_profiles
        load_profiles()

        from boom.bootloader import (BOOT_VERSION, BOOT_TITLE, BOOT_MACHINE_ID,
                                     BOOT_LINUX, BOOT_INITRD, BOOT_OPTIONS,
                                     BOOT_DEVICETREE)
        xtitle = "title"
        xmachine_id = "ffffffff"
        xversion = "4.11.5-100.fc24.x86_64"
        xlinux = "/vmlinuz-4.11.5-100.fc24.x86_64"
        xinitrd = "/initramfs-4.11.5-100.fc24.x86_64.img"
        xoptions = "root=/dev/sda5 ro  rhgb quiet"
        xdevicetree = "device.tree"

        bp = BootParams(xversion, root_device="/dev/sda5")
        be = BootEntry(title=xtitle, machine_id=xmachine_id, boot_params=bp)
        be.devicetree = xdevicetree

        self.assertEqual(be[BOOT_VERSION], "4.11.5-100.fc24.x86_64")
        self.assertEqual(be[BOOT_TITLE], "title")
        self.assertEqual(be[BOOT_MACHINE_ID], "ffffffff")
        self.assertEqual(be[BOOT_LINUX], xlinux)
        self.assertEqual(be[BOOT_INITRD], xinitrd)
        self.assertEqual(be[BOOT_OPTIONS], xoptions)
        self.assertEqual(be[BOOT_DEVICETREE], xdevicetree)

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

        from boom.bootloader import (BOOT_VERSION, BOOT_TITLE, BOOT_MACHINE_ID,
                                     BOOT_LINUX, BOOT_INITRD, BOOT_OPTIONS,
                                     BOOT_DEVICETREE)
        xtitle = "title"
        xmachine_id = "ffffffff"
        xversion = "4.11.5-100.fc24.x86_64"
        xlinux = "/vmlinuz-4.11.5-100.fc24.x86_64"
        xinitrd = "/initramfs-4.11.5-100.fc24.x86_64.img"
        xoptions = "root=/dev/sda5 ro  rhgb quiet"
        xdevicetree = "device.tree"

        bp = BootParams(xversion, root_device="/dev/sda5")
        be = BootEntry(title="qux", machine_id="11111111", boot_params=bp)
        be.devicetree = xdevicetree

        be[BOOT_VERSION] = xversion
        be[BOOT_TITLE] = xtitle
        be[BOOT_MACHINE_ID] = xmachine_id
        be[BOOT_LINUX] = xlinux
        be[BOOT_INITRD] = xinitrd
        be[BOOT_DEVICETREE] = xdevicetree

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
        be = BootEntry(title="title", machine_id="ffffffff", boot_params=bp)
        with self.assertRaises(TypeError) as cm:
            be[123] = "qux"

    def test_BootEntry_keys(self):
        from boom.osprofile import OsProfile, load_profiles
        load_profiles()

        xkeys = ['BOOT_TITLE', 'BOOT_MACHINE_ID', 'BOOT_LINUX', 'BOOT_INITRD',
                 'BOOT_OPTIONS', 'BOOT_VERSION']

        bp = BootParams("4.11.5-100.fc24.x86_64", root_device="/dev/sda5")
        be = BootEntry(title="title", machine_id="ffffffff", boot_params=bp)

        self.assertEqual(be.keys(), xkeys)

    def test_BootEntry_values(self):
        from boom.osprofile import OsProfile, load_profiles
        load_profiles()

        xvalues = [
            'title',
            'ffffffff',
            '/vmlinuz-4.11.5-100.fc24.x86_64',
            '/initramfs-4.11.5-100.fc24.x86_64.img',
            'root=/dev/sda5 ro  rhgb quiet',
            '4.11.5-100.fc24.x86_64'
        ]

        bp = BootParams("4.11.5-100.fc24.x86_64", root_device="/dev/sda5")
        be = BootEntry(title="title", machine_id="ffffffff", boot_params=bp)

        self.assertEqual(be.values(), xvalues)

    def test_BootEntry_items(self):
        from boom.osprofile import OsProfile, load_profiles
        load_profiles()

        xkeys = ['BOOT_TITLE', 'BOOT_MACHINE_ID', 'BOOT_LINUX', 'BOOT_INITRD',
                 'BOOT_OPTIONS', 'BOOT_VERSION']

        xvalues = [
            'title',
            'ffffffff',
            '/vmlinuz-4.11.5-100.fc24.x86_64',
            '/initramfs-4.11.5-100.fc24.x86_64.img',
            'root=/dev/sda5 ro  rhgb quiet',
            '4.11.5-100.fc24.x86_64'
        ]

        xitems = zip(xkeys, xvalues)
        bp = BootParams("4.11.5-100.fc24.x86_64", root_device="/dev/sda5")
        be = BootEntry(title="title", machine_id="ffffffff", boot_params=bp)

        self.assertEqual(be.items(), xitems)

    def test__add_entry_loads_entries(self):
        boom.bootloader._entries = None
        osp = self._get_test_OsProfile()
        be = self._get_test_BootEntry(osp)
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
        boom.osprofile._profiles = None
        boom.bootloader.load_entries()
        self.assertTrue(boom.osprofile._profiles)
        self.assertTrue(boom.bootloader._entries)

    def test_find_entries_loads_entries(self):
        boom.bootloader._entries = None
        boom.bootloader.find_entries()
        self.assertTrue(boom.osprofile._profiles)
        self.assertTrue(boom.bootloader._entries)

    def test_find_entries_by_boot_id(self):
        boot_id = "58700f7f7cfd6f31a3f5c2ae908608e1fe34b1cc"
        boom.bootloader._entries = None
        bes = boom.bootloader.find_entries(boot_id=boot_id)
        self.assertEqual(len(bes), 1)

    def test_find_entries_by_title(self):
        title = "Fedora (4.11.5-100.fc24.x86_64) 24 (Workstation Edition)"
        boom.bootloader._entries = None
        bes = boom.bootloader.find_entries(title=title)
        self.assertEqual(len(bes), 1)

    def test_find_entries_by_version(self):
        version = "4.10.17-100.fc24.x86_64"
        boom.bootloader._entries = None
        bes = boom.bootloader.find_entries(version=version)
        self.assertEqual(len(bes), 1)

    def test_find_entries_by_root_device(self):
        root_device = "/dev/vg_root/root"
        boom.bootloader._entries = None
        bes = boom.bootloader.find_entries(root_device=root_device)
        self.assertEqual(len(bes), 1)

    def test_find_entries_by_lvm_root_lv(self):
        lvm_root_lv = "vg_root/root"
        boom.bootloader._entries = None
        bes = boom.bootloader.find_entries(lvm_root_lv=lvm_root_lv)
        self.assertEqual(len(bes), 1)

    def test_find_entries_by_btrfs_subvol_id(self):
        btrfs_subvol_id = "23"
        boom.bootloader._entries = None
        bes = boom.bootloader.find_entries(btrfs_subvol_id=btrfs_subvol_id)
        self.assertEqual(len(bes), 2)

    def test_find_entries_by_btrfs_subvol_path(self):
        btrfs_subvol_path = "/snapshot/today"
        boom.bootloader._entries = None
        bes = boom.bootloader.find_entries(btrfs_subvol_path=btrfs_subvol_path)
        self.assertEqual(len(bes), 1)

    def test_delete_unwritten_BootEntry_raises(self):
        bp = BootParams("4.11.5-100.fc24.x86_64", root_device="/dev/sda5")
        be = BootEntry(title="title", machine_id="ffffffff", boot_params=bp)
        with self.assertRaises(ValueError) as cm:
            be.delete_entry()

    def test_delete_BootEntry_deletes(self):
        bp = BootParams("4.11.5-100.fc24.x86_64", root_device="/dev/sda5")
        be = BootEntry(title="title", machine_id="ffffffff", boot_params=bp)
        be.write_entry()
        be.delete_entry()
        self.assertFalse(exists(be._entry_path))


class BootLoaderTests(unittest.TestCase):
    # Module tests
    def test_import(self):
        import boom.bootloader

    def _nr_machine_id(self, machine_id):
        entries = boom.bootloader._entries
        match = [e for e in entries if e.machine_id == machine_id]
        return len(match)

    # Profile store tests

    def test_load_entries(self):
        # Test that loading the test entries succeeds.
        boom.bootloader.load_entries()
        entry_count = 0
        for entry in listdir(boom.bootloader.BOOT_ENTRIES_PATH):
            if entry.endswith(".conf"):
                entry_count += 1
        self.assertEqual(len(boom.bootloader._entries), entry_count)

    def test_load_entries_with_machine_id(self):
        # Test that loading the test entries by machine_id succeeds,
        # and returns the expected number of profiles.
        machine_id = "ffffffff"
        boom.bootloader.load_entries(machine_id=machine_id)
        entry_count = 0
        for entry in listdir(boom.bootloader.BOOT_ENTRIES_PATH):
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

        entries = find_entries(machine_id="ffffffff")
        self.assertEqual(len(entries), self._nr_machine_id("ffffffff"))

# vim: set et ts=4 sw=4 :

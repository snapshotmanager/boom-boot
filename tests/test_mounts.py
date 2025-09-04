# Copyright Red Hat
#
# tests/test_mounts.py - Boom mount helper tests.
#
# This file is part of the boom project.
#
# SPDX-License-Identifier: Apache-2.0
import unittest
import logging
from sys import stdout
from os import listdir, makedirs, unlink
from os.path import abspath, basename, dirname, exists, join
from io import StringIO
from glob import glob
import shutil
import re

log = logging.getLogger()

from boom import *
import boom.mounts
from boom.mounts import *

from tests import *

orig_boot_path = get_boot_path()

BOOT_ROOT_TEST = abspath("./tests")


class MountsHelperTests(unittest.TestCase):
    """Test internal boom.mounts helpers. Cases in this class must
        not modify on-disk state and do not use a unique test
        fixture.
    """
    def setUp(self):
        log.info("Preparing %s", self._testMethodName)
        set_boot_path(BOOT_ROOT_TEST)

    def tearDown(self):
        log.info("Tearing down %s", self._testMethodName)
        set_boot_path(orig_boot_path)

    def test_parse_mount_units(self):
        mount_list = [
            "/dev/test/var:/var:xfs:defaults",
            "UUID=b0ebd35b-3956-4b17-bd07-f38dfea021a7:/boot:xfs:rw,x-foo=bar",
            "LABEL=quux:/boot:xfs:rw,x-foo=bar",
            "PARTUUID=7b23f5bd-4f12-48e1-8ea4-70b30df7e540:/boot:xfs:rw,x-bar=baz",
            "PARTLABEL=quux:/boot:xfs:rw,x-foo=bar",
            "/dev/test/var:/var:xfs",
        ]
        xmount_str = [
            "systemd.mount-extra=/dev/test/var:/var:xfs:defaults",
            "systemd.mount-extra=UUID=b0ebd35b-3956-4b17-bd07-f38dfea021a7:/boot:xfs:rw,x-foo=bar",
            "systemd.mount-extra=LABEL=quux:/boot:xfs:rw,x-foo=bar",
            "systemd.mount-extra=PARTUUID=7b23f5bd-4f12-48e1-8ea4-70b30df7e540:/boot:xfs:rw,x-bar=baz",
            "systemd.mount-extra=PARTLABEL=quux:/boot:xfs:rw,x-foo=bar",
            "systemd.mount-extra=/dev/test/var:/var:xfs:defaults",
        ]

        for mount, xmount in zip(mount_list, xmount_str):
            self.assertEqual(parse_mount_units([mount])[0], xmount)

    def test_parse_mount_units_bad_spec(self):
        mount_list = [
            "/dev:",
            "/dev/vda2:quux:xfs:ro",
            "/dev/sda5:/foo:ext4:defaults:0:0",
            "/dev/sda5:    :ext4:defaults",
            "         :/foo:ext4:defaults",
            "/dev/vda1:/mnt:xfs:  ",
            "::::",
            "    "
        ]
        for mount in mount_list:
            with self.subTest(mount=mount):
                with self.assertRaises(BoomMountError):
                    parse_mount_units([mount])

    def test_parse_swap_units(self):
        swap_list = ["/dev/test/var:defaults", "/dev/sda5:pri=1"]
        xswap_str = ["systemd.swap-extra=/dev/test/var:defaults",
                     "systemd.swap-extra=/dev/sda5:pri=1"]
        for swap, xswap in zip(swap_list, xswap_str):
            self.assertEqual(parse_swap_units([swap]), [xswap])

    def test_parse_swap_units_bad_spec(self):
        swap_list = [
            "foobar",
            ":foobar",
            "/dev/rhel/root:",
            " /dev/sda1 : ",
            " :defaults ",
            "::",
            "   "
        ]
        for swap in swap_list:
            with self.subTest(swap=swap):
                with self.assertRaises(BoomMountError):
                    parse_swap_units([swap])

    @unittest.skipIf(not have_root_lv(), "requires root LV")
    def test__detect_fstype(self):
        root_device = f"/dev/{get_root_lv()}"
        fstype = boom.mounts._detect_fstype(root_device)
        self.assertIsNotNone(fstype)
        self.assertRegex(fstype, r"^[A-Za-z0-9._+-]+$")

    @unittest.skipIf(not have_root_lv(), "requires root LV")
    def test_parse_mount_units_no_fstype(self):
        root_device = f"/dev/{get_root_lv()}"
        mount_list = [f"{root_device}:/somewhere"]
        fstype = boom.mounts._detect_fstype(root_device)
        xunit = f"systemd.mount-extra={root_device}:/somewhere:{fstype}:defaults"

        unit = parse_mount_units(mount_list)[0]

        self.assertEqual(unit, xunit)

# vim: set et ts=4 sw=4 :

# Copyright Red Hat
#
# tests/test_lvm2.py - Boom LVM2 integration tests.
#
# This file is part of the boom project.
#
# SPDX-License-Identifier: Apache-2.0
import unittest
import logging

# Test suite paths
from tests import *

import boom
from boom.lvm2 import is_lvm_device_path, vg_lv_from_device_path


log = logging.getLogger()

# Override default BOOM_ROOT and BOOT_ROOT
# NOTE: with test fixtures that use the sandbox, this path is further
# overridden by the class setUp() method to point to the appropriate
# sandbox location.
boom.set_boot_path(BOOT_ROOT_TEST)


class Lvm2Tests(unittest.TestCase):
    """Tests for the stratis module.
    """
    def setUp(self):
        log.info("Preparing %s", self._testMethodName)

    def tearDown(self):
        log.info("Tearing down %s", self._testMethodName)

    # lvm2 module tests

    def test_is_lvm_device_path_badpath(self):
        self.assertEqual(is_lvm_device_path("/dev/stratis/foo"), False)

    def test_is_lvm_device_path_nosuchvg(self):
        self.assertEqual(is_lvm_device_path("/dev/nosuchvg/nosuchlv"), False)

    @unittest.skipIf(not have_root(), "requires root privileges")
    def test_is_lvm_device_path_not_a_blockdev(self):
        lv_path = "/dev/null"
        self.assertEqual(is_lvm_device_path(lv_path), False)

    @unittest.skipIf(not have_root_lv() or not have_root(), "requires root LV")
    def test_is_lvm_device_path_root_lv(self):
        lv_path = f"/dev/{get_root_lv()}"
        self.assertEqual(is_lvm_device_path(lv_path), True)

    @unittest.skipIf(not have_root(), "requires root privileges")
    def test_vg_lv_from_device_path_not_a_blockdev(self):
        lv_path = "/dev/null"
        self.assertEqual(vg_lv_from_device_path(lv_path), "")

    @unittest.skipIf(not have_root_lv() or not have_root(), "requires root LV")
    def test_vg_lv_from_device_path_root_lv(self):
        vg_lv = get_root_lv()
        lv_path = f"/dev/{vg_lv}"
        self.assertEqual(is_lvm_device_path(lv_path), True)
        self.assertEqual(vg_lv_from_device_path(lv_path), vg_lv)

# vim: set et ts=4 sw=4 :

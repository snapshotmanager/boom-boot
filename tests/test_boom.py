# Copyright Red Hat
#
# tests/test_boom.py - Boom module tests.
#
# This file is part of the boom project.
#
# SPDX-License-Identifier: GPL-2.0-only
import unittest
import logging
import boom
from sys import stdout
from os.path import abspath

from tests import *

log = logging.getLogger()

BOOT_ROOT_TEST = abspath("./tests")
# Override default BOOT_ROOT.
boom.set_boot_path(BOOT_ROOT_TEST)


class BoomTests(unittest.TestCase):
    def setUp(self):
        log.debug("Preparing %s", self._testMethodName)

    def tearDown(self):
        log.debug("Tearing down %s", self._testMethodName)

    # Module tests
    def test_import(self):
        import boom

    # Helper routine tests

    def test_parse_name_value_default(self):
        # Test each allowed quoting style
        nvp = "n=v"
        (name, value) = boom.parse_name_value(nvp)
        self.assertEqual(name, "n")
        self.assertEqual(value, "v")
        nvp = "n='v'"
        (name, value) = boom.parse_name_value(nvp)
        self.assertEqual(name, "n")
        self.assertEqual(value, "v")
        nvp = 'n="v"'
        (name, value) = boom.parse_name_value(nvp)
        self.assertEqual(name, "n")
        self.assertEqual(value, "v")
        nvp = 'n = "v"'
        (name, value) = boom.parse_name_value(nvp)
        self.assertEqual(name, "n")
        self.assertEqual(value, "v")

        # Assert that a comment following a value is permitted, with or
        # without intervening whitespace.
        nvp = 'n=v # Qux.'
        (name, value) = boom.parse_name_value(nvp)
        self.assertEqual(name, "n")
        self.assertEqual(value, "v ")
        nvp = 'n=v#Qux.'
        (name, value) = boom.parse_name_value(nvp)
        self.assertEqual(name, "n")
        self.assertEqual(value, "v")

        # Assert that a malformed nvp raises ValueError
        with self.assertRaises(ValueError) as cm:
            nvp = "n v"
            (name, value) = boom.parse_name_value(nvp)
        with self.assertRaises(ValueError) as cm:
            nvp = "n==v"
            (name, value) = boom.parse_name_value(nvp)
        with self.assertRaises(ValueError) as cm:
            nvp = "n+=v"
            (name, value) = boom.parse_name_value(nvp)

        # Test that values with embedded assignment are accepted
        (name, value) = boom.parse_name_value('n=v=v1')
        self.assertEqual(value, "v=v1")

    def test_parse_name_value_whitespace(self):
        # Test each allowed quoting style
        nvp = "n v"
        (name, value) = boom.parse_name_value(nvp, separator=None)
        self.assertEqual(name, "n")
        self.assertEqual(value, "v")
        nvp = "n 'v'"
        (name, value) = boom.parse_name_value(nvp, separator=None)
        self.assertEqual(name, "n")
        self.assertEqual(value, "v")
        nvp = 'n "v"'
        (name, value) = boom.parse_name_value(nvp, separator=None)
        self.assertEqual(name, "n")
        self.assertEqual(value, "v")
        nvp = 'n   "v"'
        (name, value) = boom.parse_name_value(nvp, separator=None)
        self.assertEqual(name, "n")
        self.assertEqual(value, "v")

        # Assert that a comment following a value is permitted, with or
        # without intervening whitespace. Trailing whitespace is
        # included in the parsed value.
        nvp = 'n v # Qux.'
        (name, value) = boom.parse_name_value(nvp, separator=None)
        self.assertEqual(name, "n")
        self.assertEqual(value, "v ")
        nvp = 'n v#Qux.'
        (name, value) = boom.parse_name_value(nvp, separator=None)
        self.assertEqual(name, "n")
        self.assertEqual(value, "v")

        # Assert that a malformed nvp raises ValueError
        with self.assertRaises(ValueError) as cm:
            nvp = "n=v"
            (name, value) = boom.parse_name_value(nvp, separator=None)
        with self.assertRaises(ValueError) as cm:
            nvp = "n==v"
            (name, value) = boom.parse_name_value(nvp, separator=None)
        with self.assertRaises(ValueError) as cm:
            nvp = "n+=v"
            (name, value) = boom.parse_name_value(nvp, separator=None)

        # Test that values with embedded assignment are accepted
        (name, value) = boom.parse_name_value('n v=v1', separator=None)
        self.assertEqual(value, "v=v1")

    def test_blank_or_comment(self):
        self.assertTrue(boom.blank_or_comment(""))
        self.assertTrue(boom.blank_or_comment("# this is a comment"))
        self.assertFalse(boom.blank_or_comment("THIS_IS_NOT=foo"))

    def test_set_debug_mask(self):
        boom.set_debug_mask(boom.BOOM_DEBUG_ALL)

    def test_set_debug_mask_bad_mask(self):
        with self.assertRaises(ValueError) as cm:
            boom.set_debug_mask(boom.BOOM_DEBUG_ALL + 1)

    def test_BoomLogger(self):
        bl = boom.BoomLogger("boom", 0)
        bl.debug("debug")

    def test_BoomLogger_set_debug_mask(self):
        bl = boom.BoomLogger("boom", 0)
        bl.set_debug_mask(boom.BOOM_DEBUG_ALL)

    def test_BoomLogger_set_debug_mask_bad_mask(self):
        bl = boom.BoomLogger("boom", 0)
        with self.assertRaises(ValueError) as cm:
            bl.set_debug_mask(boom.BOOM_DEBUG_ALL + 1)

    def test_BoomLogger_debug_masked(self):
        bl = boom.BoomLogger("boom", 0)
        boom.set_debug_mask(boom.BOOM_DEBUG_ALL)
        bl.set_debug_mask(boom.BOOM_DEBUG_ENTRY)
        bl.debug_masked("qux")

    def test_BoomConfig__str__(self):
        bc = boom.BoomConfig(boot_path="/boot", legacy_enable=False)
        xstr = ('[global]\nboot_root = /boot\nboom_root = /boot/boom\n\n'
                '[legacy]\nenable = False\nformat = grub1\nsync = True\n\n'
                '[cache]\nenable = True\nauto_clean = True\n'
                'cache_path = /boot/boom/cache\n')
        self.assertEqual(str(bc), xstr)

    def test_BoomConfig__repr__(self):
        bc = boom.BoomConfig(boot_path="/boot", legacy_enable=False)
        xrepr = ('BoomConfig(boot_path="/boot", boom_path="/boot/boom", '
                 'enable_legacy=False, legacy_format="grub1", '
                 'legacy_sync=True, cache_enable=True, auto_clean=True, '
                 'cache_path="/boot/boom/cache")')
        self.assertEqual(repr(bc), xrepr)

    def test_set_boom_config(self):
        bc = boom.BoomConfig(boot_path="/boot", legacy_enable=False)
        boom.set_boom_config(bc)

    def test_set_boom_config_bad_config(self):
        class Qux(object):
            pass

        with self.assertRaises(TypeError) as cm:
            boom.set_boom_config(None)

        with self.assertRaises(TypeError) as cm:
            boom.set_boom_config(Qux())

    def test_parse_btrfs_subvol(self):
        self.assertEqual((None, "23"), boom.parse_btrfs_subvol("23"))
        self.assertEqual(("/svol", None), boom.parse_btrfs_subvol("/svol"))
        self.assertEqual((None, None), boom.parse_btrfs_subvol(None))

    def test_Selection_from_cmd_args_subvol_id(self):
        cmd_args = MockArgs()
        s = boom.Selection.from_cmd_args(cmd_args)
        self.assertEqual(s.btrfs_subvol_id, "23")
        self.assertEqual(s.boot_id, None)

    def test_Selection_from_cmd_args_subvol(self):
        cmd_args = MockArgs()
        cmd_args.btrfs_subvolume = "/svol"
        s = boom.Selection.from_cmd_args(cmd_args)
        self.assertEqual(s.btrfs_subvol_path, "/svol")

    def test_Selection_from_cmd_args_root_lv(self):
        cmd_args = MockArgs()
        cmd_args.root_lv = "vg00/lvol0"
        s = boom.Selection.from_cmd_args(cmd_args)
        self.assertEqual(s.lvm_root_lv, "vg00/lvol0")

    def test_Selection_from_cmd_args_no_btrfs(self):
        cmd_args = MockArgs()
        cmd_args.btrfs_subvolume = ""
        cmd_args.root_lv = "vg00/lvol0"
        s = boom.Selection.from_cmd_args(cmd_args)
        self.assertEqual(s.lvm_root_lv, "vg00/lvol0")

    def test_Selection_invalid_selection(self):
        # A boot_id is invalid for an OsProfile select
        s = boom.Selection(boot_id="12345678")
        with self.assertRaises(ValueError) as cm:
            s.check_valid_selection(profile=True)

    def test_Selection_is_null(self):
        s = boom.Selection()
        self.assertTrue(s.is_null())

    def test_Selection_is_non_null(self):
        s = boom.Selection(boot_id="1")
        self.assertFalse(s.is_null())


class BoomPathTests(unittest.TestCase):
    def setUp(self):
        log.debug("Preparing %s", self._testMethodName)

    def tearDown(self):
        log.debug("Tearing down %s", self._testMethodName)

    def test_set_boot_path(self):
        boom.set_boot_path(BOOT_ROOT_TEST)

    def test_set_boot_path_bad_path(self):
        with self.assertRaises(ValueError) as cm:
            boom.set_boot_path("/the/wrong/path")

    def test_set_boom_path(self):
        boom.set_boom_path(BOOT_ROOT_TEST + "/boom")

    def test_set_boom_path_bad_path(self):
        with self.assertRaises(ValueError) as cm:
            boom.set_boom_path("/the/wrong/path")

    def test_set_boom_path_non_abs(self):
        boom.set_boot_path(BOOT_ROOT_TEST)
        boom.set_boom_path("boom/")

    def test_set_boom_path_non_abs_bad(self):
        boom.set_boot_path(BOOT_ROOT_TEST + "/boom")
        with self.assertRaises(ValueError) as cm:
            boom.set_boom_path("absolutely/the/wrong/path")

    def test_set_boot_path_non_abs(self):
        with self.assertRaises(ValueError) as cm:
            boom.set_boot_path("absolutely/the/wrong/path")

    def test_set_boom_path_no_profiles(self):
        boom.set_boot_path(BOOT_ROOT_TEST)
        with self.assertRaises(ValueError) as cm:
            boom.set_boom_path("loader")

    def test_set_get_cache_path(self):
        cache_path = BOOT_ROOT_TEST + "/boom/cache"
        boom.set_cache_path(cache_path)
        self.assertEqual(boom.get_cache_path(), cache_path)
# vim: set et ts=4 sw=4 :

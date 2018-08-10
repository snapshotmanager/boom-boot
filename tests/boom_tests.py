# Copyright (C) 2017 Red Hat, Inc., Bryn M. Reeves <bmr@redhat.com>
#
# boom_tests.py - Boom module tests.
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
import boom
from sys import stdout
from os.path import abspath

log = logging.getLogger()
log.level = logging.DEBUG
log.addHandler(logging.FileHandler("test.log"))

BOOT_ROOT_TEST = abspath("./tests")
# Override default BOOT_ROOT.
boom.set_boot_path(BOOT_ROOT_TEST)


class BoomTests(unittest.TestCase):
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

# vim: set et ts=4 sw=4 :

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

log = logging.getLogger()
log.level = logging.DEBUG
log.addHandler(logging.FileHandler("test.log"))

BOOM_ROOT_TEST = "./tests/boom"
# Override default BOOM_ROOT.
boom.BOOM_ROOT = BOOM_ROOT_TEST


class BoomTests(unittest.TestCase):
    # Module tests
    def test_import(self):
        import boom

    # Helper routine tests

    def test_parse_name_value_default(self):
        # Test each allowed quoting style
        nvp = "n=v"
        (name, value) = boom._parse_name_value(nvp)
        self.assertEqual(name, "n")
        self.assertEqual(value, "v")
        nvp = "n='v'"
        (name, value) = boom._parse_name_value(nvp)
        self.assertEqual(name, "n")
        self.assertEqual(value, "v")
        nvp = 'n="v"'
        (name, value) = boom._parse_name_value(nvp)
        self.assertEqual(name, "n")
        self.assertEqual(value, "v")
        nvp = 'n = "v"'
        (name, value) = boom._parse_name_value(nvp)
        self.assertEqual(name, "n")
        self.assertEqual(value, "v")

        # Assert that a comment following a value is permitted, with or
        # without intervening whitespace.
        nvp = 'n=v # Qux.'
        (name, value) = boom._parse_name_value(nvp)
        self.assertEqual(name, "n")
        self.assertEqual(value, "v ")
        nvp = 'n=v#Qux.'
        (name, value) = boom._parse_name_value(nvp)
        self.assertEqual(name, "n")
        self.assertEqual(value, "v")

        # Assert that a malformed nvp raises ValueError
        with self.assertRaises(ValueError) as cm:
            nvp = "n v"
            (name, value) = boom._parse_name_value(nvp)
        with self.assertRaises(ValueError) as cm:
            nvp = "n==v"
            (name, value) = boom._parse_name_value(nvp)
        with self.assertRaises(ValueError) as cm:
            nvp = "n+=v"
            (name, value) = boom._parse_name_value(nvp)

        # Test that values with embedded assignment are accepted
        (name, value) = boom._parse_name_value('n=v=v1')
        self.assertEqual(value, "v=v1")

    def test_parse_name_value_whitespace(self):
        # Test each allowed quoting style
        nvp = "n v"
        (name, value) = boom._parse_name_value(nvp, separator=None)
        self.assertEqual(name, "n")
        self.assertEqual(value, "v")
        nvp = "n 'v'"
        (name, value) = boom._parse_name_value(nvp, separator=None)
        self.assertEqual(name, "n")
        self.assertEqual(value, "v")
        nvp = 'n "v"'
        (name, value) = boom._parse_name_value(nvp, separator=None)
        self.assertEqual(name, "n")
        self.assertEqual(value, "v")
        nvp = 'n   "v"'
        (name, value) = boom._parse_name_value(nvp, separator=None)
        self.assertEqual(name, "n")
        self.assertEqual(value, "v")

        # Assert that a comment following a value is permitted, with or
        # without intervening whitespace. Trailing whitespace is
        # included in the parsed value.
        nvp = 'n v # Qux.'
        (name, value) = boom._parse_name_value(nvp, separator=None)
        self.assertEqual(name, "n")
        self.assertEqual(value, "v ")
        nvp = 'n v#Qux.'
        (name, value) = boom._parse_name_value(nvp, separator=None)
        self.assertEqual(name, "n")
        self.assertEqual(value, "v")

        # Assert that a malformed nvp raises ValueError
        with self.assertRaises(ValueError) as cm:
            nvp = "n=v"
            (name, value) = boom._parse_name_value(nvp, separator=None)
        with self.assertRaises(ValueError) as cm:
            nvp = "n==v"
            (name, value) = boom._parse_name_value(nvp, separator=None)
        with self.assertRaises(ValueError) as cm:
            nvp = "n+=v"
            (name, value) = boom._parse_name_value(nvp, separator=None)

        # Test that values with embedded assignment are accepted
        (name, value) = boom._parse_name_value('n v=v1', separator=None)
        self.assertEqual(value, "v=v1")

    def test_blank_or_comment(self):
        self.assertTrue(boom._blank_or_comment(""))
        self.assertTrue(boom._blank_or_comment("# this is a comment"))
        self.assertFalse(boom._blank_or_comment("THIS_IS_NOT=foo"))

# vim: set et ts=4 sw=4 :

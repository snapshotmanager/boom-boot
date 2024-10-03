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
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
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
from boom.stratis import *

# Override default BOOM_ROOT and BOOT_ROOT
# NOTE: with test fixtures that use the sandbox, this path is further
# overridden by the class setUp() method to point to the appropriate
# sandbox location.
boom.set_boot_path(BOOT_ROOT_TEST)

log = logging.getLogger()
log.level = logging.DEBUG
log.addHandler(logging.FileHandler("test.log"))


class StratisTests(unittest.TestCase):
    """Tests for the BootEntry class that do not depend on external
        test data.
    """
    # Stratis module tests

    def test_is_stratis_device_path_badpath(self):
        self.assertEqual(is_stratis_device_path("/dev/notstratis/foo"), False)

    def test_is_stratis_device_path_nosuchpool(self):
        self.assertEqual(is_stratis_device_path("/dev/stratis/nosuchpool/fs1"), False)

    def test_format_pool_uuid_valid(self):
        uuid_val = "b4580e1e30b0424e8efc7e578698fa8f"
        uuid_xval = "b4580e1e-30b0-424e-8efc-7e578698fa8f"
        self.assertEqual(format_pool_uuid(uuid_val), uuid_xval)

    def test_format_pool_uuid_baduuid(self):
        uuid_val = "QUUX"
        with self.assertRaises(ValueError) as cm:
            format_pool_uuid(uuid_val)

# vim: set et ts=4 sw=4 :

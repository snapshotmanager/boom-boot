# Copyright Red Hat
#
# tests/test_stratis.py - Boom Stratis integration tests.
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
from boom.stratis import *


log = logging.getLogger()

# Override default BOOM_ROOT and BOOT_ROOT
# NOTE: with test fixtures that use the sandbox, this path is further
# overridden by the class setUp() method to point to the appropriate
# sandbox location.
boom.set_boot_path(BOOT_ROOT_TEST)


class StratisTests(unittest.TestCase):
    """Tests for the BootEntry class that do not depend on external
        test data.
    """
    def setUp(self):
        log.debug("Preparing %s", self._testMethodName)

    def tearDown(self):
        log.debug("Tearing down %s", self._testMethodName)

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

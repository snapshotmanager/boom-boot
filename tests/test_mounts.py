# Copyright Red Hat
#
# tests/test_mounts.py - Boom mount helper tests.
#
# This file is part of the boom project.
#
# SPDX-License-Identifier: GPL-2.0-only
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
from boom.mounts import *

from tests import *

BOOT_ROOT_TEST = abspath("./tests")
set_boot_path(BOOT_ROOT_TEST)


class MountsHelperTests(unittest.TestCase):
    """Test internal boom.mounts helpers. Cases in this class must
        not modify on-disk state and do not use a unique test
        fixture.
    """
    def setUp(self):
        log.debug("Preparing %s", self._testMethodName)

    def tearDown(self):
        log.debug("Tearing down %s", self._testMethodName)

    def test_parse_mount_units(self):
        mount_list = ["/dev/test/var:/var:xfs:defaults"]
        xmount_str = "systemd.mount-extra=/dev/test/var:/var:xfs:defaults"
        self.assertEqual(parse_mount_units(mount_list)[0], xmount_str)

    def test_parse_mount_units_bad_spec(self):
        mount_list = "/dev:"
        with self.assertRaises(BoomMountError):
            parse_mount_units(mount_list)

# vim: set et ts=4 sw=4 :

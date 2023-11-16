# Copyright (C) 2017 Red Hat, Inc., Bryn M. Reeves <bmr@redhat.com>
#
# test_mounts.py - Boom mount helper tests.
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
from os import listdir, makedirs, unlink
from os.path import abspath, basename, dirname, exists, join
from glob import glob
import shutil
import re

# Python3 moves StringIO to io
try:
    from StringIO import StringIO
except:
    from io import StringIO

log = logging.getLogger()
log.level = logging.DEBUG
log.addHandler(logging.FileHandler("test.log"))

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
    def test_parse_mount_units(self):
        mount_list = ["/dev/test/var:/var:xfs:defaults"]
        xmount_str = "systemd.mount-extra=/dev/test/var:/var:xfs:defaults"
        self.assertEqual(parse_mount_units(mount_list)[0], xmount_str)

    def test_parse_mount_units_bad_spec(self):
        mount_list = "/dev:"
        with self.assertRaises(BoomMountError):
            parse_mount_units(mount_list)

# vim: set et ts=4 sw=4 :

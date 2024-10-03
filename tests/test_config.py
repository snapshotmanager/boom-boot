# Copyright (C) 2017 Red Hat, Inc., Bryn M. Reeves <bmr@redhat.com>
#
# test_config.py - Boom report API tests.
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
from os.path import abspath, join
from sys import stdout
import shutil

try:
    # Python2
    from ConfigParser import SafeConfigParser as ConfigParser, ParsingError
except:
    # Python3
    from configparser import ConfigParser, ParsingError

log = logging.getLogger()
log.level = logging.DEBUG
log.addHandler(logging.FileHandler("test.log"))

# Test suite paths
from tests import *

from boom import *
from boom.config import *
BOOT_ROOT_TEST = abspath("./tests")
set_boot_path(BOOT_ROOT_TEST)

class ConfigBasicTests(unittest.TestCase):
    """Basic tests for the boom.config sub-module.
    """

    def test_sync_config(self):
        """Test that the internal _sync_config() helper works.
        """
        import boom.config # for _sync_config()
        cfg = ConfigParser()
        bc = BoomConfig()

        cfg.add_section("global")
        cfg.add_section("legacy")

        boot_path = "/boot"
        boom_path = "/boot/boom"
        legacy_format = "grub1"

        bc.legacy_enabled = False
        bc.legacy_sync = False
        bc.legacy_format = legacy_format

        bc.boot_path = boot_path
        bc.boom_path = boom_path

        boom.config._sync_config(bc, cfg)
        self.assertEqual(cfg.get("legacy", "enable"), "no")
        self.assertEqual(cfg.get("legacy", "sync"), "no")
        self.assertEqual(cfg.get("legacy", "format"), legacy_format)
        self.assertEqual(cfg.get("global", "boot_root"), boot_path)
        self.assertEqual(cfg.get("global", "boom_root"), boom_path)


class ConfigTests(unittest.TestCase):
    # The set of configuration files to use for this test class
    conf_path = join(BOOT_ROOT_TEST, "boom_configs/default/boot")

    # The path to the boot directory in the test sandbox
    boot_path = join(SANDBOX_PATH, "boot")

    # The path to the sandbox boom.conf configuration file
    boom_conf = join(boot_path, "boom/boom.conf")

    def setUp(self):
        """Set up a test fixture for the ConfigTests class.
        """
        reset_sandbox()

        # Sandbox paths
        shutil.copytree(self.conf_path, join(SANDBOX_PATH, "boot"))
        # Set boom paths
        set_boot_path(self.boot_path)

    def tearDown(self):
        rm_sandbox()
        reset_boom_paths()

    def test_get_boom_config_path(self):
        """Test that the correct boom.conf path is returned from a call
            to the `get_boom_config_path()` function.
        """
        conf_path = self.boom_conf
        self.assertEqual(get_boom_config_path(), conf_path)

    def test_set_boom_config_path_abs(self):
        """Test that the correct boom.conf path is returned from a call
            to the `get_boom_config_path()` function when an absolute
            path is given.
        """
        conf_dir = join(SANDBOX_PATH, "boot/boom")
        conf_path = join(conf_dir, "boom.conf")
        set_boom_config_path(conf_dir)
        self.assertEqual(get_boom_config_path(), conf_path)

    def test_load_boom_config_default(self):
        """Test the `load_boom_config()` function with the default
            configuration file.
        """
        load_boom_config()

class BadConfigTests(ConfigTests):
    # The set of configuration files to use for this test class
    conf_path = join(BOOT_ROOT_TEST, "boom_configs/badconfig/boot")

    def test_load_boom_config_default(self):
        """Test the `load_boom_config()` function with the default
            configuration file.
        """
        with self.assertRaises(ValueError) as cm:
            load_boom_config()

# vim: set et ts=4 sw=4 :

# Copyright Red Hat
#
# tests/test_config.py - Boom report API tests.
#
# This file is part of the boom project.
#
# SPDX-License-Identifier: GPL-2.0-only
import unittest
import logging
from configparser import ConfigParser, ParsingError
from os.path import abspath, join
from sys import stdout
import shutil


log = logging.getLogger()

# Test suite paths
from tests import *

from boom import *
from boom.config import *
BOOT_ROOT_TEST = abspath("./tests")
set_boot_path(BOOT_ROOT_TEST)

class ConfigBasicTests(unittest.TestCase):
    """Basic tests for the boom.config sub-module.
    """

    def setUp(self):
        log.debug("Preparing %s", self._testMethodName)

    def tearDown(self):
        log.debug("Tearing down %s", self._testMethodName)

    def test_sync_config(self):
        """Test that the internal _sync_config() helper works.
        """
        import boom.config # for _sync_config()
        cfg = ConfigParser()
        bc = BoomConfig()

        cfg.add_section("global")
        cfg.add_section("legacy")
        cfg.add_section("cache")

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
        log.debug("Preparing %s", self._testMethodName)

        reset_sandbox()

        # Sandbox paths
        shutil.copytree(self.conf_path, join(SANDBOX_PATH, "boot"))
        # Set boom paths
        set_boot_path(self.boot_path)

    def tearDown(self):
        log.debug("Tearing down %s", self._testMethodName)

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

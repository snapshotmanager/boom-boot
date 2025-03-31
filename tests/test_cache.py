# Copyright Red Hat
#
# tests/test_cache.py - Boom cache API tests.
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
from boom.osprofile import *
from boom.bootloader import *
from boom.hostprofile import *
from boom.command import *
from boom.config import *
from boom.report import *
from boom.cache import *

# For access to non-exported members
import boom.cache

from tests import *

BOOT_ROOT_TEST = abspath("./tests")
config = BoomConfig()
config.legacy_enable = False
config.legacy_sync = False
set_boom_config(config)
set_boot_path(BOOT_ROOT_TEST)

debug_masks = ['profile', 'entry', 'report', 'command', 'all']


class CacheHelperTests(unittest.TestCase):
    """Test internal boom.cache helpers. Cases in this class must
        not modify on-disk state and do not use a unique test
        fixture.
    """

    # Test fixture init/cleanup
    def setUp(self):
        """Set up a test fixture for the CacheHelperTests class.
        """
        log.debug("Preparing %s", self._testMethodName)

        set_boom_config(config)
        set_boot_path(BOOT_ROOT_TEST)

    def tearDown(self):
        log.debug("Tearing down %s", self._testMethodName)

        # Drop any in-memory entries and profiles modified by tests
        drop_entries()
        drop_profiles()
        drop_host_profiles()
        drop_cache()

    def test__make_relative_with_non_abs_path(self):
        path = "not/an/absolute/path"
        self.assertEqual(path, boom.cache._make_relative(path))

    def test__make_relative_with_abs_path(self):
        path = "/vmlinuz"
        self.assertEqual(path[1:], boom.cache._make_relative(path))

    def test__make_relative_root_is_empty_string(self):
        path = "/"
        self.assertEqual("", boom.cache._make_relative(path))

    def test__image_path_to_boot(self):
        image_path = "vmlinuz"
        xboot_path = join(get_boot_path(), image_path)
        boot_path = boom.cache._image_path_to_boot(join("/", image_path))
        self.assertEqual(boot_path, xboot_path)

    def test__image_id_to_cache_path(self):
        img_id = "47dc6ad4ea9ca5453e607987d49c33858bd553e0"
        xcache_file = "47dc6ad4ea9ca5453e607987d49c33858bd553e0.img"
        self.assertEqual(boom.cache._image_id_to_cache_path(img_id),
                         join(get_cache_path(), xcache_file))

    def test__image_id_from_path(self):
        img_path = join(get_boot_path(), "vmlinuz-5.5.5-1.fc30.x86_64")
        ximg_id = "fdfb8e5a3857adca47f25ee47078bad4a757cc92"
        self.assertEqual(boom.cache._image_id_from_path(img_path), ximg_id)

    def test__image_id_from_bad_path_raises(self):
        img_path = "/qux/qux/qux"  # non-existent
        with self.assertRaises(IOError) as cm:
            boom.cache._image_id_from_path(img_path)

class CacheTests(unittest.TestCase):
    """Test boom.command APIs
    """

    # Main BLS loader directory for sandbox
    loader_path = join(BOOT_ROOT_TEST, "loader")

    # Main boom configuration path for sandbox
    boom_path = join(BOOT_ROOT_TEST, "boom")

    # Main grub configuration path for sandbox
    grub_path = join(BOOT_ROOT_TEST, "grub")

    # Test fixture init/cleanup
    def setUp(self):
        """Set up a test fixture for the CommandTests class.

            Defines standard objects for use in these tests.
        """
        log.debug("Preparing %s", self._testMethodName)

        reset_sandbox()

        # Sandbox paths
        boot_sandbox = join(SANDBOX_PATH, "boot")
        boom_sandbox = join(SANDBOX_PATH, "boot/boom")
        grub_sandbox = join(SANDBOX_PATH, "boot/grub")
        loader_sandbox = join(SANDBOX_PATH, "boot/loader")

        # Initialise sandbox from main
        makedirs(boot_sandbox)
        shutil.copytree(self.boom_path, boom_sandbox)
        shutil.copytree(self.loader_path, loader_sandbox)
        shutil.copytree(self.grub_path, grub_sandbox)

        # Copy boot images
        images = glob(join(BOOT_ROOT_TEST, "initramfs*"))
        images += glob(join(BOOT_ROOT_TEST, "vmlinuz*"))
        for image in images:
            def _dotfile(img_path):
                pattern = ".%s.boomrestored"
                img_name = basename(img_path)
                img_dir = dirname(img_path)
                return join(img_dir, pattern % img_name)

            shutil.copy2(image, boot_sandbox)
            if exists(_dotfile(image)):
                shutil.copy2(_dotfile(image), boot_sandbox)

        # Set boom paths
        set_boot_path(boot_sandbox)

        # Tests that deal with legacy configs will enable this.
        config = BoomConfig()
        config.legacy_enable = False
        config.legacy_sync = False

        # Reset profiles, entries, and host profiles to known state.
        load_profiles()
        load_entries()
        load_host_profiles()
        load_cache()

    def tearDown(self):
        log.debug("Tearing down %s", self._testMethodName)

        # Drop any in-memory entries and profiles modified by tests
        drop_entries()
        drop_profiles()
        drop_host_profiles()
        drop_cache()

        # Clear sandbox data
        rm_sandbox()
        reset_boom_paths()

    def _make_null_testimg(self, restored=False):
        """Return an empty file in the configured $BOOT path for test use.
            If ``restored`` is ``True`` the image will be made to look like
            an image restored by boom.
        """
        img_name = "testimg"
        boot_path = get_boot_path()
        print(boot_path)
        # The img_id of an empty file is the sha1 null hash: da39a3e
        img_file = open(join(boot_path, img_name), "w")
        img_file.close()

        if restored:
            boomrestored_name = "." + img_name + ".boomrestored"
            boomrestored_file = open(join(boot_path, boomrestored_name), "w")
            boomrestored_file.close()

        return img_name

    def test_drop_cache(self):
        drop_cache()
        self.assertEqual(len(boom.cache._index), 0)
        self.assertEqual(len(boom.cache._paths), 0)
        self.assertEqual(len(boom.cache._images), 0)

    def test_load_cache(self):
        load_cache()
        self.assertTrue(len(boom.cache._index))
        self.assertTrue(len(boom.cache._paths))
        self.assertTrue(len(boom.cache._images))

        # Verify number of images
        boom_cache_path = get_cache_path()
        ximage_count = 0
        for p in listdir(boom_cache_path):
            if p.endswith(".img"):
                ximage_count += 1
        self.assertEqual(len(boom.cache._images), ximage_count)

    def test_load_cache_no_cacheindex(self):
        # Wipe cache
        unlink(join(SANDBOX_PATH, "boot/boom/cache/cacheindex.json"))
        load_cache()
        self.assertFalse(len(boom.cache._index))
        self.assertFalse(len(boom.cache._paths))
        self.assertFalse(len(boom.cache._images))

    def test_write_cache(self):
        # Re-write the current cache state
        write_cache()

        # Write an empty cache
        drop_cache()
        write_cache()

    def test__insert(self):
        img_name = self._make_null_testimg()
        img_path = join(get_boot_path(), img_name)

        cache_name = "da39a3ee5e6b4b0d3255bfef95601890afd80709.img"
        cache_path = join(get_cache_path(), cache_name)

        boom.cache._insert(img_path, cache_path)
        self.assertTrue(exists(cache_path))

    def test__insert_bad_path_raises(self):
        img_path = "/qux/qux/qux"

        cache_name = "da39a3ee5e6b4b0d3255bfef95601890afd80709.img"
        cache_path = join(get_cache_path(), cache_name)

        with self.assertRaises(IOError) as cm:
            boom.cache._insert(img_path, cache_path)

    def test__remove_boot(self):
        img_name = self._make_null_testimg(restored=True)
        img_path = join(get_boot_path(), img_name)

        self.assertTrue(exists(img_path))
        boom.cache._remove_boot(img_path)
        self.assertFalse(exists(img_path))

    def test__remove_boot_bad_path_raises(self):
        with self.assertRaises(ValueError) as cm:
            boom.cache._remove_boot("nosuch.img")

    def test__remove_boot_not_restored_raises(self):
        img_name = self._make_null_testimg(restored=False)
        img_path = join(get_boot_path(), img_name)

        with self.assertRaises(ValueError) as cm:
            boom.cache._remove_boot(img_path)

    def test__remove(self):
        img_name = self._make_null_testimg()
        img_path = join(get_boot_path(), img_name)

        cache_name = "da39a3ee5e6b4b0d3255bfef95601890afd80709.img"
        cache_path = join(get_cache_path(), cache_name)

        boom.cache._insert(img_path, cache_path)
        self.assertTrue(exists(cache_path))

        boom.cache._remove(cache_path)
        self.assertFalse(exists(cache_path))

    def test__remove_nonex_path_raises(self):
        cache_name = "da39a3ee5e6b4b0d3255bfef95601890afd80709.img"
        cache_path = join(get_cache_path(), cache_name)

        with self.assertRaises(OSError) as cm:
            boom.cache._remove(cache_path)

    def test__remove_bad_path_raises(self):
        cache_path = "/da39a3ee5e6b4b0d3255bfef95601890afd80709.img"

        with self.assertRaises(ValueError) as cm:
            boom.cache._remove(cache_path)

    def test_cache_path(self):
        img_name = self._make_null_testimg(restored=False)
        img_path = join("/", img_name)

        cache_path(img_path)

        ces = find_cache_paths(Selection(path=img_path))
        self.assertEqual(len(ces), 1)

    def test_cache_path_dupe(self):
        img_name = self._make_null_testimg(restored=False)
        img_path = join("/", img_name)

        ce1 = cache_path(img_path)
        ce2 = cache_path(img_path)

        self.assertEqual(repr(ce1), repr(ce2))

    def test_cache_path_nonex_path_raises(self):
        img_name = "nonexistent"
        img_path = join("/", img_name)

        with self.assertRaises(OSError) as cm:
            cache_path(img_path)

    def test_cache_path_nonreg_path_raises(self):
        img_path = "/"

        with self.assertRaises(ValueError) as cm:
            cache_path(img_path)

    def test_backup_path(self):
        img_name = self._make_null_testimg(restored=False)
        img_path = join("/", img_name)
        backup_img = img_path + ".boom0"

        backup_path(img_path)

        # Assert backup is in cache
        ces = find_cache_paths(Selection(path=backup_img))
        self.assertEqual(len(ces), 1)

        # Assert original is not in cache
        ces = find_cache_paths(Selection(path=img_path))
        self.assertEqual(len(ces), 0)

    def test_uncache_path(self):
        img_name = self._make_null_testimg(restored=False)
        img_path = join("/", img_name)

        cache_path(img_path)

        ces = find_cache_paths(Selection(path=img_path))
        self.assertEqual(len(ces), 1)

        uncache_path(img_path)

        ces = find_cache_paths(Selection(path=img_path))
        self.assertEqual(len(ces), 0)


    def test_uncache_path_not_cached(self):
        img_name = self._make_null_testimg(restored=False)
        img_path = join("/", img_name)

        with self.assertRaises(ValueError) as cm:
            uncache_path(img_path)

    def test_uncache_in_use(self):
        img_path = "/vmlinuz-4.16.11-100.fc26.x86_64"
        uncache_path(img_path)

        ces = find_cache_paths(Selection(path=img_path))
        self.assertEqual(len(ces), 1)

    def test_uncache_in_use_force(self):
        img_path = "/vmlinuz-4.16.11-100.fc26.x86_64"
        uncache_path(img_path, force=True)

        ces = find_cache_paths(Selection(path=img_path))
        self.assertEqual(len(ces), 0)

    def test_uncache_restored(self):
        img_path = "/initramfs-3.10.1-1.el7.img"
        uncache_path(img_path)

        ces = find_cache_paths(Selection(path=img_path))
        self.assertEqual(len(ces), 1)

    def test_uncache_restored_force(self):
        img_path = "/initramfs-3.10.1-1.el7.img"
        uncache_path(img_path, force=True)

        ces = find_cache_paths(Selection(path=img_path))
        self.assertEqual(len(ces), 0)

    def test_clean_cache(self):
        clean_cache()

    def test_clean_cache_unrefed(self):
        cache_path("/initramfs-2.6.0.img")
        clean_cache()

    def test_cache_state_missing_and_restore(self):
        img_path="/initramfs-2.6.0.img"
        ce = cache_path(img_path)
        unlink(join(get_boot_path(), img_path[1:]))
        self.assertEqual(ce.state, CACHE_MISSING)
        ce.restore()
        self.assertEqual(ce.state, CACHE_RESTORED)

    def test_cache_state_missing_and_restore_with_dest(self):
        img_path="/initramfs-2.6.0.img"
        ce = cache_path(img_path)
        unlink(join(get_boot_path(), img_path[1:]))
        self.assertEqual(ce.state, CACHE_MISSING)
        ce.restore(dest=img_path + ".boom0")
        self.assertEqual(ce.state, CACHE_RESTORED)

    def test_cache_restore_non_missing_raises(self):
        # A path that is not RESTORED|MISSING
        img_path = "/vmlinuz-4.16.11-100.fc26.x86_64"
        ce = find_cache_paths(Selection(path=img_path))[0]
        with self.assertRaises(ValueError) as cm:
            ce.restore()

    def test_cache_purge_restored(self):
        img_path="/initramfs-2.6.0.img"
        ce = cache_path(img_path)
        unlink(join(get_boot_path(), img_path[1:]))
        self.assertEqual(ce.state, CACHE_MISSING)
        ce.restore()
        self.assertEqual(ce.state, CACHE_RESTORED)
        ce.purge()
        self.assertEqual(ce.state, CACHE_MISSING)

    def test_cache_purge_not_restored(self):
        # A path that is not RESTORED|MISSING
        img_path = "/vmlinuz-4.16.11-100.fc26.x86_64"
        ce = find_cache_paths(Selection(path=img_path))[0]
        self.assertEqual(ce.state, CACHE_CACHED)
        with self.assertRaises(ValueError) as cm:
            ce.purge()

    def test_find_cache_paths(self):
        ces = find_cache_paths()
        self.assertTrue(ces)

    def test_find_cache_images(self):
        ces = find_cache_images()
        self.assertTrue(ces)

# vim: set et ts=4 sw=4 :

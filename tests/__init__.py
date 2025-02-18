# Copyright Red Hat
#
# tests/__init__.py - Boom test package initialisation
#
# This file is part of the boom project.
#
# SPDX-License-Identifier: GPL-2.0-only
from os.path import join, abspath, exists
from os import environ, getcwd, geteuid, getegid, makedirs
from subprocess import Popen, PIPE
import logging
import shutil
import errno

import boom

log = logging.getLogger()
log.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s')
file_handler = logging.FileHandler("test.log")
file_handler.setFormatter(formatter)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
log.addHandler(file_handler)
log.addHandler(console_handler)

# Root of the testing directory
BOOT_ROOT_TEST = abspath("./tests")

# Location of the temporary sandbox for test data
SANDBOX_PATH = join(BOOT_ROOT_TEST, "sandbox")

# Test sandbox functions

def rm_sandbox():
    """Remove the test sandbox at SANDBOX_PATH.
    """
    try:
        shutil.rmtree(SANDBOX_PATH)
    except OSError as e:
        if e.errno != errno.ENOENT:
            raise


def mk_sandbox():
    """Create a new test sandbox at SANDBOX_PATH.
    """
    makedirs(SANDBOX_PATH)


def reset_sandbox():
    """Reset the test sandbox at SANDBOX_PATH by removing it and
        re-creating the directory.
    """
    rm_sandbox()
    mk_sandbox()

def reset_boom_paths():
    """Reset configurable boom module paths to the default test values.
    """
    boom.set_boot_path(BOOT_ROOT_TEST)

def set_mock_path():
    """Set the PATH environment variable to tests/bin to include mock
        binaries used in the boom test suite.
    """
    os_path = environ['PATH']
    os_path = join(getcwd(), "tests/bin") + ":" + os_path
    environ['PATH'] = os_path


# Mock objects

class MockArgs(object):
    """Mock arguments class for testing boom command line infrastructure.
    """
    add_opts = ""
    all = False
    architecture = None
    backup = False
    boot_id = None
    btrfs_opts = ""
    btrfs_subvolume = "23"
    command = ""
    config = ""
    debug = ""
    del_opts = ""
    efi = ""
    efi = ""
    expand_variables = False
    from_host = ""
    grub_arg = ""
    grub_class = ""
    grub_users = ""
    host_id = None
    host_name = ""
    host_profile = ""
    host_profile = ""
    id = ""
    identifier = ""
    initramfs_pattern = ""
    initrd = ""
    json = False
    kernel_pattern = ""
    label = ""
    linux = ""
    lvm_opts = ""
    machine_id = ""
    mount = ""
    name = ""
    name_prefixes = False
    no_dev = False
    no_fstab = False
    no_headings = False
    options = ""
    optional_keys = ""
    os_id = ""
    os_options = ""
    os_release = ""
    os_version = ""
    os_version_id = ""
    profile = ""
    root_device = ""
    root_lv = ""
    rows = False
    separator = ""
    short_name = ""
    sort = ""
    swap = ""
    title = ""
    update = False
    type = ""
    uname_pattern = ""
    verbose = 0
    version = ""

# Cached logical volume to use for tests
_lv_cache = None

def _root_lv_from_cmdline():
    """Return the root logical volume according to the kernel command
        line, or the empty string if no rd.lvm.lv argument is found.
    """
    with open("/proc/cmdline", "r") as f:
        for line in f.read().splitlines():
            if isinstance(line, bytes):
                line = line.decode('utf8', 'ignore')
            args = line.split()
            for arg in args:
                if "rd.lvm.lv" in arg:
                    (rd, vglv) = arg.split("=")
                    return "/dev/%s" % vglv
        return None


def get_logical_volume():
    """Return an extant logical volume path suitable for use for
        device presence checks.

        The actual volume returned is unimportant.

        The device is not modified or written to in any way by the
        the test suite.
    """
    global _lv_cache
    if _lv_cache:
        return _lv_cache

    if not have_root() or not have_lvm():
        """The LVM2 binary is not present or not usable. Attempt to
            guess a usable device name based on the content of the
            system kernel command line.
        """
        return _root_lv_from_cmdline()

    p = Popen(["lvs", "--noheadings", "-ovgname,name"], stdin=None,
              stdout=PIPE, stderr=None, close_fds=True)
    out = p.communicate()[0]
    lvs = []
    for line in out.splitlines():
        if isinstance(line, bytes):
            line = line.decode('utf8', 'ignore')
        (vg, lv) = line.strip().split()
        if "swap" in lv:
            continue
        if "root" in lv:
            _lv_cache = "/dev/%s/%s" % (vg, lv)
            return _lv_cache
        lvs.append("/dev/%s/%s" % (vg, lv))
    _lv_cache = lvs[0]
    return _lv_cache


def get_root_lv():
    """Return the logical volume found by ``get_logical_volume()``
        in LVM VG/LV notation.
    """
    lv = get_logical_volume()
    if lv and not exists(lv):
        return None
    return lv[5:] if lv else None


def have_root_lv():
    """Return ``True`` if a usable root logical volume is present,
        or ``False`` otherwise.
    """
    return bool(get_root_lv())

# Test predicates

def have_root():
    """Return ``True`` if the test suite is running as the root user,
        and ``False`` otherwise.
    """
    return geteuid() == 0 and getegid() == 0


def have_lvm():
    """Return ``True`` if the test suite is running on a system with
        at least one logical volume, or ``False`` otherwise.
    """
    try:
        p = Popen(["lvs", "--noheadings", "-oname"], stdin=None, stdout=PIPE,
                  stderr=None, close_fds=True)
        out = p.communicate()[0]
        if len(out.splitlines()):
            return True
    except:
        pass
    return False


def have_grub1():
    """Return ``True`` if the grub1 bootloader commands are present,
        or ``False`` otherwise.
    """
    try:
        p = Popen(["grub", "--help"], stdin=None, stdout=PIPE, stderr=PIPE,
                  close_fds=True)
        out = p.communicate(input="\n")[0]
        return True
    except OSError:
        return False


__all__ = [
    'BOOT_ROOT_TEST', 'SANDBOX_PATH',
    'rm_sandbox', 'mk_sandbox', 'reset_sandbox', 'reset_boom_paths',
    'set_mock_path', 'get_logical_volume', 'get_root_lv', 'have_root_lv',
    'MockArgs',
    'have_root', 'have_lvm', 'have_grub1'
]

# vim: set et ts=4 sw=4 :

# Copyright (C) 2017 Red Hat, Inc., Bryn M. Reeves <bmr@redhat.com>
#
# boom/__init__.py - Boom package initialisation
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

from os.path import join, abspath
from os import geteuid, getegid, makedirs
from subprocess import Popen, PIPE
import shutil
import errno

import boom

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

# Mock objects

class MockArgs(object):
    """Mock arguments class for testing boom command line infrastructure.
    """
    add_opts = ""
    architecture = None
    boot_id = "12345678"
    btrfs_opts = ""
    btrfs_subvolume = "23"
    command = ""
    config = ""
    debug = ""
    del_opts = ""
    efi = ""
    efi = ""
    from_host = ""
    host_id = None
    host_name = ""
    host_profile = ""
    host_profile = ""
    identifier = ""
    initramfs_pattern = ""
    initrd = ""
    kernel_pattern = ""
    label = ""
    linux = ""
    lvm_opts = ""
    machine_id = ""
    name = ""
    name_prefixes = False
    no_dev = False
    no_headings = False
    options = ""
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
    title = ""
    type = ""
    uname_pattern = ""
    verbose = 0
    version = ""

# Cached logical volume to use for tests
_lv_cache = None

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

    p = Popen(["lvs", "--noheadings", "-ovgname,name"], stdout=PIPE,
              close_fds=True)
    out = p.communicate()[0]
    lvs = []
    for line in out.splitlines():
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
    return get_logical_volume()[5:]


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
    p = Popen(["lvs", "--noheadings", "-oname"], stdout=PIPE, stderr=None)
    out = p.communicate()[0]
    if len(out.splitlines()):
        return True
    return False


def have_grub1():
    """Return ``True`` if the grub1 bootloader commands are present,
        or ``False`` otherwise.
    """
    try:
        p = Popen(["grub", "--help"], stdout=PIPE, stderr=PIPE)
        out = p.communicate()[0]
        return True
    except OSError:
        return False


__all__ = [
    'BOOT_ROOT_TEST', 'SANDBOX_PATH',
    'rm_sandbox', 'mk_sandbox', 'reset_sandbox', 'reset_boom_paths',
    'get_logical_volume', 'get_root_lv',
    'MockArgs',
    'have_root', 'have_lvm', 'have_grub1'
]

# vim: set et ts=4 sw=4 :

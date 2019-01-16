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
    boot_id = "12345678"
    title = ""
    version = ""
    machine_id = ""
    linux = ""
    initrd = ""
    efi = ""
    root_device = ""
    root_lv = ""
    btrfs_subvolume = "23"
    os_id = ""
    name = ""
    short_name = ""
    os_version = ""
    os_version_id = ""
    os_options = ""
    profile = ""
    uname_pattern = ""
    host_profile = ""
    label = ""


# Test predicates

def have_root():
    """Return ``True`` if the test suite is running as the root user,
        and ``False`` otherwise.
    """
    return geteuid() == 0 and getegid() == 0

__all__ = [
    'BOOT_ROOT_TEST', 'SANDBOX_PATH',
    'rm_sandbox', 'mk_sandbox', 'reset_sandbox', 'reset_boom_paths',
    'MockArgs',
    'have_root'
]

# vim: set et ts=4 sw=4 :

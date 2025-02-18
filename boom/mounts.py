# Copyright Red Hat
#
# boom/mounts.py - Boom command line mount support
#
# This file is part of the boom project.
#
# SPDX-License-Identifier: GPL-2.0-only
"""The ``boom.mounts`` module provides helper routines for handling
command-line mount units as supported by systemd.
"""
from subprocess import run, PIPE, DEVNULL, CalledProcessError
import logging

from boom import BoomError

# Module logging configuration
_log = logging.getLogger(__name__)

_log_debug = _log.debug
_log_info = _log.info
_log_warn = _log.warning
_log_error = _log.error


class BoomMountError(BoomError):
    """Boom exception indicating a problem parsing a command line
    mount specification.
    """


#: Format for systemd command line mount units
MOUNT_UNIT_FMT = "systemd.mount-extra=%s:%s:%s:%s"

#: Format for systemd command line swap units
SWAP_UNIT_FMT = "systemd.swap-extra=%s:%s"

#: The blkid command
_blkid = "blkid"


def _detect_fstype(dev):
    """Detect the file system type corresponding to device ``dev``."""
    p = run([_blkid, dev], stdin=DEVNULL, stdout=PIPE, stderr=PIPE, check=True)
    _log_info("parsing mount blkid out: %s", p.stdout)
    for tag in p.stdout.decode("utf8").split():
        if "=" in tag:
            if tag.startswith("TYPE="):
                (_tag, fstype) = tag.split("=")
                return fstype.lstrip('"').rstrip('"')
    raise BoomMountError("Could not determine fstype for %s" % dev)


def _parse_mount_unit(mount):
    """Parse a boom command line mount specification into the format
    required by the systemd boot syntax.

    :param mount: The boom command line mount specification.
    :returns: A string in systemd mount unit format.
    """
    _log_info("parsing mount unit: %s", mount)
    parts = mount.split(":")
    if len(parts) < 2:
        raise BoomMountError("Invalid mount specification: '%s'" % mount)
    what = parts[0]
    where = parts[1]
    if len(parts) > 2:
        fstype = parts[2]
    else:
        try:
            fstype = _detect_fstype(what)
        except CalledProcessError:
            raise BoomMountError("Could not determine fstype for %s" % what)
    if len(parts) > 3:
        options = parts[3]
    else:
        options = "defaults"

    return MOUNT_UNIT_FMT % (what, where, fstype, options)


def parse_mount_units(mounts):
    """Parse a list of command line mount specifications.

    :param mounts: A list of boom command line mount specifications.
    :retruns: A list of strings in systemd swap unit format.
    """
    _log_info("parsing mount units")
    return [_parse_mount_unit(mnt) for mnt in mounts]


def _parse_swap_unit(swap):
    """Parse a boom command line swap specification into the format
    required by the systemd boot syntax.

    :param mount: The boom command line swap specification.
    :returns: A string in systemd swap unit format.
    """
    if ":" in swap:
        (what, options) = swap.split(":")
    else:
        what = swap
        options = "defaults"
    return SWAP_UNIT_FMT % (what, options)


def parse_swap_units(swaps):
    """Parse a list of command line swap specifications.

    :param swaps: A list of boom command line swap specifications.
    :returns: A list of strings in systemd mount unit format.
    """
    return [_parse_swap_unit(swap) for swap in swaps]


__all__ = [
    "parse_mount_units",
    "parse_swap_units",
    "BoomMountError",
]

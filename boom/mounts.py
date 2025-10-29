# Copyright Red Hat
#
# boom/mounts.py - Boom command line mount support
#
# This file is part of the boom project.
#
# SPDX-License-Identifier: Apache-2.0
"""The ``boom.mounts`` module provides helper routines for handling
command-line mount units as supported by systemd.
"""
from subprocess import run, PIPE, DEVNULL, CalledProcessError, TimeoutExpired
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

    @staticmethod
    def malformed_mount(mount):
        return BoomMountError(f"Malformed mount unit: {mount}")

    @staticmethod
    def malformed_swap(swap):
        return BoomMountError(f"Malformed swap unit: {swap}")

    @staticmethod
    def unknown_fstype(dev):
        return BoomMountError(f"Could not determine fstype for {dev}")

    @staticmethod
    def invalid_device(device):
        return BoomMountError(f"Invalid mount device: {device}")

    @staticmethod
    def invalid_swap_device(device):
        return BoomMountError(f"Invalid swap device: {device}")

    @staticmethod
    def invalid_options(options):
        return BoomMountError(f"Invalid options: '{options}'")

    @staticmethod
    def invalid_mount_point(mount_point):
        return BoomMountError(f"Invalid mount point: {mount_point}")


#: Format for systemd command line mount units
MOUNT_UNIT_FMT = "systemd.mount-extra=%s:%s:%s:%s"

#: Format for systemd command line swap units
SWAP_UNIT_FMT = "systemd.swap-extra=%s:%s"

#: The blkid command
_BLKID = "blkid"

_DEV_PREFIXES = ("/dev/", "UUID=", "LABEL=", "PARTUUID=", "PARTLABEL=")


def _detect_fstype(dev):
    """Detect the file system type corresponding to device ``dev``."""
    p = run(
        [_BLKID, "--", dev],
        stdin=DEVNULL,
        stdout=PIPE,
        stderr=PIPE,
        check=True,
        timeout=10,
    )
    decoded_output = p.stdout.decode("utf8", errors="replace")
    _log_debug("parsing blkid out: %s", decoded_output)
    for tag in decoded_output.split():
        if "=" in tag:
            if tag.startswith("TYPE="):
                (_tag, fstype) = tag.split("=")
                return fstype.lstrip('"').rstrip('"')
    raise BoomMountError.unknown_fstype(dev)


def _parse_mount_unit(mount):
    """Parse a boom command line mount specification into the format
    required by the systemd boot syntax.

    :param mount: The boom command line mount specification.
    :returns: A string in systemd mount unit format.
    """
    _log_debug("parsing mount unit: %s", mount)
    parts = mount.split(":")

    if len(parts) < 2:
        raise BoomMountError.malformed_mount(mount)

    what = parts[0].strip()
    where = parts[1].strip()

    if not what.startswith(_DEV_PREFIXES):
        raise BoomMountError.invalid_device(what)

    if len(parts) > 2:
        fstype = parts[2].strip()
    else:
        try:
            fstype = _detect_fstype(what)
        except (CalledProcessError, TimeoutExpired) as err:
            raise BoomMountError.unknown_fstype(what) from err
    if len(parts) > 3:
        options = parts[3].strip()
    else:
        options = "defaults"

    if not where.startswith("/"):
        if not (where == "none" and fstype == "swap"):
            raise BoomMountError.invalid_mount_point(where)

    if len(parts) > 4:
        raise BoomMountError.malformed_mount(mount)

    if any(not part for part in [what, where, fstype, options]):
        raise BoomMountError.malformed_mount(mount)

    return MOUNT_UNIT_FMT % (what, where, fstype, options)


def parse_mount_units(mounts):
    """Parse a list of command line mount specifications.

    :param mounts: A list of boom command line mount specifications.
    :returns: A list of strings in systemd mount unit format.
    """
    _log_debug("parsing mount units")
    return [_parse_mount_unit(mnt.strip()) for mnt in mounts]


def _parse_swap_unit(swap):
    """Parse a boom command line swap specification into the format
    required by the systemd boot syntax.

    :param swap: The boom command line swap specification.
    :returns: A string in systemd swap unit format.
    """
    _log_debug("parsing swap unit: %s", swap)
    if ":" in swap:
        (what, options) = swap.split(":", maxsplit=1)
        what = what.strip()
        options = options.strip()
        if not what:
            raise BoomMountError.invalid_swap_device(swap)
        if not options:
            raise BoomMountError.invalid_options(swap)
    else:
        what = swap.strip()
        options = "defaults"

    if ":" in options:
        raise BoomMountError.malformed_swap(swap)

    if not what.startswith(_DEV_PREFIXES):
        raise BoomMountError.invalid_swap_device(what)

    return SWAP_UNIT_FMT % (what, options)


def parse_swap_units(swaps):
    """Parse a list of command line swap specifications.

    :param swaps: A list of boom command line swap specifications.
    :returns: A list of strings in systemd swap unit format.
    """
    _log_debug("parsing swap units")
    return [_parse_swap_unit(swap.strip()) for swap in swaps]


__all__ = [
    "parse_mount_units",
    "parse_swap_units",
    "BoomMountError",
]

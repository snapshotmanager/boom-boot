# Copyright Red Hat
#
# boom/lvm2.py - Boom LVM2 storage integration
#
# This file is part of the boom project.
#
# SPDX-License-Identifier: Apache-2.0
"""The ``boom.lvm2`` module contains functions and constants
needed to obtain information from lvm about the volume groups
and logical volumes present on the system.
"""
from subprocess import run, CalledProcessError
from os.path import exists
import logging

# Module logging configuration
_log = logging.getLogger(__name__)

_log_debug = _log.debug
_log_info = _log.info
_log_warn = _log.warning
_log_error = _log.error

#: LVM2 device-mapper UUID prefix
LVM_UUID_PREFIX = "LVM-"

_CMD_ENV = {
    "LC_ALL": "C",
}


def vg_lv_from_device_path(devpath: str) -> str:
    """Return a ``"vg_name/lv_name"`` string for the LVM device at
    ``devpath``.

    :param devpath: The path to an LVM logical volume.
    :type devpath: ``str``
    :returns: A ``"vg_name/lv_name"`` string for ``devpath``.
    :rtype: ``str``
    """
    lvs_cmd_args = ["lvs", "--noheadings", "--options", "vg_name,lv_name", devpath]
    try:
        lvs_cmd = run(lvs_cmd_args, env=_CMD_ENV, capture_output=True, check=True)
    except FileNotFoundError:
        return ""
    except CalledProcessError as err:
        stderr = err.stderr.decode("utf8")
        if "not found" not in stderr:
            _log_debug(
                "Error calling lvs command: '%s': %s",
                " ".join(lvs_cmd_args),
                stderr,
            )
        return ""
    vg, lv = lvs_cmd.stdout.decode("utf8").split()
    return f"{vg}/{lv}"


def is_lvm_device_path(devpath: str) -> bool:
    """Return ``True`` if ``devpath`` corresponds to an LVM2 logical
    volume device path or ``False`` otherwise.

    :param devpath: A device path to test.
    :type devpath: ``str``
    :returns: ``True`` if ``devpath`` is an LVM2 logical volume or
              ``False``
    """
    if not devpath or not exists(devpath):
        return False

    dmsetup_cmd_args = [
        "dmsetup",
        "info",
        "--noheadings",
        "--columns",
        "--options",
        "uuid",
        devpath,
    ]

    try:
        dmsetup_cmd = run(
            dmsetup_cmd_args, env=_CMD_ENV, capture_output=True, check=True
        )
    except FileNotFoundError:
        return False
    except CalledProcessError as err:
        stderr = err.stderr.decode("utf8")
        if "not found" not in stderr:
            _log_debug(
                "Error calling dmsetup command: '%s': %s",
                " ".join(dmsetup_cmd_args),
                stderr,
            )
        return False
    uuid = dmsetup_cmd.stdout.decode("utf8").strip()
    return uuid.startswith(LVM_UUID_PREFIX)


__all__ = [
    "vg_lv_from_device_path",
    "is_lvm_device_path",
]

# vim: set et ts=4 sw=4 :

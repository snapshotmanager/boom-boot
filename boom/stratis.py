# Copyright Red Hat
#
# boom/stratis.py - Boom Stratis storage integration
#
# This file is part of the boom project.
#
# SPDX-License-Identifier: GPL-2.0-only
"""The ``boom.stratis`` module contains functions and constants
needed to obtain information from a running ``stratisd`` daemon
about the Stratis storage pools and file systems present on the
system.

This includes the ability to obtain the stratis ``pool_uuid``
value for a given Stratis storage pool name. This is needed to
set the ``stratis.rootfs.pool_uuid`` kernel command line argument
that is read by the Stratis early userspace systemd generator.
"""
from __future__ import print_function

import logging
from os import sep as path_sep
from os.path import normpath
from uuid import UUID
import dbus

from boom import *

# Module logging configuration
_log = logging.getLogger(__name__)
_log.set_debug_mask(BOOM_DEBUG_STRATIS)

_log_debug = _log.debug
_log_debug_stratis = _log.debug_masked
_log_info = _log.info
_log_warn = _log.warning
_log_error = _log.error

# Constants for the Stratisd DBus service

#: The DBus name of the stratisd service
_STRATISD_SERVICE = "org.storage.stratis3"
#: The path to the stratisd service object
_STRATISD_PATH = "/org/storage/stratis3"
#: The DBus name of the pool interface
_POOL_IFACE = "org.storage.stratis3.pool.r0"
#: The DBus timeout for stratisd in milliseconds
_STRATISD_TIMEOUT = 120000

#: The DBus ObjectManager interface implemented by stratisd
_DBUS_OBJECT_MANAGER_IFACE = "org.freedesktop.DBus.ObjectManager"


def pool_name_to_pool_uuid(pool_name):
    """Return the UUID of the pool named ``pool_name`` as a string.

    :param pool_name: The name of the Stratis pool.
    :returns: A string representation of the pool UUID value. The
              returned string contains the un-formatted character
              sequence that makes up the pool UUID.

    :rtype: str
    """
    bus = dbus.SystemBus()
    _log_debug_stratis(
        "Connecting to %s at %s via system bus", (_STRATISD_SERVICE, _STRATISD_PATH)
    )
    proxy = bus.get_object(_STRATISD_SERVICE, _STRATISD_PATH, introspect=False)
    object_manager = dbus.Interface(proxy, _DBUS_OBJECT_MANAGER_IFACE)
    managed_objects = object_manager.GetManagedObjects(_STRATISD_TIMEOUT)
    try:
        props = next(
            obj_data[_POOL_IFACE]
            for _, obj_data in managed_objects.items()
            if _POOL_IFACE in obj_data and obj_data[_POOL_IFACE]["Name"] == pool_name
        )
    except StopIteration as e:
        raise IndexError("Stratis pool '%s' not found" % pool_name)
    pool_uuid = str(props["Uuid"])
    _log_debug(
        "Looked up pool_uuid=%s for Stratis pool %s",
        format_pool_uuid(pool_uuid),
        pool_name,
    )
    return pool_uuid


def symlink_to_pool_uuid(link_path):
    """Return the UUID of the pool corresponding to the stratis file system
    at ``link_path`` as a string.

    :param link_path: A symbolic link corresponding to a Stratis file
                     system on the local system.
    :returns: A string representation of the UUID value. The returned
              string contains the un-formatted character sequence that
              makes up the pool UUID.
    :rtype: str
    """
    # Separate the "pool" and "fs" components from a Stratis file system
    # link path formatted as "/dev/stratis/pool/ps".
    (pool, fs) = normpath(link_path).split(path_sep)[-2:]
    _log_debug_stratis("Looking up pool UUID for Stratis symlink '%s'" % link_path)
    return pool_name_to_pool_uuid(pool)


def format_pool_uuid(pool_uuid):
    """Return the UUID ``pool_uuid`` formatted as a hyphen-separated
    string.

    :param pool_uuid: The UUID value to format.
    :returns: A hyphen-separated string representation of the UUID.
    :rtype: str
    """
    uuid = UUID(pool_uuid)
    return str(uuid)


def is_stratis_device_path(dev_path):
    prefix = "/dev/stratis/"
    if not normpath(dev_path).startswith(prefix):
        return False
    try:
        pool_uuid = symlink_to_pool_uuid(dev_path)
    except (dbus.DBusException, IndexError):
        return False
    return True


__all__ = [
    "symlink_to_pool_uuid",
    "pool_name_to_pool_uuid",
    "format_pool_uuid",
    "is_stratis_device_path",
]

# vim: set et ts=4 sw=4 :

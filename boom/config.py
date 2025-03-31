# Copyright Red Hat
#
# boom/config.py - Boom persistent configuration
#
# This file is part of the boom project.
#
# SPDX-License-Identifier: GPL-2.0-only
"""The ``boom.config`` module defines classes, constants and functions
for reading and writing persistent (on-disk) configuration for the boom
library and tools.

Users of the module can load and write configuration data, and obtain
the values of configuration keys defined in the boom configuration file.
"""
from __future__ import print_function

from os.path import dirname

from os import fdopen, rename, chmod, fdatasync
from configparser import ConfigParser, ParsingError
from tempfile import mkstemp
import logging

from boom import *


class BoomConfigError(BoomError):
    """Base class for boom configuration errors."""

    pass


# Module logging configuration
_log = logging.getLogger(__name__)

_log_debug = _log.debug
_log_info = _log.info
_log_warn = _log.warning
_log_error = _log.error

#
# Constants for configuration sections and options: to add a new option,
# create a new _CFG_* constant giving the name of the option and add a
# hook to load_boom_config() to set the value when read.
#
# To add a new section add the section name constant as _CFG_SECT_* and
# add a new branch to load_boom_config() to test for the presence of
# the section and handle the options found within.
#
_CFG_SECT_GLOBAL = "global"
_CFG_SECT_LEGACY = "legacy"
_CFG_BOOT_ROOT = "boot_root"
_CFG_BOOM_ROOT = "boom_root"
# *_path synonyms for backwards compatibility
_CFG_BOOT_PATH = "boot_path"
_CFG_BOOM_PATH = "boom_path"
_CFG_LEGACY_ENABLE = "enable"
_CFG_LEGACY_FMT = "format"
_CFG_LEGACY_SYNC = "sync"
_CFG_SECT_CACHE = "cache"
_CFG_CACHE_ENABLE = "enable"
_CFG_CACHE_AUTOCLEAN = "auto_clean"
_CFG_CACHE_PATH = "cache_path"


def _read_boom_config(path=None):
    """Read boom persistent configuration values from the defined path
    and return them as a ``BoomConfig`` object.

    :param path: the configuration file to read, or None to read the
                 currently configured config file path.

    :rtype: BoomConfig
    """
    path = path or get_boom_config_path()
    _log_debug("reading boom configuration from '%s'", path)
    cfg = ConfigParser()
    try:
        cfg.read(path)
    except ParsingError as e:
        _log_error("Failed to parse configuration file '%s': %s", path, e)

    bc = BoomConfig()

    trues = ["True", "true", "Yes", "yes"]

    if not cfg.has_section(_CFG_SECT_GLOBAL):
        raise ValueError("Missing 'global' section in %s" % path)

    if cfg.has_section(_CFG_SECT_GLOBAL):
        if cfg.has_option(_CFG_SECT_GLOBAL, _CFG_BOOT_ROOT):
            _log_debug("Found global.boot_root")
            bc.boot_path = cfg.get(_CFG_SECT_GLOBAL, _CFG_BOOT_ROOT)
        if cfg.has_option(_CFG_SECT_GLOBAL, _CFG_BOOT_PATH):
            _log_debug("Found global.boot_path: redirecting to global.boot_root")
            bc.boot_path = cfg.get(_CFG_SECT_GLOBAL, _CFG_BOOT_PATH)
        if cfg.has_option(_CFG_SECT_GLOBAL, _CFG_BOOM_ROOT):
            _log_debug("Found global.boom_root")
            bc.boom_path = cfg.get(_CFG_SECT_GLOBAL, _CFG_BOOM_ROOT)
        if cfg.has_option(_CFG_SECT_GLOBAL, _CFG_BOOM_PATH):
            _log_debug("Found global.boom_path: redirecting to global.boom_root")
            bc.boom_path = cfg.get(_CFG_SECT_GLOBAL, _CFG_BOOM_PATH)

    if cfg.has_section(_CFG_SECT_LEGACY):
        if cfg.has_option(_CFG_SECT_LEGACY, _CFG_LEGACY_ENABLE):
            _log_debug("Found legacy.enable")
            enable = cfg.get(_CFG_SECT_LEGACY, _CFG_LEGACY_ENABLE)
            bc.legacy_enable = any([t for t in trues if t in enable])

        if cfg.has_option(_CFG_SECT_LEGACY, _CFG_LEGACY_FMT):
            bc.legacy_format = cfg.get(_CFG_SECT_LEGACY, _CFG_LEGACY_FMT)

        if cfg.has_option(_CFG_SECT_LEGACY, _CFG_LEGACY_SYNC):
            _log_debug("Found legacy.sync")
            sync = cfg.get(_CFG_SECT_LEGACY, _CFG_LEGACY_SYNC)
            bc.legacy_sync = any([t for t in trues if t in sync])

    if cfg.has_section(_CFG_SECT_CACHE):
        if cfg.has_option(_CFG_SECT_CACHE, _CFG_CACHE_ENABLE):
            _log_debug("Found cache.enable")
            enable = cfg.get(_CFG_SECT_CACHE, _CFG_CACHE_ENABLE)
            bc.cache_enable = any([t for t in trues if t in enable])

        if cfg.has_option(_CFG_SECT_CACHE, _CFG_CACHE_PATH):
            _log_debug("Found cache.cache_path")
            bc.cache_path = cfg.get(_CFG_SECT_CACHE, _CFG_CACHE_PATH)

    _log_debug("read configuration: %s", repr(bc))
    bc._cfg = cfg
    return bc


def load_boom_config(path=None):
    """Load boom persistent configuration values from the defined path
    and make the them the active configuration.

    :param path: the configuration file to read, or None to read the
                 currently configured config file path

    :rtype: None
    """
    bc = _read_boom_config(path=path)
    set_boom_config(bc)
    return bc


def _sync_config(bc, cfg):
    """Sync the configuration values of ``BoomConfig`` object ``bc`` to
    the ``ConfigParser`` ``cfg``.
    """

    def yes_no(value):
        if value:
            return "yes"
        return "no"

    def attr_has_value(obj, attr):
        return hasattr(obj, attr) and getattr(obj, attr) is not None

    if attr_has_value(bc, "boot_path"):
        cfg.set(_CFG_SECT_GLOBAL, _CFG_BOOT_ROOT, bc.boot_path)
    if attr_has_value(bc, "boom_path"):
        cfg.set(_CFG_SECT_GLOBAL, _CFG_BOOM_ROOT, bc.boom_path)
    if attr_has_value(bc, "legacy_enable"):
        cfg.set(_CFG_SECT_LEGACY, _CFG_LEGACY_ENABLE, yes_no(bc.legacy_enable))
    if attr_has_value(bc, "legacy_format"):
        cfg.set(_CFG_SECT_LEGACY, _CFG_LEGACY_FMT, bc.legacy_format)
    if attr_has_value(bc, "legacy_sync"):
        cfg.set(_CFG_SECT_LEGACY, _CFG_LEGACY_SYNC, yes_no(bc.legacy_sync))
    if attr_has_value(bc, "cache_enable"):
        cfg.set(_CFG_SECT_CACHE, _CFG_CACHE_ENABLE, yes_no(bc.cache_enable))
    if attr_has_value(bc, "cache_auto_clean"):
        cfg.set(_CFG_SECT_CACHE, _CFG_CACHE_AUTOCLEAN, yes_no(bc.cache_auto_clean))
    if attr_has_value(bc, "cache_path"):
        cfg.set(_CFG_SECT_CACHE, _CFG_CACHE_PATH, bc.cache_path)


def __make_config(bc):
    """Create a new ``ConfigParser`` corresponding to the ``BoomConfig``
    object ``bc`` and return the result.
    """
    cfg = ConfigParser()
    cfg.add_section("global")
    cfg.add_section("legacy")
    cfg.add_section("cache")
    _sync_config(bc, cfg)
    bc._cfg = cfg
    return bc


def write_boom_config(config=None, path=None):
    """Write boom configuration to disk.

    :param config: the configuration values to write, or None to
                   write the current configuration
    :param path: the configuration file to read, or None to read the
                 currently configured config file path

    :rtype: None
    """
    path = path or get_boom_config_path()
    cfg_dir = dirname(path)
    (tmp_fd, tmp_path) = mkstemp(prefix="boom", dir=cfg_dir)

    config = config or get_boom_config()

    if not hasattr("config", "_cfg") or not config._cfg:
        __make_config(config)
    else:
        _sync_config(config, config._cfg)

    with fdopen(tmp_fd, "w") as f_tmp:
        config._cfg.write(f_tmp)
        fdatasync(tmp_fd)

    try:
        rename(tmp_path, path)
        chmod(path, BOOT_CONFIG_MODE)
    except Exception as e:
        _log_error("Error writing configuration file %s: %s", path, e)
        try:
            unlink(tmp_path)
        except Exception:
            _log_error("Error unlinking temporary path %s", tmp_path)
        raise e


__all__ = [
    "BoomConfigError",
    # Configuration file handling
    "load_boom_config",
    "write_boom_config",
]

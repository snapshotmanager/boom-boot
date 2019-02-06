# Copyright (C) 2017 Red Hat, Inc., Bryn M. Reeves <bmr@redhat.com>
#
# config.py - Boom persistent configuration
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
"""The ``boom.config`` module defines classes and constants and functions
for reading and writing persistent (on-disk) configuration for the boom
library and tools.

Users of the module can load and write configuration data, and obtain
the values of configuration keys defined in the boom configuration file.
"""
from boom import *

from os.path import (
    isabs, isdir, dirname, exists as path_exists, join as path_join
)

from os import fdopen, rename, chmod, fdatasync, dup
from tempfile import mkstemp
from errno import ENOENT
import logging

try:
    # Python2
    from ConfigParser import SafeConfigParser as ConfigParser, ParsingError
except:
    # Python3
    from configparser import ConfigParser, ParsingError

class BoomConfigError(BoomError):
    """Base class for boom configuration errors.
    """
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
_CFG_LEGACY_ENABLE = "enable"
_CFG_LEGACY_FMT = "format"
_CFG_LEGACY_SYNC = "sync"


def _read_boom_config(path=None):
    """Read boom persistent configuration values from the defined path
        and return them as a ``BoomConfig`` object.

        :param path: the configuration file to read, or None to read the
                     currently configured config file path.

        :returntype: BoomConfig
    """
    path = path or get_boom_config_path()
    _log_debug("reading boom configuration from '%s'" % path)
    cfg = ConfigParser()
    try:
        cfg.read(path)
    except ParsingError as e:
        _log_error("Failed to parse configuration file '%s': %s" %
                   (path, e))

    bc = BoomConfig()

    trues = ['True', 'true', 'Yes', 'yes']

    if cfg.has_section(_CFG_SECT_GLOBAL):
        if cfg.has_option(_CFG_SECT_GLOBAL, _CFG_BOOT_ROOT):
            _log_debug("Found global.boot_path")
            bc.boot_path = cfg.get(_CFG_SECT_GLOBAL, _CFG_BOOT_ROOT)
        if cfg.has_option(_CFG_SECT_GLOBAL, _CFG_BOOM_ROOT):
            _log_debug("Found global.boom_path")
            bc.boom_path = cfg.get(_CFG_SECT_GLOBAL, _CFG_BOOM_ROOT)

    if cfg.has_section(_CFG_SECT_LEGACY):
        if cfg.has_option(_CFG_SECT_LEGACY, _CFG_LEGACY_ENABLE):
            _log_debug("Found legacy.enable")
            enable = cfg.get(_CFG_SECT_LEGACY, _CFG_LEGACY_ENABLE)
            bc.legacy_enable = any([t for t in trues if t in enable])

        if cfg.has_option(_CFG_SECT_LEGACY, _CFG_LEGACY_FMT):
            bc.legacy_format = cfg.get(_CFG_SECT_LEGACY,
                                       _CFG_LEGACY_FMT)

        if cfg.has_option(_CFG_SECT_LEGACY, _CFG_LEGACY_SYNC):
            _log_debug("Found legacy.sync")
            sync = cfg.get(_CFG_SECT_LEGACY, _CFG_LEGACY_SYNC)
            bc.legacy_sync = any([t for t in trues if t in sync])

    _log_debug("read configuration: %s" % repr(bc))
    bc._cfg = cfg
    return bc


def load_boom_config(path=None):
    """Load boom persistent configuration values from the defined path
        and make the them the active configuration.

        :param path: the configuration file to read, or None to read the
                     currently configured config file path

        :returntype: None
    """
    bc = _read_boom_config(path=path)
    set_boom_config(bc)


def __sync_config(bc, cfg):
    """Sync the configuration values of ``BoomConfig`` object ``bc`` to
        the ``ConfigParser`` ``cfg``.
    """

    def attr_has_value(obj, attr):
        return hasattr(obj, attr) and getattr(obj, attr) is not None

    if attr_has_value(bc, "boot_path"):
        cfg.set(_CFG_SECT_GLOBAL, _CFG_BOOT_ROOT, bc.boot_path)
    if attr_has_value(bc, "boom_path"):
        cfg.set(_CFG_SECT_GLOBAL, _CFG_BOOM_ROOT, bc.boom_path)
    if attr_has_value(bc, "legacy_enable"):
        cfg.set(_CFG_SECT_LEGACY, _CFG_LEGACY_ENABLE, str(bc.legacy_enable))
    if attr_has_value(bc, "legacy_format"):
        cfg.set(_CFG_SECT_LEGACY, _CFG_LEGACY_FMT, bc.legacy_format)
    if attr_has_value(bc, "legacy_sync"):
        cfg.set(_CFG_SECT_LEGACY, _CFG_LEGACY_SYNC, bc.legacy_sync)


def __make_config(bc):
    """Create a new ``ConfigParser`` corresponding to the ``BoomConfig``
        object ``bc`` and return the result.
    """
    cfg = ConfigParser()
    cfg.add_section("global")
    cfg.add_section("legacy")
    __sync_config(bc, cfg)
    return bc


def write_boom_config(config=None, path=None):
    """Write boom configuration to disk.

        :param config: the configuration values to write, or None to
                       write the current configuration
        :param path: the configuration file to read, or None to read the
                     currently configured config file path

        :returntype: None
    """
    path = path or get_boom_config_path()
    cfg_dir = dirname(path)
    (tmp_fd, tmp_path) = mkstemp(prefix="boom", dir=cfg_dir)

    config = config or get_boom_config()

    if not config._cfg:
        config._cfg = __make_config(config)
    else:
        __sync_config(config, config._cfg)

    with fdopen(tmp_fd, "w") as f_tmp:
        config._cfg.write(f_tmp)
        fdatasync(tmp_fd)

    try:
        rename(tmp_path, path)
        chmod(path, BOOT_CONFIG_MODE)
    except Exception as e:
        _log_error("Error writing configuration file %s: %s" %
                   (path, e))
        try:
            unlink(tmp_path)
        except:
            pass
        raise e


__all__ = [
    'BoomConfigError', 'BoomConfig',

    # Configuration file handling
    'load_boom_config',
    'write_boom_config'
]

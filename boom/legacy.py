# Copyright Red Hat
#
# boom/legacy.py - Boom legacy bootloader manager
#
# This file is part of the boom project.
#
# SPDX-License-Identifier: GPL-2.0-only
"""The ``boom.legacy`` module defines classes and constants for working
with legacy bootloader configuration formats.

Legacy formats are read-only and can only be updated by synchronising
the entire current set of boot entries to the legacy format, or removing
all entries from the legacy configuration file.
"""
from __future__ import print_function

from subprocess import Popen, PIPE
from os.path import dirname, exists, isabs, join as path_join
from os import chmod, dup, fdatasync, fdopen, rename, unlink
from tempfile import mkstemp
import logging
import re

from boom import *
from boom.bootloader import *

#: Format strings use to construct begin/end markers
BOOM_LEGACY_BEGIN_FMT = "#--- BOOM_%s_BEGIN ---"
BOOM_LEGACY_END_FMT = "#--- BOOM_%s_END ---"

#: Constants for legacy boot loaders supported by boom
BOOM_LOADER_GRUB1 = "grub1"
BOOM_GRUB1_CFG_PATH = "grub/grub.conf"

# Module logging configuration
_log = logging.getLogger(__name__)

_log_debug = _log.debug
_log_info = _log.info
_log_warn = _log.warning
_log_error = _log.error

#: Grub1 root device cache
__grub1_device = None


def _get_grub1_device(force=False):
    """Determine the current grub1 root device and return it as a
    string. This function will attempt to use a cached value
    from a previous call (to avoid shelling out to Grub a
    second time), unless the ``force`` argument is ``True``.

    If no usable Grub1 environment is detected the function
    raises the ``BoomLegacyFormatError`` exception.

    :param force: force the cache to be updated.
    """
    # Grub1 device cache
    global __grub1_device

    if __grub1_device and not force:
        return __grub1_device

    # The grub1 binary
    grub_cmd = "grub"
    # The command to issue to discover the /boot device
    find_cmd = "find /%s\n" % _loader_map[BOOM_LOADER_GRUB1][2]
    # Regular expression matching a valid grub device string
    find_rgx = r" \(hd\d+,\d+\)"

    try:
        _log_debug("Calling grub1 shell with '%s'", find_cmd)
        p = Popen(grub_cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        out = p.communicate(input=bytes(find_cmd.encode("utf8")))
    except OSError:
        raise BoomLegacyFormatError("Could not execute grub1 shell.")

    for line in out[0].decode("utf8").splitlines():
        if re.match(find_rgx, line):
            __grub1_device = line.lstrip().rstrip()
            _log_debug("Set grub1 device to '%s'", __grub1_device)
            return __grub1_device


class BoomLegacyFormatError(BoomError):
    """Boom exception indicating an invalid or corrupt boom legacy
    boot configuration, for example, missing begin or end marks
    in the legacy bootloader configuration file, or an unknown
    or invalid legacy bootloader type.
    """

    pass


def find_legacy_loader(loader, cfg_path):
    """Look up a legacy loader format in the table of available formats
    and return a tuple containing the format name, decorator class
    and the configuration file path. If ``cfg_path`` is set it will
    override the default file location for the format.

    :param loader: the legacy bootloader format to operate on
    :param cfg_path: the path to the legacy bootloader configuration
                     file. If ``cfg_path`` is None the default path
                     for the specified loader will be used.
    :raises BoomLegacyFormatError: if the legacy configuration file
                                   contains invalid boom entries or
                                   the specified legacy format is
                                   unknown or invalid.
    :returns: (name, decorator, path) tuple
    """
    if not loader:
        raise BoomLegacyFormatError("Invalid legacy bootloader format: %s" % loader)
    if loader not in _loader_map:
        raise BoomLegacyFormatError("Unknown legacy bootloader format: %s" % loader)

    (name, decorator, path) = _loader_map[loader]
    path = cfg_path or path
    return (name, decorator, path)


def write_legacy_loader(selection=None, loader=BOOM_LOADER_GRUB1, cfg_path=None):
    """Synchronise boom's configuration with the specified legacy boot
    loader.

    For boot loaders that support only a single configuration file
    with multiple boot entries, boom will generate a block of
    configuration statements bounded by "BOOM_BEGIN"/"BOOM_END" on
    a line by themselves and prefixed with the comment character
    for that configuration format (e.g. '#').

    :param selection: A ``Selection`` object specifying the match
                      criteria for the operation.
    :param loader: the legacy boot loader type to write
    :param cfg_path: the path to the legacy bootloader configuration
                     file. If ``cfg_path`` is None the default path
                     for the specified loader will be used.
    """
    (name, decorator, path) = find_legacy_loader(loader, cfg_path)

    if not isabs(path):
        path = path_join(get_boot_path(), path)

    cfg_dir = dirname(path)

    if not exists(cfg_dir):
        _log_error("Cannot write %s configuration: '%s' does not exist'", name, cfg_dir)
        return

    begin_tag = BOOM_LEGACY_BEGIN_FMT % name
    end_tag = BOOM_LEGACY_END_FMT % name

    (tmp_fd, tmp_path) = mkstemp(prefix="boom", dir=cfg_dir)

    try:
        with fdopen(tmp_fd, "w") as tmp_f:
            # Our original file descriptor will be closed on exit from
            # the fdopen with statement: save a copy so that we can call
            # fdatasync once at the end of writing rather than on each
            # loop iteration.
            tmp_fd = dup(tmp_fd)
            with open(path, "r") as cfg_f:
                for line in cfg_f:
                    tmp_f.write(line)
            tmp_f.write(begin_tag + "\n")
            bes = find_entries(selection=selection)
            # Entries are naturally in the order returned by the file system:
            # this may lead to confusing re-ordering of entries in the legacy
            # boot loader configuration file, as boom entries are modified or
            # re-written (causing a change to the entry's inode number).
            #
            # Prevent this by sorting entries lexically by version.
            for be in sorted(bes, key=lambda b: (b.version, b.title)):
                dbe = decorator(be)
                tmp_f.write(str(dbe) + "\n")
            tmp_f.write(end_tag + "\n")
    except BoomLegacyFormatError as e:
        _log_error("Error formatting %s configuration: %s", name, e)
        try:
            unlink(tmp_path)
        except OSError:
            _log_error("Error unlinking temporary file '%s'", tmp_path)
        return

    try:
        fdatasync(tmp_fd)
        rename(tmp_path, path)
        chmod(path, BOOT_ENTRY_MODE)
    except Exception as e:
        _log_error("Error writing legacy configuration file %s: %s", path, e)
        try:
            unlink(tmp_path)
        except Exception:
            _log_error("Error unlinking temporary path %s", tmp_path)
        raise e


def clear_legacy_loader(loader=BOOM_LOADER_GRUB1, cfg_path=None):
    """Delete all boom managed entries from the specified legacy boot
    loader configuration file.

    If the specified ``loader`` is unknown or invalid the
    BoomLegacyFormatError exception is raised.

    This erases any lines from the file beginning with a valid
    'BOOM_*_BEGIN' line and ending with a valid 'BOOM_*_END' line.

    If both marker lines are absent this function has no effect
    and no error is raised: the file does not contain any existing
    boom legacy configuration entries.

    If one of the two markers is missing this function will not
    modify the file and a BoomLegacyFormatError exception is
    raised internally and recorded in the log. Legacy configuration
    cannot be written in this case as the file is in an inconsistent
    state that boom cannot automatically correct.

    If the configuration path is not absolute it is assumed to be
    relative to the configured system '/boot' directory as returned
    by ``boom.get_boot_path()``.

    :param loader: the legacy bootloader format to operate on
    :param cfg_path: the path to the legacy bootloader configuration
                     file. If ``cfg_path`` is None the default path
                     for the specified loader will be used.
    :returns: None
    """

    def _legacy_format_error(err, fmt_data):
        """Helper function to clean up the temporary file and raise the
        corresponding BoomLegacyFormatError exception.
        """
        if fmt_data[0] is int:
            fmt_data = ("line %d" % fmt_data[0], fmt_data[1])

        try:
            unlink(tmp_path)
        except OSError as e:
            _log_error("Could not unlink '%s': %s", tmp_path, e)
        raise BoomLegacyFormatError(err % fmt_data)

    (name, decorator, path) = find_legacy_loader(loader, cfg_path)

    if not isabs(path):
        path = path_join(get_boot_path(), path)

    cfg_dir = dirname(path)

    if not exists(cfg_dir):
        _log_error("Cannot clear %s configuration: '%s' does not exist'", name, cfg_dir)
        return

    begin_tag = BOOM_LEGACY_BEGIN_FMT % name
    end_tag = BOOM_LEGACY_END_FMT % name

    # Pre-set configuration error messages. Use a string format for
    # the line number so that 'EOF' can be passed for end-of-file.
    err_dupe_begin = (
        "Duplicate Boom begin tag at %s in legacy " + "configuration file '%s'"
    )
    err_dupe_end = "Duplicate Boom end tag at %s in legacy " + "configuration file '%s'"
    err_no_begin = "Missing Boom begin tag at %s in legacy " + "configuration file '%s'"
    err_no_end = "Missing Boom end tag at %s in legacy " + "configuration file '%s'"

    line_nr = 1
    found_boom = False
    in_boom_cfg = False

    (tmp_fd, tmp_path) = mkstemp(prefix="boom", dir=cfg_dir)

    try:
        with fdopen(tmp_fd, "w") as tmp_f:
            # Our original file descriptor will be closed on exit from
            # the fdopen with statement: save a copy so that we can call
            # fdatasync once at the end of writing rather than on each
            # loop iteration.
            tmp_fd = dup(tmp_fd)
            with open(path, "r") as cfg_f:
                for line in cfg_f:
                    if begin_tag in line:
                        if in_boom_cfg or found_boom:
                            _legacy_format_error(err_dupe_begin, (line_nr, path))
                        in_boom_cfg = True
                        continue
                    if end_tag in line:
                        if found_boom:
                            _legacy_format_error(err_dupe_end, (line_nr, path))
                        if not in_boom_cfg:
                            _legacy_format_error(err_no_begin, (line_nr, path))
                        in_boom_cfg = False
                        found_boom = True
                        continue
                    if not in_boom_cfg:
                        tmp_f.write(line)
                    line_nr += 1
    except BoomLegacyFormatError as e:
        _log_error("Error parsing %s configuration: %s", name, e)
        found_boom = False

    if in_boom_cfg and not found_boom:
        _legacy_format_error(err_no_end, ("EOF", path))

    if not found_boom:
        # No boom entries: nothing to do.
        try:
            unlink(tmp_path)
        except OSError as e:
            _log_error("Could not unlink '%s': %s", tmp_path, e)
        return

    try:
        fdatasync(tmp_fd)
        rename(tmp_path, path)
        chmod(path, BOOT_ENTRY_MODE)
    except Exception as e:
        _log_error("Error writing legacy configuration file %s: %s", path, e)
        try:
            unlink(tmp_path)
        except Exception:
            _log_error("Error unlinking temporary path %s", tmp_path)
        raise e


class Grub1BootEntry(object):
    """Class transforming a Boom ``BootEntry`` into legacy Grub1
    boot entry notation.

    The Grub1BootEntry decorates the ``__str__`` method of the
    BootEntry superclass by returning data formatted in Grub1
    configuration notation rather than BLS.

    Currently this uses a simple fixed format string for the
    Grub1 syntax. If additional legacy formats are required it
    may be better to extend the generic BootEntry.__str()
    formatter to be able to accept maps of alternate format
    keys. This is somewhat complicated by aspects like the
    grub1 boot device key (since this has no representation or
    equivalent in BLS notation).
    """

    be = None

    def __init__(self, boot_entry):
        self.be = boot_entry

    def __str__(self):
        grub1_tab = " " * 8
        grub1_fmt = (
            "title %s\n"
            + grub1_tab
            + "root %s\n"
            + grub1_tab
            + "kernel %s %s\n"
            + grub1_tab
            + "initrd %s"
        )

        return grub1_fmt % (
            self.be.title,
            _get_grub1_device(),
            self.be.linux,
            self.be.options,
            self.be.initrd,
        )


#: Map of legacy boot loader decorator classes and defaults.
#: Each entry in _loader_map is a three tuple containing the
#: format's name, decorator class and default configuration path.
_loader_map = {BOOM_LOADER_GRUB1: ("Grub1", Grub1BootEntry, BOOM_GRUB1_CFG_PATH)}

__all__ = [
    # Exception class for errors in legacy format handling
    "BoomLegacyFormatError",
    # Write legacy boot configuration
    "write_legacy_loader",
    "clear_legacy_loader",
    # Lookup legacy boot loader formats
    "find_legacy_loader",
    # Legacy bootloader names
    "BOOM_LOADER_GRUB1",
    # Legacy bootloader decorator classes
    "Grub1BootEntry",
]

# vim: set et ts=4 sw=4 :

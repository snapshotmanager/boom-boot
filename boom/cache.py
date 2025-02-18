# Copyright Red Hat
#
# boom/cache.py - Boom boot image cache
#
# This file is part of the boom project.
#
# SPDX-License-Identifier: GPL-2.0-only
"""The ``boom.cache`` module defines classes, constants and functions
for maintaining an on-disk cache of kernel, initramfs and auxiliary
images required to load boom-defined boot entries.
"""
from __future__ import print_function

from hashlib import sha1
from os import chmod, chown, fdatasync, listdir, stat, unlink
from stat import S_ISREG, ST_MODE, ST_UID, ST_GID, ST_MTIME, filemode
from os.path import (
    join as path_join,
    exists as path_exists,
    sep as path_sep,
    basename,
    dirname,
)
from json import load as json_load, dump as json_dump
from errno import ENOENT
import shutil
import logging

from boom import *
from boom.bootloader import *

# Module logging configuration
_log = logging.getLogger(__name__)
_log.set_debug_mask(BOOM_DEBUG_CACHE)

_log_debug = _log.debug
_log_debug_cache = _log.debug_masked
_log_info = _log.info
_log_warn = _log.warning
_log_error = _log.error

#: Block size for hashing image files
_hash_size = 1024**2

#: The name of the JSON cache index file
_CACHE_INDEX = "cacheindex.json"

#: The extension used for cached image files
_IMAGE_EXT = ".img"

#
# Constants for access to cache metadata dictionaries
#

#: Path timestamp
PATH_TS = "path_ts"
#: Path mode
PATH_MODE = "path_mode"
#: Path user ID
PATH_UID = "path_uid"
#: Path group ID
PATH_GID = "path_gid"
#: Path attribute map
PATH_ATTRS = "path_attrs"

#: Image timestamp
IMAGE_TS = "image_ts"

# Cache states
#: Path is cached
CACHE_CACHED = "CACHED"
#: Path is cached and missing from /boot
CACHE_MISSING = "MISSING"
#: Path is cached but image missing or damaged
CACHE_BROKEN = "BROKEN"
#: Path is cached and has been restored to /boot
CACHE_RESTORED = "RESTORED"

#
# Path names in the boom boot image cache
#
# img_path  -  The path to an image as specified in a BLS snippet, or an
#              argument to cache_path(), relative to the root of the
#              /boot file system. E.g. "/vmlinuz-5.0.0".
#
# boot_path  - The absolute path to an image relative to the host root
#              file system. E.g. "/boot/vmlinuz-5.0.0".
#
# cache_path - The absolute path to a cached boot image relative to the
#              host root file system. E.g.
#              "/boot/boom/cache/1562375e4d022e814ba39521d0852e490b7c07f8.img"
#

#: The index of img_path names to lists of image identifiers.
_index = {}

#: Mapping of img_path to path metadata dictionaries
_paths = {}

#: Mapping of image identifiers to image metadata.
_images = {}


def _make_relative(img_path):
    """Convert an image path with a leading path separator into
    a relative path fragment suitable for passing to the
    os.path.join() function.

    :param img_path: The path to convert.
    :returns: The path without any leading path separator.
    """
    if img_path[0] == path_sep:
        img_path = img_path[1:]
    return img_path


def _image_path_to_boot(img_path):
    """Convert an image path relative to /boot into an absolute
    path to the corresponding boot image.

    :param img_path: The path to the image relative to the
                     /boot file system.
    :returns: The absolute path to the image including the
              current /boot file system mount point.
    :rtype: str
    """
    img_path = _make_relative(img_path)
    return path_join(get_boot_path(), img_path)


def _image_id_to_cache_path(img_id):
    """Convert an image path relative to /boot into a path
    for the corresponding cache entry.

    :param img_id: The SHA1 digest of the image
    :returns: The cache path for the image found at ``img_path``.
    :rtype: str
    """
    return path_join(get_cache_path(), "%s%s" % (img_id, _IMAGE_EXT))


def _image_id_from_file(img_file):
    """Calculate the image identifier (SHA1) for the image file
    open at ``img_file``.

    :param img_file: An file-like object open for binary reading.
    :returns: The image identifier for ``img_file``.
    :rtype: str
    """
    digest = sha1(usedforsecurity=False)
    while True:
        hashdata = img_file.read(_hash_size)
        if not hashdata:
            break
        digest.update(hashdata)
    return digest.hexdigest()


def _image_id_from_path(img_path):
    """Calculate the image identifier (SHA1) for the image found
    at ``img_path``.

    :param img_path: The absolute path to the on-disk image.
    :returns: The image identifier for ``img_path``.
    :rtype: str
    """
    with open(img_path, "rb") as img_file:
        return _image_id_from_file(img_file)


def drop_cache():
    """Discard the in-memory cache state. Calling this function has
    no effect on the persistent cache state but will free all
    in-memory representations and clear the cache index.
    """
    global _index, _paths, _images
    _index = {}
    _paths = {}
    _images = {}


def _load_image_ids(cache_path):
    """Read the set of image_id values from the cache directory.

    :returns: A list of image_id values.
    """
    ids = []
    for entry in listdir(cache_path):
        if not entry.endswith(_IMAGE_EXT):
            continue
        ids.append(entry.rstrip(_IMAGE_EXT))
    return ids


def load_cache(verify=True, digests=False):
    """Read the state of the on-disk boot image cache into memory."""
    global _index, _paths, _images
    drop_cache()

    cache_path = get_cache_path()

    index_path = path_join(cache_path, _CACHE_INDEX)

    _log_debug("Loading cache entries from '%s'", index_path)

    # Get the set of known image_id values
    ids = _load_image_ids(cache_path)

    cachedata = {}
    try:
        with open(index_path, "r") as index_file:
            cachedata = json_load(index_file)
    except IOError as e:
        if e.errno != ENOENT:
            raise e
        _log_debug("No metadata found: starting empty cache")
        return

    index = cachedata["index"]

    for path in index.keys():
        for image_id in index[path]:
            if image_id not in ids:
                _log_warn(
                    "Image identifier '%s' not found in cache for path %s",
                    image_id,
                    path,
                )
                # mark as broken

    paths = cachedata["paths"]
    for path in paths.keys():
        if path not in index:
            _log_warn("No image for path '%s' found in cache", path)
            # mark as broken

    images = cachedata["images"]
    for image_id in images.keys():
        if image_id not in ids:
            _log_warn("Found unknown image_id '%s'", image_id)
            # clean up?

    _log_debug(
        "Loaded %d cache paths and %d images", len(paths), len(sum(index.values(), []))
    )

    _index = index
    _paths = paths
    _images = images


def write_cache():
    """Write the current in-memory state of the cache to disk."""
    cache_path = get_cache_path()

    index_path = path_join(cache_path, _CACHE_INDEX)

    cachedata = {"index": _index, "paths": _paths, "images": _images}

    with open(index_path, "w") as index_file:
        json_dump(cachedata, index_file)
        fdatasync(index_file.fileno())


def _insert_copy(boot_path, cache_path):
    """Insert an image into the cache by physical data copy."""
    shutil.copy2(boot_path, cache_path)


def _insert(boot_path, cache_path):
    """Insert an image into the cache.

    :param boot_path: The absolute path to the image to add.
    :param cache_path: The cache path at which to insert.
    :returns: None
    """
    try:
        # FIXME: implement hard link support with fall-back to copy.
        _insert_copy(boot_path, cache_path)
    except Exception as e:
        _log_error("Error copying '%s' to cache: %s", boot_path, e)
        raise e


def _remove_boot(boot_path):
    """Remove a boom restored boot image from /boot."""
    boot_dir = dirname(boot_path)
    dot_path = _RESTORED_DOT_PATTERN % basename(boot_path)
    if not path_exists(path_join(boot_dir, dot_path)):
        raise ValueError("'%s' is not boom managed" % boot_path)
    unlink(boot_path)
    unlink(path_join(boot_dir, dot_path))


def _remove_copy(cache_path):
    """Remove an image copy from the cache store."""
    unlink(cache_path)


def _remove(cache_path):
    """Remove an image from the cache store.

    :param cache_path: The path to the image to be removed.
    :returns: None
    """
    if not cache_path.startswith(get_cache_path()):
        raise ValueError("'%s' is not a boom cache path" % cache_path)
    try:
        _remove_copy(cache_path)
    except Exception as e:
        _log_error("Error removing cache image '%s': %s", cache_path, e)
        raise e


def _insert_path(path, img_id, mode, uid, gid, attrs):
    """Insert a path into the path map and index dictionaries."""
    global _paths, _index

    if path not in _paths:
        _paths[path] = {}
    _paths[path][PATH_MODE] = mode
    _paths[path][PATH_UID] = uid
    _paths[path][PATH_GID] = gid
    _paths[path][PATH_ATTRS] = attrs

    # Add the img_id to the list of images for this path
    if path in _index and img_id not in _index[path]:
        _index[path].append(img_id)
    else:
        _index[path] = [img_id]


def _find_backup_name(img_path):
    """Generate a new, unique backup pathname."""
    img_backup = ("%s.boom" % img_path)[1:] + "%d"

    def _backup_path(backup_nr):
        return path_join(get_boot_path(), img_backup % backup_nr)

    backup_nr = 0
    while path_exists(_backup_path(backup_nr)):
        backup_nr += 1
    return path_sep + img_backup % backup_nr


def _cache_path(img_path, update=True, backup=False):
    """Add an image to the boom boot image cache.

    :param img_path: The path to the on-disk boot image relative to
                     the configured /boot directory.
    :returns: None
    """

    def this_entry():
        """Return a new CacheEntry object representing the newly cached
        path.
        """
        return CacheEntry(img_path, _paths[img_path], [(img_id, image_ts)])

    global _index, _paths, _images

    boot_path = _image_path_to_boot(img_path)
    st = stat(boot_path)

    if not S_ISREG(st[ST_MODE]):
        _log_error("Image at path '%s' is not a regular file.", img_path)
        raise ValueError("'%s' is not a regular file" % img_path)

    img_id = _image_id_from_path(boot_path)
    cache_path = _image_id_to_cache_path(img_id)
    image_ts = st[ST_MTIME]

    if not update and backup:
        ces = find_cache_images(Selection(orig_path=img_path))
        if ces:
            return ces[0]

    if backup:
        if img_id in _images:
            return find_cache_images(Selection(img_id=img_id))[0]

        img_path = _find_backup_name(img_path)
        _log_debug_cache("Backing up path '%s' as '%s'", boot_path, img_path)

    if img_path in _paths and img_id in _index[img_path]:
        _log_info(
            "Image with img_id=%s already cached for path '%s'", img_id[0:6], img_path
        )
        return this_entry()
    _log_info("Adding new image with img_id=%s for path '%s'", img_id[0:6], img_path)

    path_mode = st[ST_MODE]
    path_uid = st[ST_UID]
    path_gid = st[ST_GID]
    path_attrs = {}  # FIXME xattr support

    # Physically cache the image
    _insert_copy(boot_path, cache_path)

    # Set cache entry metadata
    _images[img_id] = {IMAGE_TS: image_ts}
    _insert_path(img_path, img_id, path_mode, path_uid, path_gid, path_attrs)
    write_cache()

    return this_entry()


def cache_path(img_path, update=False):
    """Add an image to the boom boot image cache.

    :param img_path: The path to the on-disk boot image relative to
                     the configured /boot directory.
    :returns: None
    """
    _log_debug_cache("Caching path '%s'", img_path)
    return _cache_path(img_path, update=update)


def backup_path(img_path, update=False):
    """Back up an image to the boom boot image cache.

    :param img_path: The path to the on-disk boot image relative to
                     the configured /boot directory.
    :param backup_path: The path where the backup image will be created.
    :returns: None
    """
    ce = _cache_path(img_path, update=update, backup=True)
    ce.restore()
    return ce


def uncache_path(img_path, force=False):
    """Remove paths from the boot image cache.

    Remove ``img_path`` from the boot image cache and discard any
    unused images referenced by the cache entry. Images that are
    shared with other cached paths are not removed.

    :param img_path: The cached path to remove
    """
    global _index, _paths, _images

    if img_path not in _paths:
        raise ValueError("Path '%s' is not cached." % img_path)

    boot_path = _image_path_to_boot(img_path)
    img_id = _index[img_path][0]
    ts = _images[img_id][IMAGE_TS]

    ce = CacheEntry(img_path, _paths[img_path], [(img_id, ts)])
    count = ce.count

    if count and not force:
        _log_info("Retaining cache path '%s' used by %d boot entries", img_path, count)
        return

    if count:
        _log_warn("Uncaching path '%s' used by %d boot entries", img_path, count)

    # Remove entry from the path index and metadata
    images = _index.pop(img_path)
    _paths.pop(img_path)
    # Clean up unused images
    for img_id in images:
        all_images = sum(_index.values(), [])
        # Shared image?
        if img_id not in all_images:
            _images.pop(img_id)
            cache_path = _image_id_to_cache_path(img_id)
            _remove(cache_path)
    if _is_restored(boot_path):
        _remove_boot(boot_path)

    write_cache()


def clean_cache():
    """Remove unused cache entries.

    Iterate over the set of cache entries and remove any paths
    that are not referenced by any BootEntry, and remove all
    images that are not referenced by a path.
    """
    ces = find_cache_paths()
    nr_unused = 0
    for ce in ces:
        if not ce.count:
            nr_unused += 1
            ce.uncache()
    if nr_unused:
        _log_info("Removed %d unused cache entries", nr_unused)


#: Boom restored dot file pattern
_RESTORED_DOT_PATTERN = ".%s.boomrestored"


def _is_restored(boot_path):
    """Return ``True`` if ``boot_path`` was restored by boom, or
    ``False`` otherwise.

    :param boot_path: The absolute path to a boot image.
    """
    boot_dir = dirname(boot_path)
    dot_path = _RESTORED_DOT_PATTERN % basename(boot_path)
    return path_exists(path_join(boot_dir, dot_path))


class CacheEntry(object):
    """In-memory representation of cached boot image."""

    #: The image path for this CacheEntry
    path = None

    @property
    def orig_path(self):
        if "boom" in self.path:
            orig_path, ext = self.path.rsplit(".", maxsplit=1)
            if ext.startswith("boom") and ext[4:].isdigit():
                return orig_path
        return self.path

    @property
    def img_id(self):
        return self.images[0][0]

    @property
    def disp_img_id(self):
        shas = set([img_id for (img_id, ts) in self.images])
        width = find_minimum_sha_prefix(shas, 7)
        return self.images[0][0][0:width]

    @property
    def mode(self):
        """The file system mode for this CacheEntry."""
        return self._pathdata[PATH_MODE]

    @property
    def uid(self):
        """The file system uid for this CacheEntry."""
        return self._pathdata[PATH_UID]

    @property
    def gid(self):
        """The file system gid for this CacheEntry."""
        return self._pathdata[PATH_GID]

    @property
    def attrs(self):
        """The dictionary of extended attrs for this CacheEntry."""
        return self._pathdata[PATH_ATTRS]

    @property
    def timestamp(self):
        """The timestamp of the most recent image for this CacheEntry."""
        return self.images[0][1]

    @property
    def state(self):
        """Return a string representing the state of this cache entry."""
        boot_path = _image_path_to_boot(self.path)
        cache_path = _image_id_to_cache_path(self.images[0][0])
        boot_exists = path_exists(boot_path)
        cache_exists = path_exists(cache_path)
        if boot_exists and cache_exists:
            boot_path_id = _image_id_from_path(boot_path)
            if _is_restored(boot_path) and self.img_id == boot_path_id:
                return CACHE_RESTORED
            else:
                return CACHE_CACHED
        if cache_exists and not boot_exists:
            return CACHE_MISSING
        if boot_exists and not cache_exists:
            return CACHE_BROKEN
        return CACHE_UNKNOWN

    @property
    def count(self):
        """Return the current number of boot entries that reference
        this cache entry.
        """
        return len(find_entries(Selection(path=self.path)))

    #: The list of cached images for this CacheEntry sorted by increasing age
    images = []

    def __init__(self, path, pathdata, images):
        """Initialise a CacheEntry object with information from
        the on-disk cache.
        """
        self.path = path
        self._pathdata = pathdata
        self.images = images

    def __str__(self):
        fmt = "Path: %s\nImage ID: %s\nMode: %s\nUid: %d Gid: %d\nTs: %d"
        return fmt % (
            self.path,
            self.disp_img_id,
            filemode(self.mode),
            self.uid,
            self.gid,
            self.timestamp,
        )

    def __repr__(self):
        shas = set([img_id for (img_id, ts) in self.images])
        width = find_minimum_sha_prefix(shas, 7)
        rep = '"%s", %s, %s' % (
            self.path,
            self._pathdata,
            # FIXME: properly generate minimum abrevs
            [(img_id[0 : width - 1], ts) for (img_id, ts) in self.images],
        )
        return "CacheEntry(" + rep + ")"

    def restore(self, dest=None):
        """Restore this CacheEntry to the /boot file system."""
        img_id = self.images[0][0]
        if dest:
            if dest not in _index:
                _insert_path(dest, img_id, self.mode, self.uid, self.gid, self.attrs)
            self.path = dest
            write_cache()
        boot_path = _image_path_to_boot(self.path)
        cache_path = _image_id_to_cache_path(img_id)
        dot_path = _RESTORED_DOT_PATTERN % basename(boot_path)
        boot_dir = dirname(boot_path)

        restore_states = (CACHE_MISSING, CACHE_RESTORED)
        if self.state not in restore_states:
            raise ValueError(
                "Restore failed: CacheEntry state is not " "%s or %s" % restore_states
            )

        shutil.copy2(cache_path, boot_path)
        try:
            chown(boot_path, self.uid, self.gid)
            chmod(boot_path, self.mode)
        except OSError as e:
            try:
                unlink(boot_path)
            except OSError:
                pass
            raise e

        try:
            dot_file = open(path_join(boot_dir, dot_path), "w")
            dot_file.close()
        except OSError as e:
            try:
                unlink(boot_path)
            except OSError:
                pass
            raise e

    def purge(self):
        """Remove the boom restored image copy from the /boot file system."""
        boot_path = _image_path_to_boot(self.path)
        if self.state is not CACHE_RESTORED:
            raise ValueError("Purge failed: CacheEntry state is not RESTORED")
        _remove_boot(boot_path)

    def uncache(self):
        """Remove this CacheEntry from the boot image cache."""
        uncache_path(self.path)


def select_cache_entry(s, ce):
    """Test CacheEntry against Selection criteria.

    Test the supplied ``CacheEntry`` against the selection criteria
    in ``s`` and return ``True`` if it passes, or ``False``
    otherwise.

    :param s: The selection criteria
    :param be: The CacheEntry to test
    :rtype: bool
    :returns: True if CacheEntry passes selection or ``False``
              otherwise.
    """
    # Version matches if version string is contained in image path.
    if s.version and s.version not in ce.path:
        return False

    # Image path match is an exact match.
    if s.linux and s.linux != ce.path:
        return False
    if s.initrd and s.initrd != ce.path:
        return False
    if s.path and s.path != ce.path:
        return False
    if s.orig_path and s.orig_path != ce.orig_path:
        return False
    if s.timestamp and s.timestamp != ce.timestamp:
        return False
    if s.img_id and s.img_id not in ce.img_id:
        return False
    return True


def _find_cache_entries(selection=None, images=False):
    """Find cache entries matching selection criteria.

    Return a list of ``CacheEntry`` objects matching the supplied
    ``selection`` criteria. If ``images`` is ``True`` a separate
    entry is returned for each image in the cache: otherwise one
    ``CacheEntry`` object is returned for each cached path.

    ;param selection: cache entry selection criteria.
    :param images: return results by images instead of paths.
    :returns: A list of matching ``CacheEntry`` objects.
    """
    global _index, _paths, _images
    matches = []

    if not _index:
        load_cache()

    # Use null search criteria if unspecified
    selection = selection if selection else Selection()

    selection.check_valid_selection(cache=True)

    _log_debug_cache("Finding cache entries for %s", repr(selection))

    for path in _index:

        def ts_key(val):
            return val[1]

        def tuplicate(img_id):
            """Return a (img_id, image_ts) tuple for the given img_id."""
            return (img_id, _images[img_id][IMAGE_TS])

        entry_images = [tuplicate(img_id) for img_id in _index[path]]
        # Sort images list from newest to oldest
        entry_images = sorted(entry_images, reverse=True, key=ts_key)
        if not images:
            ce = CacheEntry(path, _paths[path], entry_images)
            if select_cache_entry(selection, ce):
                matches.append(ce)
        else:
            for img_tuple in entry_images:
                ce = CacheEntry(path, _paths[path], [img_tuple])
                if select_cache_entry(selection, ce):
                    matches.append(ce)

    return matches


def find_cache_paths(selection=None):
    """Find cache entries matching selection criteria.

    Return a list of ``CacheEntry`` objects matching the supplied
    ``selection`` criteria, one for each path that exists in the
    cache. For each cached path a ``CacheEntry`` object is returned
    with a list of images that are cached for that path. The image
    list is sorted by timestamp with the most recent entry first.

    ;param selection: cache entry selection criteria.
    :returns: A list of matching ``CacheEntry`` objects.
    """
    matches = _find_cache_entries(selection=selection, images=False)
    _log_debug_cache("Found %d cached paths", len(matches))
    return matches


def find_cache_images(selection=None):
    """Find cache entries matching selection criteria.

    Return a list of ``CacheEntry`` objects matching the supplied
    ``selection`` criteria, one for each image that exists in the
    cache. Each ``CacheEntry`` object is returned with a list
    containing a single image.

    ;param selection: cache entry selection criteria.
    :returns: A list of matching ``CacheEntry`` objects.
    """
    matches = _find_cache_entries(selection=selection, images=True)
    _log_debug_cache("Found %d cached images", len(matches))
    return matches


__all__ = [
    "CACHE_CACHED",
    "CACHE_MISSING",
    "CACHE_BROKEN",
    "CACHE_RESTORED",
    "drop_cache",
    "load_cache",
    "write_cache",
    "cache_path",
    "backup_path",
    "uncache_path",
    "clean_cache",
    "find_cache_paths",
    "find_cache_images",
]

# vim: set et ts=4 sw=4 :

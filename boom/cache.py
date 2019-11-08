# Copyright (C) 2017 Red Hat, Inc., Bryn M. Reeves <bmr@redhat.com>
#
# cache.py - Boom boot image cache
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
"""The ``boom.cache`` module defines classes, constants and functions
for maintaining an on-disk cache of kernel, initramfs and auxiliary
images required to load boom-defined boot entries.
"""
from __future__ import print_function

from boom import *

from hashlib import sha1
from os import listdir, unlink, stat
from stat import S_ISREG, S_IMODE, ST_MODE, ST_UID, ST_GID, ST_MTIME
from os.path import (
    join as path_join, exists as path_exists, sep as path_sep,
    basename, dirname
)
from json import load as json_load, dump as json_dump
import shutil
import logging

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

        :param img_file: An open file-like object.
        :returns: The image identifier for ``img_file``.
        :rtype: str
    """
    digest = sha1()
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
    with open(img_path) as img_file:
        return _image_id_from_file(img_file)


def drop_cache():
    """Discard the in-memory cache state. Calling this function has
        no effect on the persistent cache state but will free all
        in-memory represenatations and clear the cache index.
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
    """Read the state of the on-disk boot image cache into memory.
    """
    global _index, _paths, _images
    drop_cache()

    cache_path = get_cache_path()

    index_path = path_join(cache_path, _CACHE_INDEX)

    # Get the set of known image_id values
    ids = _load_image_ids(cache_path)

    cachedata = {}
    with open(index_path, "r") as index_file:
        cachedata = json_load(index_file)

    index = cachedata["index"]

    for path in index.keys():
        for image_id in index[path]:
            if image_id not in ids:
                _log_warn("Image identifier '%s' not found in cache" %
                          image_id)
                # mark as broken

    paths = cachedata["paths"]
    for path in paths.keys():
        if path not in index:
            _log_warn("No image for path '%' found in cache" % path)
            # mark as broken

    images = cachedata["images"]
    for image_id in images.keys():
        if image_id not in ids:
            _log_warn("Found orphan image_id '%s'" % image)
            # clean up?

    _index = index
    _paths = paths
    _images = images


def write_cache():
    """Write the current in-memory state of the cache to disk.
    """
    cache_path = get_cache_path()

    index_path = path_join(cache_path, _CACHE_INDEX)

    cachedata = {
        "index": _index,
        "paths": _paths,
        "images": _images
    }

    with open(index_path, "w") as index_file:
        json_dump(cachedata, index_file)


def _insert_copy(boot_path, cache_path):
    """Insert an image into the cache by physical data copy.
    """
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
        _log_error("Error copying '%s' to cache: %s" % (boot_path, e))
        raise e


def _remove_boot(boot_path):
    """Remove a boom restored boot image from /boot.
    """
    boot_dir = dirname(boot_path)
    dot_path = _RESTORED_DOT_PATTERN % basename(boot_path)
    if not path_exists(path_join(boot_dir, dot_path)):
        raise ValueError("'%s' is not boom managed")
    unlink(boot_path)
    unlink(path_join(boot_dir, dot_path))


def _remove_copy(cache_path):
    """Remove an image copy from the cache store.
    """
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
        _log_error("Error removing cache image '%s': %s" %
                   (cache_path, e))
        raise e


def cache_path(img_path, update=True):
    """Add an image to the boom boot image cache.

        :param img_path: The path to the on-disk boot image relative to
                         the configured /boot directory.
        :returns: None
    """
    global _index, _paths, _images

    _log_debug_cache("Caching path '%s'" % img_path)

    boot_path = _image_path_to_boot(img_path)
    st = stat(boot_path)

    if not S_ISREG(st[ST_MODE]):
        _log_error("Image at path '%s' is not a regular file." % img_path)
        raise ValueError("'%s' is not a regular file" % img_path)

    img_id = _image_id_from_path(boot_path)
    cache_path = _image_id_to_cache_path(img_id)

    # Already present?
    if img_path in _paths:
        _log_info("Path '%s' already cached." % img_path)
        if not update:
            return

    if img_path in _paths and img_id in _paths[img_path]:
        _log_info("Image with img_id=%s already cached for path '%s'" %
                  (img_id[0:6], img_path))
        return
    _log_info("Adding new image with img_id=%s for path '%s'" %
              (img_id[0:6], img_path))

    # Initialise path dictionary and index list for new path
    if img_path not in _paths:
        _paths[img_path] = {}
    if img_path not in _index:
        _index[img_path] = []

    path_ts = image_ts = st[ST_MTIME]

    path_mode = st[ST_MODE]
    path_uid = st[ST_UID]
    path_gid = st[ST_GID]
    path_attrs = {}  # FIXME xattr support

    # Physically cache the image
    _insert_copy(boot_path, cache_path)

    # Set cache entry metadata
    _images[img_id] = {IMAGE_TS: image_ts}
    _paths[img_path][PATH_MODE] = path_mode
    _paths[img_path][PATH_UID] = path_uid
    _paths[img_path][PATH_GID] = path_gid
    _paths[img_path][PATH_ATTRS] = path_attrs

    # Add the img_id to the list of images for this path
    _index[img_path].append(img_id)

    write_cache()


def uncache_path(img_path):
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
    if ce.count:
        _log_warn("Uncaching path '%s' used by %d boot entries"
                  % (img_path, ce.count))

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

# vim: set et ts=4 sw=4 :

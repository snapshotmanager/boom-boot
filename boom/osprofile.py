# Copyright (C) 2017 Red Hat, Inc., Bryn M. Reeves <bmr@redhat.com>
#
# osprofile.py - Boom OS profiles
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
"""The ``boom.osprofile``  module defines the `OsProfile` class that
represents an operating system profile. An `OsProfile` defines the
identity of a profile and includes template values used to generate boot
loader entries.

Functions are provided to read and write operating system profiles from
an on-disk store, and to retrieve ``OsProfile`` instances using various
selection criteria.

The ``OsProfile`` class includes named properties for each profile
attribute ("profile key"). In addition, the class serves as a container
type, allowing attributes to be accessed via dictionary-style indexing.
This simplifies iteration over a profile's key / value pairs and allows
straightforward access to all members in scripts and the Python shell.

All profile key names are made available as named members of the module:
``BOOM_OS_*``, and the ``PROFILE_KEYS`` list. Human-readable names for
all the profile keys are stored in the ``KEY_NAMES`` dictionary: these
are suitable for display use and are used by default by the
``OsProfile`` string formatting routines.
"""
from boom import *
from hashlib import sha1
from os import listdir
from tempfile import mkstemp
from os.path import basename, join as path_join, exists as path_exists
from os import fdopen, rename, chmod, unlink
import logging
import re

#: Boom profiles directory name.
BOOM_PROFILES = "profiles"

#: File name format for Boom profiles.
BOOM_OS_PROFILE_FORMAT = "%s-%s%s.profile"

#: The file mode with which to create Boom profiles.
BOOM_PROFILE_MODE = 0o644

# Constants for Boom profile keys

#: Constant for the Boom OS identifier profile key.
BOOM_OS_ID = "BOOM_OS_ID"
#: Constant for the Boom OS name profile key.
BOOM_OS_NAME = "BOOM_OS_NAME"
#: Constant for the Boom OS short name profile key.
BOOM_OS_SHORT_NAME = "BOOM_OS_SHORT_NAME"
#: Constant for the Boom OS version string profile key.
BOOM_OS_VERSION = "BOOM_OS_VERSION"
#: Constant for the Boom OS version ID string profile key.
BOOM_OS_VERSION_ID = "BOOM_OS_VERSION_ID"
#: Constant for the Boom OS uname pattern profile key.
BOOM_OS_UNAME_PATTERN = "BOOM_OS_UNAME_PATTERN"
#: Constant for the Boom OS kernel pattern profile key.
BOOM_OS_KERNEL_PATTERN = "BOOM_OS_KERNEL_PATTERN"
#: Constant for the Boom OS initramfs pattern profile key.
BOOM_OS_INITRAMFS_PATTERN = "BOOM_OS_INITRAMFS_PATTERN"
#: Constant for the Boom OS LVM2 root options key.
BOOM_OS_ROOT_OPTS_LVM2 = "BOOM_OS_ROOT_OPTS_LVM2"
#: Constant for the Boom OS BTRFS root options key.
BOOM_OS_ROOT_OPTS_BTRFS = "BOOM_OS_ROOT_OPTS_BTRFS"
#: Constant for the Boom OS command line options key.
BOOM_OS_OPTIONS = "BOOM_OS_OPTIONS"

#: Ordered list of possible profile keys, partitioned into mandatory
#: keys, root option keys, and optional keys (currently the Linux
#: kernel command line).
PROFILE_KEYS = [
    # Keys 0-7 (ID to INITRAMFS_PATTERN) are mandatory.
    BOOM_OS_ID, BOOM_OS_NAME, BOOM_OS_SHORT_NAME, BOOM_OS_VERSION,
    BOOM_OS_VERSION_ID, BOOM_OS_UNAME_PATTERN,
    BOOM_OS_KERNEL_PATTERN, BOOM_OS_INITRAMFS_PATTERN,
    # At least one of keys 8-9 (ROOT_OPTS) is required.
    BOOM_OS_ROOT_OPTS_LVM2, BOOM_OS_ROOT_OPTS_BTRFS,
    # The OPTIONS key is optional.
    BOOM_OS_OPTIONS
]

#: A map of Boom profile keys to human readable key names suitable
#: for use in formatted output. These key names are used when an
#: ``OsProfile`` object is formatted as a string.
KEY_NAMES = {
    BOOM_OS_ID: "OS ID",
    BOOM_OS_NAME: "Name",
    BOOM_OS_SHORT_NAME: "Short name",
    BOOM_OS_VERSION: "Version",
    BOOM_OS_VERSION_ID: "Version ID",
    BOOM_OS_UNAME_PATTERN: "UTS release pattern",
    BOOM_OS_KERNEL_PATTERN: "Kernel pattern",
    BOOM_OS_INITRAMFS_PATTERN: "Initramfs pattern",
    BOOM_OS_ROOT_OPTS_LVM2: "Root options (LVM2)",
    BOOM_OS_ROOT_OPTS_BTRFS: "Root options (BTRFS)",
    BOOM_OS_OPTIONS: "Options"
}

#: Boom profile keys that must exist in a valid profile.
REQUIRED_KEYS = PROFILE_KEYS[0:8]

#: Boom profile keys for different forms of root device specification.
ROOT_KEYS = PROFILE_KEYS[9:10]

#: Keys with default values
_DEFAULT_KEYS = {
    BOOM_OS_KERNEL_PATTERN: "/boot/kernel-%{version}",
    BOOM_OS_INITRAMFS_PATTERN: "/boot/initramfs-%{version}.img",
    BOOM_OS_ROOT_OPTS_LVM2: "rd.lvm.lv=%{lvm_root_lv}",
    BOOM_OS_ROOT_OPTS_BTRFS: "rootflags=%{btrfs_subvolume}",
    BOOM_OS_OPTIONS: "root=%{root_device} ro %{root_opts}"
}

# Module logging configuration
_log = logging.getLogger(__name__)
_log.set_debug_mask(BOOM_DEBUG_PROFILE)

_log_debug = _log.debug
_log_debug_profile = _log.debug_masked
_log_info = _log.info
_log_warn = _log.warning
_log_error = _log.error

#: Global profile list
_profiles = []
_profiles_by_id = {}

#: Whether profiles have been read from disk
_profiles_loaded = False


def boom_profiles_path():
    """Return the path to the boom profiles directory.

        :returns: The boom profiles path.
        :returntype: str
    """
    return path_join(get_boom_path(), BOOM_PROFILES)


def _is_null_profile(osp):
    """Test for the Null Profile.

        Test ``osp`` and return ``True`` if it is the Null Profile.
        The Null Profile has an empty identity and defines no profile
        keys: it is used in the case that no valid match is found for
        an entry loaded from disk (for e.g. an entry that has been
        hand-edited and matches no known version or options string,
        or an entry for which the original profile has been deleted).

        :param osp: The OsProfile to test
        :returns: ``True`` if ``osp`` is the Null Profile or ``False``
                  otherwise
        :returntype: bool
    """
    global _null_profile
    if osp.os_id == _null_profile.os_id:
        return True
    return False


def profiles_loaded():
    """Test whether profiles have been loaded from disk.

        :returntype: bool
        :returns: ``True`` if profiles are loaded in memory or ``False``
                  otherwise
    """
    global _profiles_loaded
    return _profiles_loaded


def load_profiles():
    """Load OsProfile data from disk.

        Load the set of profiles found at the path
        ``boom.osprofile.boom_profiles_path()`` into the global profile
        list.

        This function may be called to explicitly load, or reload the
        set of profiles on-disk. Profiles are also loaded implicitly
        if an API function or method that requires access to profiles
        is invoked (for example, ``boom.bootloader.load_entries()``.

        :returns: None
    """
    global _profiles, _profiles_by_id, _profiles_loaded, _null_profile
    _profiles = []
    _profiles_by_id = {}
    _profiles.append(_null_profile)
    _profiles_by_id[_null_profile.os_id] = _null_profile
    profiles_path = boom_profiles_path()
    profile_files = listdir(profiles_path)
    _log_info("Loading profiles from %s" % profiles_path)
    for pf in profile_files:
        if not pf.endswith(".profile"):
            continue
        pf_path = path_join(profiles_path, pf)
        try:
            osp = OsProfile(profile_file=pf_path)
        except Exception as e:
            _log_warn("Failed to load OsProfile from '%s': %s" %
                      (osp.disp_os_id))
        _profiles.append(osp)
        _profiles_by_id[osp.os_id] = osp
    _profiles_loaded = True
    _log_info("Loaded %d profiles" % (len(_profiles) - 1))



def write_profiles(force=False):
    """Write all OsProfile data to disk.

        Write the current list of profiles to the directory located at
        ``boom.osprofile.boom_profiles_path()``.

        :returntype: None
    """
    global _profiles
    _log_debug("Writing profiles to %s" % boom_profiles_path())
    for osp in _profiles:
        if _is_null_profile(osp):
            continue
        try:
            osp.write_profile(force)
        except Exception as e:
            _log_warn("Failed to write OsProfile(os_id='%s'): %s" %
                      (osp.disp_os_id, e))


def min_os_id_width():
    """Calculate the minimum unique width for os_id values.

        Calculate the minimum width to ensure uniqueness when displaying
        os_id values.

        :returns: the minimum os_id width.
        :returntype: int
    """
    min_prefix = 7
    if not _profiles:
        return min_prefix

    shas = set()
    for osp in _profiles:
        shas.add(osp.os_id)
    return _find_minimum_sha_prefix(shas, min_prefix)


def select_profile(s, osp):
    """Test the supplied profile against selection criteria.

        Test the supplied ``OsProfile`` against the selection criteria
        in ``s`` and return ``True`` if it passes, or ``False``
        otherwise.

        :param osp: The OsProfile to test
        :returntype: bool
        :returns: True if osp passes selection or ``False`` otherwise.
    """
    if _is_null_profile(osp):
        return False
    if s.os_id and not osp.os_id.startswith(s.os_id):
        return False
    if s.os_name and osp.name != s.os_name:
        return False
    if s.os_short_name and osp.short_name != s.os_short_name:
        return False
    if s.os_version and osp.version != s.os_version:
        return False
    if s.os_version_id and osp.version_id != s.version_id:
        return False
    if s.os_uname_pattern and osp.uname_pattern != s.os_uname_pattern:
        return False
    if s.os_kernel_pattern and osp.kernel_pattern != s.os_kernel_pattern:
        return False
    if (s.os_initramfs_pattern and
        osp.os_initramfs_pattern != s.initramfs_pattern):
        return False
    if s.os_options and osp.os_options != s.os_options:
        return False
    return True


def find_profiles(selection=None, match_fn=select_profile):
    """Find profiles matching selection criteria.

        Return a list of ``OsProfile`` objects matching the specified
        criteria. Matching proceeds as the logical 'and' of all criteria.
        Criteria that are unset (``None``) are ignored.

        If the optional ``match_fn`` parameter is specified, the match
        criteria parameters are ignored and each ``OsProfile`` is tested
        in turn by calling ``match_fn``. If the matching function returns
        ``True`` the ``OsProfile`` will be included in the results.

        If no ``OsProfile`` matches the specified criteria the empty list
        is returned.

        OS profiles will be automatically loaded from disk if they are
        not already in memory.

        :param selection: A ``Selection`` object specifying the match
                          criteria for the operation.
        :param match_fn: An optional match function to test profiles.
        :returns: a list of ``OsProfile`` objects.
        :returntype: list
    """
    global _profiles

    # Use null search criteria if unspecified
    s = selection if selection else Selection()

    selection.check_valid_selection(profile=True)

    if not profiles_loaded():
        load_profiles()

    matches = []

    _log_debug_profile("Finding profiles for %s" % repr(selection))
    for osp in _profiles:
        if _is_null_profile(osp):
            continue
        if match_fn(selection, osp):
            matches.append(osp)
    _log_debug_profile("Found %d profiles" % len(matches))
    return matches


def get_os_profile_by_id(os_id):
    """Find an OsProfile by its os_id.

        Return the OsProfile object corresponding to ``os_id``, or
        ``None`` if it is not found.

        :returntype: OsProfile
        :returns: An OsProfile matching os_id or None if no match was
                  found
    """
    if os_id in _profiles_by_id:
        return _profiles_by_id[os_id]
    return None


def match_os_profile(entry):
    """Attempt to match a BootEntry to a corresponding OsProfile.

        Probe all loaded ``OsProfile`` objects with the supplied
        ``BootEntry`` in turn, until an ``OsProfile`` reports a match.
        Checking terminates on the first matching ``OsProfile``.

        :param entry: A ``BootEntry`` object with no attached
                      ``OsProfile``.
        :returns: The corresponding ``OsProfile`` for the supplied
                  ``BootEntry`` or ``None`` if no match is found.
        :returntype: ``BootEntry`` or ``NoneType``.
    """
    global _profiles, _profiles_loaded

    if not _profiles_loaded:
        load_profiles()

    # Do not report a boot_id: it will change if an OsProfile is
    # matched to the entry.
    _log_debug("Attempting to match profile for BootEntry(title='%s', "
               "version='%s') with unknown os_id" %
               (entry.title, entry.version))

    # Attempt to match by uname pattern
    for osp in _profiles:
        if _is_null_profile(osp):
            continue
        if osp.match_uname_version(entry.version):
            _log_debug("Matched BootEntry(version='%s', boot_id='%s') "
                       "to OsProfile(name='%s', os_id='%s')" %
                        (entry.version, entry.disp_boot_id, osp.name,
                         osp.disp_os_id))
            return osp

    # No matching uname pattern: attempt to match options template
    for osp in _profiles:
        if _is_null_profile(osp):
            continue
        if osp.match_options(entry):
            _log_debug("Matched BootEntry(version='%s', boot_id='%s') "
                       "to OsProfile(name='%s', os_id='%s')" %
                       (entry.version, entry.disp_boot_id, osp.name,
                       osp.disp_os_id))
            return osp

    _log_debug_profile("No matching profile found for boot_id=%s" %
                       entry.boot_id)

    return _null_profile


def match_os_profile_by_version(version):
    """Attempt to match a version string to an OsProfile.

        Attempt to find a profile with a uname pattern that matches
        ``version``. The first OsProfile with a match is returned.

        :param version: A uname release version string to match.
        :returntype: OsProfile
        :returns: An OsProfile matching version or None if not match
                  was found
    """
    global _profiles, _profiles_loaded

    if not _profiles_loaded:
        load_profiles()

    for osp in _profiles:
        if osp.match_uname_version(version):
            return osp
    return None

class OsProfile(object):
    """ Class OsProfile implements Boom operating system profiles.
        Objects of type OsProfile define the paths, kernel command line
        options, root device flags and file name patterns needed to boot
        an instance of that operating system.
    """
    _profile_data = None
    _unwritten = False
    _comments = None

    def __str__(self):
        """Format this OsProfile as a human readable string.

            Profile attributes are printed as "Name: value, " pairs,
            with like attributes grouped together onto lines.

            :returns: A human readable string representation of this OsProfile.

            :returntype: string
        """
        breaks = [BOOM_OS_ID, BOOM_OS_SHORT_NAME, BOOM_OS_VERSION_ID,
                  BOOM_OS_UNAME_PATTERN, BOOM_OS_INITRAMFS_PATTERN,
                  BOOM_OS_ROOT_OPTS_LVM2, BOOM_OS_ROOT_OPTS_BTRFS,
                  BOOM_OS_OPTIONS]

        fields = [f for f in PROFILE_KEYS if f in self._profile_data]
        osp_str = ""
        tail = ""
        for f in fields:
            osp_str += '%s: "%s"' % (KEY_NAMES[f], self._profile_data[f])
            tail = ",\n" if f in breaks else ", "
            osp_str += tail
        osp_str = osp_str.rstrip(tail)
        return osp_str

    def __repr__(self):
        """Format this OsProfile as a machine readable string.

            Return a machine-readable representation of this `OsProfile`
            object. The string is formatted as a call to the `OsProfile`
            constructor, with values passed as a dictionary to the
            `profile_data` keyword argument.

            :returns: a string representation of this `OsProfile`.

            :returntype: <class 'boom.osprofile.OsProfile>
        """
        osp_str = "OsProfile(profile_data={"
        fields = [f for f in PROFILE_KEYS if f in self._profile_data]
        for f in fields:
            osp_str += '%s:"%s", ' % (f, self._profile_data[f])
        osp_str = osp_str.rstrip(", ")
        return osp_str + "})"

    def __len__(self):
        """Return the length (key count) of this ``OsProfile``.

            :returns: the ``OsProfile`` length as an integer.
            :returntype: ``int``
        """
        return len(self._profile_data)

    def __getitem__(self, key):
        """Return an item from this ``OsProfile``.

            :returns: the item corresponding to the key requested.
            :returntype: the corresponding type of the requested key.
            :raises: TypeError if ``key`` is of an invalid type.
                     KeyError if ``key`` is valid but not present.
        """
        if not isinstance(key, str):
            raise TypeError("OsProfile key must be a string.")

        if key in self._profile_data:
            return self._profile_data[key]

        raise KeyError("Key %s not in profile." % key)

    def __setitem__(self, key, value):
        """Set the specified ``OsProfile`` key to the given value.

            :param key: the ``OsProfile`` key to be set.
            :param value: the value to set for the specified key.
        """
        if not isinstance(key, str):
            raise TypeError("OsProfile key must be a string.")

        if key not in PROFILE_KEYS:
            raise ValueError("Invalid OsProfile key: %s" % key)

        self._profile_data[key] = value

    def keys(self):
        """Return the list of keys for this OsProfile.

            :returntype: list
            :returns: A list of OsProfile key names
        """
        return self._profile_data.keys()

    def values(self):
        """Return the list of key values for this OsProfile.

            :returntype: list
            :returns: A list of OsProfile key values
        """
        return self._profile_data.values()

    def items(self):
        """Return the items list for this OsProfile.

            Return a list of ``(key, value)`` tuples representing the
            key items in this ``OsProfile``.

            :returntype: list
            :returns: A list of OsProfile key item tuples
        """
        return self._profile_data.items()

    def _dirty(self):
        """Mark this ``OsProfile`` as needing to be written to disk.

            A newly created ``OsProfile`` object is always dirty and
            a call to its ``write_profile()`` method will always write
            a new profile file. Writes may be avoided for profiles
            that are not marked as dirty.

            A clean ``OsProfile`` is marked as dirty if a new value
            is written to any of its writable properties.

            :returns None:
        """
        self._unwritten = True

    def _generate_os_id(self):
        """Generate a new OS identifier.

            Generate a new sha1 profile identifier for this profile,
            using the short_name, version, and version_id values and
            store it in _profile_data.

            :returns: None
        """
        hashdata = (self.short_name + self.version + self.version_id)

        digest = sha1(hashdata.encode('utf-8')).hexdigest()
        self._profile_data[BOOM_OS_ID] = digest

    def __from_data(self, profile_data, dirty=True):
        """Initialise an OsProfile from in-memory data.

            Initialise a new OsProfile object using the profile data
            in the `profile_data` dictionary.

            This method should not be called directly: to build a new
            ``Osprofile`` object from in-memory data, use the class
            initialiser with the ``profile_data`` argument.

            :returns: None
        """
        err_str = "Invalid profile data (missing %s)"

        # Set profile defaults
        for key in _DEFAULT_KEYS:
            if key not in profile_data:
                profile_data[key] = _DEFAULT_KEYS[key]

        for key in REQUIRED_KEYS:
            if key == BOOM_OS_ID:
                continue
            if key not in profile_data:
                raise ValueError(err_str % key)

        root_opts = [key for key in ROOT_KEYS if key in profile_data]
        if not any(root_opts):
            root_opts_err = err_str % "ROOT_OPTS"
            raise ValueError(root_opts_err)

        # Empty OPTIONS is permitted: set the corresponding
        # value in the _profile_data dictionary to the empty string.
        if BOOM_OS_OPTIONS not in profile_data:
            profile_data[BOOM_OS_OPTIONS] = ""
        self._profile_data = dict(profile_data)

        if BOOM_OS_ID not in self._profile_data:
            self._generate_os_id()

        if dirty:
            self._dirty()

    def __from_file(self, profile_file):
        """Initialise a new OsProfile from data stored in a file.

            Initialise a new OsProfile object using the profile data
            in profile_file.

            This method should not be called directly: to build a new
            ``Osprofile`` object from in-memory data, use the class
            initialiser with the ``profile_file`` argument.

            :returns: None
        """
        profile_data = {}
        comments = {}
        comment = ""

        _log_debug("Loading OsProfile from '%s'" % basename(profile_file))
        with open(profile_file, "r") as pf:
            for line in pf:
                if _blank_or_comment(line):
                    comment += line if line else ""
                else:
                    name, value = _parse_name_value(line)
                    profile_data[name] = value
                    if comment:
                        comments[name] = comment
                        comment = ""
        self._comments = comments

        try:
            self.__from_data(profile_data, dirty=False)
        except ValueError as e:
            raise ValueError(str(e) + "in %s" % profile_file)

    def __init__(self, name=None, short_name=None, version=None,
                 version_id=None, profile_file=None, profile_data=None):
        """Initialise a new ``OsProfile`` object.

            If neither ``profile_file`` nor ``profile_data`` is given,
            all of ``name``, ``short_name``, ``version``, and
            ``version_id`` must be given.

            These values form the profile identity and are used to
            generate the profile unique identifier.

            :param name: The name of the operating system.
            :param short_name: A short name for the operating system,
                               suitable for use in file names.
            :param version: A string describing the version of the
                            operating system.
            :param version_id: A short alphanumeric string representing
                               the operating system version and suitable
                               for use in generating file names.
            :param profile_data: An optional dictionary mapping from
                                 ``BOOM_OS_*`` keys to profile values.
            :param profile_file: An optional path to a file from which
                                 profile data should be loaded. The file
                                 should be in Boom profile format, with
                                 ``BOOM_OS_*`` key=value pairs.
            :returns: A new ``OsProfile`` object.
            :returntype: class OsProfile
        """
        global _profiles
        self._profile_data = {}

        if profile_data and profile_file:
            raise ValueError("Only one of 'profile_data' or 'profile_file' "
                             "may be specified.")

        if profile_data:
            return self.__from_data(profile_data)
        if profile_file:
            return self.__from_file(profile_file)

        self._dirty()

        self._profile_data[BOOM_OS_NAME] = name
        self._profile_data[BOOM_OS_SHORT_NAME] = short_name
        self._profile_data[BOOM_OS_VERSION] = version
        self._profile_data[BOOM_OS_VERSION_ID] = version_id

        required_args = [name, short_name, version, version_id]
        if all([not val for val in required_args]):
            # NULL profile
            for key in PROFILE_KEYS:
                self._profile_data[key] = ""
        elif any([not val for val in required_args]):
            raise ValueError("Invalid profile arguments: name, "
                             "short_name, version, and version_id are"
                             "mandatory.")
        for key in _DEFAULT_KEYS:
            self._profile_data[key] = _DEFAULT_KEYS[key]

        self._generate_os_id()
        _profiles.append(self)

    def match_uname_version(self, version):
        """Test OsProfile for version string match.

            Test the supplied version string to determine whether it
            matches the uname_pattern of this ``OsProfile``.

            :param version: A uname release version string to match.
            :returns: ``True`` if thi version matches this profile, or
                      ``False`` otherwise.
            :returntype: bool
        """
        _log_debug_profile("Matching uname pattern '%s' to '%s'" %
                           (self.uname_pattern, version))
        if self.uname_pattern and version:
            if re.search(self.uname_pattern, version):
                return True
        return False

    def match_options(self, entry):
        """Test OsProfile for options template match.

            Test the supplied ``BootEntry`` to determine whether it
            matches the options template defined by this ``OsProfile``.

            Used as a match of last resort when no uname pattern match
            exists.

            :param entry: A ``BootEntry`` to match against this profile.
            :returns: ``True`` if this entry matches this profile, or
                      ``False`` otherwise.
            :returntype: bool
        """
        # Attempt to match a distribution-formatted options line
        if self.options and entry.options:
            options_pattern = _key_regex_from_format(self.options)
            _log_debug_profile("Matching options pattern '%s' to '%s'" %
                               (options_pattern, entry.options))
            if re.match(options_pattern, entry.options):
                return True
        return False

    # We use properties for the OsProfile attributes: this is to
    # allow the values to be stored in a dictionary. Although
    # properties are quite verbose this reduces the code volume
    # and complexity needed to marshal and unmarshal the various
    # file formats used, as well as conversion to and from string
    # representations of OsProfile objects.

    # Keys obtained from os-release data form the profile's identity:
    # the corresponding attributes are read-only.

    @property
    def disp_os_id(self):
        """The display os_id of this profile.

            Return the shortest prefix of this OsProfile's os_id that
            is unique within the current set of loaded profiles.

            :getter: return this OsProfile's os_id.
            :type: str
        """
        return self.os_id[:min_os_id_width()]

    @property
    def os_id(self):
        """The ``os_id`` of this profile.

            :getter: returns the ``os_id`` as a string.
            :type: string
        """
        return self._profile_data[BOOM_OS_ID]

    @property
    def name(self):
        """The ``name`` of this profile.

            :getter: returns the ``name`` as a string.
            :type: string
        """
        return self._profile_data[BOOM_OS_NAME]

    @property
    def short_name(self):
        """The ``short_name`` of this profile.

            :getter: returns the ``short_name`` as a string.
            :type: string
        """
        return self._profile_data[BOOM_OS_SHORT_NAME]

    @property
    def version(self):
        """The ``version`` of this profile.

            :getter: returns the ``version`` as a string.
            :type: string
        """
        return self._profile_data[BOOM_OS_VERSION]

    @property
    def version_id(self):
        """The ``version_id`` of this profile.

            :getter: returns the ``version_id`` as a string.
            :type: string
        """
        return self._profile_data[BOOM_OS_VERSION_ID]

    # Configuration keys specify values that may be modified and
    # have a corresponding <key>.setter.

    @property
    def uname_pattern(self):
        """The current ``uname_pattern`` setting of this profile.

            :getter: returns the ``uname_pattern`` as a string.
            :setter: stores a new ``uname_pattern`` setting.
            :type: string
        """
        return self._profile_data[BOOM_OS_UNAME_PATTERN]

    @uname_pattern.setter
    def uname_pattern(self, value):
        self._profile_data[BOOM_OS_UNAME_PATTERN] = value
        self._dirty()

    @property
    def kernel_pattern(self):
        """The current ``kernel_pattern`` setting of this profile.

            :getter: returns the ``kernel_pattern`` as a string.
            :setter: stores a new ``kernel_pattern`` setting.
            :type: string
        """
        return self._profile_data[BOOM_OS_KERNEL_PATTERN]

    @kernel_pattern.setter
    def kernel_pattern(self, value):
        self._profile_data[BOOM_OS_KERNEL_PATTERN] = value
        self._dirty()

    @property
    def initramfs_pattern(self):
        """The current ``initramfs_pattern`` setting of this profile.

            :getter: returns the ``initramfs_pattern`` as a string.
            :setter: store a new ``initramfs_pattern`` setting.
            :type: string
        """
        return self._profile_data[BOOM_OS_INITRAMFS_PATTERN]

    @initramfs_pattern.setter
    def initramfs_pattern(self, value):
        self._profile_data[BOOM_OS_INITRAMFS_PATTERN] = value
        self._dirty()

    @property
    def root_opts_lvm2(self):
        """The current LVM2 root options setting of this profile.

            :getter: returns the ``root_opts_lvm2`` value as a string.
            :setter: store a new ``root_opts_lvm2`` value.
            :type: string
        """
        if BOOM_OS_ROOT_OPTS_LVM2 not in self._profile_data:
            return None
        return self._profile_data[BOOM_OS_ROOT_OPTS_LVM2]

    @root_opts_lvm2.setter
    def root_opts_lvm2(self, value):
        self._profile_data[BOOM_OS_ROOT_OPTS_LVM2] = value
        self._dirty()

    @property
    def root_opts_btrfs(self):
        """The current BTRFS root options setting of this profile.

            :getter: returns the ``root_opts_btrfs`` value as a string.
            :setter: store a new ``root_opts_btrfs`` value.
            :type: string
        """
        if BOOM_OS_ROOT_OPTS_BTRFS not in self._profile_data:
            return None
        return self._profile_data[BOOM_OS_ROOT_OPTS_BTRFS]

    @root_opts_btrfs.setter
    def root_opts_btrfs(self, value):
        self._profile_data[BOOM_OS_ROOT_OPTS_BTRFS] = value
        self._dirty()

    @property
    def options(self):
        """The current kernel command line options setting for this
            profile.

            :getter: returns the ``options`` value as a string.
            :setter: store a new ``options`` value.
            :type: string
        """
        if BOOM_OS_OPTIONS not in self._profile_data:
            return None
        return self._profile_data[BOOM_OS_OPTIONS]

    @options.setter
    def options(self, value):
        self._profile_data[BOOM_OS_OPTIONS] = value
        self._dirty()

    @classmethod
    def from_os_release(cls, os_release):
        """Build an OsProfile from os-release file data.

            Construct a new OsProfile object using data obtained from
            a file in os-release(5) format.

            :param os_release: String data in os-release(5) format
            :returns: A new OsProfile for the specified os-release data
            :returntype: OsProfile
        """
        release_data = {}
        for line in os_release:
            if _blank_or_comment(line):
                continue
            name, value = _parse_name_value(line)
            release_data[name] = value
        osp = OsProfile(release_data["NAME"],
                        release_data["ID"],
                        release_data["VERSION"],
                        release_data["VERSION_ID"])

        for key in _DEFAULT_KEYS:
            osp._profile_data[key] = _DEFAULT_KEYS[key]

        return osp

    @classmethod
    def from_os_release_file(cls, path):
        """Build an OsProfile from an on-disk os-release file.

            Construct a new OsProfile object using data obtained from
            the file specified by 'path'.

            :param os_release: Path to a file in os-release(5) format
            :returns: A new OsProfile for the specified os-release file
            :returntype: OsProfile
        """
        with open(path, "r") as f:
            return cls.from_os_release(f)

    @classmethod
    def from_host_os_release(cls):
        """Build an OsProfile from the current hosts's os-release.

            Construct a new OsProfile object using data obtained from
            the running hosts's /etc/os-release file.

            :returns: A new OsProfile for the current host
            :returntype: OsProfile
        """
        return cls.from_os_release_file("/etc/os-release")

    def _profile_path(self):
        """Return the path to this profile's on-disk data.

            Return the full path to this OsProfile in the Boom profiles
            directory (or the location to which it will be written, if
            it has not yet been written).

            :returntype: str
            :returns: The absolute path for this OsProfile's file
        """
        profile_id = (self.os_id, self.short_name, self.version_id)
        profile_path_name = BOOM_OS_PROFILE_FORMAT % (profile_id)
        return path_join(boom_profiles_path(), profile_path_name)

    def write_profile(self, force=False):
        """Write out profile data to disk.

            Write out this ``OsProfile``'s data to a file in Boom
            format to the paths specified by the current configuration.

            Currently the ``os_id``, ``short_name`` and ``version_id``
            keys are used to construct the file name.

            If the value of ``force`` is ``False`` and the ``OsProfile``
            is not currently marked as dirty (either new, or modified
            since the last load operation) the write will be skipped.

            :param force: Force this profile to be written to disk even
                          if the entry is unmodified.
            :raises: ``OsError`` if the temporary entry file cannot be
                     renamed, or if setting file permissions on the
                     new entry file fails.
        """
        if not force and not self._unwritten:
            return

        profile_path = self._profile_path()

        _log_debug("Writing OsProfile(name='%s', os_id='%s') to '%s'" %
                   (self.name, self.disp_os_id, basename(profile_path)))

        (tmp_fd, tmp_path) = mkstemp(prefix="boom", dir=boom_profiles_path())
        with fdopen(tmp_fd, "w") as f:
            for key in [k for k in PROFILE_KEYS if k in self._profile_data]:
                if self._comments and key in self._comments:
                    f.write(self._comments[key].rstrip() + '\n')
                f.write('%s="%s"\n' % (key, self._profile_data[key]))
        try:
            rename(tmp_path, profile_path)
            chmod(profile_path, BOOM_PROFILE_MODE)
        except Exception as e:
            _log_error("Error writing profile file '%s': %s" %
                       (profile_path, e))
            try:
                unlink(tmp_path)
            except:
                pass
            raise e

        _log_debug("Wrote profile (os_id=%s)'" % self.disp_os_id)

    def delete_profile(self):
        """Delete on-disk data for this profile.

            Remove the on-disk profile corresponding to this
            ``OsProfile`` object. This will permanently erase the
            current file (although the current data may be re-written at
            any time by calling ``write_profile()`` before the object is
            disposed of).

            :returntype: ``NoneType``
            :raises: ``OsError`` if an error occurs removing the file or
                     ``ValueError`` if the profile does not exist.
        """
        global _profiles
        profile_path = self._profile_path()
        _log_debug("Deleting OsProfile(name='%s', os_id='%s') from '%s'" %
                   (self.name, self.disp_os_id, basename(profile_path)))
        if _profiles and self in _profiles:
            _profiles.remove(self)

        if not path_exists(profile_path):
            return

        try:
            unlink(profile_path)
        except Exception as e:
            _log_error("Error removing profile file '%s': %s" %
                       (profile_path, e))

        _log_debug("Deleted OsProfile(os_id='%s')" % self.disp_os_id)


_null_profile = OsProfile(name="", short_name="", version="", version_id="")

__all__ = [
    'OsProfile',
    'profiles_loaded', 'load_profiles', 'write_profiles', 'find_profiles',
    'get_os_profile_by_id', 'match_os_profile', 'select_profile',
    'match_os_profile_by_version',

    # Module constants
    'BOOM_PROFILES', 'BOOM_OS_PROFILE_FORMAT',
    'BOOM_PROFILE_MODE',

    # Exported key names
    'BOOM_OS_ID', 'BOOM_OS_NAME', 'BOOM_OS_SHORT_NAME',
    'BOOM_OS_VERSION', 'BOOM_OS_VERSION_ID', 'BOOM_OS_UNAME_PATTERN',
    'BOOM_OS_KERNEL_PATTERN', 'BOOM_OS_INITRAMFS_PATTERN',
    'BOOM_OS_ROOT_OPTS_LVM2', 'BOOM_OS_ROOT_OPTS_BTRFS',
    'BOOM_OS_OPTIONS',

    'PROFILE_KEYS', 'KEY_NAMES', 'REQUIRED_KEYS', 'ROOT_KEYS',

    # Path configuration
    'boom_profiles_path',
]

# vim: set et ts=4 sw=4 :

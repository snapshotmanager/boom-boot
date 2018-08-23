# Copyright (C) 2017 Red Hat, Inc., Bryn M. Reeves <bmr@redhat.com>
#
# command_tests.py - Boom command API tests.
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
import unittest
import logging
from sys import stdout
from os import listdir
from os.path import exists, abspath
import re

# Python3 moves StringIO to io
try:
    from StringIO import StringIO
except:
    from io import StringIO

log = logging.getLogger()
log.level = logging.DEBUG
log.addHandler(logging.FileHandler("test.log"))

from boom import *
from boom.osprofile import *
from boom.bootloader import *
from boom.command import *
from boom.config import *
from boom.report import *

from tests import MockArgs

BOOT_ROOT_TEST = abspath("./tests")
config = BoomConfig()
config.legacy_enable = False
config.legacy_sync = False
set_boom_config(config)
set_boot_path(BOOT_ROOT_TEST)


class CommandTests(unittest.TestCase):
    #
    # Test internal boom.command helpers: methods in this part of the
    # test suite import boom.command directly in order to access the
    # non-public helper routines not included in __all__.
    #
    def test_int_if_val_with_val(self):
        import boom.command
        val = "1"
        self.assertEqual(boom.command._int_if_val(val), int(val))

    def test_int_if_val_with_none(self):
        import boom.command
        val = None
        self.assertEqual(boom.command._int_if_val(val), None)

    def test_int_if_val_with_badint(self):
        import boom.command
        val = "qux"
        with self.assertRaises(ValueError) as cm:
            boom.command._int_if_val(val)

    def test_subvol_from_arg_subvol(self):
        import boom.command
        xtuple = ("/svol", None)
        self.assertEqual(boom.command._subvol_from_arg("/svol"), xtuple)

    def test_subvol_from_arg_subvolid(self):
        import boom.command
        xtuple = (None, "23")
        self.assertEqual(boom.command._subvol_from_arg("23"), xtuple)

    def test_subvol_from_arg_none(self):
        import boom.command
        self.assertEqual(boom.command._subvol_from_arg(None), (None, None))

    def test_str_indent(self):
        import boom.command
        instr = "1\n2\n3\n4"
        xstr = "    1\n    2\n    3\n    4"
        indent = 4
        outstr = boom.command._str_indent(instr, indent)
        self.assertEqual(outstr, xstr)

    def test_str_indent_bad_indent(self):
        import boom.command
        instr = "1\n2\n3\n4"
        indent = "qux"
        with self.assertRaises(TypeError) as cm:
            outstr = boom.command._str_indent(instr, indent)

    def test_str_indent_bad_str(self):
        import boom.command
        instr = None
        indent = 4
        with self.assertRaises(AttributeError) as cm:
            outstr = boom.command._str_indent(instr, indent)

    def test_canonicalize_lv_name(self):
        import boom.command
        xlv = "vg/lv"
        for lvstr in  ["vg/lv", "/dev/vg/lv"]:
            self.assertEqual(xlv, boom.command._canonicalize_lv_name(lvstr))

    def test_canonicalize_lv_name_bad_lv(self):
        import boom.command
        with self.assertRaises(ValueError) as cm:
            boom.command._canonicalize_lv_name("vg/lv/foo/bar/baz")
        with self.assertRaises(ValueError) as cm:
            boom.command._canonicalize_lv_name("vg-lv")
        with self.assertRaises(ValueError) as cm:
            boom.command._canonicalize_lv_name("/dev/mapper/vg-lv")

    def test_expand_fields_defaults(self):
        import boom.command
        default = "f1,f2,f3"
        xfield = default
        self.assertEqual(xfield, boom.command._expand_fields(default, ""))

    def test_expand_fields_replace(self):
        import boom.command
        default = "f1,f2,f3"
        options = "f4,f5,f6"
        xfield = options
        self.assertEqual(xfield, boom.command._expand_fields(default, options))

    def test_expand_fields_add(self):
        import boom.command
        default = "f1,f2,f3"
        options = "+f4,f5,f6"
        xfield = default + ',' + options[1:]
        self.assertEqual(xfield, boom.command._expand_fields(default, options))

    def test_command_find_profile_with_profile_arg(self):
        import boom.command
        _find_profile = boom.command._find_profile
        cmd_args = MockArgs()
        cmd_args.profile = "d4439b7d2f928c39f1160c0b0291407e5990b9e0" # F26
        cmd_args.machine_id = "12345" # No HostProfile
        osp = _find_profile(cmd_args, "", cmd_args.machine_id, "test")
        self.assertEqual(osp.os_id, cmd_args.profile)

    def test_command_find_profile_with_version_arg(self):
        import boom.command
        _find_profile = boom.command._find_profile
        cmd_args = MockArgs()
        cmd_args.profile = None
        cmd_args.version = "4.16.11-100.fc26.x86_64" # F26
        cmd_args.machine_id = "12345" # No HostProfile
        xprofile = "d4439b7d2f928c39f1160c0b0291407e5990b9e0"
        osp = _find_profile(cmd_args, cmd_args.version,
                            cmd_args.machine_id, "test")
        self.assertEqual(osp.os_id, xprofile)

    def test_command_find_profile_with_bad_version_arg(self):
        import boom.command
        _find_profile = boom.command._find_profile
        cmd_args = MockArgs()
        cmd_args.profile = None
        cmd_args.version = "4.16.11-100.x86_64" # no match
        cmd_args.machine_id = "12345" # No HostProfile
        xprofile = "d4439b7d2f928c39f1160c0b0291407e5990b9e0"
        osp = _find_profile(cmd_args, "", cmd_args.machine_id, "test")
        self.assertEqual(osp, None)

    def test_command_find_profile_bad_profile(self):
        import boom.command
        _find_profile = boom.command._find_profile
        cmd_args = MockArgs()
        cmd_args.profile = "quxquxquxquxquxquxquxqux" # nonexistent
        cmd_args.machine_id = "12345" # No HostProfile
        osp = _find_profile(cmd_args, "", cmd_args.machine_id, "test")
        self.assertEqual(osp, None)

    def test_command_find_profile_ambiguous_profile(self):
        import boom.command
        _find_profile = boom.command._find_profile
        cmd_args = MockArgs()
        cmd_args.profile = "9" # ambiguous
        cmd_args.machine_id = "12345" # No HostProfile
        osp = _find_profile(cmd_args, "", cmd_args.machine_id, "test")
        self.assertEqual(osp, None)

    def test_command_find_profile_ambiguous_host(self):
        import boom.command
        _find_profile = boom.command._find_profile
        cmd_args = MockArgs()
        cmd_args.profile = ""
        cmd_args.machine_id = "fffffffffff" # Ambiguous HostProfile
        osp = _find_profile(cmd_args, "", cmd_args.machine_id, "test")
        self.assertEqual(osp, None)

    def test_command_find_profile_host(self):
        import boom.command
        _find_profile = boom.command._find_profile
        cmd_args = MockArgs()
        cmd_args.profile = ""
        cmd_args.machine_id = "ffffffffffffc"
        cmd_args.label = ""
        hp = _find_profile(cmd_args, "", cmd_args.machine_id, "test")
        self.assertTrue(hp)
        self.assertTrue(hasattr(hp, "add_opts"))

    def test_command_find_profile_host_os_mismatch(self):
        import boom.command
        _find_profile = boom.command._find_profile
        cmd_args = MockArgs()
        cmd_args.profile = "3fc389bba581e5b20c6a46c7fc31b04be465e973"
        cmd_args.machine_id = "ffffffffffffc"
        cmd_args.label = ""
        hp = _find_profile(cmd_args, "", cmd_args.machine_id, "test")
        self.assertFalse(hp)

    def test_command_find_profile_no_matching(self):
        import boom.command
        _find_profile = boom.command._find_profile
        cmd_args = MockArgs()
        cmd_args.profile = ""
        cmd_args.machine_id = "1111111111111111" # no matching
        hp = _find_profile(cmd_args, "", cmd_args.machine_id,
                           "test", optional=False)
        self.assertFalse(hp)

    #
    # API call tests
    #
    # BootEntry tests
    #

    def test_list_entries(self):
        path = boom_entries_path()
        nr = len([p for p in listdir(path) if p.endswith(".conf")])
        bes = list_entries()
        self.assertTrue(len(bes), nr)

    def test_list_entries_match_machine_id(self):
        machine_id = "611f38fd887d41dea7eb3403b2730a76"
        path = boom_entries_path()
        nr = len([p for p in listdir(path) if p.startswith(machine_id)])
        bes = list_entries(Selection(machine_id=machine_id))
        self.assertTrue(len(bes), nr)

    def test_list_entries_match_version(self):
        version = "4.10.17-100.fc24.x86_64"
        path = boom_entries_path()
        nr = len([p for p in listdir(path) if version in p])
        bes = list_entries(Selection(version=version))
        self.assertEqual(len(bes), nr)

    def test_create_entry_notitle(self):
        # Fedora 24 (Workstation Edition)
        osp = get_os_profile_by_id("9cb53ddda889d6285fd9ab985a4c47025884999f")
        osp.title = None
        with self.assertRaises(ValueError) as cm:
            be = create_entry(None, "2.6.0", "ffffffff", "/dev/vg_hex/root",
                              lvm_root_lv="vg_hex/root", profile=osp)

    def test_create_entry_noversion(self):
        # Fedora 24 (Workstation Edition)
        osp = get_os_profile_by_id("9cb53ddda889d6285fd9ab985a4c47025884999f")
        with self.assertRaises(ValueError) as cm:
            be = create_entry("ATITLE", None, "ffffffff", "/dev/vg_hex/root",
                              lvm_root_lv="vg_hex/root", profile=osp)

    def test_create_entry_nomachineid(self):
        # Fedora 24 (Workstation Edition)
        osp = get_os_profile_by_id("9cb53ddda889d6285fd9ab985a4c47025884999f")
        with self.assertRaises(ValueError) as cm:
            be = create_entry("ATITLE", "2.6.0", "", "/dev/vg_hex/root",
                              lvm_root_lv="vg_hex/root", profile=osp)

    def test_create_entry_norootdevice(self):
        # Fedora 24 (Workstation Edition)
        osp = get_os_profile_by_id("9cb53ddda889d6285fd9ab985a4c47025884999f")
        with self.assertRaises(ValueError) as cm:
            be = create_entry("ATITLE", "2.6.0", "ffffffff", None,
                              lvm_root_lv="vg_hex/root", profile=osp)

    def test_create_entry_noosprofile(self):
        # Fedora 24 (Workstation Edition)
        osp = get_os_profile_by_id("9cb53ddda889d6285fd9ab985a4c47025884999f")
        with self.assertRaises(ValueError) as cm:
            be = create_entry("ATITLE", "2.6.0", "ffffffff",
                              "/dev/vg_hex/root", lvm_root_lv="vg_hex/root")

    def test_create_dupe(self):
        # Fedora 24 (Workstation Edition)
        osp = get_os_profile_by_id("9cb53ddda889d6285fd9ab985a4c47025884999f")

        title = "Fedora (4.1.1-100.fc24.x86_64) 24 (Workstation Edition)"
        machine_id = "611f38fd887d41dea7eb3403b2730a76"
        version = "4.1.1-100.fc24"
        root_device = "/dev/sda5"
        btrfs_subvol_id = "23"

        with self.assertRaises(ValueError) as cm:
            create_entry(title, version, machine_id, root_device,
                         btrfs_subvol_id=btrfs_subvol_id, profile=osp,
                         allow_no_dev=True)

    def test_create_delete_entry(self):
        # Fedora 24 (Workstation Edition)
        osp = get_os_profile_by_id("9cb53ddda889d6285fd9ab985a4c47025884999f")
        be = create_entry("ATITLE", "2.6.0", "ffffffff", "/dev/vg_hex/root",
                          lvm_root_lv="vg_hex/root", profile=osp)
        self.assertTrue(exists(be._entry_path))

        delete_entries(Selection(boot_id=be.boot_id))
        self.assertFalse(exists(be._entry_path))

    def test_create_delete_entry_with_legacy(self):
        config = BoomConfig()
        config.legacy_enable = True
        config.legacy_sync = True
        set_boom_config(config)
        set_boot_path(BOOT_ROOT_TEST)

        # Fedora 24 (Workstation Edition)
        osp = get_os_profile_by_id("9cb53ddda889d6285fd9ab985a4c47025884999f")
        be = create_entry("ATITLE", "2.6.0", "ffffffff", "/dev/vg_hex/root",
                          lvm_root_lv="vg_hex/root", profile=osp)
        self.assertTrue(exists(be._entry_path))

        delete_entries(Selection(boot_id=be.boot_id))
        self.assertFalse(exists(be._entry_path))


    def test_delete_entries_no_matching_raises(self):
        with self.assertRaises(IndexError) as cm:
            delete_entries(Selection(boot_id="thereisnospoon"))

    def test_clone_entry_no_boot_id(self):
        with self.assertRaises(ValueError) as cm:
            bad_be = clone_entry(Selection())

    def test_clone_entry_no_matching_boot_id(self):
        with self.assertRaises(ValueError) as cm:
            bad_be = clone_entry(Selection(boot_id="qqqqqqq"), title="FAIL")

    def test_clone_entry_ambiguous_boot_id(self):
        with self.assertRaises(ValueError) as cm:
            bad_be = clone_entry(Selection(boot_id="6"), title="NEWTITLE")


    def test_clone_entry_add_opts(self):
        be = clone_entry(Selection(boot_id="9591d36"), title="NEWNEWTITLE",
                         add_opts="foo", allow_no_dev=True)
        self.assertTrue(exists(be._entry_path))
        be.delete_entry()
        self.assertFalse(exists(be._entry_path))

    def test_clone_entry_del_opts(self):
        be = clone_entry(Selection(boot_id="9591d36"), title="NEWNEWTITLE",
                         del_opts="rhgb quiet", allow_no_dev=True)
        self.assertTrue(exists(be._entry_path))
        be.delete_entry()
        self.assertFalse(exists(be._entry_path))

    def test_clone_delete_entry(self):
        # Fedora 24 (Workstation Edition)
        osp = get_os_profile_by_id("9cb53ddda889d6285fd9ab985a4c47025884999f")
        be = create_entry("ATITLE", "2.6.0", "ffffffff", "/dev/vg_hex/root",
                          lvm_root_lv="vg_hex/root", profile=osp)
        self.assertTrue(exists(be._entry_path))

        be2 = clone_entry(Selection(boot_id=be.boot_id), title="ANEWTITLE",
                          version="2.6.1")

        self.assertTrue(exists(be2._entry_path))

        be.delete_entry()
        be2.delete_entry()

        self.assertFalse(exists(be._entry_path))
        self.assertFalse(exists(be2._entry_path))

    def test_clone_entry_no_args(self):
        # Fedora 24 (Workstation Edition)
        osp = get_os_profile_by_id("9cb53ddda889d6285fd9ab985a4c47025884999f")
        be = create_entry("ATITLE", "2.6.0", "ffffffff", "/dev/vg_hex/root",
                          lvm_root_lv="vg_hex/root", profile=osp)
        self.assertTrue(exists(be._entry_path))

        with self.assertRaises(ValueError) as cm:
            be2 = clone_entry(Selection(boot_id=be.boot_id))

        be.delete_entry()

    def test_clone_entry_with_add_del_opts(self):
        # Entry with options +"debug" -"rhgb quiet"
        orig_boot_id = "78861b7"
        be = clone_entry(Selection(boot_id=orig_boot_id),
                         title="clone with addopts")
        orig_be = find_entries(Selection(boot_id=orig_boot_id))[0]
        self.assertTrue(orig_be)
        self.assertTrue(be)
        self.assertEqual(orig_be.options, be.options)
        be.delete_entry()

    def test_clone_dupe(self):
        # Fedora 24 (Workstation Edition)
        osp = get_os_profile_by_id("9cb53ddda889d6285fd9ab985a4c47025884999f")
        be = create_entry("CLONE_TEST", "2.6.0", "ffffffff", "/dev/vg_hex/root",
                          lvm_root_lv="vg_hex/root", profile=osp)
        self.assertTrue(exists(be._entry_path))

        be2 = clone_entry(Selection(boot_id=be.boot_id), title="ANEWTITLE",
                          version="2.6.1")

        with self.assertRaises(ValueError) as cm:
            be3 = clone_entry(Selection(boot_id=be.boot_id), title="ANEWTITLE",
                              version="2.6.1")

        be.delete_entry()
        be2.delete_entry()

    def test_edit_entry_no_boot_id(self):
        with self.assertRaises(ValueError) as cm:
            bad_be = edit_entry(Selection())

    def test_edit_entry_no_matching_boot_id(self):
        with self.assertRaises(ValueError) as cm:
            bad_be = edit_entry(Selection(boot_id="qqqqqqq"), title="FAIL")

    def test_edit_entry_ambiguous_boot_id(self):
        with self.assertRaises(ValueError) as cm:
            bad_be = edit_entry(Selection(boot_id="6"), title="NEWTITLE")


    def test_edit_entry_add_opts(self):
        # Fedora 24 (Workstation Edition)
        osp = get_os_profile_by_id("9cb53ddda889d6285fd9ab985a4c47025884999f")
        orig_be = create_entry("EDIT_TEST", "2.6.0", "ffffffff",
                               "/dev/vg_hex/root", lvm_root_lv="vg_hex/root",
                               profile=osp)

        # Confirm original entry has been written
        self.assertTrue(exists(orig_be._entry_path))

        # Save these - they will be overwritten by the edit operation
        orig_id = orig_be.boot_id
        orig_entry_path = orig_be._entry_path

        edit_title = "EDITED_TITLE"
        edit_add_opts = "foo"

        # FIXME: restore allow_no_dev
        edit_be = edit_entry(Selection(boot_id=orig_id), title=edit_title,
                              add_opts=edit_add_opts)

        # Confirm edited entry has been written
        self.assertTrue(exists(edit_be._entry_path))

        # Confirm original entry has been removed
        self.assertFalse(exists(orig_entry_path))

        # Verify new boot_id
        self.assertFalse(orig_id == edit_be.boot_id)

        # Verify edited title and options
        self.assertEqual(edit_title, edit_be.title)
        self.assertEqual(edit_be.bp.add_opts, [edit_add_opts])
        self.assertTrue(edit_add_opts in edit_be.options)

        # Clean up entries
        edit_be.delete_entry()

    def test_edit_entry_add_opts_with_add_opts(self):
        edit_title = "EDITED_TITLE"
        edit_add_opts = "foo"
        orig_add_opts = "bar"

        # Fedora 24 (Workstation Edition)
        osp = get_os_profile_by_id("9cb53ddda889d6285fd9ab985a4c47025884999f")
        orig_be = create_entry("EDIT_TEST", "2.6.0", "ffffffff",
                               "/dev/vg_hex/root", lvm_root_lv="vg_hex/root",
                               add_opts="bar", profile=osp)

        # Confirm original entry has been written
        self.assertTrue(exists(orig_be._entry_path))

        # Save these - they will be overwritten by the edit operation
        orig_id = orig_be.boot_id
        orig_entry_path = orig_be._entry_path

        # FIXME: restore allow_no_dev
        edit_be = edit_entry(Selection(boot_id=orig_id), title=edit_title,
                             add_opts=edit_add_opts)

        # Confirm edited entry has been written
        self.assertTrue(exists(edit_be._entry_path))

        # Confirm original entry has been removed
        self.assertFalse(exists(orig_entry_path))

        # Verify new boot_id
        self.assertFalse(orig_id == edit_be.boot_id)

        # Verify edited title and options
        self.assertEqual(edit_title, edit_be.title)
        self.assertEqual(edit_be.bp.add_opts, [edit_add_opts, orig_add_opts])
        # Verify original added opts
        self.assertTrue(orig_add_opts in edit_be.options)
        # Verify edit added opts
        self.assertTrue(edit_add_opts in edit_be.options)

        # Clean up entries
        edit_be.delete_entry()

    def test_edit_entry_del_opts(self):
        # Fedora 24 (Workstation Edition)
        osp = get_os_profile_by_id("9cb53ddda889d6285fd9ab985a4c47025884999f")
        orig_be = create_entry("EDIT_TEST", "2.6.0", "ffffffff",
                               "/dev/vg_hex/root", lvm_root_lv="vg_hex/root",
                               profile=osp)

        # Confirm original entry has been written
        self.assertTrue(exists(orig_be._entry_path))

        # Save these - they will be overwritten by the edit operation
        orig_id = orig_be.boot_id
        orig_entry_path = orig_be._entry_path

        edit_title = "EDITED_TITLE"
        edit_del_opts = "rhgb"

        # FIXME: restore allow_no_dev
        edit_be = edit_entry(Selection(boot_id=orig_id), title=edit_title,
                             del_opts=edit_del_opts)

        # Confirm edited entry has been written
        self.assertTrue(exists(edit_be._entry_path))

        # Confirm original entry has been removed
        self.assertFalse(exists(orig_entry_path))

        # Verify new boot_id
        self.assertFalse(orig_id == edit_be.boot_id)

        # Verify edited title and options
        self.assertEqual(edit_title, edit_be.title)
        self.assertEqual(edit_be.bp.del_opts, [edit_del_opts])
        self.assertTrue(edit_del_opts not in edit_be.options)

        # Clean up entries
        edit_be.delete_entry()

    def test_edit_entry_del_opts_with_del_opts(self):
        edit_title = "EDITED_TITLE"
        edit_del_opts = "rhgb"
        orig_del_opts = "quiet"

        # Fedora 24 (Workstation Edition)
        osp = get_os_profile_by_id("9cb53ddda889d6285fd9ab985a4c47025884999f")
        orig_be = create_entry("EDIT_TEST", "2.6.0", "ffffffff",
                               "/dev/vg_hex/root", lvm_root_lv="vg_hex/root",
                               del_opts="quiet", profile=osp)

        # Confirm original entry has been written
        self.assertTrue(exists(orig_be._entry_path))

        # Save these - they will be overwritten by the edit operation
        orig_id = orig_be.boot_id
        orig_entry_path = orig_be._entry_path

        # Verify original deled opts
        self.assertTrue(orig_del_opts not in orig_be.options)
        self.assertEqual(orig_be.bp.del_opts, [orig_del_opts])

        print("\nORIG DEL_OPTS: %s" % orig_be.bp.del_opts)
        print("\nORIG OPTIONS: %s" % orig_be.options)

        # FIXME: restore allow_no_dev
        edit_be = edit_entry(Selection(boot_id=orig_id), title=edit_title,
                             del_opts=edit_del_opts)

        print("\nEDIT DEL_OPTS: %s" % edit_be.bp.del_opts)
        print("\nEDIT OPTIONS: %s" % edit_be.options)

        # Confirm edited entry has been written
        self.assertTrue(exists(edit_be._entry_path))

        # Confirm original entry has been removed
        self.assertFalse(exists(orig_entry_path))

        # Verify new boot_id
        self.assertFalse(orig_id == edit_be.boot_id)

        # Verify edited title and options
        self.assertEqual(edit_title, edit_be.title)
        self.assertEqual(edit_be.bp.del_opts, [edit_del_opts, orig_del_opts])
        # Verify original deleted opts
        self.assertTrue(orig_del_opts not in edit_be.options)
        # Verify edit deleted opts
        self.assertTrue(edit_del_opts not in edit_be.options)

        # Clean up entries
        edit_be.delete_entry()

    def test_print_entries_no_matching(self):
        xoutput = r"BootID.*Version.*Name.*RootDevice"
        output = StringIO()
        opts = BoomReportOpts(report_file=output)
        print_entries(selection=Selection(boot_id="thereisnoboot"), opts=opts)
        self.assertTrue(re.match(xoutput, output.getvalue()))

    def test_print_entries_default_stdout(self):
        print_entries()

    def test_print_entries_boot_id_filter(self):
        xoutput = [r"BootID.*Version.*Name.*RootDevice",
                   r"debfd7f.*4.11.12-100.fc24.x86_64.*Fedora.*"
                   r"/dev/vg00/lvol0-snapshot"]
        output = StringIO()
        opts = BoomReportOpts(report_file=output)
        print_entries(selection=Selection(boot_id="debfd7f"), opts=opts)
        print(output.getvalue())
        for pair in zip(xoutput, output.getvalue().splitlines()):
            self.assertTrue(re.match(pair[0], pair[1]))

    #
    # API call tests
    #
    # OsProfile tests
    #

    def test_command_create_delete_profile(self):
        osp = create_profile("Some Distro", "somedist", "1 (Qunk)", "1",
                             uname_pattern="sd1",
                             kernel_pattern="/vmlinuz-%{version}",
                             initramfs_pattern="/initramfs-%{version}.img",
                             root_opts_lvm2="rd.lvm.lv=%{lvm_root_lv}",
                             root_opts_btrfs="rootflags=%{btrfs_subvolume}",
                             options="root=%{root_device} %{root_opts}")
        self.assertTrue(osp)
        self.assertEqual(osp.os_name, "Some Distro")

        # Use the OsProfile.delete_profile() method
        osp.delete_profile()

    def test_command_create_delete_profiles(self):
        osp = create_profile("Some Distro", "somedist", "1 (Qunk)", "1",
                             uname_pattern="sd1",
                             kernel_pattern="/vmlinuz-%{version}",
                             initramfs_pattern="/initramfs-%{version}.img",
                             root_opts_lvm2="rd.lvm.lv=%{lvm_root_lv}",
                             root_opts_btrfs="rootflags=%{btrfs_subvolume}",
                             options="root=%{root_device} %{root_opts}")

        self.assertTrue(osp)
        self.assertEqual(osp.os_name, "Some Distro")

        # Use the command.delete_profiles() API call
        delete_profiles(selection=Selection(os_id=osp.os_id))

    def test_command_delete_profiles_no_match(self):
        with self.assertRaises(IndexError) as cm:
            delete_profiles(selection=Selection(os_id="XyZZy"))

    def test_command_create_delete_profile_from_file(self):
        os_release_path = "tests/os-release/fedora26-test-os-release"
        osp = create_profile(None, None, None, None,
                             profile_file=os_release_path, uname_pattern="sd1",
                             kernel_pattern="/vmlinuz-%{version}",
                             initramfs_pattern="/initramfs-%{version}.img",
                             root_opts_lvm2="rd.lvm.lv=%{lvm_root_lv}",
                             root_opts_btrfs="rootflags=%{btrfs_subvolume}",
                             options="root=%{root_device} %{root_opts}")
        self.assertTrue(osp)
        self.assertEqual(osp.os_name, "Fedora")
        self.assertEqual(osp.os_version, "26 (Testing Edition)")
        osp.delete_profile()

    def test_command_create_delete_profile_from_profile_data(self):
        profile_data = {
            BOOM_OS_NAME: "Some Distro", BOOM_OS_SHORT_NAME: "somedist",
            BOOM_OS_VERSION: "1 (Qunk)", BOOM_OS_VERSION_ID: "1",
            BOOM_OS_UNAME_PATTERN: "sd1",
            BOOM_OS_KERNEL_PATTERN: "/vmlinuz-%{version}",
            BOOM_OS_INITRAMFS_PATTERN: "/initramfs-%{version}.img",
            BOOM_OS_ROOT_OPTS_LVM2: "rd.lvm.lv=%{lvm_root_lv}",
            BOOM_OS_ROOT_OPTS_BTRFS: "rootflags=%{btrfs_subvolume}",
            BOOM_OS_OPTIONS: "root=%{root_device} %{root_opts}",
            BOOM_OS_TITLE: "This is a title (%{version})"
        }

        # All fields: success
        osp = create_profile(None, None, None, None, profile_data=profile_data)
        self.assertTrue(osp)
        self.assertEqual(osp.os_name, "Some Distro")
        self.assertEqual(osp.os_version, "1 (Qunk)")
        osp.delete_profile()

        # Pop identity fields in reverse checking order:
        # OS_VERSION_ID, OS_VERSION, OS_SHORT_NAME, OS_NAME

        profile_data.pop(BOOM_OS_VERSION_ID)
        with self.assertRaises(ValueError) as cm:
            bad_osp = create_profile(None, None, None, None,
                                     profile_data=profile_data)

        profile_data.pop(BOOM_OS_VERSION)
        with self.assertRaises(ValueError) as cm:
            bad_osp = create_profile(None, None, None, None,
                                     profile_data=profile_data)

        profile_data.pop(BOOM_OS_SHORT_NAME)
        with self.assertRaises(ValueError) as cm:
            bad_osp = create_profile(None, None, None, None,
                                     profile_data=profile_data)

        profile_data.pop(BOOM_OS_NAME)
        with self.assertRaises(ValueError) as cm:
            bad_osp = create_profile(None, None, None, None,
                                     profile_data=profile_data)

    def test_clone_profile_no_os_id(self):
        with self.assertRaises(ValueError) as cm:
            bad_osp = clone_profile(Selection())

    def test_clone_profile_no_args(self):
        with self.assertRaises(ValueError) as cm:
            bad_osp = clone_profile(Selection(os_id="d4439b7"))

    def test_clone_profile_no_matching_os_id(self):
        with self.assertRaises(ValueError) as cm:
            bad_osp = clone_profile(Selection(os_id="fffffff"), name="NEW")

    def test_clone_profile_ambiguous_os_id(self):
        with self.assertRaises(ValueError) as cm:
            bad_osp = clone_profile(Selection(os_id="d"), name="NEW")

    def test_clone_profile_new_name(self):
        osp = clone_profile(Selection(os_id="d4439b7"),
                            name="NEW", short_name="new", version="26 (Not)",
                            version_id="~26")
        self.assertTrue(osp)
        self.assertEqual("NEW", osp.os_name)
        self.assertEqual("new", osp.os_short_name)
        osp.delete_profile()

    def test_create_edit_profile(self):
        osp = create_profile("Test1", "test", "1 (Test)", "1",
                             uname_pattern="t1")

        self.assertTrue(osp)

        edit_osp = edit_profile(Selection(os_id=osp.os_id),
                                uname_pattern="t2")

        self.assertTrue(edit_osp)
        self.assertEqual(osp.uname_pattern, "t2")
        osp.delete_profile()
        edit_osp.delete_profile()

    def test_edit_no_matching_os_id(self):
        with self.assertRaises(ValueError) as cm:
            edit_osp = edit_profile(Selection(os_id="notfound"),
                                    uname_pattern="nf2")

    def test_edit_ambiguous_os_id(self):
        with self.assertRaises(ValueError) as cm:
            edit_osp = edit_profile(Selection(os_id="d"),
                                    uname_pattern="d2")

# Calling the main() entry point from the test suite causes a SysExit
# exception in ArgParse() (too few arguments).
#    def test_boom_main_noargs(self):
#        args = [abspath('bin/boom'), '--help']
#        main(args)

# vim: set et ts=4 sw=4 :

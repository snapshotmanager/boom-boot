# Copyright (C) 2017 Red Hat, Inc., Bryn M. Reeves <bmr@redhat.com>
#
# report_tests.py - Boom report API tests.
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
from StringIO import StringIO

log = logging.getLogger()
log.level = logging.DEBUG
log.addHandler(logging.FileHandler("test.log"))

import boom
BOOT_ROOT_TEST = abspath("./tests")
boom.set_boot_path(BOOT_ROOT_TEST)

import boom.report

from boom.report import *

_report_objs = [
    (1, "foo", "ffffffffffffffffffffffffffffffffffffffff"),
    (2, "bar", "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"),
    (3, "baz", "1111111111111111111111111111111111111111"),
    (4, "qux", "2222222222222222222222222222222222222222")
]

BR_NUM = 1
BR_STR = 2
BR_SHA = 4

_test_obj_types = [
    BoomReportObjType(BR_NUM, "Num", "num_", lambda o: o[0]),
    BoomReportObjType(BR_STR, "Str", "str_", lambda o: o[1]),
    BoomReportObjType(BR_SHA, "Sha", "sha_", lambda o: o[2])
]


class ReportTests(unittest.TestCase):
    def test_BoomFieldType_no_name(self):
        with self.assertRaises(ValueError):
            bf = BoomFieldType(BR_NUM, None, "None", "Nothing", 0,
                               REP_NUM, lambda x: x)

    def test_BoomFieldType_bogus_dtype_raises(self):
        with self.assertRaises(ValueError):
            bf = BoomFieldType(BR_NUM, "none", "None", "Nothing", 0,
                               "fzzrt", lambda x: x)

    def test_BoomFieldType_dtype_NUM(self):
        bf = BoomFieldType(BR_NUM, "none", "None", "Nothing", 0,
                           REP_NUM, lambda x: x)
        self.assertEqual(bf.dtype, REP_NUM)

    def test_BoomFieldType_dtype_STR(self):
        bf = BoomFieldType(BR_STR, "none", "None", "Nothing", 0,
                           REP_STR, lambda x: x)
        self.assertEqual(bf.dtype, REP_STR)

    def test_BoomFieldType_dtype_SHA(self):
        bf = BoomFieldType(BR_SHA, "none", "None", "Nothing", 0,
                           REP_SHA, lambda x: x)
        self.assertEqual(bf.dtype, REP_SHA)

    def test_BoomFieldType_bogus_align_raises(self):
        with self.assertRaises(ValueError):
            bf = BoomFieldType(BR_NUM, "none", "None", "Nothing", 0,
                               REP_NUM, lambda x: x, align="qux")

    def test_BoomFieldType_with_align_l(self):
        bf = BoomFieldType(BR_NUM, "none", "None", "Nothing", 0,
                           REP_NUM, lambda x: x, align=ALIGN_LEFT)

    def test_BoomFieldType_with_align_r(self):
        bf = BoomFieldType(BR_NUM, "none", "None", "Nothing", 0,
                           REP_NUM, lambda x: x, align=ALIGN_RIGHT)

    def test_BoomFieldType_negative_width_raises(self):
        with self.assertRaises(ValueError) as cm:
            bf = BoomFieldType(BR_NUM, "none", "None", "Nothing", -1,
                               REP_NUM, lambda x: x)

    def test_BoomFieldType_simple_str_int_report(self):
        bf_name = BoomFieldType(BR_STR, "name", "Name", "Nothing", 8,
                                REP_STR, lambda f, d: f.report_str(d))
        bf_num = BoomFieldType(BR_NUM, "number", "Number", "Nothing", 8,
                               REP_NUM, lambda f, d: f.report_num(d))

        output = StringIO()
        opts = BoomReportOpts(report_file=output)

        xoutput = ("Name     Number  \nfoo             1\n" +
                   "bar             2\nbaz             3\nqux             4\n")

        br = BoomReport(_test_obj_types, [bf_name, bf_num], "name,number",
                        opts, None, None)

        for obj in _report_objs:
            br.report_object(obj)
        br.report_output()

        print("\n" + output.getvalue() + "\n")
        self.assertEqual(output.getvalue(), xoutput)

# vim: set et ts=4 sw=4 :

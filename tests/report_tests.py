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
from os.path import exists
from StringIO import StringIO

log = logging.getLogger()
log.level = logging.DEBUG
log.addHandler(logging.FileHandler("test.log"))

import boom
BOOT_ROOT_TEST = "./tests"
BOOM_ROOT_TEST = BOOT_ROOT_TEST + "/boom"
boom.BOOM_ROOT = BOOM_ROOT_TEST
boom.BOOT_ROOT = BOOT_ROOT_TEST

import boom.report

from boom.report import (
    BoomField, BoomReport, BoomReportOpts,
    REP_INT, REP_STR, REP_SHA,
    ALIGN_LEFT, ALIGN_RIGHT
)

class ReportTests(unittest.TestCase):
    def test_default_sort_fn(self):
        bigger = 1000
        smaller = 1
        _default_sort_fn = boom.report._default_sort_fn
        self.assertTrue(_default_sort_fn(bigger, smaller))

    def test_BoomField_no_name(self):
        with self.assertRaises(ValueError):
            bf = BoomField(None, "None", 0, REP_INT, lambda x: x)

    def test_BoomField_bogus_dtype_raises(self):
        with self.assertRaises(ValueError):
            bf = BoomField("none", "None", 0, "fzzrt", lambda x: x)

    def test_BoomField_dtype_INT(self):
        bf = BoomField("none", "None", 0, REP_INT, lambda x: x)
        self.assertEqual(bf.dtype, REP_INT)

    def test_BoomField_dtype_STR(self):
        bf = BoomField("none", "None", 0, REP_STR, lambda x: x)
        self.assertEqual(bf.dtype, REP_STR)

    def test_BoomField_dtype_SHA(self):
        bf = BoomField("none", "None", 0, REP_SHA, lambda x: x)
        self.assertEqual(bf.dtype, REP_SHA)

    def test_BoomField_bogus_align_raises(self):
        with self.assertRaises(ValueError):
            bf = BoomField("none", "None", 0, REP_INT,
                           lambda x: x, align="qux")

    def test_BoomField_with_align_l(self):
        bf = BoomField("none", "None", 0, REP_INT,
                       lambda x: x, align=ALIGN_LEFT)

    def test_BoomField_with_align_r(self):
        bf = BoomField("none", "None", 0, REP_INT,
                       lambda x: x, align=ALIGN_RIGHT)

    def test_BoomField_negative_width_raises(self):
        with self.assertRaises(ValueError) as cm:
            bf = BoomField("none", "None", -1, REP_INT, lambda x: x)

    def test_BoomField_simple_str_int_report(self):
        bf_name = BoomField("name", "Name", 8, REP_STR, lambda x: x[0])
        bf_num = BoomField("number", "Number", 8, REP_INT, lambda x: x[1])

        output = StringIO()
        xoutput = ("Name     Number   \nOne             1 \nTwo             " +
                   "2 \nThree           3 \n")

        br = BoomReport(output, "simple", [bf_name, bf_num], None)
        br.add_row_data(("One", 1))
        br.add_row_data(("Two", 2))
        br.add_row_data(("Three", 3))
        br.output()

        self.assertEqual(output.getvalue(), xoutput)

# vim: set et ts=4 sw=4 :

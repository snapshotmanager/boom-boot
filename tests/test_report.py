# Copyright Red Hat
#
# tests/test_report.py - report API tests.
#
# This file is part of the boom project.
#
# SPDX-License-Identifier: GPL-2.0-only
import unittest
import logging
from os.path import exists, abspath
import uuid
from io import StringIO

log = logging.getLogger()

import boom
BOOT_ROOT_TEST = abspath("./tests")
boom.set_boot_path(BOOT_ROOT_TEST)

import boom.report

from boom.report import (
    REP_NUM,
    REP_STR,
    REP_SHA,
    REP_TIME,
    REP_UUID,
    REP_SIZE,
    REP_STR_LIST,
    ALIGN_LEFT,
    ALIGN_RIGHT,
    ReportOpts,
    ReportObjType,
    FieldType,
    Report,
)

_report_objs = [
    (
        1,
        "foo",
        "ffffffffffffffffffffffffffffffffffffffff",
        "2023-09-05 14:40:53",
        uuid.UUID("00000000-0000-0000-0000-000000000000"),
        1024,
        ["foo", "bar", "baz"],
    ),
    (
        2,
        "bar",
        "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF",
        "1978-01-10 09:13:12",
        uuid.UUID("1d133bcc-6137-5267-b870-e469f7188dbe"),
        1024**2,
        ["one", "two", "three"],
    ),
    (
        3,
        "baz",
        "1111111111111111111111111111111111111111",
        "2022-08-01 16:43:32",
        uuid.UUID("3576355e-e4d7-5a57-9f24-b3f4e0e326ef"),
        1024**3,
        ["baz", "quux"],
    ),
    (
        4,
        "qux",
        "2222222222222222222222222222222222222222",
        "2020-01-01 23:32:08",
        uuid.UUID("046e4f15-1ddd-5724-b032-878248a71d4b"),
        1024**4,
        ["string", "list"],
    ),
]

PR_NUM = 1
PR_STR = 2
PR_SHA = 4
PR_TIME = 8
PR_UUID = 16
PR_SIZE = 32
PR_STR_LIST = 64

_test_obj_types = [
    ReportObjType(PR_NUM, "Num", "num_", lambda o: o[0]),
    ReportObjType(PR_STR, "Str", "str_", lambda o: o[1]),
    ReportObjType(PR_SHA, "Sha", "sha_", lambda o: o[2]),
    ReportObjType(PR_TIME, "Time", "time_", lambda o: o[3]),
    ReportObjType(PR_UUID, "Uuid", "uuid_", lambda o: o[4]),
    ReportObjType(PR_SIZE, "Size", "size_", lambda o: o[5]),
    ReportObjType(PR_STR_LIST, "StrList", "strlist_", lambda o: o[6]),
]


class ReportTests(unittest.TestCase):
    def setUp(self):
        log.debug("Preparing %s", self._testMethodName)

    def tearDown(self):
        log.debug("Tearing down %s", self._testMethodName)

    def test_FieldType_no_type(self):
        with self.assertRaises(ValueError):
            FieldType(0, None, "None", "Nothing", 0, REP_NUM, lambda x: x)

    def test_FieldType_no_name(self):
        with self.assertRaises(ValueError):
            FieldType(PR_NUM, None, "None", "Nothing", 0, REP_NUM, lambda x: x)

    def test_FieldType_bogus_dtype_raises(self):
        with self.assertRaises(ValueError):
            FieldType(PR_NUM, "none", "None", "Nothing", 0, "fzzrt", lambda x: x)

    def test_FieldType_dtype_NUM(self):
        pf = FieldType(PR_NUM, "none", "None", "Nothing", 0, REP_NUM, lambda x: x)
        self.assertEqual(pf.dtype, REP_NUM)

    def test_FieldType_dtype_STR(self):
        pf = FieldType(PR_STR, "none", "None", "Nothing", 0, REP_STR, lambda x: x)
        self.assertEqual(pf.dtype, REP_STR)

    def test_FieldType_dtype_SHA(self):
        pf = FieldType(PR_SHA, "none", "None", "Nothing", 0, REP_SHA, lambda x: x)
        self.assertEqual(pf.dtype, REP_SHA)

    def test_FieldType_dtype_TIME(self):
        pf = FieldType(PR_TIME, "none", "None", "Nothing", 0, REP_TIME, lambda x: x)
        self.assertEqual(pf.dtype, REP_TIME)

    def test_FieldType_dtype_UUID(self):
        pf = FieldType(PR_UUID, "none", "None", "Nothing", 0, REP_UUID, lambda x: x)
        self.assertEqual(pf.dtype, REP_UUID)

    def test_FieldType_dtype_SIZE(self):
        pf = FieldType(PR_SIZE, "none", "None", "Nothing", 0, REP_SIZE, lambda x: x)
        self.assertEqual(pf.dtype, REP_SIZE)

    def test_FieldType_dtype_STR_LIST(self):
        pf = FieldType(
            PR_STR_LIST, "none", "non", "Nothing", 0, REP_STR_LIST, lambda x: x
        )
        self.assertEqual(pf.dtype, REP_STR_LIST)

    def test_FieldType_bogus_align_raises(self):
        with self.assertRaises(ValueError):
            FieldType(
                PR_NUM,
                "none",
                "None",
                "Nothing",
                0,
                REP_NUM,
                lambda x: x,
                align="qux",
            )

    def test_FieldType_with_align_l(self):
        FieldType(
            PR_NUM,
            "none",
            "None",
            "Nothing",
            0,
            REP_NUM,
            lambda x: x,
            align=ALIGN_LEFT,
        )

    def test_FieldType_with_align_r(self):
        FieldType(
            PR_NUM,
            "none",
            "None",
            "Nothing",
            0,
            REP_NUM,
            lambda x: x,
            align=ALIGN_RIGHT,
        )

    def test_FieldType_negative_width_raises(self):
        with self.assertRaises(ValueError) as cm:
            FieldType(PR_NUM, "none", "None", "Nothing", -1, REP_NUM, lambda x: x)

    def test_FieldType_simple_str_int_report(self):
        pf_name = FieldType(
            PR_STR,
            "name",
            "Name",
            "Nothing",
            8,
            REP_STR,
            lambda f, d: f.report_str(d),
        )
        pf_num = FieldType(
            PR_NUM,
            "number",
            "Number",
            "Nothing",
            8,
            REP_NUM,
            lambda f, d: f.report_num(d),
        )

        output = StringIO()
        opts = ReportOpts(report_file=output)

        xoutput = (
            "Name     Number\n"
            "foo             1\n"
            "bar             2\n"
            "baz             3\n"
            "qux             4\n"
        )

        pr = Report(
            _test_obj_types, [pf_name, pf_num], "name,,number", opts, None, None
        )

        for obj in _report_objs:
            pr.report_object(obj)
        pr.report_output()

        self.assertEqual(output.getvalue(), xoutput)

    def test_FieldType_simple_str_int_report_as_rows(self):
        pf_name = FieldType(
            PR_STR,
            "name",
            "Name",
            "Nothing",
            8,
            REP_STR,
            lambda f, d: f.report_str(d),
        )
        pf_num = FieldType(
            PR_NUM,
            "number",
            "Number",
            "Nothing",
            8,
            REP_NUM,
            lambda f, d: f.report_num(d),
        )

        output = StringIO()
        opts = ReportOpts(columns_as_rows=True, report_file=output)

        xoutput = (
            "Name foo      bar      baz      qux\n"
            "Number        1        2        3        4\n"
        )

        pr = Report(
            _test_obj_types, [pf_name, pf_num], "name,,number", opts, None, None
        )

        for obj in _report_objs:
            pr.report_object(obj)
        pr.report_output()

        self.assertEqual(output.getvalue(), xoutput)

    def test_FieldType_simple_str_int_report_noheadings(self):
        pf_name = FieldType(
            PR_STR,
            "name",
            "Name",
            "Nothing",
            8,
            REP_STR,
            lambda f, d: f.report_str(d),
        )
        pf_num = FieldType(
            PR_NUM,
            "number",
            "Number",
            "Nothing",
            8,
            REP_NUM,
            lambda f, d: f.report_num(d),
        )

        output = StringIO()
        opts = ReportOpts(headings=False, report_file=output)

        xoutput = (
            "foo             1\n"
            "bar             2\n"
            "baz             3\n"
            "qux             4\n"
        )

        pr = Report(
            _test_obj_types, [pf_name, pf_num], "name,,number", opts, None, None
        )

        for obj in _report_objs:
            pr.report_object(obj)
        pr.report_output()

        self.assertEqual(output.getvalue(), xoutput)

    def test_FieldType_simple_str_int_report_default_fields(self):
        pf_name = FieldType(
            PR_STR,
            "name",
            "Name",
            "Nothing",
            8,
            REP_STR,
            lambda f, d: f.report_str(d),
        )
        pf_num = FieldType(
            PR_NUM,
            "number",
            "Number",
            "Nothing",
            8,
            REP_NUM,
            lambda f, d: f.report_num(d),
        )

        output = StringIO()
        opts = ReportOpts(report_file=output)

        xoutput = (
            "Name     Number\n"
            "foo             1\n"
            "bar             2\n"
            "baz             3\n"
            "qux             4\n"
        )

        pr = Report(_test_obj_types, [pf_name, pf_num], None, opts, None, None)

        for obj in _report_objs:
            pr.report_object(obj)
        pr.report_output()

        self.assertEqual(output.getvalue(), xoutput)

    def test_FieldType_simple_str_int_report_with_sort(self):
        pf_name = FieldType(
            PR_STR,
            "name",
            "Name",
            "Nothing",
            8,
            REP_STR,
            lambda f, d: f.report_str(d),
        )
        pf_num = FieldType(
            PR_NUM,
            "number",
            "Number",
            "Nothing",
            8,
            REP_NUM,
            lambda f, d: f.report_num(d),
        )

        output = StringIO()
        opts = ReportOpts(report_file=output)

        xoutput = (
            "Name     Number\n"
            "bar             2\n"
            "baz             3\n"
            "foo             1\n"
            "qux             4\n"
        )

        pr = Report(
            _test_obj_types, [pf_name, pf_num], "name,,number", opts, "name", None
        )

        for obj in _report_objs:
            pr.report_object(obj)
        pr.report_output()

        self.assertEqual(output.getvalue(), xoutput)

    def test_FieldType_simple_str_int_report_with_sort_num(self):
        pf_name = FieldType(
            PR_STR,
            "name",
            "Name",
            "Nothing",
            8,
            REP_STR,
            lambda f, d: f.report_str(d),
        )
        pf_num = FieldType(
            PR_NUM,
            "number",
            "Number",
            "Nothing",
            8,
            REP_NUM,
            lambda f, d: f.report_num(d),
        )

        output = StringIO()
        opts = ReportOpts(report_file=output)

        xoutput = (
            "Name     Number\n"
            "foo             1\n"
            "bar             2\n"
            "baz             3\n"
            "qux             4\n"
        )

        pr = Report(
            _test_obj_types, [pf_name, pf_num], "name,,number", opts, "number", None
        )

        for obj in _report_objs:
            pr.report_object(obj)
        pr.report_output()

        self.assertEqual(output.getvalue(), xoutput)

    def test_FieldType_simple_str_int_report_with_sort_ascend(self):
        pf_name = FieldType(
            PR_STR,
            "name",
            "Name",
            "Nothing",
            8,
            REP_STR,
            lambda f, d: f.report_str(d),
        )
        pf_num = FieldType(
            PR_NUM,
            "number",
            "Number",
            "Nothing",
            8,
            REP_NUM,
            lambda f, d: f.report_num(d),
        )

        output = StringIO()
        opts = ReportOpts(report_file=output)

        xoutput = (
            "Name     Number\n"
            "bar             2\n"
            "baz             3\n"
            "foo             1\n"
            "qux             4\n"
        )

        pr = Report(
            _test_obj_types, [pf_name, pf_num], "name,,number", opts, "+name", None
        )

        for obj in _report_objs:
            pr.report_object(obj)
        pr.report_output()

        self.assertEqual(output.getvalue(), xoutput)

    def test_FieldType_simple_str_int_report_with_sort_descend(self):
        pf_name = FieldType(
            PR_STR,
            "name",
            "Name",
            "Nothing",
            8,
            REP_STR,
            lambda f, d: f.report_str(d),
        )
        pf_num = FieldType(
            PR_NUM,
            "number",
            "Number",
            "Nothing",
            8,
            REP_NUM,
            lambda f, d: f.report_num(d),
        )

        output = StringIO()
        opts = ReportOpts(report_file=output)

        xoutput = (
            "Name     Number\n"
            "qux             4\n"
            "foo             1\n"
            "baz             3\n"
            "bar             2\n"
        )

        pr = Report(
            _test_obj_types, [pf_name, pf_num], "name,,number", opts, "-name", None
        )

        for obj in _report_objs:
            pr.report_object(obj)
        pr.report_output()

        self.assertEqual(output.getvalue(), xoutput)

    def test_FieldType_simple_str_int_report_with_sort_two_fields(self):
        pf_name = FieldType(
            PR_STR,
            "name",
            "Name",
            "Nothing",
            8,
            REP_STR,
            lambda f, d: f.report_str(d),
        )
        pf_num = FieldType(
            PR_NUM,
            "number",
            "Number",
            "Nothing",
            8,
            REP_NUM,
            lambda f, d: f.report_num(d),
        )

        output = StringIO()
        opts = ReportOpts(report_file=output)

        xoutput = (
            "Name     Number\n"
            "bar             2\n"
            "baz             3\n"
            "foo             1\n"
            "qux             4\n"
        )

        pr = Report(
            _test_obj_types,
            [pf_name, pf_num],
            "name,,number",
            opts,
            "name,,number",
            None,
        )

        for obj in _report_objs:
            pr.report_object(obj)
        pr.report_output()

        self.assertEqual(output.getvalue(), xoutput)

    def test_FieldType_simple_str_int_report_with_bad_sort(self):
        pf_name = FieldType(
            PR_STR,
            "name",
            "Name",
            "Nothing",
            8,
            REP_STR,
            lambda f, d: f.report_str(d),
        )
        pf_num = FieldType(
            PR_NUM,
            "number",
            "Number",
            "Nothing",
            8,
            REP_NUM,
            lambda f, d: f.report_num(d),
        )

        output = StringIO()
        opts = ReportOpts(report_file=output)

        with self.assertRaises(ValueError) as cm:
            Report(
                _test_obj_types, [pf_name, pf_num], "name,,number", opts, "nosuch", None
            )

    def test_FieldType_all_types_report(self):
        pf_name = FieldType(
            PR_STR,
            "name",
            "Name",
            "Nothing",
            8,
            REP_STR,
            lambda f, d: f.report_str(d),
        )
        pf_num = FieldType(
            PR_NUM,
            "number",
            "Number",
            "Nothing",
            8,
            REP_NUM,
            lambda f, d: f.report_num(d),
        )
        pf_sha = FieldType(
            PR_SHA,
            "sha",
            "Sha",
            "Nothing",
            8,
            REP_SHA,
            lambda f, d: f.report_sha(d),
        )
        pf_time = FieldType(
            PR_TIME,
            "time",
            "Time",
            "Nothing",
            8,
            REP_TIME,
            lambda f, d: f.report_time(d),
        )
        pf_uuid = FieldType(
            PR_UUID,
            "uuid",
            "Uuid",
            "Nothing",
            8,
            REP_UUID,
            lambda f, d: f.report_uuid(d),
        )
        pf_size = FieldType(
            PR_SIZE,
            "size",
            "Size",
            "Nothing",
            8,
            REP_SIZE,
            lambda f, d: f.report_size(d),
        )
        pf_str_list = FieldType(
            PR_STR_LIST,
            "strlist",
            "StrList",
            "Nothing",
            8,
            REP_STR_LIST,
            lambda f, d: f.report_str_list(d),
        )

        output = StringIO()
        opts = ReportOpts(report_file=output)

        xoutput = (
            "Name     Number   Sha      Time                Uuid                                 Size     StrList\n"
            "foo             1 ffffffff 2023-09-05 14:40:53 00000000-0000-0000-0000-000000000000   1.0KiB bar, baz, foo\n"
            "bar             2 FFFFFFFF 1978-01-10 09:13:12 1d133bcc-6137-5267-b870-e469f7188dbe   1.0MiB one, three, two\n"
            "baz             3 11111111 2022-08-01 16:43:32 3576355e-e4d7-5a57-9f24-b3f4e0e326ef   1.0GiB baz, quux\n"
            "qux             4 22222222 2020-01-01 23:32:08 046e4f15-1ddd-5724-b032-878248a71d4b   1.0TiB list, string\n"
        )

        pr = Report(
            _test_obj_types,
            [pf_name, pf_num, pf_sha, pf_time, pf_uuid, pf_size, pf_str_list],
            "name,number,sha,time,uuid,size,strlist",
            opts,
            None,
            None,
        )

        for obj in _report_objs:
            pr.report_object(obj)
        pr.report_output()
        print(output.getvalue())
        self.assertEqual(output.getvalue(), xoutput)

    def test_FieldType_all_types_report_json(self):
        pf_name = FieldType(
            PR_STR,
            "name",
            "Name",
            "Nothing",
            8,
            REP_STR,
            lambda f, d: f.report_str(d),
        )
        pf_num = FieldType(
            PR_NUM,
            "number",
            "Number",
            "Nothing",
            8,
            REP_NUM,
            lambda f, d: f.report_num(d),
        )
        pf_sha = FieldType(
            PR_SHA,
            "sha",
            "Sha",
            "Nothing",
            8,
            REP_SHA,
            lambda f, d: f.report_sha(d),
        )
        pf_time = FieldType(
            PR_TIME,
            "time",
            "Time",
            "Nothing",
            8,
            REP_TIME,
            lambda f, d: f.report_time(d),
        )
        pf_uuid = FieldType(
            PR_UUID,
            "uuid",
            "Uuid",
            "Nothing",
            8,
            REP_UUID,
            lambda f, d: f.report_uuid(d),
        )
        pf_size = FieldType(
            PR_SIZE,
            "size",
            "Size",
            "Nothing",
            8,
            REP_SIZE,
            lambda f, d: f.report_size(d),
        )
        pf_str_list = FieldType(
            PR_STR_LIST,
            "strlist",
            "StrList",
            "Nothing",
            8,
            REP_STR_LIST,
            lambda f, d: f.report_str_list(d),
        )

        output = StringIO()
        opts = ReportOpts(json=True, report_file=output)

        xoutput = (
            '{\n'
            '    "Test": [\n'
            '        {\n'
            '            "str_name": "foo",\n'
            '            "num_number": 1,\n'
            '            "sha_sha": "ffffffffffffffffffffffffffffffffffffffff",\n'
            '            "time_time": "2023-09-05 14:40:53",\n'
            '            "uuid_uuid": "00000000-0000-0000-0000-000000000000",\n'
            '            "size_size": "1.0KiB",\n'
            '            "strlist_strlist": [\n'
            '                "bar",\n'
            '                "baz",\n'
            '                "foo"\n'
            '            ]\n'
            '        },\n'
            '        {\n'
            '            "str_name": "bar",\n'
            '            "num_number": 2,\n'
            '            "sha_sha": "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF",\n'
            '            "time_time": "1978-01-10 09:13:12",\n'
            '            "uuid_uuid": "1d133bcc-6137-5267-b870-e469f7188dbe",\n'
            '            "size_size": "1.0MiB",\n'
            '            "strlist_strlist": [\n'
            '                "one",\n'
            '                "three",\n'
            '                "two"\n'
            '            ]\n'
            '        },\n'
            '        {\n'
            '            "str_name": "baz",\n'
            '            "num_number": 3,\n'
            '            "sha_sha": "1111111111111111111111111111111111111111",\n'
            '            "time_time": "2022-08-01 16:43:32",\n'
            '            "uuid_uuid": "3576355e-e4d7-5a57-9f24-b3f4e0e326ef",\n'
            '            "size_size": "1.0GiB",\n'
            '            "strlist_strlist": [\n'
            '                "baz",\n'
            '                "quux"\n'
            '            ]\n'
            '        },\n'
            '        {\n'
            '            "str_name": "qux",\n'
            '            "num_number": 4,\n'
            '            "sha_sha": "2222222222222222222222222222222222222222",\n'
            '            "time_time": "2020-01-01 23:32:08",\n'
            '            "uuid_uuid": "046e4f15-1ddd-5724-b032-878248a71d4b",\n'
            '            "size_size": "1.0TiB",\n'
            '            "strlist_strlist": [\n'
            '                "list",\n'
            '                "string"\n'
            '            ]\n'
            '        }\n'
            '    ]\n'
            '}\n'
        )

        pr = Report(
            _test_obj_types,
            [pf_name, pf_num, pf_sha, pf_time, pf_uuid, pf_size, pf_str_list],
            "name,number,sha,time,uuid,size,strlist",
            opts,
            None,
            "Test",
        )

        for obj in _report_objs:
            pr.report_object(obj)
        pr.report_output()
        print(output.getvalue())
        self.assertEqual(output.getvalue(), xoutput)

    def test_FieldType_with_help(self):
        pf_name = FieldType(
            PR_STR,
            "name",
            "Name",
            "Nothing",
            8,
            REP_STR,
            lambda f, d: f.report_str(d),
        )
        pf_num = FieldType(
            PR_NUM,
            "number",
            "Number",
            "Nothing",
            8,
            REP_NUM,
            lambda f, d: f.report_num(d),
        )

        output = StringIO()
        opts = ReportOpts(report_file=output)

        xoutput = (
            "Str Fields\n"
            "----------\n"
            "  name        - Nothing [str]\n"
            " \n"
            "Num Fields\n"
            "----------\n"
            "  number      - Nothing [num]\n"
        )

        pr = Report(_test_obj_types, [pf_name, pf_num], "help", opts, None, None)

        for obj in _report_objs:
            pr.report_object(obj)
        pr.report_output()

        self.assertEqual(output.getvalue(), xoutput)

    def test_FieldType_bad_field(self):
        pf_name = FieldType(
            PR_STR,
            "name",
            "Name",
            "Nothing",
            8,
            REP_STR,
            lambda f, d: f.report_str(d),
        )
        pf_num = FieldType(
            PR_NUM,
            "number",
            "Number",
            "Nothing",
            8,
            REP_NUM,
            lambda f, d: f.report_num(d),
        )

        output = StringIO()
        opts = ReportOpts(report_file=output)

        with self.assertRaises(ValueError) as cm:
            Report(_test_obj_types, [pf_name, pf_num], "nosuchfield", opts, None, None)

    def test_ReportOpts_str(self):
        opts = ReportOpts()
        xstr = (
            "columns=80\n"
            "headings=True\n"
            "buffered=True\n"
            "separator= \n"
            "field_name_prefix=\n"
            "unquoted=True\n"
            "aligned=True\n"
            "json=False\n"
            "columns_as_rows=False\n"
        )
        log.error(xstr)
        log.error(str(opts))
        self.assertTrue(str(opts).startswith(xstr))

    def test_ReportOpts_eq_equal(self):
        opts1 = ReportOpts()
        opts2 = ReportOpts()
        self.assertEqual(opts1, opts2)

    def test_ReportOpts_eq_notequal(self):
        opts1 = ReportOpts()
        opts2 = ReportOpts(headings=False)
        self.assertNotEqual(opts1, opts2)

    def test_ReportOpts_eq_notsame(self):
        opts = ReportOpts()
        obj = object()
        self.assertNotEqual(opts, obj)

    def test_ReportObjType_no_objtype(self):
        with self.assertRaises(ValueError) as cm:
            ReportObjType(None, "description", "prefix_", lambda x: x)

    def test_ReportObjType_bad_objtype(self):
        with self.assertRaises(ValueError) as cm:
            ReportObjType(-2, "description", "prefix_", lambda x: x)

    def test_ReportObjType_no_desc(self):
        with self.assertRaises(ValueError) as cm:
            ReportObjType(2, None, "prefix_", lambda x: x)

    def test_ReportObjType_no_data_fn(self):
        with self.assertRaises(ValueError) as cm:
            ReportObjType(2, "description", "prefix_", None)


# vim: set et ts=4 sw=4 :

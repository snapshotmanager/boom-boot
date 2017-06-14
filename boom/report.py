# Copyright (C) 2017 Red Hat, Inc., Bryn M. Reeves <bmr@redhat.com>
#
# boom/report.py - Text reporting
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

_default_columns = 80

class BoomReportOpts(object):
    """BoomReportOpts()
        Options controlling the formatting and output of a boom report.
    """
    columns = _default_columns
    headings = True
    buffer = True

#
# def data_fn(data):
#    :returntype: dtype
#

REP_INT = "int"
REP_STR = "str"
REP_SHA = "sha"

_dtypes = [REP_INT, REP_STR, REP_SHA]

def _default_sort_fn(v1, v2):
    return v1 > v2

_default_width = 8

ALIGN_LEFT = "left"
ALIGN_RIGHT = "right"

_align_types = [ALIGN_LEFT, ALIGN_RIGHT]

class BoomField(object):
    name = None
    head = None
    width = _default_width
    align = None
    dtype = None
    data_fn = None
    sort_fn = None

    def __init__(self, name, head, width, dtype, data_fn,
                 align=None, sort_fn=None):
        if not name:
            raise ValueError("'name' is required")
        self.name = name
        self.head = head

        if dtype not in _dtypes:
            raise ValueError("Invalid field dtype: %s " % dtype)

        if align and align not in _align_types:
            raise ValueError("Invalid field alignment: %s" % align)

        self.dtype = dtype
        self.data_fn = data_fn

        if not align:
            if dtype == REP_STR or dtype ==REP_SHA:
                self.align = ALIGN_LEFT
            if dtype == REP_INT:
                self.align = ALIGN_RIGHT
        else:
            self.align = align

        if width < 0:
            raise ValueError("Field width cannot be < 0")
        self.width = width if width else _default_width

        self.sort_fn = sort_fn


class BoomReport(object):
    """BoomReport()
        A class representing a configurable text report with multiple
        caller-defined fields. An optional title may be provided and he
        ``fields`` argument must contain a list of ``BoomField`` objects
        describing the required report.

    """
    columns = None
    headings = None
    buffer = None

    report_file = None

    _fields = None
    _data = None

    def __init__(self, rfile, title, fields, opts):
        """__init__(self, rfile, title, fields, opts) -> ``BoomReport``
            Initialise a new ``BoomReport`` object with the specified fields
            and output control options.

            :param rfile: The ``file`` to which to write the report.
            :param title: A title string or None if no title is required.
            :param fields: A list of ``BoomField`` field descriptions.
            :param opts: An instance of ``BoomReportOpts`` or None.
            :returns: A new report object.
            :returntype: ``BoomReport``.
        """

        self.columns = 80 if not opts else opts.columns
        self.headings = True if not opts else opts.headings
        self.buffer = True if not opts else opts.buffer
        self.report_file = rfile
        self._fields = fields
        self._data = []

    def _output_row(self, data):
        row = ""
        int_width_fmt = "%d"
        str_width_fmt = "-%d.%d"
        for f in self._fields:
            fdata = f.data_fn(data)
            fmt = None
            if f.dtype == REP_INT:
                fmt = int_width_fmt % f.width + "d"
            elif f.dtype == REP_STR:
                fmt = str_width_fmt % (f.width, f.width) + "s"
            elif f.dtype == REP_SHA:
                fmt = str_width_fmt % (f.width, f.width) + "s"
                if len(fdata) > f.width:
                    fdata = fdata[:f.width]
            if not fmt:
                raise ValueError("Invalid field dtype in report.")
            fstr = ("%" + fmt) % fdata
            row += fstr + " "
        self.report_file.write(row + "\n")

    def output_heading(self):
        row = ""
        for f in self._fields:
            fmt = "%%-%ds" % f.width
            fstr = fmt % f.head
            row += fstr + " "
        self.report_file.write(row + "\n")

    def add_row_data(self, data):
        """add_row_data(self, data) -> None
            Add a row of data to this ``BoomReport``. The ``data``
            argument should be an object of the type understood by this
            report's fields. It will be passed in turn to each field to
            obtain data for the current row.

            :param data: the object to report on for this row.
        """
        if self.buffer:
            self._data.append(data)
        else:
            self._output_row(data)

    def add_field(self, field):
        self._fields.append(field)

    def sort(self, field, reverse=False):
        pass

    def output(self):
        """output(self) -> int
            Output this report's data to the configured report file,
            using the configured output controls and fields.

            On success the number of rows output is returned. On
            error an exception is raised.

            :returns: the number of rows of output written.
            :returntype: ``int``
        """
        self.output_heading()
        for data in self._data:
            self._output_row(data)
        return len(self._data)



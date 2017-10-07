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
import sys

_default_columns = 80

#
# def data_fn(data):
#    :returntype: dtype
#

REP_NUM = "num"
REP_STR = "str"
REP_SHA = "sha"

_dtypes = [REP_NUM, REP_STR, REP_SHA]


def _default_sort_fn(v1, v2):
    return v1 > v2

_default_width = 8

ALIGN_LEFT = "left"
ALIGN_RIGHT = "right"

_align_types = [ALIGN_LEFT, ALIGN_RIGHT]

STANDARD_QUOTE = "'"
STANDARD_PAIR = "="


class BoomReportOpts(object):
    """BoomReportOpts()
        Options controlling the formatting and output of a boom report.
    """
    columns = 0
    headings = True
    buffered = True
    separator = None
    field_name_prefix = None
    unquoted = False
    aligned = True
    columns_as_rows = False
    report_file = None

    def __init__(self, columns=_default_columns, headings=True, buffered=True,
                 separator=" ", field_name_prefix="", unquoted=True,
                 aligned=True, report_file=sys.stdout):
        """__init__(self, columns, headings, buffered, report_file)
           -> BoomReportOpts

            Initialise a ``BoomReportOpts`` object to control output
            of a ``BoomReport``.

            :param columns: the number of columns to use for output.
            :param headings: a boolean indicating whether to output
                             column headings for this report.
            :param buffered: a boolean indicating whether to buffer
                             output from this report.
            :param report_file: a file to which output will be sent.
            :returns: a new ``BoomReportOpts`` object.
            :returntype: ``<class BoomReportOpts>``
        """
        self.columns = columns
        self.headings = headings
        self.buffered = buffered
        self.separator = separator
        self.field_name_prefix = field_name_prefix
        self.unquoted = unquoted
        self.aligned = aligned
        self.report_file = report_file


class BoomReportObjType(object):
    """BoomReportObjType()
        Class representing a type of objecct to be reported on.
        Instances of ``BoomReportObjType`` must specify an identifier,
        a description, and a data function that will return the correct
        type of object from a compound object containing data objects
        of different types. For reports that use only a single object
        type the ``data_fn`` member may be simply ``lambda x: x``.
    """

    objtype = -1
    desc = ""
    prefix = ""
    data_fn = None

    def __init__(self, objtype, desc, prefix, data_fn):
        """__init__(self, objtype, desc, prefix, data_fn)
            Initialise a new ``BoomReportObjType`` object with the
            specified ``objtype``, ``desc``, optional ``prefix`` and
            ``data_fn``. The ``objtype`` must be an integer power of two
            that is unique within a given report. The ``data_fn`` should
            accept an object as its only argument and return an object
            of the requested type.
        """
        if not objtype or objtype < 0:
            raise ValueError("BoomReportObjType objtype cannot be <= 0.")

        if not desc:
            raise ValueError("BoomReportObjType desc cannot be empty.")

        if not data_fn:
            raise ValueError("BoomReportObjType requires data_fn.")

        self.objtype = objtype
        self.desc = desc
        self.prefix = prefix
        self.data_fn = data_fn


class BoomFieldType(object):
    """BoomFieldType()
        The ``BoomFieldType`` class describes the properties of a field
        available in a ``BoomReport`` instance.
    """
    objtype = -1
    name = None
    head = None
    desc = None
    width = _default_width
    align = None
    dtype = None
    report_fn = None
    sort_fn = None

    def __init__(self, objtype, name, head, desc, width, dtype, report_fn,
                 align=None, sort_fn=None):
        if not objtype:
            raise ValueError("'objtype' must be non-zero")
        if not name:
            raise ValueError("'name' is required")
        self.objtype = objtype
        self.name = name
        self.head = head
        self.desc = desc

        if dtype not in _dtypes:
            raise ValueError("Invalid field dtype: %s " % dtype)

        if align and align not in _align_types:
            raise ValueError("Invalid field alignment: %s" % align)

        self.dtype = dtype
        self.report_fn = report_fn

        if not align:
            if dtype == REP_STR or dtype == REP_SHA:
                self.align = ALIGN_LEFT
            if dtype == REP_NUM:
                self.align = ALIGN_RIGHT
        else:
            self.align = align

        if width < 0:
            raise ValueError("Field width cannot be < 0")
        self.width = width if width else _default_width

        self.sort_fn = sort_fn


class BoomFieldProperties(object):
    field_num = None
    # sort_posn
    initial_width = 0
    width = 0
    objtype = None
    align = None
    #
    # Field flags
    #
    hidden = False
    implicit = False
    # sort_key = False
    # ascending = False
    # descending = False
    # compact_one = False # used for implicit fields
    compacted = False


class BoomField(object):
    """BoomField()
        A ``BoomField`` represents an instance of a ``BoomFieldType``
        including its associated data values.
    """
    #: reference to the containing BoomReport
    _report = None
    #: reference to the BoomFieldProperties describing this field
    _props = None
    #: The formatted string to be reported for this field.
    report_string = None
    #: The raw value of this field. Used for sorting.
    sort_value = None

    def __init__(self, report, props):
        self._report = report
        self._props = props

    def report_str(self, value):
        self.set_value(value, value)

    def report_sha(self, value):
        sha = value[:7]
        self.set_value(sha, value)

    def report_num(self, value):
        self.set_value(str(value), value)

    def set_value(self, report_string, sort_value=None):
        if report_string is None:
            raise ValueError("No value assigned to field.")
        self.report_string = report_string
        self.sort_value = sort_value if sort_value else report_string


class BoomRow(object):
    """BoomRow()
        A class representing a single data row making up a report.
    """
    #: the report that this BoomRow belongs to
    _report = None
    #: the list of report fields in display order
    _fields = None

    def __init__(self, report):
        self._report = report
        self._fields = []

    def add_field(self, field):
        self._fields.append(field)


class BoomReport(object):
    """BoomReport()
        A class representing a configurable text report with multiple
        caller-defined fields. An optional title may be provided and he
        ``fields`` argument must contain a list of ``BoomField`` objects
        describing the required report.

    """
    report_types = 0

    _fields = None
    _types = None
    _data = None
    _rows = None
    _field_properties = None
    _header_written = False
    _field_calc_needed = True
    _sort_required = False

    private = None
    opts = None

    def __get_longest_field_name_len(self, fields):
        max_len = 0
        for f in fields:
            cur_len = len(f.name)
            max_len = cur_len if cur_len > max_len else max_len
        for t in self._types:
            cur_len = len(t.prefix) + 3
            max_len = cur_len if cur_len > max_len else max_len
        return max_len

    def __do_display_fields(self, fields, display_field_types):
        name_len = self.__get_longest_field_name_len(fields)
        last_desc = ""
        banner = "-" * 79
        for f in fields:
            t = self.__find_type(f.objtype)
            if t:
                desc = t.desc
            else:
                desc = ""
            if desc != last_desc:
                if len(last_desc):
                    print(" ")
                desc_len = len(desc) + 7
                print("%s Fields" % desc)
                print("%*.*s" % (desc_len, desc_len, banner))
            print("  %-*s - %s%s%s%s" %
                  (name_len, f.name, f.desc,
                   " [" if display_field_types else "",
                   f.dtype if display_field_types else "",
                   "]" if display_field_types else ""))
            last_desc = desc

    def __display_fields(self, display_field_types):
        """__display_fields(self) -> None

            Output a list of fields for this ``BoomReport`` object.
        """
        self.__do_display_fields(self._fields, display_field_types)

    def __find_type(self, report_type):
        # FIXME implicit field handling

        for t in self._types:
            if t.objtype == report_type:
                return t

        raise ValueError("Unknown report object type: %d" % report_type)

    def __copy_field(self, field_num, implicit=False):
        fp = BoomFieldProperties()
        fp.field_num = field_num
        fp.width = fp.initial_width = self._fields[field_num].width
        fp.implicit = implicit
        fp.objtype = self.__find_type(self._fields[field_num].objtype)
        fp.align = self._fields[field_num].align
        return fp

    def __add_field(self, field_num):
        fp = self.__copy_field(field_num)
        if fp.hidden:
            self._field_properties.insert(0, fp)
        else:
            self._field_properties.append(fp)

    def __get_field(self, field_name):
        """__get_field(field_name)
        """
        # FIXME implicit fields
        for field in self._fields:
            if field.name == field_name:
                return self._fields.index(field)
        raise ValueError("No matching field name: %s" % field_name)

    def __field_match(self, field_name, type_only):
        try:
            f = self.__get_field(field_name)
            if (type_only):
                self.report_types |= self._fields[f].objtype
                return
            return self.__add_field(f)
        except ValueError as e:
            # FIXME handle '$PREFIX_all'
            # re-raise 'e' if it fails.
            raise e

    def __parse_fields(self, field_format, type_only):
        for word in field_format.split(','):
            # Allow consecutive commas
            if not word:
                continue
            try:
                self.__field_match(word, type_only)
            except ValueError as e:
                self.__display_fields(True)
                print("Unrecognised field: %s" % word)
                raise e

    def __parse_keys(self, keys, type_only):
        pass

    def __init__(self, types, fields, output_fields, opts,
                 sort_keys, private):
        """__init__(self, types, fields, output_fields, opts,
           sort_keys, private)
           -> ``BoomReport``

            Initialise a new ``BoomReport`` object with the specified fields
            and output control options.

            :param types: List of BoomReportObjType used in this report.
            :param fields: A list of ``BoomField`` field descriptions.
            :param output_fields: An optional list of output fields to
                                  be rendered by this report.
            :param opts: An instance of ``BoomReportOpts`` or None.
            :returns: A new report object.
            :returntype: ``BoomReport``.
        """

        self._fields = fields
        self._types = types
        self._private = private

        # handle opts
        #  columns
        #    sort_required, aligned
        self.opts = opts if opts else BoomReportOpts()

        self._rows = []
        self._field_properties = []

        # set field_prefix from type

        # canonicalize_field_ids()

        if not output_fields:
            output_fields = ",".join([field.name for field in fields])

        # First pass: set up types
        self.__parse_fields(output_fields, 1)
        self.__parse_keys(sort_keys, 1)

        # Second pass: initialise fields
        self.__parse_fields(output_fields, 0)
        self.__parse_keys(sort_keys, 0)

    def __recalculate_fields(self):
        for row in self._rows:
            for field in row._fields:
                field_len = len(field.report_string)
                if field_len > field._props.width:
                    field._props.width = field_len

    def __report_headings(self):
        self._header_written = True
        if not self.opts.headings:
            return

        line = ""
        props = self._field_properties
        for fp in props:
            if fp.hidden:
                continue
            fields = self._fields
            heading = fields[fp.field_num].head
            headertuple = (fp.width, fp.width, heading)
            if self.opts.aligned:
                heading = "%-*.*s" % headertuple
            line += heading
            if props.index(fp) != (len(props) - 1):
                line += self.opts.separator
        self.opts.report_file.write(line + "\n")

    def report_object(self, obj):
        """report_object(self, data) -> None
            Add a row of data to this ``BoomReport``. The ``data``
            argument should be an object of the type understood by this
            report's fields. It will be passed in turn to each field to
            obtain data for the current row.

            :param data: the object to report on for this row.
        """
        if obj is None:
            raise ValueError("Cannot report NoneType object.")

        row = BoomRow(self)
        fields = self._fields

        for fp in self._field_properties:
            field = BoomField(self, fp)
            data = fp.objtype.data_fn(obj)

            if data is None:
                raise ValueError("No data assigned to field %s" %
                                 fields[fp.field_num].name)

            try:
                fields[fp.field_num].report_fn(field, data)
            except ValueError:
                raise ValueError("No value assigned to field %s" %
                                 fields[fp.field_num].name)
            row.add_field(field)
        self._rows.append(row)

        if not self.opts.buffered:
            return self.report_output()

    def set_output_fields(self, output_fields):
        """set_output_fields(self, output_fields) -> int
            Set the list of output fields that will be rendered by this
            report. The ``output_fields`` argument should contain a
            string listing the fields to be included in order.
            For example, to select the fields 'name', 'version', and
            'id', the ``output_fields`` string should be:

                ``"name,version,id"``

            :param output_fields: the list of output fields, in order.
            :returns: the number of output fields configured.
            :returntype: int
        """
        pass

    def sort(self, field, reverse=False):
        pass

    def _output_field(self, field):
        fields = self._fields
        prefix = self.opts.field_name_prefix
        quote = "" if self.opts.unquoted else STANDARD_QUOTE

        if prefix:
            field_name = fields[field._props.field_num].name
            prefix += "%s%s%s" % (field_name.upper(), STANDARD_PAIR,
                                  STANDARD_QUOTE)

        repstr = field.report_string
        width = field._props.width
        if self.opts.aligned:
            align = field._props.align
            if not align:
                if field._props.dtype == REP_NUM:
                    align = ALIGN_RIGHT
                else:
                    align = ALIGN_LEFT
            reptuple = (width, width, repstr)
            if align == ALIGN_LEFT:
                repstr = "%-*.*s" % reptuple
            else:
                repstr = "%*.*s" % reptuple

        suffix = quote
        return prefix + repstr + suffix

    def _output_as_rows(self):
        pass

    def _output_as_columns(self):
        if not self._header_written:
            self.__report_headings()
        for row in self._rows:
            do_field_delim = False
            line = ""
            for field in row._fields:
                if field._props.hidden:
                    continue
                if do_field_delim:
                    line += self.opts.separator
                else:
                    do_field_delim = True
                line += self._output_field(field)
            self.opts.report_file.write(line + "\n")

    def report_output(self):
        """output(self) -> int
            Output this report's data to the configured report file,
            using the configured output controls and fields.

            On success the number of rows output is returned. On
            error an exception is raised.

            :returns: the number of rows of output written.
            :returntype: ``int``
        """
        if not self._rows:
            return
        if self._field_calc_needed:
            self.__recalculate_fields()
        if self._sort_required:
            self._sort_rows()
        if self.opts.columns_as_rows:
            return self._output_as_rows()
        else:
            return self._output_as_columns()

__all__ = [
    # Module constants

    'REP_NUM', 'REP_STR', 'REP_SHA',
    'ALIGN_LEFT', 'ALIGN_RIGHT',

    # Report objects
    'BoomReportOpts', 'BoomReportObjType', 'BoomField', 'BoomFieldType',
    'BoomFieldProperties', 'BoomReport'
]

# vim: set et ts=4 sw=4 :

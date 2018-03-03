"""Implementation specific tools.

This module exports a uniform interface for functionality that isn't a part of
the Python Language Specification, but does have implementation-specific APIs,
which may differ across Python implementations and versions of those
implementations.
"""
import sys

__all__ = [
    'get_format_arg_name_from_field_name',
    'next_traceback',
    'iter_traceback',
    'get_simplified_traceback',
    'get_func_pathname_and_line',
]


# Modified from: http://lucumr.pocoo.org/2016/12/29/careful-with-str-format/
# I kept the Python3 case to make it easier to port later.
# This is a necessary API but it's undocumented and moved around
# between Python releases
try:
    # Python3
    from _string import formatter_field_name_split
except ImportError:
    # Python2
    def formatter_field_name_split(field_name):
        return field_name._formatter_field_name_split()


def consume(it):
    """Consume an iterator and discard the results."""
    for _ in it:
        pass


def get_format_arg_name_from_field_name(field_name):
    arg_name, rest = formatter_field_name_split(field_name)
    # Parse all of the field-name parts for format validation
    consume(rest)
    return arg_name


def next_traceback(tb):
    return tb.tb_next


def iter_traceback(tb):
    while tb:
        yield tb
        tb = tb.tb_next


def get_simplified_traceback(tb):
    return [
        (
            tb.tb_frame.f_code.co_filename,
            tb.tb_lineno,
            tb.tb_frame.f_code.co_name,
        )
        for tb
        in iter_traceback(tb)
    ]


def get_func_pathname_and_line(func):
    code = func.func_code
    return code.co_filename, code.co_firstlineno

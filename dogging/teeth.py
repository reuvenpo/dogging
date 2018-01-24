"""Parsing related functions.

This module contains all tools and functions related to parsing strings.
"""
from string import Formatter
from .chew_toys import is_int_like
from .bone import get_format_arg_name_from_field_name

__all__ = [
    'get_format_arg_names',
    'check_format_arg_names_no_positional',
]

_formatter = Formatter()


def validate_format_conv_method_and_get_field_name(replacement_field):
    # In these tuples:
    # The 2nd field is the field-name.
    # The 4th field is the conversion-method.
    _formatter.convert_field(0, replacement_field[3])
    return replacement_field[1]


def get_format_arg_names(format_string):
    return [
        get_format_arg_name_from_field_name(field_name)
        for field_name
        in (
            validate_format_conv_method_and_get_field_name(replacement_field)
            for replacement_field
            in _formatter.parse(format_string)
        )
        # None indicates that there is no replacement at all
        if field_name is not None
    ]


def some_format_arg_names_are_positional(arg_names):
    return any(
        arg_name == '' or is_int_like(arg_name)
        for arg_name
        in arg_names
    )


def check_format_arg_names_no_positional(arg_names):
    if some_format_arg_names_are_positional(arg_names):
        raise ValueError(
            'Unnamed or positional arg-names in format specification'
        )

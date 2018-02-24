from sys import exc_info
from time import time
from inspect import getcallargs
from inspect import getargspec
from functools import wraps
from functools import partial
from itertools import imap as map
from itertools import chain
from collections import Iterable
import logging
# Import the logging levels for user convenience
from logging import DEBUG, INFO, WARN, WARNING, ERROR, FATAL, CRITICAL

from .chew_toys import *
from .teeth import *
from .bone import *

__all__ = [
    'dog', 'ComputedArgNames', 'ExtraAttributes',
    'DEBUG', 'INFO', 'WARN', 'WARNING', 'ERROR', 'FATAL', 'CRITICAL',
]

# Be explicit about exporting these from the module
DEBUG = DEBUG
INFO = INFO
WARN = WARN
WARNING = WARNING
ERROR = ERROR
FATAL = FATAL
CRITICAL = CRITICAL

_COMPUTED_ARG_PREFIX = '>'  # Common prefix for computed format arg-names
_SPECIAL_ARG_PREFIX = '@'  # Common prefix for special format arg-names
# Names of the special format arg-names
_ARG_PATHNAME = _SPECIAL_ARG_PREFIX + 'pathname'
_ARG_LINE = _SPECIAL_ARG_PREFIX + 'line'
_ARG_LOGGER = _SPECIAL_ARG_PREFIX + 'logger'
_ARG_FUNC = _SPECIAL_ARG_PREFIX + 'func'
_ARG_TIME = _SPECIAL_ARG_PREFIX + 'time'
_ARG_RET = _SPECIAL_ARG_PREFIX + 'ret'
_ARG_ERR = _SPECIAL_ARG_PREFIX + 'err'
_ARG_TRACEBACK = _SPECIAL_ARG_PREFIX + 'traceback'

_ENTER_ARGS = {
    _ARG_PATHNAME,
    _ARG_LINE,
    _ARG_LOGGER,
    _ARG_FUNC,
}
_EXIT_ARGS = {
    _ARG_PATHNAME,
    _ARG_LINE,
    _ARG_LOGGER,
    _ARG_FUNC,
    _ARG_TIME,
    _ARG_RET,
}
_ERROR_ARGS = {
    _ARG_PATHNAME,
    _ARG_LINE,
    _ARG_LOGGER,
    _ARG_FUNC,
    _ARG_TIME,
    _ARG_RET,  # In this case it's the default return value
    _ARG_ERR,
    _ARG_TRACEBACK,
}
_ALL_ARGS = {
    _ARG_PATHNAME,
    _ARG_LINE,
    _ARG_LOGGER,
    _ARG_FUNC,
    _ARG_TIME,
    _ARG_RET,
    _ARG_ERR,
    _ARG_TRACEBACK,
}


def resolve_specification_string(spec):
    return INFO, spec, (), ()


def resolve_specification_sequence(spec):
    level = INFO
    format_string = None
    extras = []
    computers = []

    for part in spec:
        if isinstance(part, int):
            level = part
        elif isinstance(part, basestring):
            format_string = part
        elif issubclass(part, ExtraAttributes):
            extras.append(part)
        elif issubclass(part, ComputedArgNames):
            computers.append(part)
        else:
            raise TypeError(
                'unsupported type for sequence specification: {}'.format(
                    part.__name__ if type(part) is type else type(part).__name__
                )
            )

    if format_string is None:
        raise ValueError('must specify a format string in a sequence specification')

    return level, format_string, extras, computers


def resolve_specification_none(_):
    return None, None, (), ()


SPEC_RESOLVERS = {
    str: resolve_specification_string,
    unicode: resolve_specification_string,
    tuple: resolve_specification_sequence,
    list: resolve_specification_sequence,
    type(None): resolve_specification_none,
}


def resolve_specification(spec):
    try:
        resolver = SPEC_RESOLVERS[type(spec)]
    except KeyError:
        raise TypeError('Unsupported specification: {!r}'.format(spec))
    return resolver(spec)


def separate_arg_names_by_prefix(arg_names, prefix):
    return filter2(
        (lambda arg_name: arg_name.startswith(prefix)),
        arg_names
    )


def separate_special_arg_names(arg_names):
    """Split the arg_names into two lists, one of the special, and one of the regular arg-names."""
    return separate_arg_names_by_prefix(arg_names, _SPECIAL_ARG_PREFIX)


def separate_computed_arg_names(arg_names):
    """Split the arg_names into two lists, one of the computed, and one of the regular arg-names."""
    return separate_arg_names_by_prefix(arg_names, _COMPUTED_ARG_PREFIX)


def check_special_arg_names_support(phase, arg_names, supported):
    if arg_names and not arg_names <= supported:
        raise ValueError(
            'unsupported special arg-names for {!r} logging phase: {}'
            .format(
                phase,
                ', '.join(
                    arg_name
                    for arg_name
                    in arg_names - supported
                )
            )
        )


class Message(object):
    __slots__ = ('message', 'builder')

    def __init__(self, message, builder):
        self.message = message
        self.builder = builder

    def __str__(self):
        return self.message.format(**self.builder())


class DynamicAttributesBase(object):
    """Base class for classes describing dynamic attributes.

    You can subclass this class to describe dynamic attributes used in
     different contexts of the library, by creating methods whose names
     don't begin with '_'.
    In your methods, you can access the ``self._args`` property, returning
     the dictionary of arg-names used to format the message for the specific
     LogRecord. This means access to the function's parameters, as well as any
     relevant special-arg-names. (If you want to use a special-arg-names you
     should first make sure it's in the dictionary. Keep reading)
    By default, only the arg-names used by the logging message of a phase will
     be available to the methods of your subclass. In order to use arg-names
     that weren't referenced by the message, you must specify them in
     a class-attribute ``__args__``, which should be any iterable of strings.
     The same checks that apply to arg-names in the logging message apply
     to these strings. (!) For consistency and robustness, specify any
     arg-names you intend to use in the __args__ attribute of your class (!).

    This class is not intended to be subclassed directly (and will not be
     recognised by the system). Instead, subclass one of this classes
     subclasses exported by the library.
    """
    __slots__ = ['__cache', '__builder']
    __args__ = ()

    def __init__(self, builder):
        self.__builder = builder
        self.__cache = None

    def __iter__(self):
        return (attr for attr in dir(self) if not attr.startswith('_'))

    def __getitem__(self, item):
        return getattr(self, item)()

    @property
    def _args(self):
        if self.__cache is None:
            self.__cache = self.__builder()
        return self.__cache


class ExtraAttributes(DynamicAttributesBase):
    """Base class for classes describing dynamic extra LogRecord attributes.

    Your subclass can be passed as an argument to a dog's extras parameter, or
     as an element of a sequence of a logging-phase specification.
    When LogRecords will be generated by the logging module for messages made
     by the dog, their dictionaries will be updated with attributes whose names
     match the names of your methods, and whose values equal the return values
     from your methods.
    All your methods will be called every time a LogRecord is generated.
    """
    pass


class ComputedArgNames(DynamicAttributesBase):
    """Base class for classes describing dynamic computed format arg-names.

    Your subclass can be passed as an element of a sequence of a
     logging-phase specification.
    When building the values of arg-names for a log message's format string,
     additional arg names will be available to the format string. These
     arg-names will be the names of your defined methods, prefixed with '>'.
    Your methods will be called for every logging message whose format string
     has requested them. That is, per message, only the necessary methods
     will be called.
    """
    pass


def join_dynamic_attributes(dynamic_attributes):
    # ``dynamic_attributes`` is a sequence of ``DynamicAttributesBase``
    #  subclasses.
    # The methods of those classes are used to generate dynamic attributes
    #  used by the library and logging system.
    # We allow specifying multiple such classes, but if any of
    #  their methods conflict, the methods of classes later in
    #  the sequence should override those earlier in the sequence.
    # The most concise and (probably) efficient way of implementing
    #  this, is by using the sequence of classes as the bases of
    #  another class, in reverse order.
    # This also handles any multiple inheritance the user may have
    #  specified really gracefully.
    # If you understood what i was doing here without
    #  reading this comment or reading the docs, congrats,
    #  you are a Master of the Dark Arts.
    return type('JoinedDynamicAttributes', tuple(reversed(dynamic_attributes)), {})


def iter_dynamic_attribute_requested_arg_names(dynamic_attributes):
    """Iterate all arg names requested by a DynamicAttributesBase subclass."""
    return chain.from_iterable(
        cls.__args__
        for cls
        in dynamic_attributes.mro()
        if hasattr(cls, '__args__')
    )


class dog(object):
    __slots__ = (
        '_enter_level', '_enter_format', '_enter_extras',
        '_enter_computer', '_enter_computed_arg_names',
        '_enter_special_arg_names', '_enter_regular_arg_names',
        '_exit_level', '_exit_format', '_exit_extras',
        '_exit_computer', '_exit_computed_arg_names',
        '_exit_special_arg_names', '_exit_regular_arg_names',
        '_error_level', '_error_format', '_error_extras',
        '_error_computer', '_error_computed_arg_names',
        '_error_special_arg_names', '_error_regular_arg_names',
        'logger', '_catch', '_propagate', '_exc_info',
        '_default_ret', '_default_ret_arg',
    )

    def __init__(
        self,
        enter=None, exit=None, error=None,
        extras=(),
        logger=None,
        catch=Exception, propagate_exception=True,
        exc_info=False, default_ret=None
    ):
        # Set empty values as default
        self._enter_level = None
        self._exit_level = None
        self._error_level = None

        self._enter_format = None
        self._exit_format = None
        self._error_format = None

        self._enter_extras = None
        self._exit_extras = None
        self._error_extras = None

        self._enter_computer = None
        self._exit_computer = None
        self._error_computer = None

        self._enter_computed_arg_names = None
        self._exit_computed_arg_names = None
        self._error_computed_arg_names = None

        self._enter_special_arg_names = None
        self._exit_special_arg_names = None
        self._error_special_arg_names = None

        self._enter_regular_arg_names = None
        self._exit_regular_arg_names = None
        self._error_regular_arg_names = None

        # Simple attributes
        self.logger = logger
        self._catch = catch
        self._propagate = propagate_exception
        self._exc_info = exc_info
        self._default_ret = default_ret

        if propagate_exception:
            self._default_ret_arg = {}
        else:
            self._default_ret_arg = {_ARG_RET: self._default_ret}

        if extras:
            self._set_extras_for_all_phases(extras)
        self._resolve_specifications(enter, exit, error)
        self._parse_format_strings()
        self._validate_special_arg_names()
        self._validate_computed_arg_names()

    def _set_extras_for_all_phases(self, extras):
        if not isinstance(extras, Iterable):
            raise TypeError('extras argument must be an iterable')
        extras = join_dynamic_attributes(tuple(extras))
        self._enter_extras = extras
        self._exit_extras = extras
        self._error_extras = extras

    def _add_extras(self, enter, exit, error):
        def join_extras(cls, more_classes):
            return join_dynamic_attributes(tuple(chain((cls,), more_classes)))

        if enter:
            if self._enter_extras:
                self._enter_extras = join_extras(self._enter_extras, enter)
            else:
                self._enter_extras = join_dynamic_attributes(tuple(enter))
        if exit:
            if self._exit_extras:
                self._exit_extras = join_extras(self._exit_extras, exit)
            else:
                self._exit_extras = join_dynamic_attributes(tuple(exit))
        if error:
            if self._error_extras:
                self._error_extras = join_extras(self._error_extras, error)
            else:
                self._error_extras = join_dynamic_attributes(tuple(error))

    def _resolve_specifications(self, enter, exit, error):
        self._enter_level, self._enter_format, enter_extra, enter_computers = resolve_specification(enter)
        self._exit_level, self._exit_format, exit_extra, exit_computers = resolve_specification(exit)
        self._error_level, self._error_format, error_extra, error_computers = resolve_specification(error)

        self._add_extras(enter_extra, exit_extra, error_extra)

        self._enter_computer = join_dynamic_attributes(enter_computers) if enter_computers else None
        self._exit_computer = join_dynamic_attributes(exit_computers) if exit_computers else None
        self._error_computer = join_dynamic_attributes(error_computers) if error_computers else None

    def _get_phases_arg_names(self):
        def _get_format_arg_names(fmt):
            return (
                get_format_arg_names(fmt)
                if fmt is not None
                else ()
            )

        # Extract the arg names from the replacement fields in the format string
        enter_arg_names = _get_format_arg_names(self._enter_format)
        exit_arg_names = _get_format_arg_names(self._exit_format)
        error_arg_names = _get_format_arg_names(self._error_format)
        # Check the format strings are valid
        for arg_names in (enter_arg_names, exit_arg_names, error_arg_names):
            if arg_names:
                check_format_arg_names_no_positional(arg_names)

        def chain_arg_names_with_dynamic_attributes_arg_names(arg_names, dynamic_attributes):
            return chain(
                arg_names,
                iter_dynamic_attribute_requested_arg_names(dynamic_attributes),
            )

        # Add references from extra parameters to arg_name lists
        if self._enter_extras:
            enter_arg_names = chain_arg_names_with_dynamic_attributes_arg_names(enter_arg_names, self._enter_extras)
        if self._exit_extras:
            exit_arg_names = chain_arg_names_with_dynamic_attributes_arg_names(exit_arg_names, self._exit_extras)
        if self._error_extras:
            error_arg_names = chain_arg_names_with_dynamic_attributes_arg_names(error_arg_names, self._error_extras)

        # Add references from computed arg names to arg_names lists
        if self._enter_computer:
            enter_arg_names = chain_arg_names_with_dynamic_attributes_arg_names(enter_arg_names, self._enter_computer)
        if self._exit_computer:
            exit_arg_names = chain_arg_names_with_dynamic_attributes_arg_names(exit_arg_names, self._exit_computer)
        if self._error_computer:
            error_arg_names = chain_arg_names_with_dynamic_attributes_arg_names(error_arg_names, self._error_computer)

        return enter_arg_names, exit_arg_names, error_arg_names

    def _separate_phase_arg_names_to_categories(
        self,
        enter_arg_names, exit_arg_names, error_arg_names
    ):
        # For each logging phase, find which special arg names we would need.
        # Also collect the regular references to check them when wrapping a function.
        three_frozen_sets = (frozenset(),) * 3

        def separate_arg_names(fmt, arg_names):
            if fmt is None:
                return three_frozen_sets
            computed, arg_names = (
                map(frozenset, separate_computed_arg_names(arg_names))
            )
            special, regular = (
                map(frozenset, separate_special_arg_names(arg_names))
            )
            return computed, special, regular

        self._enter_computed_arg_names, self._enter_special_arg_names, self._enter_regular_arg_names = (
            separate_arg_names(self._enter_format, enter_arg_names)
        )

        self._exit_computed_arg_names, self._exit_special_arg_names, self._exit_regular_arg_names = (
            separate_arg_names(self._exit_format, exit_arg_names)
        )

        self._error_computed_arg_names, self._error_special_arg_names, self._error_regular_arg_names = (
            separate_arg_names(self._error_format, error_arg_names)
        )

    def _parse_format_strings(self):
        per_phase_arg_names = self._get_phases_arg_names()
        self._separate_phase_arg_names_to_categories(*per_phase_arg_names)

    def _validate_special_arg_names(self):
        # Check that each phases special-arg-names are suitable for the specific phase.
        check_special_arg_names_support('enter', self._enter_special_arg_names, _ENTER_ARGS)
        check_special_arg_names_support('exit', self._exit_special_arg_names, _EXIT_ARGS)
        check_special_arg_names_support('error', self._error_special_arg_names, _ERROR_ARGS)
        if self._propagate and _ARG_RET in self._error_special_arg_names:
            raise ValueError('Can not use @ret in error message when allowing error propagation')

    def _validate_computed_arg_names(self):
        for arg_names, computer in (
            (self._enter_computed_arg_names, self._enter_computer),
            (self._exit_computed_arg_names, self._exit_computer),
            (self._error_computed_arg_names, self._error_computer),
        ):
            if any(
                arg_name[1] == '_'  # arg_name[0] == _COMPUTED_ARG_PREFIX
                for arg_name
                in arg_names
            ):
                raise ValueError('Computed arg-names should not begin with an underscore')

            supplied_dynamic_attributes = set(attr for attr in dir(computer) if not attr.startswith('_'))
            if any(
                arg_name[1:] not in supplied_dynamic_attributes
                for arg_name
                in arg_names
            ):
                raise ValueError('Not all computed arg name definitions are supplied')

    # This function always returns the same value throughout the
    # lifetime of a dog instance
    def _build_default_return_arg(self):
        return self._default_ret_arg

    def _check_function_args(self, func):
        args, varargs, keywords, _ = getargspec(func)
        func_args = set(args)
        func_args.add(varargs)
        func_args.add(keywords)

        unrecognized_arg_names = set()

        for regular_phase_arg_names in (
            self._enter_regular_arg_names,
            self._exit_regular_arg_names,
            self._error_regular_arg_names
        ):
            if regular_phase_arg_names and not regular_phase_arg_names <= func_args:
                unrecognized_arg_names |= (regular_phase_arg_names - func_args)

        if unrecognized_arg_names:
            raise TypeError(
                'Function {} does not have these arguments, which were referenced in the dog: {}'
                .format(
                    func.__name__,
                    ', '.join(repr(arg) for arg in unrecognized_arg_names)
                )
            )

    def __call__(self, func):
        wrapped_func = unwrap(func)
        self._check_function_args(wrapped_func)

        # Cache some values so we don't need to recalculate
        #  them every time the wrapper is called:

        # Reference global invariants in the closure to avoid global lookup
        _time = time
        _partial = partial
        _lambda_dict = lambda_dict
        _getcallargs = getcallargs
        _get_simplified_traceback = get_simplified_traceback
        ARG_PATHNAME = _ARG_PATHNAME
        ARG_LINE = _ARG_LINE
        ARG_LOGGER = _ARG_LOGGER
        ARG_FUNC = _ARG_FUNC
        ARG_TIME = _ARG_TIME
        ARG_RET = _ARG_RET
        ARG_ERR = _ARG_ERR
        ARG_TRACEBACK = _ARG_TRACEBACK

        # Reference private invariants in the closure to avoid dictionary lookup
        log = self._log
        catch = self._catch
        propagate = self._propagate
        default_ret = self._default_ret
        enter_level = self._enter_level
        enter_format = self._enter_format
        enter_extras = self._enter_extras
        enter_computer = self._enter_computer
        enter_computed_arg_names = self._enter_computed_arg_names
        exit_level = self._exit_level
        exit_format = self._exit_format
        exit_extras = self._exit_extras
        exit_computer = self._exit_computer
        exit_computed_arg_names = self._exit_computed_arg_names
        error_level = self._error_level
        error_format = self._error_format
        error_extras = self._error_extras
        error_computer = self._error_computer
        error_computed_arg_names = self._error_computed_arg_names

        # Check which phases are required
        need_log_enter = self._enter_format is not None
        need_log_exit = self._exit_format is not None
        need_log_error = self._error_format is not None

        # Check which phases require regular arguments
        enter_needs_func_arguments = bool(self._enter_regular_arg_names)
        exit_needs_func_arguments = bool(self._exit_regular_arg_names)
        error_needs_func_arguments = bool(self._error_regular_arg_names)

        # Check which special arg-names are required by the enter phase
        enter_special_arg_names = self._enter_special_arg_names
        enter_needs_pathname_arg = ARG_PATHNAME in enter_special_arg_names
        enter_needs_line_arg = ARG_LINE in enter_special_arg_names
        enter_needs_logger_arg = ARG_LOGGER in enter_special_arg_names
        enter_needs_func_arg = ARG_FUNC in enter_special_arg_names

        # Check which special arg-names are required by the exit phase
        exit_special_arg_names = self._exit_special_arg_names
        exit_needs_pathname_arg = ARG_PATHNAME in exit_special_arg_names
        exit_needs_line_arg = ARG_LINE in exit_special_arg_names
        exit_needs_logger_arg = ARG_LOGGER in exit_special_arg_names
        exit_needs_func_arg = ARG_FUNC in exit_special_arg_names
        exit_needs_time_arg = ARG_TIME in exit_special_arg_names
        exit_needs_return_arg = ARG_RET in exit_special_arg_names

        # Check which special arg-names are required by the error phase
        error_special_arg_names = self._error_special_arg_names
        error_needs_pathname_arg = ARG_PATHNAME in error_special_arg_names
        error_needs_line_arg = ARG_LINE in error_special_arg_names
        error_needs_logger_arg = ARG_LOGGER in error_special_arg_names
        error_needs_func_arg = ARG_FUNC in error_special_arg_names
        error_needs_time_arg = ARG_TIME in error_special_arg_names
        error_needs_error_arg = ARG_ERR in error_special_arg_names
        error_needs_traceback_arg = ARG_TRACEBACK in error_special_arg_names
        error_needs_return_arg = ARG_RET in error_special_arg_names

        if error_needs_return_arg:
            build_default_return_arg = self._build_default_return_arg
        else:
            build_default_return_arg = _lambda_dict

        needs_time_arg = exit_needs_time_arg or error_needs_time_arg

        pathname, line = get_caller_pathname_and_line()

        # These builders always return the same value throughout the
        # lifetime of ``func``:

        @run_once
        def build_pathname_arg():
            return {ARG_PATHNAME: pathname}

        @run_once
        def build_line_arg():
            return {ARG_LINE: line}

        @run_once
        def build_function_arg():
            return {ARG_FUNC: wrapped_func}

        @wraps(func)
        def wrapper(*args, **kwargs):
            tb = None
            start_time = None
            end_time = None
            _logger = wrapper.logger
            log_enter = _partial(log, _logger, enter_level, enter_format, enter_extras, enter_computer, enter_computed_arg_names)
            log_exit = _partial(log, _logger, exit_level, exit_format, exit_extras, exit_computer, exit_computed_arg_names)
            log_error = _partial(log, _logger, error_level, error_format, error_extras, error_computer, error_computed_arg_names)

            @run_once
            def build_func_arguments_args():
                return _getcallargs(wrapped_func, *args, **kwargs)

            # Allowed to run every time because the logger may change
            def build_logger_arg():
                return {ARG_LOGGER: _logger}

            def build_time_arg():
                return {ARG_TIME: end_time - start_time}

            # log enter
            if need_log_enter:
                log_enter((
                    build_pathname_arg
                    if enter_needs_pathname_arg
                    else _lambda_dict,

                    build_line_arg
                    if enter_needs_line_arg
                    else _lambda_dict,

                    build_func_arguments_args
                    if enter_needs_func_arguments
                    else _lambda_dict,

                    build_logger_arg
                    if enter_needs_logger_arg
                    else _lambda_dict,

                    build_function_arg
                    if enter_needs_func_arg
                    else _lambda_dict,
                ))
            # Call the wrapped object
            try:
                if needs_time_arg:
                    start_time = _time()
                ret = func(*args, **kwargs)
                if exit_needs_time_arg:
                    end_time = _time()
            except catch:
                # duplicate this little clause here instead of wrapping the
                # call to ``func`` with an extra try-finally clause.
                if error_needs_time_arg:
                    end_time = _time()
                t, v, tb = exc_info()

                # log error
                if need_log_error:
                    def build_error_arg():
                        return {ARG_ERR: v}

                    # This:
                    # >>> def build_traceback_reference():
                    # >>>     return {_ARG_TRACEBACK: _get_simplified_traceback(tb)}
                    # causes:
                    # ``SyntaxError: can not delete variable 'tb' referenced in nested scope``
                    # So that's why we make this more complicated.
                    if error_needs_traceback_arg:
                        # The first part is this frame so we cut it off
                        simplified_tb = _get_simplified_traceback(next_traceback(tb))

                        def build_traceback_arg():
                            return {ARG_TRACEBACK: simplified_tb}
                    else:
                        build_traceback_arg = _lambda_dict

                    log_error((
                        build_pathname_arg
                        if error_needs_pathname_arg
                        else _lambda_dict,

                        build_line_arg
                        if error_needs_line_arg
                        else _lambda_dict,

                        build_func_arguments_args
                        if error_needs_func_arguments
                        else _lambda_dict,

                        build_logger_arg
                        if error_needs_logger_arg
                        else _lambda_dict,

                        build_function_arg
                        if error_needs_func_arg
                        else _lambda_dict,

                        build_time_arg
                        if error_needs_time_arg
                        else _lambda_dict,

                        build_error_arg
                        if error_needs_error_arg
                        else _lambda_dict,

                        build_traceback_arg,

                        build_default_return_arg,
                    ))

                if propagate:
                    # Elide this frame from the traceback
                    # https://stackoverflow.com/questions/44813333/
                    raise t, v, next_traceback(tb)
                ret = default_ret
            finally:
                del tb

            def build_return_arg():
                return {ARG_RET: ret}

            # log exit
            if need_log_exit:
                log_exit((
                    build_pathname_arg
                    if exit_needs_pathname_arg
                    else _lambda_dict,

                    build_line_arg
                    if exit_needs_line_arg
                    else _lambda_dict,

                    build_func_arguments_args
                    if exit_needs_func_arguments
                    else _lambda_dict,

                    build_logger_arg
                    if exit_needs_logger_arg
                    else _lambda_dict,

                    build_function_arg
                    if exit_needs_func_arg
                    else _lambda_dict,

                    build_time_arg
                    if exit_needs_time_arg
                    else _lambda_dict,

                    build_return_arg
                    if exit_needs_return_arg
                    else _lambda_dict,
                ))

            return ret

        logger = self._get_logger(wrapped_func)
        wrapper.logger = logger
        wrapper.__wrapped__ = func
        return wrapper

    def __repr__(self):
        arguments = []

        if self._enter_format:
            arguments.append('enter=({}, {!r})'.format(
                logging.getLevelName(self._enter_level),
                self._enter_format,
            ))
        if self._exit_format:
            arguments.append('exit=({}, {!r})'.format(
                logging.getLevelName(self._exit_level),
                self._exit_format,
            ))
        if self._error_format:
            arguments.append('error=({}, {!r})'.format(
                logging.getLevelName(self._error_level),
                self._error_format,
            ))

        if self.logger is not None:
            arguments.append('logger={!r}'.format(self.logger))

        if self._catch is not StandardError:
            arguments.append('catch={!r}'.format(self._catch))

        if not self._propagate:
            arguments.append('propagate_exception={!r}'.format(self._propagate))

        if not self._exc_info:
            arguments.append('exc_info={!r}'.format(
                self._exc_info
            ))

        if self._default_ret is not None:
            arguments.append('default_ret={!r}'.format(self._default_ret))

        return '{cls}({signature})'.format(
            cls=self.__class__.__name__,
            signature=', '.join(arguments)
        )

    def _get_logger(self, wrapped_func):
        logger = self.logger
        if logger is None:
            logger = logging.getLogger(wrapped_func.__globals__['__name__'])
        elif isinstance(logger, str):
            logger = logging.getLogger(logger)
        return logger

    def _log(self, logger, level, message, extras, arg_name_computer, arg_names_to_compute, builders):
        @run_once
        def basic_builder():
            arguments = {}
            for build in builders:
                arguments.update(build())
            return arguments

        if extras:
            extra = extras(basic_builder)  # Instantiate the class
        else:
            extra = None

        if arg_name_computer:
            arg_name_computer = arg_name_computer(basic_builder)

            def builder():
                arguments = {
                    arg_name: getattr(arg_name_computer, arg_name[1:])()
                    for arg_name
                    in arg_names_to_compute
                }
                arguments.update(basic_builder())
                return arguments
        else:
            builder = basic_builder

        logger.log(
            level,
            Message(message, builder),
            exc_info=self._exc_info,
            extra=extra
        )


# A decorative doggo!
# doggo = dog(
#     enter='{@func.__name__}: *wag*',
#     exit='{@func.__name__}: whimper...',
#     error=(CRITICAL, '{@func.__name__}: bark! bark!',
# )

# Stack dogs for extra fun!
# doggos = lambda fun: doggo(doggo(doggo(fun)))

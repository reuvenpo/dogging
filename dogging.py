from sys import exc_info as _exc_info
from inspect import getcallargs as _getcallargs
from inspect import getargspec as _getargspec
from string import Formatter as _Formatter
from functools import wraps as _wraps
from functools import partial as _partial
from itertools import imap as _map
from itertools import chain as _chain
import logging as _logging
# Import the logging levels for user convenience
from logging import DEBUG, INFO, WARN, WARNING, ERROR, FATAL, CRITICAL

__all__ = [
    'dog', 'Extra',
    'DEBUG', 'INFO', 'WARN', 'WARNING', 'ERROR', 'FATAL', 'CRITICAL',
    'doggo',
]

# Be explicit about exporting these from the module
DEBUG = DEBUG
INFO = INFO
WARN = WARN
WARNING = WARNING
ERROR = ERROR
FATAL = FATAL
CRITICAL = CRITICAL

# Names of the special references
# _REF_FMT = '__{}__'
_REF_FMT = '@{}'  # Common format for special references
_REF_LOGGER = _REF_FMT.format('logger')
_REF_FUNC = _REF_FMT.format('func')
_REF_RET = _REF_FMT.format('ret')
_REF_ERR = _REF_FMT.format('err')
_REF_TRACEBACK = _REF_FMT.format('traceback')

_ENTER_REFS = {
    _REF_LOGGER,
    _REF_FUNC,
}
_EXIT_REFS = {
    _REF_LOGGER,
    _REF_FUNC,
    _REF_RET,
}
_ERROR_REFS = {
    _REF_LOGGER,
    _REF_FUNC,
    _REF_RET,  # In this case it's the default return value
    _REF_ERR,
    _REF_TRACEBACK,
}
_ALL_REFS = {
    _REF_LOGGER,
    _REF_FUNC,
    _REF_RET,
    _REF_ERR,
    _REF_TRACEBACK,
}

_DEFAULT_LOGGER = '__logger__'


# Utilities:

def _raise(exception):
    raise exception


def _filter2(predicate, it):
    """Split the iterable ``it`` into two lists based on the function ``func``.

    This function is a lot like the builtin ``filter``, except that instead of
    throwing out the items that don't match, it splits the otiginal iterable
    into two lists: one of matching objects and one of the other objects.
    >>> _filter2((lambda x: x > 5), range(10))
    ([6, 7, 8, 9], [0, 1, 2, 3, 4, 5])
    """
    yes = []
    no = []
    append = (no.append, yes.append)
    for obj in it:
        append[bool(predicate(obj))](obj)  # bool is a subclass of int

    return yes, no


def _is_int_like(obj):
    """Can the object be turned into an integer?

    Returns True or False indicating if the object can be turned into an int.
    """
    try:
        int(obj)
    except StandardError:
        return False
    return True


def _unwrap(func):
    """Unwrap all layers of function wrappers.

    This is a simple version of Python3's ``inspect.unwrap()``
    """
    while True:
        try:
            func = func.__wrapped__
        except AttributeError:
            break
    return func


_formatter = _Formatter()


def _unpack_lambda(func):
    return func()


@_unpack_lambda
def _lambda_dict():
    constant = {}

    def _lambda_dict():
        """Return an empty dictionary."""
        return constant
    return _lambda_dict


# WARNING implementation specific
# Modified from: http://lucumr.pocoo.org/2016/12/29/careful-with-str-format/
# I kept the Python3 case to make it easier to port later.
# This is a necessary API but it's undocumented and moved around
# between Python releases
try:
    # Python3
    from _string import formatter_field_name_split as _formatter_field_name_split
except ImportError:
    # Python2
    def _formatter_field_name_split(field_name):
        return field_name._formatter_field_name_split()


# WARNING not thread safe because we don't need it to be.
def _run_once(func):
    """Call function once and cache its result.

    This decorator is meant for idempotent functions taking no arguments.
    Their return value is cached after the first call, and no subsequent calls
    to the function will be made.
    """
    func.done = False

    def wrapper():
        if func.done:
            return func.ret
        ret = func()
        func.done = True
        func.ret = ret
        return ret

    return wrapper


def _iter_traceback(tb):
    while tb:
        yield tb
        tb = tb.tb_next


def _get_simplified_traceback(tb):
    return [
        (
            tb.tb_frame.f_code.co_filename,
            tb.tb_lineno,
            tb.tb_frame.f_code.co_name,
        )
        for tb
        in _iter_traceback(tb)
    ]


# Helper functions

def _resolve_specification_string(spec):
    return INFO, spec, None


def _resolve_specification_sequence(spec):
    length = len(spec)
    if length == 2:
        level, format_string = spec
        return level, format_string, None
    if length == 3:
        level, format_string, extra = spec
        return level, format_string, extra
    raise ValueError('Unsupported length of sequence in specification')


def _resolve_specification_none(_):
    return None, None, None


_SPEC_RESOLVERS = {
    str: _resolve_specification_string,
    unicode: _resolve_specification_string,
    tuple: _resolve_specification_sequence,
    list: _resolve_specification_sequence,
    type(None): _resolve_specification_none,
}


def _resolve_specification(spec):
    try:
        resolver = _SPEC_RESOLVERS[type(spec)]
    except KeyError:
        raise TypeError('Unsupported specification: {!r}'.format(spec))
    return resolver(spec)


# WARNING implementation specific
def _get_format_arg_name_from_field_name(field_name):
    arg_name, rest = _formatter_field_name_split(field_name)
    # Parse all of the field-name parts for format validation
    for _ in rest:
        pass
    return arg_name


def _get_format_arg_names(format_string):
    return [
        _get_format_arg_name_from_field_name(field_name)
        for field_name
        in (
            # In these tuples:
            # The 1st field is the field-name.
            # The 3rd field is the conversion-method.
            # I intentionally build the tuple this way to squeeze in the
            #  conversion-method validation while still using list comp.
            (
                replacement_field[1],
                _formatter.convert_field(0, replacement_field[3]),
            )[0]
            for replacement_field
            in _formatter.parse(format_string)
        )
        # None indicates that there is no replacement at all
        if field_name is not None
    ]


def _some_format_arg_names_are_positional(arg_names):
    return any(
        arg_name == '' or _is_int_like(arg_name)
        for arg_name
        in arg_names
    )


def _check_format_arg_names_no_positional(arg_names):
    if _some_format_arg_names_are_positional(arg_names):
        raise ValueError(
            'Unnamed or positional replacement-fields in format specification'
        )


def _separate_special_from_regular_arg_names(arg_names):
    """Split the arg_names into two lists, one of the special, and one of the regular references."""
    special_refs = _ALL_REFS
    return _filter2((lambda arg_name: arg_name in special_refs), arg_names)


def _check_special_format_arg_names_support(phase, arg_names, supported):
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


class _Message(object):
    __slots__ = ('message', 'builder')

    def __init__(self, message, builder):
        self.message = message
        self.builder = builder

    def __str__(self):
        return self.message.format(**self.builder())


class Extra(object):
    """Base class for classes describing dynamic extra logging parameters.

    Subclass this class and create methods whose names don't begin with '_'.
    Your subclass can be passed as an argument to a dog's extra parameter.
    When LogRecords will be generated by the logging module for messages made
     by the dog, their dictionaries will be updated with attributes whose names
     match the names of your methods, and whose values equal the return values
     from your methods.
    Your methods will be called every time a LogRecord is generated.
    In your methods, you can access the ``self.refs`` property, returning
     the dictionary of parameters used to format the message for the specific
     LogRecord. This means access to the functions parameters, as well as any
     relevant special-references. (If you want to use a special-reference you
     should first make sure it's in the dictionary)
    By default, only the parameters used by the logging message of a phase will
     be available to the methods of your subclass. In order to request
     parameters that weren't referenced by the message, you must specify them in
     a class-attribute ``__refs__``, which should be any iterable of strings.
     The same checks that apply to format arguments in the logging message apply
     to these strings. (!) For consistency and robustness, specify any
     parameters you intend to use in the __refs__ attribute of your class (!).
    """
    def __init__(self, builder):
        self.__builder = builder
        self.__cache = None

    def __iter__(self):
        return (attr for attr in dir(self) if not attr.startswith('_'))

    def __getitem__(self, item):
        return getattr(self, item)()

    # For compatibility with the dict constructor, just in case
    def keys(self):
        return list(self)

    @property
    def refs(self):
        if self.__cache is None:
            self.__cache = self.__builder()
        return self.__cache


class dog(object):
    __slots__ = (
        '_enter_level', '_enter_format', '_enter_extra',
        '_enter_special_arg_names', '_enter_regular_arg_names',
        '_exit_level', '_exit_format', '_exit_extra',
        '_exit_special_arg_names', '_exit_regular_arg_names',
        '_error_level', '_error_format', '_error_extra',
        '_error_special_arg_names', '_error_regular_arg_names',
        'logger', '_catch', '_propagate', '_exc_info',
        '_default_ret', '_default_ret_ref',
    )

    def __init__(
        self,
        enter=None, exit=None, error=None,
        extra=None,
        logger=None,
        catch=Exception, propagate_exception=True,
        exc_info=False, default_ret=None
    ):
        self._enter_extra = extra
        self._exit_extra = extra
        self._error_extra = extra

        # Levels, format string and extras for each logging phase
        self._enter_level, self._enter_format, enter_extra = _resolve_specification(enter)
        self._exit_level, self._exit_format, exit_extra = _resolve_specification(exit)
        self._error_level, self._error_format, error_extra = _resolve_specification(error)

        # Override extra per-phase
        if enter_extra:
            self._enter_extra = enter_extra
        if exit_extra:
            self._exit_extra = exit_extra
        if error_extra:
            self._error_extra = error_extra

        # Extract the arg names from the replacement fields in the format string
        enter_arg_names = (
            _get_format_arg_names(self._enter_format)
            if self._enter_format is not None
            else None
        )
        exit_arg_names = (
            _get_format_arg_names(self._exit_format)
            if self._exit_format is not None
            else None
        )
        error_arg_names = (
            _get_format_arg_names(self._error_format)
            if self._error_format is not None
            else None
        )
        # Check the format strings are valid
        for arg_names in (enter_arg_names, exit_arg_names, error_arg_names):
            if arg_names is not None:
                _check_format_arg_names_no_positional(arg_names)

        # Add references from extra parameters to arg_name lists
        if self._enter_extra:
            enter_arg_names = _chain(enter_arg_names, self._enter_extra.__refs__)
        if self._exit_extra:
            exit_arg_names = _chain(exit_arg_names, self._exit_extra.__refs__)
        if self._error_extra:
            error_arg_names = _chain(error_arg_names, self._error_extra.__refs__)

        # For each logging phase, find which special arg names we would need
        #  and check that they are suitable for the specific phase.
        # Also collect the regular references to check them when wrapping a function.
        pair_of_frozen_sets = (frozenset(),) * 2
        self._enter_special_arg_names, self._enter_regular_arg_names = (
            _map(frozenset, _separate_special_from_regular_arg_names(enter_arg_names))
            if self._enter_format is not None
            else pair_of_frozen_sets
        )
        _check_special_format_arg_names_support('enter', self._enter_special_arg_names, _ENTER_REFS)
        self._exit_special_arg_names, self._exit_regular_arg_names = (
            _map(frozenset, _separate_special_from_regular_arg_names(exit_arg_names))
            if self._exit_format is not None
            else pair_of_frozen_sets
        )
        _check_special_format_arg_names_support('exit', self._exit_special_arg_names, _EXIT_REFS)
        self._error_special_arg_names, self._error_regular_arg_names = (
            _map(frozenset, _separate_special_from_regular_arg_names(error_arg_names))
            if self._error_format is not None
            else pair_of_frozen_sets
        )
        _check_special_format_arg_names_support('error', self._error_special_arg_names, _ERROR_REFS)
        if propagate_exception and _REF_RET in self._error_special_arg_names:
            raise ValueError('Can not use @ret in error message when allowing error propagation')

        # Simple attributes
        self.logger = logger or _DEFAULT_LOGGER
        self._catch = catch
        self._propagate = propagate_exception
        self._exc_info = exc_info
        self._default_ret = default_ret

        if propagate_exception:
            self._default_ret_ref = {}
        else:
            self._default_ret_ref = {_REF_RET: self._default_ret}

    # This function always returns the same value throughout the
    # lifetime of a dog instance
    def _build_default_return_reference(self):
        return self._default_ret_ref

    def _check_function_args(self, func):
        args, varargs, keywords, _ = _getargspec(func)
        func_args = set(args)
        func_args.add(varargs)
        func_args.add(keywords)

        unrecognized_args = set()

        for phase_args in (
            self._enter_regular_arg_names,
            self._exit_regular_arg_names,
            self._error_regular_arg_names
        ):
            if phase_args and not phase_args <= func_args:
                unrecognized_args |= (phase_args - func_args)

        if unrecognized_args:
            raise TypeError(
                'Function {} does not have these arguments, which were referenced in the dog: {}'
                .format(
                    func.__name__,
                    ', '.join(repr(arg) for arg in unrecognized_args)
                )
            )

    def __call__(self, func):
        wrapped_func = _unwrap(func)
        self._check_function_args(wrapped_func)

        # Cache some values so we don't need to recalculate
        #  them every time the wrapper is called:

        # Reference global invariants in the closure to avoid global lookup
        partial = _partial
        lambda_dict = _lambda_dict
        getcallargs = _getcallargs
        get_simplified_traceback = _get_simplified_traceback
        REF_LOGGER = _REF_LOGGER
        REF_FUNC = _REF_FUNC
        REF_RET = _REF_RET
        REF_ERR = _REF_ERR
        REF_TRACEBACK = _REF_TRACEBACK

        # Reference private invariants in the closure to avoid dictionary lookup
        log = self._log
        catch = self._catch
        propagate = self._propagate
        default_ret = self._default_ret
        enter_level = self._enter_level
        enter_format = self._enter_format
        enter_extra = self._enter_extra
        exit_level = self._exit_level
        exit_format = self._exit_format
        exit_extra = self._exit_extra
        error_level = self._error_level
        error_format = self._error_format
        error_extra = self._error_extra

        # Check which phases are required
        need_log_enter = self._enter_format is not None
        need_log_exit = self._exit_format is not None
        need_log_error = self._error_format is not None

        # Check which phases require regular arguments
        enter_needs_arguments = bool(self._enter_regular_arg_names)
        exit_needs_arguments = bool(self._exit_regular_arg_names)
        error_needs_arguments = bool(self._error_regular_arg_names)

        # Check which special references are required by the enter phase
        enter_special_arg_names = self._enter_special_arg_names
        enter_needs_logger_ref = REF_LOGGER in enter_special_arg_names
        enter_needs_func_ref = REF_FUNC in enter_special_arg_names

        # Check which special references are required by the exit phase
        exit_special_arg_names = self._exit_special_arg_names
        exit_needs_logger_ref = REF_LOGGER in exit_special_arg_names
        exit_needs_func_ref = REF_FUNC in exit_special_arg_names
        exit_needs_return_ref = REF_RET in exit_special_arg_names

        # Check which special references are required by the error phase
        error_special_arg_names = self._error_special_arg_names
        error_needs_logger_ref = REF_LOGGER in error_special_arg_names
        error_needs_func_ref = REF_FUNC in error_special_arg_names
        error_needs_error_ref = REF_ERR in error_special_arg_names
        error_needs_traceback_ref = REF_TRACEBACK in error_special_arg_names
        error_needs_return_ref = REF_RET in error_special_arg_names

        if error_needs_return_ref:
            build_default_return_reference = self._build_default_return_reference
        else:
            build_default_return_reference = lambda_dict

        # This function always returns the same value throughout the
        # lifetime of ``func``
        @_run_once
        def build_function_reference():
            return {REF_FUNC: wrapped_func}

        @_wraps(func)
        def wrapper(*args, **kwargs):
            tb = None
            logger = self._get_logger(wrapped_func)
            log_enter = partial(log, logger, enter_level, enter_format, extra=enter_extra)
            log_exit = partial(log, logger, exit_level, exit_format, extra=exit_extra)
            log_error = partial(log, logger, error_level, error_format, extra=error_extra)

            @_run_once
            def build_argument_references():
                return getcallargs(wrapped_func, *args, **kwargs)

            # Allowed to run all the time because the logger may change
            def build_logger_reference():
                return {REF_LOGGER: logger}

            # log enter
            if need_log_enter:
                log_enter((
                    build_argument_references
                    if enter_needs_arguments
                    else lambda_dict,

                    build_logger_reference
                    if enter_needs_logger_ref
                    else lambda_dict,

                    build_function_reference
                    if enter_needs_func_ref
                    else lambda_dict,
                ))
            # Call the wrapped object
            try:
                ret = func(*args, **kwargs)
            except catch:
                t, v, tb = _exc_info()

                # log error
                if need_log_error:
                    def build_err_reference():
                        return {REF_ERR: v}

                    # This:
                    # >>> def build_traceback_reference():
                    # >>>     return {_REF_TRACEBACK: _get_simplified_traceback(tb)}
                    # causes:
                    # ``SyntaxError: can not delete variable 'tb' referenced in nested scope``
                    # So that's why we make this more complicated.
                    if error_needs_traceback_ref:
                        # The first part is this frame so we cut it off
                        simplified_tb = get_simplified_traceback(tb.tb_next)

                        def build_traceback_reference():
                            return {REF_TRACEBACK: simplified_tb}
                    else:
                        build_traceback_reference = lambda_dict

                    log_error((
                        build_argument_references
                        if error_needs_arguments
                        else lambda_dict,

                        build_logger_reference
                        if error_needs_logger_ref
                        else lambda_dict,

                        build_function_reference
                        if error_needs_func_ref
                        else lambda_dict,

                        build_err_reference
                        if error_needs_error_ref
                        else lambda_dict,

                        build_traceback_reference,

                        build_default_return_reference,
                    ))

                if propagate:
                    # Elide this frame from the traceback
                    # https://stackoverflow.com/questions/44813333/
                    raise t, v, tb.tb_next
                ret = default_ret
            finally:
                del tb

            def build_return_reference():
                return {REF_RET: ret}

            # log exit
            if need_log_exit:
                log_exit((
                    build_argument_references
                    if exit_needs_arguments
                    else lambda_dict,
                    build_logger_reference
                    if exit_needs_logger_ref
                    else lambda_dict,
                    build_function_reference
                    if exit_needs_func_ref
                    else lambda_dict,
                    build_return_reference
                    if exit_needs_return_ref
                    else lambda_dict,
                ))

            return ret

        wrapper.__wrapped__ = func
        return wrapper

    def __repr__(self):
        arguments = []

        if self._enter_format:
            arguments.append('enter=({}, {!r})'.format(
                _logging.getLevelName(self._enter_level),
                self._enter_format,
            ))
        if self._exit_format:
            arguments.append('exit=({}, {!r})'.format(
                _logging.getLevelName(self._exit_level),
                self._exit_format,
            ))
        if self._error_format:
            arguments.append('error=({}, {!r})'.format(
                _logging.getLevelName(self._error_level),
                self._error_format,
            ))

        if self._extra is not None:
            arguments.append('extra={!r}'.format(self._extra))

        if self.logger != _DEFAULT_LOGGER:
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
        if isinstance(logger, str):
            return wrapped_func.__globals__[logger]
        else:
            return logger

    def _log(self, logger, level, message, builders, extra):
        @_run_once
        def builder():
            arguments = {}
            for build in builders:
                arguments.update(build())
            return arguments

        extra = extra(builder) if extra else None

        logger.log(
            level,
            _Message(message, builder),
            exc_info=self._exc_info,
            extra=extra
        )


# A decorative doggo!
doggo = dog(
    enter='{{{}.__name__}}: *wag*'.format(_REF_FUNC),
    exit='{{{}.__name__}}: whimper...'.format(_REF_FUNC),
    error=( CRITICAL, '{{{}.__name__}}: bark! bark!'.format(_REF_FUNC)),
)

# Stack dogs for extra fun!
# doggos = lambda fun: doggo(doggo(doggo(fun)))

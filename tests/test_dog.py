import sys
import os
import unittest
import logging

from dogging import *

from .configure_logging import handler
from .base import *

logger = logging.getLogger(__name__)


class SanityTestCase(DogTestBaseMixin, unittest.TestCase):
    """Test class checking the "idle" state of ``dog`` is correct.

    This class collects tests that check that the ``dog``'s default behaviour
    when not accepting any arguments is correct and that no errors are thrown
    when initializing it with no configuration.
    """
    def test_return_value(self):
        @dog()
        def foo(value):
            return value

        val = 'my string'
        ret = foo(val)
        self.assertIs(val, ret, 'the decorated function returned an unexpected value')
        self.assertEqual([], handler.records, 'log records were generated unexpectedly')

    def test_auto_logger_detection(self):
        @dog()
        def foo(value):
            return value

        self.assertIs(logger, foo.logger, 'the logger was not detected correctly')


class CustomLoggerTestCase(DogTestBaseMixin, unittest.TestCase):
    """Test case checking the dynamics of specifying a custom logger at different times."""
    def test_logger_defined_per_dog(self):
        """Test that when a logger is defined on the dog explicitly, it propagates to decorated functions."""
        logger_name = type(self).__name__
        alt_logger = logging.getLogger(logger_name)

        _dog = dog(
            'enter {@logger.name}',
            'exit {@logger.name}',
            logger=alt_logger,
        )

        @_dog
        def foo():
            alt_logger.info('inside')

        @_dog
        def bar():
            alt_logger.info('inside')

        self.assertIs(alt_logger, foo.logger, 'custom logger was not assigned to function')
        self.assertIs(alt_logger, bar.logger, 'custom logger was not assigned to function')

        foo()

        self.assertEqual(
            [
                'enter ' + logger_name,
                'inside',
                'exit ' + logger_name,
            ],
            [record.message for record in handler.records]
        )

        handler.flush()

        bar()

        self.assertEqual(
            [
                'enter ' + logger_name,
                'inside',
                'exit ' + logger_name,
            ],
            [record.message for record in handler.records]
        )

    def test_logger_customised_per_function(self):
        """Test that a function can explicitly specify a logger, and that it doesnt affect other functions."""
        logger_name = type(self).__name__
        alt_logger = logging.getLogger(logger_name)

        _dog = dog(
            'enter {@logger.name}',
            'exit {@logger.name}',
            logger=alt_logger,
        )

        @_dog
        def foo():
            alt_logger.info('inside')

        @_dog
        def bar():
            alt_logger.info('inside')

        self.assertIs(alt_logger, foo.logger, 'custom logger was not assigned to function')
        self.assertIs(alt_logger, bar.logger, 'custom logger was not assigned to function')

        foo.logger = alt_logger = logging.getLogger(logger_name + 'foo')
        bar.logger = alt_logger = logging.getLogger(logger_name + 'bar')

        foo()

        self.assertEqual(
            [
                'enter ' + logger_name + 'foo',
                'inside',
                'exit ' + logger_name + 'foo',
            ],
            [record.message for record in handler.records]
        )

        handler.flush()

        bar()

        self.assertEqual(
            [
                'enter ' + logger_name + 'bar',
                'inside',
                'exit ' + logger_name + 'bar',
            ],
            [record.message for record in handler.records]
        )

    def test_logger_specified_by_name(self):
        logger_name = 'foobar'
        alt_logger = logging.getLogger(logger_name)

        @dog(
            'enter {@logger.name}',
            'exit {@logger.name}',
            logger=logger_name,
        )
        def foo():
            alt_logger.info('inside')

        self.assertIs(
            alt_logger, foo.logger,
            'custom logger was not assigned to function, or the correct logger '
            'was not detected, based on the logger name given to the dog'
        )

        foo()

        self.assertEqual(
            [
                'enter ' + logger_name,
                'inside',
                'exit ' + logger_name,
            ],
            [record.message for record in handler.records]
        )


class StoppedErrorPropagationTestCase(DogTestBaseMixin, unittest.TestCase):
    def test_stopped_exception_and_specific_default_ret(self):
        default_value = 123

        @dog(propagate_exception=False, default_ret=default_value,)
        def foo():
            raise Exception()

        self.assertEqual(
            default_value, foo(),
            'function did not return the default value when raising an exception'
        )

    def test_stopped_exception_all_phases_log(self):
        @dog(
            'entering',
            'exiting',
            'faulting',
            propagate_exception=False,
        )
        def foo():
            raise Exception()

        foo()
        self.assertEqual(
            [
                'entering',
                'faulting',
                'exiting',
            ],
            [record.message for record in handler.records],
            'when the function raised an exception, and te dog was told '
            'to stop it, the log messages were emitted in the wrong order'
        )


# Tests for broken format strings:


class BrokenFormatStringMixin(DogTestPhasesMixin):
    """Base class for test cases where dog initialisation should fail because of a bad format string.

    Subclasses need only to define the message that is considered incorrect as
    the ``message`` class attribute. The ``bar`` arg name should be used as
    the arg name. This arg name refers to a real parameter of the decorated
    function, which means that if the format string is somehow deemed correct,
    an error **will not** be raised because the arg-name could not be
    recognised.
    """
    message = None

    enter_init_fails = True
    exit_init_fails = True
    error_init_fails = True
    enter_init_fail_exception = ValueError
    exit_init_fail_exception = ValueError
    error_init_fail_exception = ValueError

    def get_function(self, work):
        def foo(bar):
            return work()
        return foo

    def setUp(self):
        """
        :type self: BrokenFormatStringMixin | unittest.TestCase
        """
        super(BrokenFormatStringMixin, self).setUp()
        self.enter_message = self.message
        self.exit_message = self.message
        self.error_message = self.message


class FormatStringMissingClosingCurlyTestCase(BrokenFormatStringMixin, unittest.TestCase):
    message = 'abc {bar def'


class FormatStringMissingOpeningCurlyTestCase(BrokenFormatStringMixin, unittest.TestCase):
    message = 'abc bar} def'


class FormatStringMissingClosingSquareTestCase(BrokenFormatStringMixin, unittest.TestCase):
    message = 'abc {bar[} def'


class FormatStringEmptyAttributeTestCase(BrokenFormatStringMixin, unittest.TestCase):
    message = 'abc {bar.} def'


class FormatStringEmptyConversionTestCase(BrokenFormatStringMixin, unittest.TestCase):
    message = 'abc {bar!} def'


class FormatStringIncorrectConversionTestCase(BrokenFormatStringMixin, unittest.TestCase):
    message = 'abc {bar!x} def'


# Tests for simple messages with no references:


class SimpleMessageTestCase(DogTestPhasesMixin, unittest.TestCase):
    """Test case of simple messages with no formatting.

    This class mostly checks that all logging phases work correctly in all
    combinations, which means it doesn't modify any of the default behaviour
    defined in DogTestPhasesMixin.
    """
    pass


class UnicodeSimpleMessageTestCase(DogTestPhasesMixin, unittest.TestCase):
    """Test that unicode log message formats work well too"""
    enter_message = DogTestPhasesMixin.enter_message.decode('utf')
    inner_message = DogTestPhasesMixin.inner_message.decode('utf')
    exit_message = DogTestPhasesMixin.exit_message.decode('utf')
    error_message = DogTestPhasesMixin.error_message.decode('utf')
    enter_expected_log_message = enter_message
    inner_expected_log_message = inner_message
    exit_expected_log_message = exit_message
    error_expected_log_message = error_message


class ListSpecSimpleMessageTestCase(DogTestPhasesMixin, unittest.TestCase):
    """Test that the simplest form of sequence specifications works."""
    def get_dog_enter_spec(self):
        return [self.enter_message]

    def get_dog_exit_spec(self):
        return [self.exit_message]

    def get_dog_error_spec(self):
        return [self.error_message]


class EmptyListSpecSimpleMessageTestCase(DogTestPhasesMixin, unittest.TestCase):
    """Test that empty sequences are not allowed as sequence specifications."""
    enter_init_fails = True
    exit_init_fails = True
    error_init_fails = True
    enter_init_fail_exception = ValueError
    exit_init_fail_exception = ValueError
    error_init_fail_exception = ValueError

    def get_dog_enter_spec(self):
        return []

    def get_dog_exit_spec(self):
        return []

    def get_dog_error_spec(self):
        return []


class TupleSpecSimpleMessageTestCase(DogTestPhasesMixin, unittest.TestCase):
    """Previous sequence specification tests use lists. Test that tuples work too."""
    def get_dog_enter_spec(self):
        return self.enter_message,

    def get_dog_exit_spec(self):
        return self.exit_message,

    def get_dog_error_spec(self):
        return self.error_message,


class EmptyTupleSpecSimpleMessageTestCase(DogTestPhasesMixin, unittest.TestCase):
    """Previous sequence specification tests use lists. Test that tuples work too."""
    enter_init_fails = True
    exit_init_fails = True
    error_init_fails = True
    enter_init_fail_exception = ValueError
    exit_init_fail_exception = ValueError
    error_init_fail_exception = ValueError

    def get_dog_enter_spec(self):
        return ()

    def get_dog_exit_spec(self):
        return ()

    def get_dog_error_spec(self):
        return ()


class InvalidSpecSimpleMessageTestCase(DogTestPhasesMixin, unittest.TestCase):
    """Test that log message specifications raise a TypeError when given unsupported types."""
    enter_init_fails = True
    exit_init_fails = True
    error_init_fails = True
    enter_init_fail_exception = TypeError
    exit_init_fail_exception = TypeError
    error_init_fail_exception = TypeError

    def get_dog_enter_spec(self):
        return object()

    def get_dog_exit_spec(self):
        return object()

    def get_dog_error_spec(self):
        return object()


class InvalidListSpecSimpleMessageTestCase(DogTestPhasesMixin, unittest.TestCase):
    """Test that sequence specifications containing unsupported types, fail."""
    enter_init_fails = True
    exit_init_fails = True
    error_init_fails = True
    enter_init_fail_exception = TypeError
    exit_init_fail_exception = TypeError
    error_init_fail_exception = TypeError

    def get_dog_enter_spec(self):
        return [object()]

    def get_dog_exit_spec(self):
        return [object()]

    def get_dog_error_spec(self):
        return [object()]


class LogLevelInSequenceSpecificationTestCase(DogTestPhasesMixin, unittest.TestCase):
    """Test that specifying log levels in sequence specifications works correctly."""
    # We override this check and use a more granular one below:
    def check_log_record_logging_levels(self):
        pass

    def get_dog_enter_spec(self):
        return [DEBUG, self.enter_message]

    def get_dog_exit_spec(self):
        return [WARNING, self.exit_message]

    def get_dog_error_spec(self):
        return [ERROR, self.error_message]

    def check_enter_record(self, record):
        self.assertEqual(DEBUG, record.levelno)
        super(LogLevelInSequenceSpecificationTestCase, self).check_enter_record(record)

    def check_exit_record(self, record):
        self.assertEqual(WARNING, record.levelno)
        super(LogLevelInSequenceSpecificationTestCase, self).check_exit_record(record)

    def check_error_record(self, record):
        self.assertEqual(ERROR, record.levelno)
        super(LogLevelInSequenceSpecificationTestCase, self).check_error_record(record)


class PositionalArgNamesTestCase(DogTestPhasesMixin, unittest.TestCase):
    """Test that using positional arguments in log message specifications fails."""
    enter_message = 'what does {0} mean'
    exit_message = enter_message
    error_message = enter_message

    enter_init_fails = True
    exit_init_fails = True
    error_init_fails = True
    enter_init_fail_exception = ValueError
    exit_init_fail_exception = ValueError
    error_init_fail_exception = ValueError

    def get_function(self, work):
        def foo(bar, baz):
            return work()
        return foo

    def call_function(self, func):
        return func('cake', 'lie')


class ImplicitPositionalArgNamesTestCase(PositionalArgNamesTestCase):
    """Test that using implicit positional arguments in log message specifications fails."""
    enter_message = 'what does {} mean'
    exit_message = enter_message
    error_message = enter_message


# Tests for function-parameter arg-names:


class ParameterArgNameTestCase(DogTestPhasesMixin, unittest.TestCase):
    """Test case of messages with simple function-parameter arg-names.

    This class checks that all logging phases can reference
    simple function parameters.
    """
    enter_message = 'The {bar} is a {baz}!'
    exit_message = enter_message
    error_message = enter_message
    enter_expected_log_message = 'The cake is a lie!'
    exit_expected_log_message = enter_expected_log_message
    error_expected_log_message = enter_expected_log_message

    def get_function(self, work):
        def foo(bar, baz):
            return work()
        return foo

    def call_function(self, func):
        return func('cake', 'lie')


class WrongParameterArgNameTestCase(ParameterArgNameTestCase):
    """Test case of messages with simple but wrong function-parameter arg-names.

    This class checks that all logging phases can reference
    simple function parameters.
    """
    enter_message = 'The {bear} is a {buzz}!'
    exit_message = enter_message
    error_message = enter_message

    enter_decoration_fails = True
    exit_decoration_fails = True
    error_decoration_fails = True
    enter_decoration_fail_exception = TypeError
    exit_decoration_fail_exception = TypeError
    error_decoration_fail_exception = TypeError


class ArgsKwargsParameterArgNamesTestCase(DogTestPhasesMixin, unittest.TestCase):
    """Test case of messages with args and kwargs function-parameter arg-names.

    This class checks that all logging phases can reference
    args and kwargs function parameters.
    """
    enter_message = 'The {bar} is a {baz}!'
    exit_message = enter_message
    error_message = enter_message
    enter_expected_log_message = "The ('super', 'cali') is a {'fragilistic': 'expialidocious'}!"
    exit_expected_log_message = enter_expected_log_message
    error_expected_log_message = enter_expected_log_message

    def get_function(self, work):
        def foo(*bar, **baz):
            return work()
        return foo

    def call_function(self, func):
        return func('super', 'cali', fragilistic='expialidocious')


class WrongArgsKwargsParameterArgNamesTestCase(ArgsKwargsParameterArgNamesTestCase):
    """Test case of messages with wrong args and kwargs function-parameter arg-names.

    This class checks that all logging phases check args and kwargs function
    parameter correctness.
    """
    enter_message = 'The {bear} is a {buzz}!'
    exit_message = enter_message
    error_message = enter_message

    enter_decoration_fails = True
    exit_decoration_fails = True
    error_decoration_fails = True
    enter_decoration_fail_exception = TypeError
    exit_decoration_fail_exception = TypeError
    error_decoration_fail_exception = TypeError


# Tests for special arg-names:


class PathnameSpecialArgNameTestCase(DogTestPhasesSpecialArgNamesMixin, unittest.TestCase):
    """Test that logging phases can access the @pathname special arg-name."""
    arg_name = 'pathname'

    # Force function definition to happen in this file
    def get_function(self, work):
        def foo():
            return work()
        return foo

    def check_enter_message(self, message):
        # cut off the filename extension because it changes from '.py'
        # in some implementations. (Looking at you, CPython)
        self.assertEqual(
            os.path.splitext(__file__)[0],
            os.path.splitext(message)[0],
        )

    check_exit_message = check_enter_message
    check_error_message = check_enter_message


def get_this_line_number():
    """Get the line number on which this function was called.

    Right now this is the CPython way of doing this. When adding support for
    other Python implementations, just define this function conditionally, e.g.:

    if _CPython:
        def get_this_line_number: ...
    elif _IronPython:
        def get_this_line_number: ...
    elif etc...
    """
    try:
        raise ValueError()
    except ValueError:
        # Hack and slash
        return (
            sys.exc_info()[2].tb_frame  # This frame
            .f_back  # Caller's frame
            .f_lineno  # Caller's line number
        )


class LineSpecialArgNameTestCase(DogTestPhasesSpecialArgNamesMixin, unittest.TestCase):
    """Test that logging phases can access the @line special arg-name."""
    arg_name = 'line'

    # Control the line where the function is defined
    def get_function(self, work):
        def foo():
            return work()
        return foo
    definition_line = get_this_line_number() - 3

    def check_enter_message(self, message):
        self.assertEqual(str(self.definition_line), message)

    check_exit_message = check_enter_message
    check_error_message = check_enter_message


class LoggerSpecialArgNameTestCase(DogTestPhasesSpecialArgNamesMixin, unittest.TestCase):
    """Test that logging phases can access the @logger special arg-name."""
    arg_name = 'logger'
    replacement_field_modifier = '.name'

    # Force function creation to happen in this file, so that it finds our logger.
    def get_function(self, work):
        def foo():
            return work()
        return foo

    def check_enter_message(self, message):
        self.assertEqual(__name__, message)

    check_exit_message = check_enter_message
    check_error_message = check_enter_message


class FuncSpecialArgNameTestCase(DogTestPhasesSpecialArgNamesMixin, unittest.TestCase):
    """Test that logging phases can access the @func special arg-name."""
    arg_name = 'func'
    replacement_field_modifier = '.__name__'

    def check_enter_message(self, message):
        self.assertEqual('foo', message)

    check_exit_message = check_enter_message
    check_error_message = check_enter_message


class TimeSpecialArgNameTestCase(DogTestPhasesSpecialArgNamesMixin, unittest.TestCase):
    """Test that all logging phases except 'enter' can access the @time special arg-name."""
    arg_name = 'time'
    enter_init_fails = True
    enter_init_fail_exception = ValueError

    def check_exit_message(self, message):
        self.assertGreater(0.001, float(message))

    check_error_message = check_exit_message


class RetSpecialArgNameTestCase(DogTestPhasesSpecialArgNamesMixin, unittest.TestCase):
    """Test that the 'exit' logging phases can access the @ret special arg-name.

    We also check the edge case where the 'error' phase can access the @ret arg name.
    """
    arg_name = 'ret'
    return_value = 'A random long string of words'
    exit_expected_log_message = return_value
    enter_init_fails = True
    enter_init_fail_exception = ValueError
    error_init_fails = True
    error_init_fail_exception = ValueError

    def test_error_no_exception_propagation(self):
        # {@ret} IS ALLOWED in the error phase, only if exception propagation
        # is disabled.
        self.error_init_fails = False

        def get_dog_exit_args_kwargs():
            args, kwargs = super(RetSpecialArgNameTestCase, self).get_dog_error_args_kwargs()
            kwargs['propagate_exception'] = False
            kwargs['default_ret'] = self.return_value
            return args, kwargs

        # Monkey patch our instance such that when using the test_exit
        # method, an exception is thrown in the decorated function,
        # but the dog is configured to catch it and return a default value
        # instead
        self.get_dog_exit_args_kwargs = get_dog_exit_args_kwargs
        self.exit_case_function_behaviour = self.error_case_function_behaviour
        try:
            self.test_exit()
        finally:
            del self.__dict__['get_dog_exit_args_kwargs']
            del self.__dict__['exit_case_function_behaviour']


class ErrSpecialArgNameTestCase(DogTestPhasesSpecialArgNamesMixin, unittest.TestCase):
    """Test that only the 'error' logging phase can access the @err special arg-name."""
    arg_name = 'err'
    replacement_field_modifier = '!r'
    enter_init_fails = True
    enter_init_fail_exception = ValueError
    exit_init_fails = True
    exit_init_fail_exception = ValueError

    def check_error_message(self, message):
        self.assertEqual(repr(self.exception_value), message)


class TracebackSpecialArgNameTestCase(DogTestPhasesSpecialArgNamesMixin, unittest.TestCase):
    """Test that only the 'error' logging phase can access the @traceback special arg-name.

    We also generally test that the generated object works as expected,
    but checking this precisely is tricky.

    The algorithm for generating the simplified traceback is pretty straight
    forward, and has no reason to change. When this library will be ported
    to a Python implementation that has trouble with accessing the traceback
    information by python-level code, just add a conditional skip on this test
    case, and add the appropriate note in the documentation.
    Alternatively, this test will check that in such an implementation, trying
    to initialise a dog with @traceback in the format raises a ValueError with
    a message explaining the issue.
    """
    # ``traceback[0]`` is the "highest" frame in the stack trace.
    # ``traceback[0][0]`` is the file name at that frame.
    # ``traceback[0][1]`` is the line number at that frame.
    # ``traceback[0][2]`` is the name of the function at that frame.
    arg_name = 'traceback'
    replacement_field_modifier = '[0][2]'  # Name of the decorated function
    enter_init_fails = True
    enter_init_fail_exception = ValueError
    exit_init_fails = True
    exit_init_fail_exception = ValueError

    def check_error_message(self, message):
        self.assertEqual('foo', message)


# Tests for ComputedArgNames:


class SimpleComputedArgNamesTestCase(DogTestPhasesMixin, unittest.TestCase):
    """Test that a single ComputedArgNames passed to the dog works correctly."""
    computed_value = 'my computed value'
    another_computed_value = 'my other computed value'

    enter_message = '{>complicated_calculation} and {>another_complicated_calculation}'
    exit_message = enter_message
    error_message = enter_message
    enter_expected_log_message = '{} and {}'.format(computed_value, another_computed_value)
    exit_expected_log_message = enter_expected_log_message
    error_expected_log_message = enter_expected_log_message

    class Computer(ComputedArgNames):
        def complicated_calculation(self):
            return SimpleComputedArgNamesTestCase.computed_value

        def another_complicated_calculation(self):
            return SimpleComputedArgNamesTestCase.another_computed_value

    def get_dog_enter_spec(self):
        return [self.enter_message, self.Computer]

    def get_dog_exit_spec(self):
        return [self.exit_message, self.Computer]

    def get_dog_error_spec(self):
        return [self.error_message, self.Computer]


class MessageUsingUnsuppliedComputedArgNameTestCase(DogTestPhasesMixin, unittest.TestCase):
    """Test that providing a message trying to reference unsupplied computed arg-names fails."""
    enter_message = '{>computation}'
    exit_message = enter_message
    error_message = enter_message

    enter_init_fails = True
    exit_init_fails = True
    error_init_fails = True
    enter_init_fail_exception = ValueError
    exit_init_fail_exception = ValueError
    error_init_fail_exception = ValueError


class MultipleOrthogonalSimpleComputedArgNamesTestCase(DogTestPhasesMixin, unittest.TestCase):
    """Test that when providing multiple ComputedArgNames, which do not define the same arg-names, all arg-names are available."""
    computed_value = 'my computed value'
    another_computed_value = 'my other computed value'

    enter_message = '{>complicated_calculation} and {>another_complicated_calculation}'
    exit_message = enter_message
    error_message = enter_message
    enter_expected_log_message = '{} and {}'.format(computed_value, another_computed_value)
    exit_expected_log_message = enter_expected_log_message
    error_expected_log_message = enter_expected_log_message

    class Computer1(ComputedArgNames):
        def complicated_calculation(self):
            return MultipleOrthogonalSimpleComputedArgNamesTestCase.computed_value

    class Computer2(ComputedArgNames):
        def another_complicated_calculation(self):
            return MultipleOrthogonalSimpleComputedArgNamesTestCase.another_computed_value

    def get_dog_enter_spec(self):
        return [
            self.enter_message,
            self.Computer1,
            self.Computer2,
        ]

    def get_dog_exit_spec(self):
        return [
            self.exit_message,
            self.Computer1,
            self.Computer2,
        ]

    def get_dog_error_spec(self):
        return [
            self.error_message,
            self.Computer1,
            self.Computer2,
        ]


class MultipleInterferingSimpleComputedArgNamesTestCase(DogTestPhasesMixin, unittest.TestCase):
    """Test that when providing multiple ComputedArgNames, which define the same arg-names, latter definitions override former definitions."""
    computed_value = 'my computed value'
    alternative_computed_value = 'alternative computed value'
    another_computed_value = 'my other computed value'

    enter_message = '{>complicated_calculation} and {>another_complicated_calculation}'
    exit_message = enter_message
    error_message = enter_message
    enter_expected_log_message = '{} and {}'.format(alternative_computed_value, another_computed_value)
    exit_expected_log_message = enter_expected_log_message
    error_expected_log_message = enter_expected_log_message

    class Computer1(ComputedArgNames):
        def complicated_calculation(self):
            return MultipleInterferingSimpleComputedArgNamesTestCase.computed_value

        def another_complicated_calculation(self):
            return MultipleInterferingSimpleComputedArgNamesTestCase.another_computed_value

    class Computer2(ComputedArgNames):
        def complicated_calculation(self):
            return MultipleInterferingSimpleComputedArgNamesTestCase.alternative_computed_value

    def get_dog_enter_spec(self):
        return [
            self.enter_message,
            self.Computer1,
            self.Computer2,
        ]

    def get_dog_exit_spec(self):
        return [
            self.exit_message,
            self.Computer1,
            self.Computer2,
        ]

    def get_dog_error_spec(self):
        return [
            self.error_message,
            self.Computer1,
            self.Computer2,
        ]


class ReverseMultipleInterferingSimpleComputedArgNamesTestCase(DogTestPhasesMixin, unittest.TestCase):
    """Same as previous test, except that computers are provided in the opposite order, to check that order is preserved"""
    computed_value = 'my computed value'
    alternative_computed_value = 'alternative computed value'
    another_computed_value = 'my other computed value'

    enter_message = '{>complicated_calculation} and {>another_complicated_calculation}'
    exit_message = enter_message
    error_message = enter_message
    enter_expected_log_message = '{} and {}'.format(computed_value, another_computed_value)
    exit_expected_log_message = enter_expected_log_message
    error_expected_log_message = enter_expected_log_message

    class Computer1(ComputedArgNames):
        def complicated_calculation(self):
            return ReverseMultipleInterferingSimpleComputedArgNamesTestCase.computed_value

        def another_complicated_calculation(self):
            return ReverseMultipleInterferingSimpleComputedArgNamesTestCase.another_computed_value

    class Computer2(ComputedArgNames):
        def complicated_calculation(self):
            return ReverseMultipleInterferingSimpleComputedArgNamesTestCase.alternative_computed_value

    def get_dog_enter_spec(self):
        return [
            self.enter_message,
            self.Computer2,
            self.Computer1,
        ]

    def get_dog_exit_spec(self):
        return [
            self.exit_message,
            self.Computer2,
            self.Computer1,
        ]

    def get_dog_error_spec(self):
        return [
            self.error_message,
            self.Computer2,
            self.Computer1,
        ]


class ComputedArgNamesRequestingOtherArgNamesTestCase(DogTestPhasesMixin, unittest.TestCase):
    """Test that computed arg-names have access to basic and special arg names when requesting them."""
    enter_message = '{>computation}'
    exit_message = enter_message
    error_message = enter_message
    enter_expected_log_message = 'success'
    exit_expected_log_message = enter_expected_log_message
    error_expected_log_message = enter_expected_log_message

    class TestComputer(ComputedArgNames):
        __args__ = []

        def computation(self):
            missing_arg_names = [arg_name for arg_name in self.__args__ if arg_name not in self._args]
            if not missing_arg_names:
                return 'success'
            return repr(missing_arg_names)

    class EnterComputer(TestComputer):
        __args__ = [
            '@pathname',
            '@line',
            '@logger',
            '@func',
            'bar',
            'baz',
        ]

    class ExitComputer(TestComputer):
        __args__ = [
            '@pathname',
            '@line',
            '@logger',
            '@func',
            '@time',
            '@ret',
            'bar',
            'baz',
        ]

    class ErrorComputer(TestComputer):
        __args__ = [
            '@pathname',
            '@line',
            '@logger',
            '@func',
            '@time',
            '@err',
            '@traceback',
            'bar',
            'baz',
        ]

    def get_dog_enter_spec(self):
        return [
            self.enter_message,
            self.EnterComputer,
        ]

    def get_dog_exit_spec(self):
        return [
            self.exit_message,
            self.ExitComputer,
        ]

    def get_dog_error_spec(self):
        return [
            self.error_message,
            self.ErrorComputer,
        ]

    def get_function(self, work):
        def foo(bar, baz):
            return work()
        return foo

    def call_function(self, func):
        return func('cake', 'lie')

    def check_message(self, message):
        self.assertEqual('success', message, 'could not access these arg-names in a computer: ' + message)

    check_enter_message = check_message
    check_exit_message = check_message
    check_error_message = check_message


class ComputedArgNamesRequestingNonexistentRegularArgNamesTestCase(DogTestPhasesMixin, unittest.TestCase):
    """Test that dogs fail to decorate with computed arg-names requesting nonexistent regular arg-names."""
    enter_message = '{>computation}'
    exit_message = enter_message
    error_message = enter_message

    enter_decoration_fails = True
    exit_decoration_fails = True
    error_decoration_fails = True
    enter_decoration_fail_exception = TypeError
    exit_decoration_fail_exception = TypeError
    error_decoration_fail_exception = TypeError

    class TestComputer(ComputedArgNames):
        __args__ = [
            'bear',
        ]

        def computation(self):
            pass

    def get_dog_enter_spec(self):
        return [
            self.enter_message,
            self.TestComputer,
        ]

    def get_dog_exit_spec(self):
        return [
            self.exit_message,
            self.TestComputer,
        ]

    def get_dog_error_spec(self):
        return [
            self.error_message,
            self.TestComputer,
        ]


class ComputedArgNamesRequestingNonexistentSpecialArgNamesTestCase(DogTestPhasesMixin, unittest.TestCase):
    """Test that dogs fail to initialise with computed arg-names requesting nonexistent special arg-names."""
    enter_message = '{>computation}'
    exit_message = enter_message
    error_message = enter_message

    enter_init_fails = True
    exit_init_fails = True
    error_init_fails = True
    enter_init_fail_exception = ValueError
    exit_init_fail_exception = ValueError
    error_init_fail_exception = ValueError

    class TestComputer(ComputedArgNames):
        __args__ = [
            '@linen',
        ]

        def computation(self):
            pass

    def get_dog_enter_spec(self):
        return [
            self.enter_message,
            self.TestComputer,
        ]

    def get_dog_exit_spec(self):
        return [
            self.exit_message,
            self.TestComputer,
        ]

    def get_dog_error_spec(self):
        return [
            self.error_message,
            self.TestComputer,
        ]


class ComputedArgNamesNotRequestingOtherArgNamesTestCase(DogTestPhasesMixin, unittest.TestCase):
    """Test that unrequested arg-names aren't available in the computer."""
    enter_message = '{>computation}'
    exit_message = enter_message
    error_message = enter_message
    enter_expected_log_message = 'success'
    exit_expected_log_message = enter_expected_log_message
    error_expected_log_message = enter_expected_log_message

    class TestComputer(ComputedArgNames):
        def computation(self):
            unexpected_arg_names = [arg_name for arg_name in self._args]
            if not unexpected_arg_names:
                return 'success'
            return repr(unexpected_arg_names)

    def get_dog_enter_spec(self):
        return [
            self.enter_message,
            self.TestComputer,
        ]

    def get_dog_exit_spec(self):
        return [
            self.exit_message,
            self.TestComputer,
        ]

    def get_dog_error_spec(self):
        return [
            self.error_message,
            self.TestComputer,
        ]

    def get_function(self, work):
        def foo(bar, baz):
            return work()

        return foo

    def call_function(self, func):
        return func('cake', 'lie')

    def check_message(self, message):
        self.assertEqual(
            self.enter_expected_log_message, message,
            'unexpectedly available arg-names in a computer: ' + message
        )

    check_enter_message = check_message
    check_exit_message = check_message
    check_error_message = check_message


@unittest.skip(
    'Not implemented yet. Computers may access unrequested arg-names '
    'when a logging message triggers their creation.'
)
class ComputedArgNamesNotRequestingOtherArgNamesTestCase2(ComputedArgNamesNotRequestingOtherArgNamesTestCase):
    """This test case expands on the previous test.

    The point of this test is to show that even when the logging message
    triggers the creation of other arg names, they do not become accessible
    to computers that did not explicitly request them.
    """
    enter_message = '{>computation} {bar}'
    exit_message = enter_message
    error_message = enter_message
    enter_expected_log_message = 'success cake'
    exit_expected_log_message = enter_expected_log_message
    error_expected_log_message = enter_expected_log_message


# Tests for ExtraAttributes:


class SimpleExtraAttributesTestCase(DogTestPhasesMixin, unittest.TestCase):
    """Test that a single ExtraAttributes passed to the dog works correctly."""
    computed_value = 'my computed value'
    another_computed_value = 'my other computed value'

    class Extras(ExtraAttributes):
        def complicated_calculation(self):
            return SimpleExtraAttributesTestCase.computed_value

        def another_complicated_calculation(self):
            return SimpleExtraAttributesTestCase.another_computed_value

    def get_dog_enter_spec(self):
        return [self.enter_message, self.Extras]

    def get_dog_exit_spec(self):
        return [self.exit_message, self.Extras]

    def get_dog_error_spec(self):
        return [self.error_message, self.Extras]

    def check_enter_record(self, record):
        super(SimpleExtraAttributesTestCase, self).check_enter_record(record)
        if not hasattr(record, 'complicated_calculation'):
            self.fail("enter log record does not have 'complicated_calculation' attribute")
        if not hasattr(record, 'another_complicated_calculation'):
            self.fail("enter log record does not have 'another_complicated_calculation' attribute")

        self.assertEqual(self.computed_value, record.complicated_calculation)
        self.assertEqual(self.another_computed_value, record.another_complicated_calculation)

    def check_inner_record(self, record):
        super(SimpleExtraAttributesTestCase, self).check_inner_record(record)
        if hasattr(record, 'complicated_calculation'):
            self.fail("inner log record has 'complicated_calculation' attribute")
        if hasattr(record, 'another_complicated_calculation'):
            self.fail("inner log record has 'another_complicated_calculation' attribute")

    def check_exit_record(self, record):
        super(SimpleExtraAttributesTestCase, self).check_exit_record(record)
        if not hasattr(record, 'complicated_calculation'):
            self.fail("exit log record does not have 'complicated_calculation' attribute")
        if not hasattr(record, 'another_complicated_calculation'):
            self.fail("exit log record does not have 'another_complicated_calculation' attribute")

        self.assertEqual(self.computed_value, record.complicated_calculation)
        self.assertEqual(self.another_computed_value, record.another_complicated_calculation)

    def check_error_record(self, record):
        super(SimpleExtraAttributesTestCase, self).check_error_record(record)
        if not hasattr(record, 'complicated_calculation'):
            self.fail("error log record does not have 'complicated_calculation' attribute")
        if not hasattr(record, 'another_complicated_calculation'):
            self.fail("error log record does not have 'another_complicated_calculation' attribute")

        self.assertEqual(self.computed_value, record.complicated_calculation)
        self.assertEqual(self.another_computed_value, record.another_complicated_calculation)


class MultipleOrthogonalSimpleExtraAttributesTestCase(DogTestPhasesMixin, unittest.TestCase):
    """Test that when providing multiple ExtraAttributes, which do not define the same arg-names, all arg-names are available."""
    computed_value = 'my computed value'
    another_computed_value = 'my other computed value'

    class Extra1(ExtraAttributes):
        def complicated_calculation(self):
            return MultipleOrthogonalSimpleExtraAttributesTestCase.computed_value

    class Extra2(ExtraAttributes):
        def another_complicated_calculation(self):
            return MultipleOrthogonalSimpleExtraAttributesTestCase.another_computed_value

    def get_dog_enter_spec(self):
        return [
            self.enter_message,
            self.Extra1,
            self.Extra2,
        ]

    def get_dog_exit_spec(self):
        return [
            self.exit_message,
            self.Extra1,
            self.Extra2,
        ]

    def get_dog_error_spec(self):
        return [
            self.error_message,
            self.Extra1,
            self.Extra2,
        ]

    def check_enter_record(self, record):
        super(MultipleOrthogonalSimpleExtraAttributesTestCase, self).check_enter_record(record)
        if not hasattr(record, 'complicated_calculation'):
            self.fail("enter log record does not have 'complicated_calculation' attribute")
        if not hasattr(record, 'another_complicated_calculation'):
            self.fail("enter log record does not have 'another_complicated_calculation' attribute")

        self.assertEqual(self.computed_value, record.complicated_calculation)
        self.assertEqual(self.another_computed_value, record.another_complicated_calculation)

    def check_inner_record(self, record):
        super(MultipleOrthogonalSimpleExtraAttributesTestCase, self).check_inner_record(record)
        if hasattr(record, 'complicated_calculation'):
            self.fail("inner log record has 'complicated_calculation' attribute")
        if hasattr(record, 'another_complicated_calculation'):
            self.fail("inner log record has 'another_complicated_calculation' attribute")

    def check_exit_record(self, record):
        super(MultipleOrthogonalSimpleExtraAttributesTestCase, self).check_exit_record(record)
        if not hasattr(record, 'complicated_calculation'):
            self.fail("exit log record does not have 'complicated_calculation' attribute")
        if not hasattr(record, 'another_complicated_calculation'):
            self.fail("exit log record does not have 'another_complicated_calculation' attribute")

        self.assertEqual(self.computed_value, record.complicated_calculation)
        self.assertEqual(self.another_computed_value, record.another_complicated_calculation)

    def check_error_record(self, record):
        super(MultipleOrthogonalSimpleExtraAttributesTestCase, self).check_error_record(record)
        if not hasattr(record, 'complicated_calculation'):
            self.fail("error log record does not have 'complicated_calculation' attribute")
        if not hasattr(record, 'another_complicated_calculation'):
            self.fail("error log record does not have 'another_complicated_calculation' attribute")

        self.assertEqual(self.computed_value, record.complicated_calculation)
        self.assertEqual(self.another_computed_value, record.another_complicated_calculation)


class MultipleInterferingSimpleExtraAttributesTestCase(DogTestPhasesMixin, unittest.TestCase):
    """Test that when providing multiple ExtraAttributes, which define the same arg-names, latter definitions override former definitions."""
    computed_value = 'my computed value'
    alternative_computed_value = 'alternative computed value'
    another_computed_value = 'my other computed value'

    class Extra1(ExtraAttributes):
        def complicated_calculation(self):
            return MultipleInterferingSimpleExtraAttributesTestCase.computed_value

        def another_complicated_calculation(self):
            return MultipleInterferingSimpleExtraAttributesTestCase.another_computed_value

    class Extra2(ExtraAttributes):
        def complicated_calculation(self):
            return MultipleInterferingSimpleExtraAttributesTestCase.alternative_computed_value

    def get_dog_enter_spec(self):
        return [
            self.enter_message,
            self.Extra1,
            self.Extra2,
        ]

    def get_dog_exit_spec(self):
        return [
            self.exit_message,
            self.Extra1,
            self.Extra2,
        ]

    def get_dog_error_spec(self):
        return [
            self.error_message,
            self.Extra1,
            self.Extra2,
        ]

    def check_enter_record(self, record):
        super(MultipleInterferingSimpleExtraAttributesTestCase, self).check_enter_record(record)
        if not hasattr(record, 'complicated_calculation'):
            self.fail("enter log record does not have 'complicated_calculation' attribute")
        if not hasattr(record, 'another_complicated_calculation'):
            self.fail("enter log record does not have 'another_complicated_calculation' attribute")

        self.assertEqual(self.alternative_computed_value, record.complicated_calculation)
        self.assertEqual(self.another_computed_value, record.another_complicated_calculation)

    def check_inner_record(self, record):
        super(MultipleInterferingSimpleExtraAttributesTestCase, self).check_inner_record(record)
        if hasattr(record, 'complicated_calculation'):
            self.fail("inner log record has 'complicated_calculation' attribute")
        if hasattr(record, 'another_complicated_calculation'):
            self.fail("inner log record has 'another_complicated_calculation' attribute")

    def check_exit_record(self, record):
        super(MultipleInterferingSimpleExtraAttributesTestCase, self).check_exit_record(record)
        if not hasattr(record, 'complicated_calculation'):
            self.fail("exit log record does not have 'complicated_calculation' attribute")
        if not hasattr(record, 'another_complicated_calculation'):
            self.fail("exit log record does not have 'another_complicated_calculation' attribute")

        self.assertEqual(self.alternative_computed_value, record.complicated_calculation)
        self.assertEqual(self.another_computed_value, record.another_complicated_calculation)

    def check_error_record(self, record):
        super(MultipleInterferingSimpleExtraAttributesTestCase, self).check_error_record(record)
        if not hasattr(record, 'complicated_calculation'):
            self.fail("error log record does not have 'complicated_calculation' attribute")
        if not hasattr(record, 'another_complicated_calculation'):
            self.fail("error log record does not have 'another_complicated_calculation' attribute")

        self.assertEqual(self.alternative_computed_value, record.complicated_calculation)
        self.assertEqual(self.another_computed_value, record.another_complicated_calculation)


class ReverseMultipleInterferingSimpleExtraAttributesTestCase(DogTestPhasesMixin, unittest.TestCase):
    """Same as previous test, except that extras are provided in the opposite order, to check that order is preserved"""
    computed_value = 'my computed value'
    alternative_computed_value = 'alternative computed value'
    another_computed_value = 'my other computed value'

    class Extra1(ExtraAttributes):
        def complicated_calculation(self):
            return ReverseMultipleInterferingSimpleExtraAttributesTestCase.computed_value

        def another_complicated_calculation(self):
            return ReverseMultipleInterferingSimpleExtraAttributesTestCase.another_computed_value

    class Extra2(ExtraAttributes):
        def complicated_calculation(self):
            return ReverseMultipleInterferingSimpleExtraAttributesTestCase.alternative_computed_value

    def get_dog_enter_spec(self):
        return [
            self.enter_message,
            self.Extra2,
            self.Extra1,
        ]

    def get_dog_exit_spec(self):
        return [
            self.exit_message,
            self.Extra2,
            self.Extra1,
        ]

    def get_dog_error_spec(self):
        return [
            self.error_message,
            self.Extra2,
            self.Extra1,
        ]

    def check_enter_record(self, record):
        super(ReverseMultipleInterferingSimpleExtraAttributesTestCase, self).check_enter_record(record)
        if not hasattr(record, 'complicated_calculation'):
            self.fail("enter log record does not have 'complicated_calculation' attribute")
        if not hasattr(record, 'another_complicated_calculation'):
            self.fail("enter log record does not have 'another_complicated_calculation' attribute")

        self.assertEqual(self.computed_value, record.complicated_calculation)
        self.assertEqual(self.another_computed_value, record.another_complicated_calculation)

    def check_inner_record(self, record):
        super(ReverseMultipleInterferingSimpleExtraAttributesTestCase, self).check_inner_record(record)
        if hasattr(record, 'complicated_calculation'):
            self.fail("inner log record has 'complicated_calculation' attribute")
        if hasattr(record, 'another_complicated_calculation'):
            self.fail("inner log record has 'another_complicated_calculation' attribute")

    def check_exit_record(self, record):
        super(ReverseMultipleInterferingSimpleExtraAttributesTestCase, self).check_exit_record(record)
        if not hasattr(record, 'complicated_calculation'):
            self.fail("exit log record does not have 'complicated_calculation' attribute")
        if not hasattr(record, 'another_complicated_calculation'):
            self.fail("exit log record does not have 'another_complicated_calculation' attribute")

        self.assertEqual(self.computed_value, record.complicated_calculation)
        self.assertEqual(self.another_computed_value, record.another_complicated_calculation)

    def check_error_record(self, record):
        super(ReverseMultipleInterferingSimpleExtraAttributesTestCase, self).check_error_record(record)
        if not hasattr(record, 'complicated_calculation'):
            self.fail("error log record does not have 'complicated_calculation' attribute")
        if not hasattr(record, 'another_complicated_calculation'):
            self.fail("error log record does not have 'another_complicated_calculation' attribute")

        self.assertEqual(self.computed_value, record.complicated_calculation)
        self.assertEqual(self.another_computed_value, record.another_complicated_calculation)


class ExtraAttributesRequestingOtherArgNamesTestCase(DogTestPhasesMixin, unittest.TestCase):
    """Test that extra arg-names have access to basic and special arg names when requesting them."""
    class TestExtra(ExtraAttributes):
        __args__ = []

        def computation(self):
            missing_arg_names = [arg_name for arg_name in self.__args__ if arg_name not in self._args]
            if not missing_arg_names:
                return 'success'
            return repr(missing_arg_names)

    class EnterExtra(TestExtra):
        __args__ = [
            '@pathname',
            '@line',
            '@logger',
            '@func',
            'bar',
            'baz',
        ]

    class ExitExtra(TestExtra):
        __args__ = [
            '@pathname',
            '@line',
            '@logger',
            '@func',
            '@time',
            '@ret',
            'bar',
            'baz',
        ]

    class ErrorExtra(TestExtra):
        __args__ = [
            '@pathname',
            '@line',
            '@logger',
            '@func',
            '@time',
            '@err',
            '@traceback',
            'bar',
            'baz',
        ]

    def get_dog_enter_spec(self):
        return [
            self.enter_message,
            self.EnterExtra,
        ]

    def get_dog_exit_spec(self):
        return [
            self.exit_message,
            self.ExitExtra,
        ]

    def get_dog_error_spec(self):
        return [
            self.error_message,
            self.ErrorExtra,
        ]

    def get_function(self, work):
        def foo(bar, baz):
            return work()
        return foo

    def call_function(self, func):
        return func('cake', 'lie')

    def check_record(self, record):
        if not hasattr(record, 'computation'):
            self.fail("log record has no 'computation' attribute")
        self.assertEqual(
            'success', record.computation,
            'could not access these arg-names in extras: ' + record.computation
        )

    check_enter_record = check_record
    check_exit_record = check_record
    check_error_record = check_record


class ExtraAttributesRequestingNonexistentRegularArgNamesTestCase(DogTestPhasesMixin, unittest.TestCase):
    """Test that dogs fail to decorate with extra arg-names requesting nonexistent regular arg-names."""
    enter_decoration_fails = True
    exit_decoration_fails = True
    error_decoration_fails = True
    enter_decoration_fail_exception = TypeError
    exit_decoration_fail_exception = TypeError
    error_decoration_fail_exception = TypeError

    class TestExtras(ExtraAttributes):
        __args__ = [
            'bear',
        ]

        def computation(self):
            pass

    def get_dog_enter_spec(self):
        return [
            self.enter_message,
            self.TestExtras,
        ]

    def get_dog_exit_spec(self):
        return [
            self.exit_message,
            self.TestExtras,
        ]

    def get_dog_error_spec(self):
        return [
            self.error_message,
            self.TestExtras,
        ]


class ExtraAttributesRequestingNonexistentSpecialArgNamesTestCase(DogTestPhasesMixin, unittest.TestCase):
    """Test that dogs fail to initialise with extra arg-names requesting nonexistent special arg-names."""
    enter_init_fails = True
    exit_init_fails = True
    error_init_fails = True
    enter_init_fail_exception = ValueError
    exit_init_fail_exception = ValueError
    error_init_fail_exception = ValueError

    class TestExtras(ExtraAttributes):
        __args__ = [
            '@linen',
        ]

        def computation(self):
            pass

    def get_dog_enter_spec(self):
        return [
            self.enter_message,
            self.TestExtras,
        ]

    def get_dog_exit_spec(self):
        return [
            self.exit_message,
            self.TestExtras,
        ]

    def get_dog_error_spec(self):
        return [
            self.error_message,
            self.TestExtras,
        ]


class ExtraAttributesNotRequestingOtherArgNamesTestCase(DogTestPhasesMixin, unittest.TestCase):
    """Test that unrequested arg-names aren't available in the extras."""
    class TestExtras(ExtraAttributes):
        def computation(self):
            unexpected_arg_names = [arg_name for arg_name in self._args]
            if not unexpected_arg_names:
                return 'success'
            return repr(unexpected_arg_names)

    def get_dog_enter_spec(self):
        return [
            self.enter_message,
            self.TestExtras,
        ]

    def get_dog_exit_spec(self):
        return [
            self.exit_message,
            self.TestExtras,
        ]

    def get_dog_error_spec(self):
        return [
            self.error_message,
            self.TestExtras,
        ]

    def get_function(self, work):
        def foo(bar, baz):
            return work()

        return foo

    def call_function(self, func):
        return func('cake', 'lie')

    def check_record(self, record):
        if not hasattr(record, 'computation'):
            self.fail("log record has no 'computation' attribute")
        self.assertEqual(
            'success', record.computation,
            'unexpectedly available arg-names in extras: ' + record.computation
        )

    check_enter_record = check_record
    check_exit_record = check_record
    check_error_record = check_record


@unittest.skip(
    'Not implemented yet. Extras may access unrequested arg-names '
    'when a logging message triggers their creation.'
)
class ExtraAttributesNotRequestingOtherArgNamesTestCase2(ExtraAttributesNotRequestingOtherArgNamesTestCase):
    """This test case expands on the previous test.

    The point of this test is to show that even when the logging message
    triggers the creation of other arg names, they do not become accessible
    to extras that did not explicitly request them.
    """
    enter_message = '{bar}'
    exit_message = enter_message
    error_message = enter_message
    enter_expected_log_message = 'cake'
    exit_expected_log_message = enter_expected_log_message
    error_expected_log_message = enter_expected_log_message

    def check_record(self, record):
        if not hasattr(record, 'computation'):
            self.fail("log record has no 'computation' attribute")
        self.assertEqual(
            'success', record.computation,
            'unexpectedly available arg-names in extras: ' + record.computation
        )

    check_enter_record = check_record
    check_exit_record = check_record
    check_error_record = check_record


class CrossPhaseExtraAttributesTestCase(DogTestPhasesMixin, unittest.TestCase):
    """Test that specifying a single extra class for the entire dog works correctly."""
    computed_value = 'my computed value'
    another_computed_value = 'my other computed value'

    class Extra1(ExtraAttributes):
        def complicated_calculation(self):
            return CrossPhaseExtraAttributesTestCase.computed_value

        def another_complicated_calculation(self):
            return CrossPhaseExtraAttributesTestCase.another_computed_value

    def get_dog_enter_args_kwargs(self):
        args, kwargs = super(CrossPhaseExtraAttributesTestCase, self).get_dog_enter_args_kwargs()
        kwargs['extras'] = [self.Extra1]
        return args, kwargs

    def get_dog_exit_args_kwargs(self):
        args, kwargs = super(CrossPhaseExtraAttributesTestCase, self).get_dog_exit_args_kwargs()
        kwargs['extras'] = [self.Extra1]
        return args, kwargs

    def get_dog_error_args_kwargs(self):
        args, kwargs = super(CrossPhaseExtraAttributesTestCase, self).get_dog_error_args_kwargs()
        kwargs['extras'] = [self.Extra1]
        return args, kwargs

    def check_enter_record(self, record):
        super(CrossPhaseExtraAttributesTestCase, self).check_enter_record(record)
        if not hasattr(record, 'complicated_calculation'):
            self.fail("enter log record does not have 'complicated_calculation' attribute")
        if not hasattr(record, 'another_complicated_calculation'):
            self.fail("enter log record does not have 'another_complicated_calculation' attribute")

        self.assertEqual(self.computed_value, record.complicated_calculation)
        self.assertEqual(self.another_computed_value, record.another_complicated_calculation)

    def check_inner_record(self, record):
        super(CrossPhaseExtraAttributesTestCase, self).check_inner_record(record)
        if hasattr(record, 'complicated_calculation'):
            self.fail("inner log record has 'complicated_calculation' attribute")
        if hasattr(record, 'another_complicated_calculation'):
            self.fail("inner log record has 'another_complicated_calculation' attribute")

    def check_exit_record(self, record):
        super(CrossPhaseExtraAttributesTestCase, self).check_exit_record(record)
        if not hasattr(record, 'complicated_calculation'):
            self.fail("exit log record does not have 'complicated_calculation' attribute")
        if not hasattr(record, 'another_complicated_calculation'):
            self.fail("exit log record does not have 'another_complicated_calculation' attribute")

        self.assertEqual(self.computed_value, record.complicated_calculation)
        self.assertEqual(self.another_computed_value, record.another_complicated_calculation)

    def check_error_record(self, record):
        super(CrossPhaseExtraAttributesTestCase, self).check_error_record(record)
        if not hasattr(record, 'complicated_calculation'):
            self.fail("error log record does not have 'complicated_calculation' attribute")
        if not hasattr(record, 'another_complicated_calculation'):
            self.fail("error log record does not have 'another_complicated_calculation' attribute")

        self.assertEqual(self.computed_value, record.complicated_calculation)
        self.assertEqual(self.another_computed_value, record.another_complicated_calculation)


class WrongTypeCrossPhaseExtraAttributesTestCase(DogTestPhasesMixin, unittest.TestCase):
    """Test that only sequence are accepted as cross-phase extras."""
    enter_init_fails = True
    exit_init_fails = True
    error_init_fails = True
    enter_init_fail_exception = TypeError
    exit_init_fail_exception = TypeError
    error_init_fail_exception = TypeError

    def get_dog_enter_args_kwargs(self):
        args, kwargs = super(WrongTypeCrossPhaseExtraAttributesTestCase, self).get_dog_enter_args_kwargs()
        kwargs['extras'] = object()
        return args, kwargs

    def get_dog_exit_args_kwargs(self):
        args, kwargs = super(WrongTypeCrossPhaseExtraAttributesTestCase, self).get_dog_exit_args_kwargs()
        kwargs['extras'] = object()
        return args, kwargs

    def get_dog_error_args_kwargs(self):
        args, kwargs = super(WrongTypeCrossPhaseExtraAttributesTestCase, self).get_dog_error_args_kwargs()
        kwargs['extras'] = object()
        return args, kwargs


class WrongUsageCrossPhaseExtraAttributesTestCase(DogTestPhasesMixin, unittest.TestCase):
    """Test that cross-phase extras can only be passed in as a part of a sequence."""
    enter_init_fails = True
    exit_init_fails = True
    error_init_fails = True
    enter_init_fail_exception = TypeError
    exit_init_fail_exception = TypeError
    error_init_fail_exception = TypeError

    computed_value = 'my computed value'
    another_computed_value = 'my other computed value'

    class Extra(ExtraAttributes):
        def complicated_calculation(self):
            return CrossPhaseExtraAttributesTestCase.computed_value

        def another_complicated_calculation(self):
            return CrossPhaseExtraAttributesTestCase.another_computed_value

    def get_dog_enter_args_kwargs(self):
        args, kwargs = super(WrongUsageCrossPhaseExtraAttributesTestCase, self).get_dog_enter_args_kwargs()
        kwargs['extras'] = self.Extra
        return args, kwargs

    def get_dog_exit_args_kwargs(self):
        args, kwargs = super(WrongUsageCrossPhaseExtraAttributesTestCase, self).get_dog_exit_args_kwargs()
        kwargs['extras'] = self.Extra
        return args, kwargs

    def get_dog_error_args_kwargs(self):
        args, kwargs = super(WrongUsageCrossPhaseExtraAttributesTestCase, self).get_dog_error_args_kwargs()
        kwargs['extras'] = self.Extra
        return args, kwargs


class WrongTypeCrossPhaseExtraAttributesTestCase2(DogTestPhasesMixin, unittest.TestCase):
    """Test that when passing in a sequence as a cross-phase extra, the contents of the sequence are checked."""
    enter_init_fails = True
    exit_init_fails = True
    error_init_fails = True
    enter_init_fail_exception = TypeError
    exit_init_fail_exception = TypeError
    error_init_fail_exception = TypeError

    def get_dog_enter_args_kwargs(self):
        args, kwargs = super(WrongTypeCrossPhaseExtraAttributesTestCase2, self).get_dog_enter_args_kwargs()
        kwargs['extras'] = [object()]
        return args, kwargs

    def get_dog_exit_args_kwargs(self):
        args, kwargs = super(WrongTypeCrossPhaseExtraAttributesTestCase2, self).get_dog_exit_args_kwargs()
        kwargs['extras'] = [object()]
        return args, kwargs

    def get_dog_error_args_kwargs(self):
        args, kwargs = super(WrongTypeCrossPhaseExtraAttributesTestCase2, self).get_dog_error_args_kwargs()
        kwargs['extras'] = [object()]
        return args, kwargs


class MultipleCrossPhaseExtraAttributesTestCase(DogTestPhasesMixin, unittest.TestCase):
    """Check that supplying several cross-phase extras works as expected"""
    computed_value = 'my computed value'
    alternative_computed_value = 'alternative computed value'
    another_computed_value = 'my other computed value'

    class Extra1(ExtraAttributes):
        def complicated_calculation(self):
            return MultipleCrossPhaseExtraAttributesTestCase.computed_value

        def another_complicated_calculation(self):
            return MultipleCrossPhaseExtraAttributesTestCase.another_computed_value

    class Extra2(ExtraAttributes):
        def complicated_calculation(self):
            return MultipleCrossPhaseExtraAttributesTestCase.alternative_computed_value

    def get_dog_enter_args_kwargs(self):
        args, kwargs = super(MultipleCrossPhaseExtraAttributesTestCase, self).get_dog_enter_args_kwargs()
        kwargs['extras'] = [self.Extra1, self.Extra2]
        return args, kwargs

    def get_dog_exit_args_kwargs(self):
        args, kwargs = super(MultipleCrossPhaseExtraAttributesTestCase, self).get_dog_exit_args_kwargs()
        kwargs['extras'] = [self.Extra1, self.Extra2]
        return args, kwargs

    def get_dog_error_args_kwargs(self):
        args, kwargs = super(MultipleCrossPhaseExtraAttributesTestCase, self).get_dog_error_args_kwargs()
        kwargs['extras'] = [self.Extra1, self.Extra2]
        return args, kwargs

    def check_enter_record(self, record):
        super(MultipleCrossPhaseExtraAttributesTestCase, self).check_enter_record(record)
        if not hasattr(record, 'complicated_calculation'):
            self.fail("enter log record does not have 'complicated_calculation' attribute")
        if not hasattr(record, 'another_complicated_calculation'):
            self.fail("enter log record does not have 'another_complicated_calculation' attribute")

        self.assertEqual(self.alternative_computed_value, record.complicated_calculation)
        self.assertEqual(self.another_computed_value, record.another_complicated_calculation)

    def check_inner_record(self, record):
        super(MultipleCrossPhaseExtraAttributesTestCase, self).check_inner_record(record)
        if hasattr(record, 'complicated_calculation'):
            self.fail("inner log record has 'complicated_calculation' attribute")
        if hasattr(record, 'another_complicated_calculation'):
            self.fail("inner log record has 'another_complicated_calculation' attribute")

    def check_exit_record(self, record):
        super(MultipleCrossPhaseExtraAttributesTestCase, self).check_exit_record(record)
        if not hasattr(record, 'complicated_calculation'):
            self.fail("exit log record does not have 'complicated_calculation' attribute")
        if not hasattr(record, 'another_complicated_calculation'):
            self.fail("exit log record does not have 'another_complicated_calculation' attribute")

        self.assertEqual(self.alternative_computed_value, record.complicated_calculation)
        self.assertEqual(self.another_computed_value, record.another_complicated_calculation)

    def check_error_record(self, record):
        super(MultipleCrossPhaseExtraAttributesTestCase, self).check_error_record(record)
        if not hasattr(record, 'complicated_calculation'):
            self.fail("error log record does not have 'complicated_calculation' attribute")
        if not hasattr(record, 'another_complicated_calculation'):
            self.fail("error log record does not have 'another_complicated_calculation' attribute")

        self.assertEqual(self.alternative_computed_value, record.complicated_calculation)
        self.assertEqual(self.another_computed_value, record.another_complicated_calculation)


class CrossPhaseAndPerPhaseExtraAttributesTestCase(DogTestPhasesMixin, unittest.TestCase):
    """Test that passing in both cross-phase extras, ad per-phase extras, works as expected.

    Specifically, we check that per-phase extras override the attributes
    provided by the cross-phase extras.
    """
    computed_value = 'my computed value'
    alternative_computed_value = 'alternative computed value'
    another_computed_value = 'my other computed value'

    class Extra1(ExtraAttributes):
        def complicated_calculation(self):
            return CrossPhaseAndPerPhaseExtraAttributesTestCase.computed_value

        def another_complicated_calculation(self):
            return CrossPhaseAndPerPhaseExtraAttributesTestCase.another_computed_value

    class Extra2(ExtraAttributes):
        def complicated_calculation(self):
            return CrossPhaseAndPerPhaseExtraAttributesTestCase.alternative_computed_value

    def get_dog_enter_args_kwargs(self):
        args, kwargs = super(CrossPhaseAndPerPhaseExtraAttributesTestCase, self).get_dog_enter_args_kwargs()
        kwargs['extras'] = [self.Extra1]
        return args, kwargs

    def get_dog_exit_args_kwargs(self):
        args, kwargs = super(CrossPhaseAndPerPhaseExtraAttributesTestCase, self).get_dog_exit_args_kwargs()
        kwargs['extras'] = [self.Extra1]
        return args, kwargs

    def get_dog_error_args_kwargs(self):
        args, kwargs = super(CrossPhaseAndPerPhaseExtraAttributesTestCase, self).get_dog_error_args_kwargs()
        kwargs['extras'] = [self.Extra1]
        return args, kwargs

    def get_dog_enter_spec(self):
        return [
            self.enter_message,
            self.Extra2,
        ]

    def get_dog_exit_spec(self):
        return [
            self.exit_message,
            self.Extra2,
        ]

    def get_dog_error_spec(self):
        return [
            self.error_message,
            self.Extra2,
        ]

    def check_enter_record(self, record):
        super(CrossPhaseAndPerPhaseExtraAttributesTestCase, self).check_enter_record(record)
        if not hasattr(record, 'complicated_calculation'):
            self.fail("enter log record does not have 'complicated_calculation' attribute")
        if not hasattr(record, 'another_complicated_calculation'):
            self.fail("enter log record does not have 'another_complicated_calculation' attribute")

        self.assertEqual(self.alternative_computed_value, record.complicated_calculation)
        self.assertEqual(self.another_computed_value, record.another_complicated_calculation)

    def check_inner_record(self, record):
        super(CrossPhaseAndPerPhaseExtraAttributesTestCase, self).check_inner_record(record)
        if hasattr(record, 'complicated_calculation'):
            self.fail("inner log record has 'complicated_calculation' attribute")
        if hasattr(record, 'another_complicated_calculation'):
            self.fail("inner log record has 'another_complicated_calculation' attribute")

    def check_exit_record(self, record):
        super(CrossPhaseAndPerPhaseExtraAttributesTestCase, self).check_exit_record(record)
        if not hasattr(record, 'complicated_calculation'):
            self.fail("exit log record does not have 'complicated_calculation' attribute")
        if not hasattr(record, 'another_complicated_calculation'):
            self.fail("exit log record does not have 'another_complicated_calculation' attribute")

        self.assertEqual(self.alternative_computed_value, record.complicated_calculation)
        self.assertEqual(self.another_computed_value, record.another_complicated_calculation)

    def check_error_record(self, record):
        super(CrossPhaseAndPerPhaseExtraAttributesTestCase, self).check_error_record(record)
        if not hasattr(record, 'complicated_calculation'):
            self.fail("error log record does not have 'complicated_calculation' attribute")
        if not hasattr(record, 'another_complicated_calculation'):
            self.fail("error log record does not have 'another_complicated_calculation' attribute")

        self.assertEqual(self.alternative_computed_value, record.complicated_calculation)
        self.assertEqual(self.another_computed_value, record.another_complicated_calculation)

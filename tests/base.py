import unittest
import logging

from dogging import *

from .configure_logging import handler

__all__ = [
    'DogTestBaseMixin',
    'DogTestPhasesMixin',
    'DogTestPhasesSpecialArgNamesMixin',
]

logger = logging.getLogger(__name__)


def list_log_records_attr(attr):
    return [getattr(record, attr) for record in handler.records]


class DogTestBaseMixin(object):
    def tearDown(self):
        """
        :type self: DogTestBaseMixin | unittest.TestCase
        """
        try:
            self.check_log_record_logging_levels()
        finally:
            handler.flush()
        super(DogTestBaseMixin, self).tearDown()

    # Default expected for log records, unless otherwise specified
    logging_level = logging.INFO

    def check_log_record_logging_levels(self):
        """Check that all log records have the expected log level.

        :type self: DogTestBaseMixin | unittest.TestCase
        """
        self.assertTrue(all(
            level == self.logging_level
            for level
            in list_log_records_attr('levelno')
        ))


class DogTestPhasesMixin(DogTestBaseMixin):
    """Mixin class for simpler, shorter dog TestCase-s.

    This class implements the common logic of all tests of log messages for
    different phases, combinations of phases, and multiple function decoration.
    The default behaviour for this mixin is just testing that simple log
    messages with a plain string-specification work, but a bunch of hooks are
    provided to enable subclasses to specify only what is special about the
    case they are testing.
    """
    # Boolean: does test-case fail in each logging phase.
    enter_init_fails = False
    exit_init_fails = False
    error_init_fails = False
    enter_decoration_fails = False
    exit_decoration_fails = False
    error_decoration_fails = False

    enter_init_fail_exception = None
    exit_init_fail_exception = None
    error_init_fail_exception = None
    enter_decoration_fail_exception = None
    exit_decoration_fail_exception = None
    error_decoration_fail_exception = None

    enter_message = 'I am entering'
    inner_message = 'inside'
    exit_message = 'I am exiting'
    error_message = 'I raised an exception'
    enter_expected_log_message = enter_message
    inner_expected_log_message = inner_message
    exit_expected_log_message = exit_message
    error_expected_log_message = error_message

    return_value = object()
    # Completely unrelated error type on purpose.
    exception_value = ZeroDivisionError('Test exception message')

    def get_dog_enter_spec(self):
        return self.enter_message

    def get_dog_exit_spec(self):
        return self.exit_message

    def get_dog_error_spec(self):
        return self.error_message

    def get_dog_enter_args_kwargs(self):
        return (), {'enter': self.get_dog_enter_spec()}

    def get_dog_exit_args_kwargs(self):
        return (), {'exit': self.get_dog_exit_spec()}

    def get_dog_error_args_kwargs(self):
        return (), {'error': self.get_dog_error_spec()}

    def get_dog_enter_exit_args_kwargs(self):
        args, kwargs = self.get_dog_enter_args_kwargs()
        more_args, more_kwargs = self.get_dog_exit_args_kwargs()

        args = args + more_args
        kwargs = kwargs.copy()
        kwargs.update(more_kwargs)
        return args, kwargs

    def get_dog_enter_error_args_kwargs(self):
        args, kwargs = self.get_dog_enter_args_kwargs()
        more_args, more_kwargs = self.get_dog_error_args_kwargs()

        args = args + more_args
        kwargs = kwargs.copy()
        kwargs.update(more_kwargs)
        return args, kwargs

    def get_return_value(self):
        return self.return_value

    def get_exception_value(self):
        return self.exception_value

    def get_function(self, work):
        def foo():
            return work()
        return foo

    def enter_case_function_behaviour(self):
        logger.log(self.logging_level, self.inner_message)
        return self.get_return_value()

    def exit_case_function_behaviour(self):
        logger.log(self.logging_level, self.inner_message)
        return self.get_return_value()

    def error_case_function_behaviour(self):
        logger.log(self.logging_level, self.inner_message)
        raise self.get_exception_value()

    def enter_exit_case_function_behaviour(self):
        logger.log(self.logging_level, self.inner_message)
        return self.get_return_value()

    def enter_error_case_function_behaviour(self):
        logger.log(self.logging_level, self.inner_message)
        raise self.get_exception_value()

    def decorate_function(self, decorator, func):
        return decorator(func)

    def call_function(self, func):
        return func()

    def check_enter_message(self, message):
        """
        :type self: DogTestPhasesMixin | unittest.TestCase
        :type message: str
        """
        self.assertEqual(self.enter_expected_log_message, message, 'enter log message is incorrect')

    def check_inner_message(self, message):
        """
        :type self: DogTestPhasesMixin | unittest.TestCase
        :type message: str
        """
        self.assertEqual(self.inner_expected_log_message, message, 'inner log message is incorrect')

    def check_exit_message(self, message):
        """
        :type self: DogTestPhasesMixin | unittest.TestCase
        :type message: str
        """
        self.assertEqual(self.exit_expected_log_message, message, 'exit log message is incorrect')

    def check_error_message(self, message):
        """
        :type self: DogTestPhasesMixin | unittest.TestCase
        :type message: str
        """
        self.assertEqual(self.error_expected_log_message, message, 'error log message is incorrect')

    def check_enter_record(self, record):
        """
        :type self: DogTestPhasesMixin | unittest.TestCase
        """
        self.assertTrue(hasattr(record, 'message'), 'Failed to format enter log message.')
        self.check_enter_message(record.message)

    def check_inner_record(self, record):
        """
        :type self: DogTestPhasesMixin | unittest.TestCase
        """
        self.assertTrue(hasattr(record, 'message'), 'Failed to format inner log message.')
        self.check_inner_message(record.message)

    def check_exit_record(self, record):
        """
        :type self: DogTestPhasesMixin | unittest.TestCase
        """
        self.assertTrue(hasattr(record, 'message'), 'Failed to format exit log message.')
        self.check_exit_message(record.message)

    def check_error_record(self, record):
        """
        :type self: DogTestPhasesMixin | unittest.TestCase
        """
        self.assertTrue(hasattr(record, 'message'), 'Failed to format error log message.')
        self.check_error_message(record.message)

    # Test methods:

    def test_enter(self):
        """
        :type self: DogTestPhasesMixin | unittest.TestCase
        """
        args, kwargs = self.get_dog_enter_args_kwargs()

        if self.enter_init_fails:
            with self.assertRaises(self.enter_init_fail_exception):
                dog(*args, **kwargs)
            return
        else:
            dog_instance = dog(*args, **kwargs)

        func = self.get_function(self.enter_case_function_behaviour)

        if self.enter_decoration_fails:
            with self.assertRaises(self.enter_decoration_fail_exception):
                self.decorate_function(dog_instance, func)
            return
        else:
            func = self.decorate_function(dog_instance, func)

        ret = self.call_function(func)

        self.assertIs(
            self.get_return_value(), ret,
            'the decorated function did not return the expected value'
        )
        records = handler.records
        self.assertEqual(2, len(records), 'unexpected amount of log records generated')
        self.check_enter_record(records[0])
        self.check_inner_record(records[1])

    def test_exit(self):
        """
        :type self: DogTestPhasesMixin | unittest.TestCase
        """
        args, kwargs = self.get_dog_exit_args_kwargs()

        if self.exit_init_fails:
            with self.assertRaises(self.exit_init_fail_exception):
                dog(*args, **kwargs)
            return
        else:
            dog_instance = dog(*args, **kwargs)

        func = self.get_function(self.exit_case_function_behaviour)

        if self.exit_decoration_fails:
            with self.assertRaises(self.exit_decoration_fail_exception):
                self.decorate_function(dog_instance, func)
            return
        else:
            func = self.decorate_function(dog_instance, func)

        ret = self.call_function(func)

        self.assertIs(
            self.get_return_value(), ret,
            'the decorated function did not return the expected value'
        )
        records = handler.records
        self.assertEqual(2, len(records), 'unexpected amount of log records generated')
        self.check_inner_record(records[0])
        self.check_exit_record(records[1])

    def test_error(self):
        """
        :type self: DogTestPhasesMixin | unittest.TestCase
        """
        args, kwargs = self.get_dog_error_args_kwargs()

        if self.error_init_fails:
            with self.assertRaises(self.error_init_fail_exception):
                dog(*args, **kwargs)
            return
        else:
            dog_instance = dog(*args, **kwargs)

        func = self.get_function(self.error_case_function_behaviour)

        if self.error_decoration_fails:
            with self.assertRaises(self.error_decoration_fail_exception):
                self.decorate_function(dog_instance, func)
            return
        else:
            func = self.decorate_function(dog_instance, func)

        expected_exception = self.get_exception_value()

        with self.assertRaises(type(expected_exception)) as cm:
            self.call_function(func)

        self.assertIs(
            expected_exception, cm.exception,
            'the exception raised by the decorated function is not the same exception caught in the test'
        )
        records = handler.records
        self.assertEqual(2, len(records), 'unexpected amount of log records generated')
        self.check_inner_record(records[0])
        self.check_error_record(records[1])

    def test_enter_exit(self):
        """
        :type self: DogTestPhasesMixin | unittest.TestCase
        """
        args, kwargs = self.get_dog_enter_exit_args_kwargs()

        if self.enter_init_fails or self.exit_init_fails:
            with self.assertRaises((self.enter_init_fail_exception, self.exit_init_fail_exception)):
                dog(*args, **kwargs)
            return
        else:
            dog_instance = dog(*args, **kwargs)

        func = self.get_function(self.enter_exit_case_function_behaviour)

        if self.enter_decoration_fails or self.exit_decoration_fails:
            with self.assertRaises((self.enter_decoration_fail_exception, self.exit_decoration_fail_exception)):
                self.decorate_function(dog_instance, func)
            return
        else:
            func = self.decorate_function(dog_instance, func)

        ret = self.call_function(func)

        self.assertIs(
            self.get_return_value(), ret,
            'the decorated function did not return the expected value'
        )
        records = handler.records
        self.assertEqual(3, len(records), 'unexpected amount of log records generated')
        self.check_enter_record(records[0])
        self.check_inner_record(records[1])
        self.check_exit_record(records[2])

    def test_enter_error(self):
        """
        :type self: DogTestPhasesMixin | unittest.TestCase
        """
        args, kwargs = self.get_dog_enter_error_args_kwargs()

        if self.enter_init_fails or self.error_init_fails:
            with self.assertRaises((self.enter_init_fail_exception, self.error_init_fail_exception)):
                dog(*args, **kwargs)
            return
        else:
            dog_instance = dog(*args, **kwargs)

        func = self.get_function(self.enter_error_case_function_behaviour)

        if self.enter_decoration_fails or self.error_decoration_fails:
            with self.assertRaises((self.enter_decoration_fail_exception, self.error_decoration_fail_exception)):
                self.decorate_function(dog_instance, func)
            return
        else:
            func = self.decorate_function(dog_instance, func)

        expected_exception = self.get_exception_value()

        with self.assertRaises(type(expected_exception)) as cm:
            self.call_function(func)

        self.assertIs(
            expected_exception, cm.exception,
            'the exception raised by the decorated function is not the same exception caught in the test'
        )
        records = handler.records
        self.assertEqual(3, len(records), 'unexpected amount of log records generated')
        self.check_enter_record(records[0])
        self.check_inner_record(records[1])
        self.check_error_record(records[2])

    # Double decoration tests

    def test_double_enter(self):
        """
        :type self: DogTestPhasesMixin | unittest.TestCase
        """
        args, kwargs = self.get_dog_enter_args_kwargs()

        if self.enter_init_fails:
            with self.assertRaises(self.enter_init_fail_exception):
                dog(*args, **kwargs)
            return
        else:
            dog_instance = dog(*args, **kwargs)

        func = self.get_function(self.enter_case_function_behaviour)

        if self.enter_decoration_fails:
            with self.assertRaises(self.enter_decoration_fail_exception):
                self.decorate_function(dog_instance, func)
            return
        else:
            func = self.decorate_function(dog_instance, func)
        func = self.decorate_function(dog_instance, func)

        ret = self.call_function(func)

        self.assertIs(
            self.get_return_value(), ret,
            'the decorated function did not return the expected value'
        )
        records = handler.records
        self.assertEqual(3, len(records), 'unexpected amount of log records generated')
        self.check_enter_record(records[0])
        self.check_enter_record(records[1])
        self.check_inner_record(records[2])

    def test_double_exit(self):
        """
        :type self: DogTestPhasesMixin | unittest.TestCase
        """
        args, kwargs = self.get_dog_exit_args_kwargs()

        if self.exit_init_fails:
            with self.assertRaises(self.exit_init_fail_exception):
                dog(*args, **kwargs)
            return
        else:
            dog_instance = dog(*args, **kwargs)

        func = self.get_function(self.exit_case_function_behaviour)

        if self.exit_decoration_fails:
            with self.assertRaises(self.exit_decoration_fail_exception):
                self.decorate_function(dog_instance, func)
            return
        else:
            func = self.decorate_function(dog_instance, func)
        func = self.decorate_function(dog_instance, func)

        ret = self.call_function(func)

        self.assertIs(
            self.get_return_value(), ret,
            'the decorated function did not return the expected value'
        )
        records = handler.records
        self.assertEqual(3, len(records), 'unexpected amount of log records generated')
        self.check_inner_record(records[0])
        self.check_exit_record(records[1])
        self.check_exit_record(records[2])

    def test_double_error(self):
        """
        :type self: DogTestPhasesMixin | unittest.TestCase
        """
        args, kwargs = self.get_dog_error_args_kwargs()

        if self.error_init_fails:
            with self.assertRaises(self.error_init_fail_exception):
                dog(*args, **kwargs)
            return
        else:
            dog_instance = dog(*args, **kwargs)

        func = self.get_function(self.error_case_function_behaviour)

        if self.error_decoration_fails:
            with self.assertRaises(self.error_decoration_fail_exception):
                self.decorate_function(dog_instance, func)
            return
        else:
            func = self.decorate_function(dog_instance, func)
        func = self.decorate_function(dog_instance, func)

        expected_exception = self.get_exception_value()

        with self.assertRaises(type(expected_exception)) as cm:
            self.call_function(func)

        self.assertIs(
            expected_exception, cm.exception,
            'the exception raised by the decorated function is not the same exception caught in the test'
        )
        records = handler.records
        self.assertEqual(3, len(records), 'unexpected amount of log records generated')
        self.check_inner_record(records[0])
        self.check_error_record(records[1])
        self.check_error_record(records[2])

    def test_double_enter_exit(self):
        """
        :type self: DogTestPhasesMixin | unittest.TestCase
        """
        args, kwargs = self.get_dog_enter_exit_args_kwargs()

        if self.enter_init_fails or self.exit_init_fails:
            with self.assertRaises((self.enter_init_fail_exception, self.exit_init_fail_exception)):
                dog(*args, **kwargs)
            return
        else:
            dog_instance = dog(*args, **kwargs)

        func = self.get_function(self.enter_exit_case_function_behaviour)

        if self.enter_decoration_fails or self.exit_decoration_fails:
            with self.assertRaises((self.enter_decoration_fail_exception, self.exit_decoration_fail_exception)):
                self.decorate_function(dog_instance, func)
            return
        else:
            func = self.decorate_function(dog_instance, func)
        func = self.decorate_function(dog_instance, func)

        ret = self.call_function(func)

        self.assertIs(
            self.get_return_value(), ret,
            'the decorated function did not return the expected value'
        )
        records = handler.records
        self.assertEqual(5, len(records), 'unexpected amount of log records generated')
        self.check_enter_record(records[0])
        self.check_enter_record(records[1])
        self.check_inner_record(records[2])
        self.check_exit_record(records[3])
        self.check_exit_record(records[4])

    def test_double_enter_error(self):
        """
        :type self: DogTestPhasesMixin | unittest.TestCase
        """
        args, kwargs = self.get_dog_enter_error_args_kwargs()

        if self.enter_init_fails or self.error_init_fails:
            with self.assertRaises((self.enter_init_fail_exception, self.error_init_fail_exception)):
                dog(*args, **kwargs)
            return
        else:
            dog_instance = dog(*args, **kwargs)

        func = self.get_function(self.enter_error_case_function_behaviour)

        if self.enter_decoration_fails or self.error_decoration_fails:
            with self.assertRaises((self.enter_decoration_fail_exception, self.error_decoration_fail_exception)):
                self.decorate_function(dog_instance, func)
            return
        else:
            func = self.decorate_function(dog_instance, func)
        func = self.decorate_function(dog_instance, func)

        expected_exception = self.get_exception_value()

        with self.assertRaises(type(expected_exception)) as cm:
            self.call_function(func)

        self.assertIs(
            expected_exception, cm.exception,
            'the exception raised by the decorated function is not the same exception caught in the test'
        )
        records = handler.records
        self.assertEqual(5, len(records), 'unexpected amount of log records generated')
        self.check_enter_record(records[0])
        self.check_enter_record(records[1])
        self.check_inner_record(records[2])
        self.check_error_record(records[3])
        self.check_error_record(records[4])


class DogTestPhasesPrefixArgNamesMixin(DogTestPhasesMixin):
    arg_name_prefix = None
    arg_name = None
    replacement_field_modifier = ''

    def setUp(self):
        """
        :type self: DogTestPhasesPrefixArgNamesMixin | unittest.TestCase
        """
        super(DogTestPhasesPrefixArgNamesMixin, self).setUp()
        self.enter_message = '{{{}{}{}}}'.format(
            self.arg_name_prefix,
            self.arg_name,
            self.replacement_field_modifier,
        )
        self.exit_message = self.enter_message
        self.error_message = self.enter_message


class DogTestPhasesSpecialArgNamesMixin(DogTestPhasesPrefixArgNamesMixin):
    arg_name_prefix = '@'

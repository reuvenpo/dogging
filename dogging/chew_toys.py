"""Utilities and helper functions

This module contains all miscellaneous tools and functions.
"""
__all__ = [
    '_raise',
    'filter2',
    'is_int_like',
    'unwrap',
    'lambda_dict',
    'run_once',
]


def _raise(exception):
    raise exception


def filter2(predicate, it):
    """Split the iterable ``it`` into two lists based on the function ``func``.

    This function is a lot like the builtin ``filter``, except that instead of
    throwing out the items that don't match, it splits the otiginal iterable
    into two lists: one of matching objects and one of the other objects.
    >>> filter2((lambda x: x > 5), range(10))
    ([6, 7, 8, 9], [0, 1, 2, 3, 4, 5])
    """
    yes = []
    no = []
    append = (no.append, yes.append)
    for obj in it:
        append[bool(predicate(obj))](obj)  # bool is a subclass of int

    return yes, no


def is_int_like(obj):
    """Can the object be turned into an integer?

    Returns True or False indicating if the object can be turned into an int.
    """
    try:
        int(obj)
    except StandardError:
        return False
    return True


def unwrap(func):
    """Unwrap all layers of function wrappers.

    This is a simple version of Python3's ``inspect.unwrap()``
    """
    while True:
        try:
            func = func.__wrapped__
        except AttributeError:
            break
    return func


def unpack_lambda(func):
    return func()


@unpack_lambda
def lambda_dict():
    constant = {}

    def _lambda_dict():
        """Return an empty dictionary."""
        return constant
    return _lambda_dict


# WARNING not thread safe because we don't need it to be.
def run_once(func):
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

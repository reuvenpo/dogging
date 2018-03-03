=====================================
Dogging - a Pythonista's best friend!
=====================================
-------------------------------------
Dogging stands for Decorator Logging!
-------------------------------------

.. contents::
    :depth: 2


Overview
========

``dog`` is a highly flexible and featureful logging function decorator.
The aim of ``dog`` is to allow the separation of an application's
logging from the stuff it's actually trying to do.

Using ``dog``, you can concisely define most of the logging you want
for a function, OUTSIDE the body of the function itself.
``dog`` **allows you to reference the function's parameters, return value,
a lot of valuable metadata, and even custom values, all of this using
the** `new "{}" style of formatting`__. The library is implemented in
such a way that as many operations as possible are done lazily, to reduce
overhead when log messages are not actually emitted, or even when you're
just not using all the features. Additionally, a lot of validation is
performed so that if the parameters you pass to the decorator don't make
sense, it fails early with an informative error message telling you what
you did wrong.

__ `python format string`_

Dogging defines three logging "phases": ``enter``, ``exit``, and ``error``:

``enter``
    logging done just before executing the function.

``exit``
    logging done just after the function returns.

``error``
    logging done just after the function raises an exception.

All logging phases have a lot of the same capabilities, but each phase
has additional features that only make sense for it.
For example, the ``exit`` phase may reference the function's return value.
Each ``dog`` may define up to one message for each phase, but it may
define messages for all phases, and dogs may even be stacked for cases
where you wish to perform richer logging to several loggers or for
different conditions.


Examples
========

Simple Usage
------------

Say you had a function ``be_cool``, which took some stuff as arguments,
did some cool stuff, and then returned some result. You'd probably write
your function something like so:

.. code:: python

    def be_cool(some, stuff):
        do(some)
        cool(stuff)

        if is_cool(stuff):
            return stuff
        else:
            return not stuff

Now, let's say you wanted to add logging to this function. You'd have to
mix in a bunch of extra logic in your code, just to make the logging work as
you want it to.

.. code:: python

    import logging
    log = logging.getLogger(__name__)

    def be_cool(some, stuff):
        log.info('gonna do some cool stuff using %s and %s!', some, stuff)
        try:
            do(some)
            cool(stuff)
        except NotCoolError as e:
            log.error('could not do some cool stuff: %s', e.message)
            raise

        if is_cool(stuff):
            return_value = stuff
        else:
            return_value = not stuff

        log.info('after doing some cool stuff, we have %s', return_value)

That's a lot of noise. It can become difficult to see which lines are actually
doing anything useful here. There's also that eternal ``getLogger()``
boilerplate at the start of each file... What if we could just...

.. code:: python

    from dogging import *

    @dog(
        'gonna do some cool stuff using {some} and {stuff}!',
        'after doing some cool stuff, we have {@ret}',
        [ERROR, 'could not do some cool stuff: {@err.message}'],
        catch=NotCoolError,
    )
    def be_cool(some, stuff):
        do(some)
        cool(stuff)

        if is_cool(stuff):
            return stuff
        else:
            return not stuff

Well, whaddayaknow ;)

More Advanced Examples
----------------------

`In format-string-syntax jargon`__, given a field ``{foo.bar[baz]!r:123}``
The ``foo`` part is called the ``arg name``. In the `Simple Usage`_
examples, we saw we can reference parameter names by just naming them
as a field's arg-name, and that we could access all sorts of metadata
by invoking arg-names that are prefixed (by convention) with a "``@``".

__ `python format string`_

There are several such, so called "special arg names" you have access to:

==========  =====  ==== ========= ===========
name        enter  exit error     description
==========  =====  ==== ========= ===========
@pathname   O      O    O         The name of the file where the function was
                                  **defined**.
@line       O      O    O         The line in the file where the function was
                                  **defined**.
@logger     O      O    O         The logger used for logging.
@func       O      O    O         The function *object*. Use ``@func.__name__``
                                  To reference its name.
@time       X      O    O         The time from the function's start to finish,
                                  or error.
@ret        X      O    O [#]_    The function's return value.
@err        X      X    O         The Exception Object raised by the function.
@traceback  X      X    O         A list of the form
                                  ``[(filename, line, function_name), ...]``
                                  Equivalent to the values you'd find in a
                                  printed traceback, in the same order.
==========  =====  ==== ========= ===========

.. [#] Under some conditions You may reference the ``@ret`` special
       reference in the error phase. Consult the full documentation.

Defining custom dynamic references
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

We can also reference arbitrary values that will be computed per log message
by defining them, passing them as part of the specification of a logging
phase, and then referencing them by their name, prefixed with "``>``" :

.. code:: python

    from dogging import *

    class FooComputer(ComputedArgNames):
        # Request access to the 'bar' and '@ret' arg-names.
        __args__ = ['bar', '@ret']

        def triple_bar(self):
            return self._args['bar'] * 3

        def half_ret(self):
            return self._args['@ret'] / 2

    @dog(
        ['{bar} * 3 = {>triple_bar}', FooComputer],
        ['{@ret} / 2 = {>half_ret}', FooComputer],
    )
    def foo(bar):
        # Your code here

You can define many such subclasses of ``ComputedArgNames``, and pass many
of them to a specific phase, or pass the same class to multiple phases
or dogs. Each time a log record is to be emitted, an instance of your class
will be created, and only the methods whose names have been invoked by the
format string of the current phase will be called.

Only methods that don't begin with an underscore ('_') are considered valid
targets of references, so you can safely name any methods that should never
be called directly with an underscore prefix.

This feature can be used to create completely dynamic log messages, completely
separately from the function you're logging, and even seperatly from any
specific instance of dog.

Different messages for different exceptions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: python

    from dogging import *

    @dog(
        # str(err) is the error message
        error='{@func.__name__} raised a KeyError: {@err}',
        catch=KeyError,
    )
    @dog(
        error='{@func.__name__} raised a ValueError or AttributeError: {@err}',
        catch=(ValueError, AttributeError),
    )
    def foo(bar, **baz):
        return bar(**baz)  # Whatever

    # A nice hack is {err.__class__.__name__} to get the exception type name,
    # or just doing {err!r} to get the repr of the exception

There are quite a few more interesting features available. This was just a
small introductory taste of the features i find most compelling and interesting


Why Dogging?
============

There are quite a few python logging decorators out there, just search
`PyPI`_ for "log decorator". Many of the solutions currently available
automatically generate log messages, whose format you might not agree
with. Others bombard you with profusely granular information about
everything going on with the function in a highly technical format.
Many others do follow the "phase" paradigm, and let you to specify a
logging message per phase, but even the ones that allow you to specify
a format string instead of just a static message, don't give you much
flexibility in terms of access to metadata, or completely dynamic custom
content.

Dogging provides the following features that i find particularly useful:

* Concise format-string definition of log messages
* Definition of all logging phases in a single decorator, further
  reducing overhead.
* Simple definition of the log-level per phase.
* Syntactic difference between function-parameter references,
  metadata(special arg-names) and custom values defined by the user,
  used strictly for logging.
* Definition of custom extra-attributes assigned to the log-records,
  separately from the log message.
* Validation of the format strings and all values used to construct
  a ``dog``, as well as the compatibility of the function being decorated
  with the decorating dog, to make sure your logging makes sense and that
  all references can be accounted for. If anything is wrong, it will fail
  before your  code runs, not while it's running.
* Lazy evaluation of all values during the logging process, in order
  to minimize overhead when not logging, and to only calculate values
  that are required to generate the log messages.


Contributing
============

If you wish to contribute or help the project in any way, feel free to open
`a GitHub issue`__ , or contact me by email with questions or suggestions for
improvement.

__ `github issues`_

.. _python format string: https://docs.python.org/2/library/string.html#format-string-syntax
.. _PyPI: https://pypi.python.org
.. _github issues: https://github.com/reuvenpo/dogging/issues

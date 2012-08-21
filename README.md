Schema validation just got Pythonic
===============================================================================

**schema** is a library for validating Python data structures, such as those
obtained from config-files, forms, external services or command-line
parsing, converted from JSON/YAML (or something else) to Python data-types.

Here is a quick example to get a feeling of **schema**:
validation of [create a gist](http://developer.github.com/v3/gists/)
request from github API.

```python
>>> from schema import Schema, And, Or, Use, Optional

>>> gist_schema = Schema({Optional('description'): str,
...                       'public': bool,
...                       'files': {str: {'content': str}}})

>>> gist = {'description': 'the description for this gist',
...         'public': True,
...         'files': {
...             'file1.txt': {
...               'content': 'String file contents'
...             }
...           }
...         }

>>> gist = gist_schema.validate(gist)

```

How `Schema` validates data
-------------------------------------------------------------------------------

### Types

If `Schema(...)` encounteres a type (such as `int`, `str`, `object`, etc),
it will check if correspoinding piece of data is instance of that type,
otherwise it will exit with error;

```python
>>> from schema import Schema

>>> Schema(int).validate(123)
123

>>> Schema(int).validate('123')
Traceback (most recent call last):
...
SchemaExit: '123' should be instance of <type 'int'>

>>> Schema(object).validate('hai')
'hai'

```

### Callables

If `Schema(...)` encounteres a callable (function, class, of object with
`__call__` method) it will call it, and if return value evaluates to
`True` it will continue validating, else -- it will exit with error.

```python
>>> import os

>>> Schema(os.path.exists).validate('./')
'./'

>>> Schema(os.path.exists).validate('./non-existent/')
Traceback (most recent call last):
...
SchemaExit: ...

>>> Schema(lambda n: n > 0).validate(123)
123

>>> Schema(lambda n: n > 0).validate(-12)
Traceback (most recent call last):
...
SchemaExit: ...

```

### Validatable

If `Schema(...)` encounteres an object with method `validate` it will run this
method on corresponding data as `data = smth.validate(data)`. This method may
raise `SchemaExit` exit-exception, which will tell `Schema` that that piece
of data is invalid, otherwise -- it will continue to validate.

As example, you can use `Use` for creating such objects. `Use` helps to use
a function or type to convert a value while validating it:

```python
>>> from schema import Use

>>> Schema(Use(int)).validate('123')
123

>>> Schema(Use(lambda f: open(f, 'a'))).validate('LICENSE-MIT')
<open file 'LICENSE-MIT', mode 'a' at 0x...>

```

Dropping the details, `Use` is basically:

```python
class Use(object):

    def __init__(self, callable_):
        self._callable = callable_

    def validate(self, data):
        try:
            return self._callable(data)
        except Exception as e:
            raise SchemaExit('%r raised %r' % (self._callable.__name__, e))
```

Now you can write your own validation-aware classes and data types.

### Lists, similar containers

If `Schema(...)` encounteres an instance of `list`, `tuple`, `set` or
`frozenset`, it will validate contents of corresponding data container against
schemas listed inside that container:


```python
>>> Schema([1, 0]).validate([1, 1, 0, 1])
[1, 1, 0, 1]

>>> Schema(set([int, float])).validate(set([5, 7, 8, 'not int or float here']))
Traceback (most recent call last):
...
SchemaExit: ...

```

### Dictionaries

If `Schema(...)` encounters an instance of `dict`, it will validate data
key-value pairs:

```python
>>> Schema({'name': str,
...         'age': lambda n: 18 < 99}).validate({'name': 'Sue', 'age': 28}) \
... == {'name': 'Sue', 'age': 28}
True

```

You can specify keys as schemas too:

```python
>>> schema = Schema({str: int,  # string keys should have integer values
...                  int: None})  # int keys should be always None

>>> data = schema.validate({'key1': 1, 'key2': 2,
...                         10: None, 20: None})

>>> schema.validate({'key1': 1,
...                   10: 'not None here'})
Traceback (most recent call last):
...
SchemaExit: ...

```

You can mark a key as optional as follows:

```python
>>> from schema import Optional
>>> Schema({'name': str,
...         Optional('occupation'): str}).validate({'name': 'Sam'})
{'name': 'Sam'}

```

**schema** has classes `And` and `Or` that help to validate several schemas
for the same data:

```python
>>> from schema import And, Or

>>> Schema({'age': And(int, lambda n: 0 < n < 99)}).validate({'age': 7})
{'age': 7}

>>> Schema({'password': And(str, lambda s: len(s) > 6)}).validate({'password': 'hai'})
Traceback (most recent call last):
...
SchemaExit: ...

>>> Schema(And(Or(int, float), lambda x: x > 0)).validate(3.1415)
3.1415

```

Example
-------------------------------------------------------------------------------

Here is a more complex example that validates list of entries with
personal information:

```python
>>> schema = Schema([{'name': And(str, lambda s: len(s)),
...                   'age':  And(Use(int), lambda n: 18 <= n <= 99),
...                   Optional('sex'): And(Use(lambda s: s.lower()),
...                                        lambda s: s in ('male', 'female'))
...                  }])
>>> data = [{'name': 'Sue', 'age': '28', 'sex': 'FEMALE'},
...         {'name': 'Sam', 'age': '42'},
...         {'name': 'Sacha', 'age': '20', 'sex': 'Male'}]
>>> sue, sam, sacha = schema.validate(data)
>>> sue['age']
28
>>> sue['sex']
'female'
>>> sam['age']
42
>>> sacha['sex']
'male'

```

Using **schema** with [**docopt**](http://github.com/docopt/docopt)
-------------------------------------------------------------------------------

Assume you are using **docopt** with the following usage-pattern:

    Usage: my_program.py [--count=N] <path> <files>...

and you would like to validate that `<files>` are readable, and that `<path>`
exists, and that `--count` is either integer from 0 to 5, or `None`.

Assuming **docopt** returns the following dict:

```python
>>> args = {'<files>': ['LICENSE-MIT', 'setup.py'],
...         '<path>': '../',
...         '--count': '3'}

```

this is how you validate it using `schema`:

```python
>>> from schema import Schema, And, Or, Use
>>> import os

>>> s = Schema({'<files>': [Use(open)],
...             '<path>': os.path.exists,
...             '--count': Or(None, And(Use(int), lambda n: 0 < n < 5))})

>>> args = s.validate(args)

>>> args['<files>']
[<open file 'LICENSE-MIT', mode 'r' at 0x...>, <open file 'setup.py', mode 'r' at 0x...>]

>>> args['<path>']
'../'

>>> args['--count']
3

```

As you can see, **schema** validated data successfully, opened files and
converted `'3'` to `int`.


Note
-------------------------------------------------------------------------------

**schema** is work-in-progress.  Backwards-incompatible changes are made on a
daily basis.

Credits
-------------------------------------------------------------------------------

This library was largely inspired by Alec Thomas'
[voluptuous](https://github.com/alecthomas/voluptuous) library, however,
**schema** tries to make it easier to use Python built-in capabilities
through lambdas, at the same time allowing to make validation-aware
classes and data types with `validate` method.

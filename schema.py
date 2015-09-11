__version__ = '0.4.1-alpha'
__all__ = ['Schema', 'And', 'Or', 'Optional', 'SchemaError']


class SchemaError(Exception):

    """Error during Schema validation."""

    def __init__(self, autos, errors, origin):
        self.autos = autos if type(autos) is list else [autos]
        self.errors = errors if type(errors) is list else [errors]
        self.origin = origin
        Exception.__init__(self, self.code)

    @property
    def code(self):
        def uniq(seq):
            seen = set()
            seen_add = seen.add
            # This way removes duplicates while preserving the order.
            return [x for x in seq if x not in seen and not seen_add(x)]
        a = uniq(i for i in self.autos if i is not None)
        e = uniq(i for i in self.errors if i is not None)
        if e:
            return '\n'.join(e)
        return '\n'.join(a)


class And(object):

    def __init__(self, *args, **kw):
        self._args = args
        assert list(kw) in (['error'], [])
        self._error = kw.get('error')

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__,
                           ', '.join(repr(a) for a in self._args))

    def validate(self, data):
        for s in [Schema(s, error=self._error) for s in self._args]:
            data = s.validate(data)
        return data


class Or(And):

    _pattern_fn = '{0!r} did not validate {1!r}'.format

    def __init__(self, *args, **kw):
        if '_pattern_fn' in kw:
            assert callable(kw['_pattern_fn'])
            self._pattern_fn = kw.pop('_pattern_fn')
        super(Or, self).__init__(*args, **kw)

    def validate(self, data):
        x = SchemaError([], [], self)
        for s in [Schema(s, error=self._error) for s in self._args]:
            try:
                return s.validate(data)
            except SchemaError as _x:
                x = _x
        raise SchemaError([self._pattern_fn(self, data)] + x.autos,
                          [self._error] + x.errors, self)


class Use(object):

    _pattern_fn = '{0!s}({1!r}) raised {2!r}'.format

    def __init__(self, callable_, error=None, _pattern_fn=None):
        assert callable(callable_)
        self._callable = callable_
        self._error = error
        if _pattern_fn is not None:
            assert callable(_pattern_fn)
            self._pattern_fn = _pattern_fn

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self._callable)

    def validate(self, data):
        try:
            return self._callable(data)
        except SchemaError as x:
            raise SchemaError([None] + x.autos, [self._error] + x.errors, self)
        except BaseException as x:
            f = _callable_str(self._callable)
            raise SchemaError(self._pattern_fn(f, data, x),
                              self._error, self)


COMPARABLE, CALLABLE, VALIDATOR, TYPE, DICT, ITERABLE = range(6)


def _priority(s):
    """Return priority for a given object."""
    if type(s) in (list, tuple, set, frozenset):
        return ITERABLE
    if type(s) is dict:
        return DICT
    if issubclass(type(s), type):
        return TYPE
    if hasattr(s, 'validate'):
        return VALIDATOR
    if callable(s):
        return CALLABLE
    else:
        return COMPARABLE


class Schema(object):

    _missing_keys_pattern_fn = 'Missing keys: {0}'.format
    _wrong_keys_pattern_fn = 'Wrong keys {0!s} in {1!r}'.format
    _should_be_instance_pattern_fn = '{0!r} should be instance of {1!r}'.format
    _validate_raises_pattern_fn = '{0!r}.validate({1!r}) raised {2!r}'.format
    _exception_raised_pattern_fn = '{0!s}({1!r}) raised {2!r}'.format
    _should_evaluate_pattern_fn = '{0!s}({1!r}) should evaluate to True'.format
    _does_not_match_pattern_fn = '{0!r} does not match {1!r}'.format

    def __init__(self, schema, error=None, **patterns):
        self._schema = schema
        self._error = error
        for pattern_name, pattern_fn in patterns.items():
            assert pattern_name.endswith('_pattern_fn')
            assert hasattr(self, pattern_name)
            assert callable(pattern_fn)
            setattr(self, pattern_name, pattern_fn)

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self._schema)

    @staticmethod
    def _dict_key_priority(s):
        """Return priority for a given key object."""
        if isinstance(s, Optional):
            return _priority(s._schema) + 0.5
        return _priority(s)

    def validate(self, data):
        s = self._schema
        e = self._error
        flavor = _priority(s)
        if flavor == ITERABLE:
            data = Schema(type(s), error=e).validate(data)
            o = Or(*s, error=e)
            return type(data)(o.validate(d) for d in data)
        if flavor == DICT:
            data = Schema(dict, error=e).validate(data)
            new = type(data)()  # new - is a dict of the validated values
            coverage = set()  # matched schema keys
            # for each key and value find a schema entry matching them, if any
            sorted_skeys = sorted(s, key=self._dict_key_priority)
            for key, value in data.items():
                for skey in sorted_skeys:
                    svalue = s[skey]
                    try:
                        nkey = Schema(skey, error=e).validate(key)
                    except SchemaError:
                        pass
                    else:
                        nvalue = Schema(svalue, error=e).validate(value)
                        new[nkey] = nvalue
                        coverage.add(skey)
                        break
            required = set(k for k in s if type(k) is not Optional)
            if not required.issubset(coverage):
                missing_keys = required - coverage
                s_missing_keys = ", ".join(repr(k) for k in missing_keys)
                raise SchemaError(self._missing_keys_pattern_fn(s_missing_keys), e, self)
            if len(new) != len(data):
                wrong_keys = set(data.keys()) - set(new.keys())
                s_wrong_keys = ', '.join(sorted(repr(k) for k in wrong_keys))
                raise SchemaError(self._wrong_keys_pattern_fn(s_wrong_keys, data),
                                  e, self)

            # Apply default-having optionals that haven't been used:
            defaults = set(k for k in s if type(k) is Optional and
                           hasattr(k, 'default')) - coverage
            for default in defaults:
                new[default.key] = default.default

            return new
        if flavor == TYPE:
            if isinstance(data, s):
                return data
            else:
                raise SchemaError(self._should_be_instance_pattern_fn(
                    data, s.__name__), e, self)
        if flavor == VALIDATOR:
            try:
                return s.validate(data)
            except SchemaError as x:
                raise SchemaError([None] + x.autos, [e] + x.errors, x.origin)
            except BaseException as x:
                raise SchemaError(self._validate_raises_pattern_fn(s, data, x),
                                  self._error, self)
        if flavor == CALLABLE:
            f = _callable_str(s)
            try:
                if s(data):
                    return data
            except SchemaError as x:
                raise SchemaError([None] + x.autos, [e] + x.errors, x.origin)
            except BaseException as x:
                raise SchemaError(self._exception_raised_pattern_fn(f, data, x),
                                  self._error, self)
            raise SchemaError(self._should_evaluate_pattern_fn(f, data), e, self)
        if s == data:
            return data
        else:
            raise SchemaError(self._does_not_match_pattern_fn(s, data), e, self)


class Optional(Schema):

    """Marker for an optional part of Schema."""

    _MARKER = object()

    def __init__(self, *args, **kwargs):
        default = kwargs.pop('default', self._MARKER)
        super(Optional, self).__init__(*args, **kwargs)
        if default is not self._MARKER:
            # See if I can come up with a static key to use for myself:
            if _priority(self._schema) != COMPARABLE:
                raise TypeError(
                    'Optional keys with defaults must have simple, '
                    'predictable values, like literal strings or ints. '
                    '"%r" is too complex.' % (self._schema,))
            self.default = default
            self.key = self._schema


def _callable_str(callable_):
    if hasattr(callable_, '__name__'):
        return callable_.__name__
    return str(callable_)

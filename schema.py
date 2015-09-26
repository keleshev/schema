__version__ = '0.3.1'


class SchemaError(Exception):

    """Error during Schema validation."""

    def __init__(self, autos, errors):
        self.autos = autos if type(autos) is list else [autos]
        self.errors = errors if type(errors) is list else [errors]
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

    def validate(self, data):
        x = SchemaError([], [])
        for s in [Schema(s, error=self._error) for s in self._args]:
            try:
                return s.validate(data)
            except SchemaError as _x:
                x = _x
        raise SchemaError(['%r did not validate %r' % (self, data)] + x.autos,
                          [self._error] + x.errors)


class Use(object):

    def __init__(self, callable_, error=None):
        assert callable(callable_)
        self._callable = callable_
        self._error = error

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self._callable)

    def validate(self, data):
        try:
            return self._callable(data)
        except SchemaError as x:
            raise SchemaError([None] + x.autos, [self._error] + x.errors)
        except BaseException as x:
            f = _callable_str(self._callable)
            raise SchemaError('%s(%r) raised %r' % (f, data, x), self._error)


COMPARABLE, CALLABLE, VALIDATOR, TYPE, DICT, ITERABLE = range(6)


def priority(s):
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

    def __init__(self, schema, error=None):
        self._schema = schema
        self._error = error

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self._schema)

    def validate(self, data):
        s = self._schema
        e = self._error
        flavor = priority(s)
        if flavor == ITERABLE:
            data = Schema(type(s), error=e).validate(data)
            o = Or(*s, error=e)
            return type(s)(o.validate(d) for d in data)
        if flavor == DICT:
            data = Schema(dict, error=e).validate(data)
            new = type(data)()  # new - is a dict of the validated values
            x = None
            coverage = set()  # matched schema keys
            # for each key and value find a schema entry matching them, if any
            sorted_skeys = sorted(s, key=priority)
            for key, value in data.items():
                valid = False
                skey = None
                for skey in sorted_skeys:
                    svalue = s[skey]
                    try:
                        nkey = Schema(skey, error=e).validate(key)
                    except SchemaError:
                        pass
                    else:
                        try:
                            nvalue = Schema(svalue, error=e).validate(value)
                        except SchemaError as _x:
                            x = _x
                            raise
                        else:
                            coverage.add(skey)
                            valid = True
                            break
                if valid:
                    new[nkey] = nvalue
                elif skey is not None:
                    if x is not None:
                        raise SchemaError(['Invalid value for key %r' % key] +
                                          x.autos, [e] + x.errors)
            required = set(k for k in s if type(k) is not Optional)
            if not required.issubset(coverage):
                missing_keys = required - coverage
                s_missing_keys = ", ".join(repr(k) for k in missing_keys)
                raise SchemaError('Missing keys: ' + s_missing_keys, e)
            if len(new) != len(data):
                wrong_keys = set(data.keys()) - set(new.keys())
                s_wrong_keys = ', '.join(repr(k) for k in sorted(wrong_keys,
                                                                 key=repr))
                raise SchemaError('Wrong keys %s in %r' % (s_wrong_keys, data),
                                  e)

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
                raise SchemaError('%r should be instance of %r' %
                                  (data, s.__name__), e)
        if flavor == VALIDATOR:
            try:
                return s.validate(data)
            except SchemaError as x:
                raise SchemaError([None] + x.autos, [e] + x.errors)
            except BaseException as x:
                raise SchemaError('%r.validate(%r) raised %r' % (s, data, x),
                                  self._error)
        if flavor == CALLABLE:
            f = _callable_str(s)
            try:
                if s(data):
                    return data
            except SchemaError as x:
                raise SchemaError([None] + x.autos, [e] + x.errors)
            except BaseException as x:
                raise SchemaError('%s(%r) raised %r' % (f, data, x),
                                  self._error)
            raise SchemaError('%s(%r) should evaluate to True' % (f, data), e)
        if s == data:
            return data
        else:
            raise SchemaError('%r does not match %r' % (s, data), e)


MARKER = object()


class Optional(Schema):

    """Marker for an optional part of Schema."""

    def __init__(self, *args, **kwargs):
        default = kwargs.pop('default', MARKER)
        super(Optional, self).__init__(*args, **kwargs)
        if default is not MARKER:
            # See if I can come up with a static key to use for myself:
            if priority(self._schema) != COMPARABLE:
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

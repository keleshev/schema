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
            f = self._callable.__name__
            raise SchemaError('%s(%r) raised %r' % (f, data, x), self._error)


COMPARABLE, CALLABLE, VALIDATOR, TYPE, DICT, ITERABLE = range(6)


def priority(s):
    """Return the priority with which a schema should be tried against an
    object.

    A priority is a tuple of at least 1 "flavor". Sorted lexically, they
    determine the order in which to try schemata against data.

    """
    if type(s) in (list, tuple, set, frozenset):
        ret = ITERABLE
    elif type(s) is dict:
        ret = DICT
    elif issubclass(type(s), type):
        ret = TYPE
    elif hasattr(s, 'validate'):
        # Deletegate to the object's priority() method if there is one,
        # allowing it to traverse into itself and return a compound priority
        # like (2, 3):
        return getattr(s, 'priority', lambda: (VALIDATOR,))()
    elif callable(s):
        ret = CALLABLE
    else:
        ret = COMPARABLE
    return (ret,)


class Schema(object):

    def __init__(self, schema, error=None):
        self._schema = schema
        self._error = error

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self._schema)

    def validate(self, data):
        s = self._schema
        e = self._error
        flavor = priority(s)[0]
        if flavor == ITERABLE:
            data = Schema(type(s), error=e).validate(data)
            return type(s)(Or(*s, error=e).validate(d) for d in data)
        if flavor == DICT:
            data = Schema(dict, error=e).validate(data)
            new = type(data)()  # new - is a dict of the validated values
            x = None
            coverage = set()  # non-optional schema keys that were matched
            covered_optionals = set()
            # for each key and value find a schema entry matching them, if any
            sorted_skeys = list(sorted(s, key=priority))
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
                            (covered_optionals if type(skey) is Optional
                             else coverage).add(skey)
                            valid = True
                            break
                if valid:
                    new[nkey] = nvalue
                elif skey is not None:
                    if x is not None:
                        raise SchemaError(['invalid value for key %r' % key] +
                                          x.autos, [e] + x.errors)
            required = set(k for k in s if type(k) is not Optional)
            if coverage != required:
                raise SchemaError('missed keys %r' % (required - coverage), e)
            if len(new) != len(data):
                wrong_keys = set(data.keys()) - set(new.keys())
                s_wrong_keys = ', '.join('%r' % k for k in sorted(wrong_keys))
                raise SchemaError('wrong keys %s in %r' % (s_wrong_keys, data),
                                  e)

            # Apply default-having optionals that haven't been used:
            defaults = set(k for k in s if type(k) is Optional and
                           hasattr(k, 'default')) - covered_optionals
            for default in defaults:
                new[default.key] = default.default

            return new
        if flavor == TYPE:
            if isinstance(data, s):
                return data
            else:
                raise SchemaError('%r should be instance of %r' % (data, s), e)
        if flavor == VALIDATOR:
            try:
                return s.validate(data)
            except SchemaError as x:
                raise SchemaError([None] + x.autos, [e] + x.errors)
            except BaseException as x:
                raise SchemaError('%r.validate(%r) raised %r' % (s, data, x),
                                  self._error)
        if flavor == CALLABLE:
            f = s.__name__
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

    def priority(self):
        return (VALIDATOR,)


MARKER = object()


class Optional(Schema):

    """Marker for an optional part of Schema."""

    def __init__(self, *args, **kwargs):
        default = kwargs.pop('default', MARKER)
        super(Optional, self).__init__(*args, **kwargs)
        if default is not MARKER:
            # See if I can come up with a static key to use for myself:
            if priority(self._schema)[0] != COMPARABLE:
                raise TypeError(
                        'Optional keys with defaults must have simple, '
                        'predictable values, like literal strings or ints. '
                        '"%r" is too complex.' % (self._schema,))
            self.default = default
            self.key = self._schema

    def priority(self):
        """Dig in one level so Optional('foo') takes precedence over
        Optional('str'). We could go deeper if we wanted.

        """
        return super(Optional, self).priority() + priority(self._schema)

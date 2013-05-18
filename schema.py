from inspect import getargspec
from functools import wraps


__version__ = '0.2.0'


class SchemaError(Exception):

    """Error during Schema validation."""

    def __init__(self, autos, errors, value):
        self.autos = autos if type(autos) is list else [autos]
        self.errors = errors if type(errors) is list else [errors]
        self.value = value
        self.errors = [None if e is None else e.format(value=self.value)
                       for e in self.errors]
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
        x = SchemaError([], [], None)
        for s in [Schema(s, error=self._error) for s in self._args]:
            try:
                return s.validate(data)
            except SchemaError as _x:
                x = _x
        raise SchemaError(['%r did not validate %r' % (self, data)] + x.autos,
                         [self._error] + x.errors, data)


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
            raise SchemaError([None] + x.autos, [self._error] + x.errors, data)
        except BaseException as x:
            f = self._callable.__name__
            raise SchemaError('%s(%r) raised %r' % (f, data, x), self._error,
                              data)


def priority(s):
    if type(s) in (list, tuple, set, frozenset):
        return 6
    if type(s) is dict:
        return 5
    if hasattr(s, 'validate'):
        return 4
    if type(s) is type:
        return 3
    if callable(s):
        return 2
    else:
        return 1


class Schema(object):

    def __init__(self, schema, error=None):
        self._schema = schema
        self._error = error

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self._schema)

    def validate(self, data):
        s = self._schema
        e = self._error
        if type(s) in (list, tuple, set, frozenset):
            data = Schema(type(s), error=e).validate(data)
            return type(s)(Or(*s, error=e).validate(d) for d in data)
        if type(s) is dict:
            data = Schema(dict, error=e).validate(data)
            new = type(data)()
            x = None
            coverage = set()  # non-optional schema keys that were matched
            for key, value in data.items():
                valid = False
                skey = None
                for skey in sorted(s, key=priority):
                    svalue = s[skey]
                    try:
                        nkey = Schema(skey).validate(key) # error got forgotten
                        try:
                            nvalue = Schema(svalue).validate(value)
                        except SchemaError as _x:
                            x = _x
                            raise
                    except SchemaError:
                        pass
                    else:
                        coverage.add(skey)
                        valid = True
                        break
                if valid:
                    new[nkey] = nvalue
                elif skey is not None:
                    if x is not None:
                        raise SchemaError(['key %r is required' % key] +
                                          x.autos, [e] + x.errors, data)
                    else:
                        raise SchemaError('key %r is required' % skey, e, data)
            coverage = set(k for k in coverage if type(k) is not Optional)
            required = set(k for k in s if type(k) is not Optional)
            if coverage != required:
                raise SchemaError('missed keys %r' % (required - coverage), e,
                                  data)
            if len(new) != len(data):
                raise SchemaError('wrong keys %r in %r' % (new, data), e, data)
            return new
        if hasattr(s, 'validate'):
            try:
                return s.validate(data)
            except SchemaError as x:
                raise SchemaError([None] + x.autos, [e] + x.errors, data)
            except BaseException as x:
                raise SchemaError('%r.validate(%r) raised %r' % (s, data, x),
                                  self._error, data)
        if type(s) is type:
            if isinstance(data, s):
                return data
            else:
                raise SchemaError('%r should be instance of %r' % (data, s), e,
                                  data)
        if callable(s):
            f = s.__name__
            try:
                if s(data):
                    return data
            except SchemaError as x:
                raise SchemaError([None] + x.autos, [e] + x.errors, data)
            except BaseException as x:
                raise SchemaError('%s(%r) raised %r' % (f, data, x),
                                  self._error, data)
            raise SchemaError('%s(%r) should evaluate to True' % (f, data), e,
                              data)
        if s == data:
            return data
        else:
            raise SchemaError('%r does not match %r' % (s, data), e, data)


class Optional(Schema):

    """Marker for an optional part of Schema."""

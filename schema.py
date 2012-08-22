

class SchemaExit(SystemExit):

    def __init__(self, autos, errors):
        self.autos = autos if type(autos) is list else [autos]
        self.errors = errors if type(errors) is list else [errors]
        for a, e in zip(self.autos, self.errors):
            if e is not None:
                message = e
                break
            if a is not None:
                message = a
                break
        SystemExit.__init__(self, message)

    @property
    def code(self):
        return '\n'.join([e or a for a, e in zip(self.autos, self.errors)
                          if a or e])


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
        for s in [Schema(s, error=self._error) for s in self._args]:
            try:
                return s.validate(data)
            except SchemaExit as x:
                pass
        raise SchemaExit(x.autos + ['%r did not validate %r' % (self, data)],
                         x.errors + [self._error])


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
        except SchemaExit as x:
            raise SchemaExit(x.autos + [None], x.errors + [self._error])
        except BaseException as x:
            f = self._callable.__name__
            raise SchemaExit('%s(%r) raised %r' % (f, data, x), self._error)


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
            new = {}
            coverage = set()  # non-optional schema keys that were matched
            for key, value in data.items():
                valid = False
                for skey, svalue in s.items():
                    try:
                        nkey = Schema(skey, error=e).validate(key)
                        nvalue = Schema(svalue, error=e).validate(value)
                    except SchemaExit as x:  # XXX
                        pass
                    else:
                        coverage.add(skey)
                        valid = True
                        break
                if valid:
                    new[nkey] = nvalue
                elif type(skey) is not Optional:
                    raise SchemaExit(x.autos + ['key %r is required' % key],
                                     x.errors + [e])
            coverage = set(k for k in coverage if type(k) is not Optional)
            required = set(k for k in s if type(k) is not Optional)
            if coverage != required:
                raise SchemaExit('missed keys %r' % (required - coverage), e)
            if len(new) != len(data):
                raise SchemaExit('wrong keys %r in %r' % (new, data), e)
            return new
        if hasattr(s, 'validate'):
            try:
                return s.validate(data)
            except SchemaExit as x:
                raise SchemaExit(x.autos + [None], x.errors + [e])
            except BaseException as x:
                raise SchemaExit('%r.validate(%r) raised %r' % (s, data, x),
                                 self._error)
        if type(s) is type:
            if isinstance(data, s):
                return data
            else:
                raise SchemaExit('%r should be instance of %r' % (data, s), e)
        if callable(s):
            f = s.__name__
            try:
                if s(data):
                    return data
            except SchemaExit as x:
                raise SchemaExit(x.autos + [None], x.errors + [e])
            except BaseException as x:
                raise SchemaExit('%s(%r) raised %r' % (f, data, x), self._error)
            raise SchemaExit('bool(%s(%r)) should be True ' % (f, data), e)
        if s == data:
            return data
        else:
            raise SchemaExit('%r does not match %r' % (s, data), e)


class Optional(Schema):

    """Marker for an optional part of Schema."""



class SchemaExit(SystemExit):

    pass


class And(object):

    def __init__(self, *args, **kw):
        self._args = args
        assert kw.keys() in (['error'], [])
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
            except SchemaExit:
                pass
        raise SchemaExit(self._error or 'did not validate %r %r' % (self, data))


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
        except Exception as e:
            raise SchemaExit(self._error
                             or '%r raised %r' % (self._callable.__name__, e))


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
                    except SchemaExit:
                        pass
                    else:
                        coverage.add(skey)
                        valid = True
                        break
                if valid:
                    new[nkey] = nvalue
                elif type(skey) is not Optional:
                    raise SchemaExit('key %r is required' % key)
            coverage = set(k for k in coverage if type(k) is not Optional)
            required = set(k for k in s if type(k) is not Optional)
            if coverage != required:
                raise SchemaExit('missed keys %r' % (required - coverage))
            if len(new) != len(data):
                raise SchemaExit('wrong keys %r in %r' % (new, data))
            return new
        if hasattr(s, 'validate'):
            return s.validate(data)
        if type(s) is type:
            if isinstance(data, s):
                return data
            else:
                raise SchemaExit('%r should be instance of %r' % (data, s))
        if callable(s):
            try:
                if s(data):
                    return data
            except Exception as e:
                raise SchemaExit('%r raised %r' % (s.__name__, e))
            raise SchemaExit('did not validate %r %r' % (s, data))
        if s == data:
            return data
        else:
            raise SchemaExit('did not validate %r %r' % (s, data))


class Optional(Schema):

    """Marker for an optional part of Schema."""

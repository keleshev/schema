

class SchemaExit(SystemExit):

    pass


class And(object):

    def __init__(self, *args):
        self._args = args

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__,
                           ', '.join(repr(a) for a in self._args))

    def validate(self, data):
        schemas = map(Schema, self._args)
        for s in schemas:
            data = s.validate(data)
        return data


class Or(And):

    def validate(self, data):
        schemas = map(Schema, self._args)
        for s in schemas:
            try:
                return s.validate(data)
            except SchemaExit:
                pass
        raise SchemaExit('did not validate %r %r' % (self, data))


class Use(object):

    def __init__(self, callable_):
        assert callable(callable_)
        self._callable = callable_

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self._callable)

    def validate(self, data):
        try:
            return self._callable(data)
        except Exception as e:
            raise SchemaExit('%r raised %r' % (self._callable.__name__, e))


class Schema(object):

    def __init__(self, schema):
        self._s = schema

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self._s)

    def validate(self, data):
        if type(self._s) in (list, tuple, set, frozenset):
            t = type(self._s)
            data = Schema(t).validate(data)
            return t(Or(*self._s).validate(d) for d in data)
        if type(self._s) is dict:
            data = Schema(dict).validate(data)
            new = {}
            coverage = set()  # non-optional schema keys that were matched
            for key, value in data.items():
                valid = False
                for skey, svalue in self._s.items():
                    try:
                        nkey = Schema(skey).validate(key)
                        nvalue = Schema(svalue).validate(value)
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
            required = set(k for k in self._s if type(k) is not Optional)
            if coverage != required:
                raise SchemaExit('missed keys %r' % (required - coverage))
            if len(new) != len(data):
                raise SchemaExit('wrong keys %r in %r' % (new, data))
            return new
        if hasattr(self._s, 'validate'):
            return self._s.validate(data)
        if type(self._s) is type:
            if isinstance(data, self._s):
                return data
            else:
                raise SchemaExit('%r should be instance of %r' % (data, self._s))
        if callable(self._s):
            try:
                if self._s(data):
                    return data
            except Exception as e:
                raise SchemaExit('%r raised %r' % (self._s.__name__, e))
            raise SchemaExit('did not validate %r %r' % (self._s, data))
        if self._s == data:
            return data
        else:
            raise SchemaExit('did not validate %r %r' % (self._s, data))


class Optional(Schema):

    """Marker for an optional part of Schema."""

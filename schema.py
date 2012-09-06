from inspect import getargspec
from functools import wraps


class SchemaError(Exception):

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
        for s in [Schema(s, error=self._error) for s in self._args]:
            try:
                return s.validate(data)
            except SchemaError as x:
                pass
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
                for skey, svalue in s.items():
                    try:
                        nkey = Schema(skey, error=e).validate(key)
                        try:
                            nvalue = Schema(svalue, error=e).validate(value)
                        except SchemaError as x:
                            raise
                    except SchemaError:
                        pass
                    else:
                        coverage.add(skey)
                        valid = True
                        break
                if valid:
                    new[nkey] = nvalue
                elif type(skey) is not Optional and skey is not None:
                    if x is not None:
                        raise SchemaError(['key %r is required' % key] +
                                          x.autos, [e] + x.errors)
                    else:
                        raise SchemaError('key %r is required' % skey, e)
            coverage = set(k for k in coverage if type(k) is not Optional)
            required = set(k for k in s if type(k) is not Optional)
            if coverage != required:
                raise SchemaError('missed keys %r' % (required - coverage), e)
            if len(new) != len(data):
                raise SchemaError('wrong keys %r in %r' % (new, data), e)
            return new
        if hasattr(s, 'validate'):
            try:
                return s.validate(data)
            except SchemaError as x:
                raise SchemaError([None] + x.autos, [e] + x.errors)
            except BaseException as x:
                raise SchemaError('%r.validate(%r) raised %r' % (s, data, x),
                                 self._error)
        if type(s) is type:
            if isinstance(data, s):
                return data
            else:
                raise SchemaError('%r should be instance of %r' % (data, s), e)
        if callable(s):
            f = s.__name__
            try:
                if s(data):
                    return data
            except SchemaError as x:
                raise SchemaError([None] + x.autos, [e] + x.errors)
            except BaseException as x:
                raise SchemaError('%s(%r) raised %r' % (f, data, x),
                                  self._error)
            raise SchemaError('%s(%r) should evalutate to True' % (f, data), e)
        if s == data:
            return data
        else:
            raise SchemaError('%r does not match %r' % (s, data), e)


class Optional(Schema):

    """Marker for an optional part of Schema."""


def guard(*schemas, **kwschema):
    def decorator(oldf):
        spec = getargspec(oldf)
        @wraps(oldf)
        def newf(*args, **kw):
        #make_env = eval('lambda %s: locals()' % formatargspec(*spec)[1:][:-1])
        #env = make_env(*args, **kw)
            env = dict(zip(reversed(spec.args), reversed(spec.defaults or ()))
                     + zip(spec.args, args)
                     + [(k, v) for k, v in kw.items() if k in spec.args])
            if spec.varargs is not None:
                env[spec.varargs] = args[len(spec.args):]
            if spec.keywords is not None:
                env[spec.keywords] = dict((k, v) for k, v in kw.items()
                                          if k not in spec.args)
            senv = dict(zip(spec.args, schemas) + kwschema.items())
            venv = Schema(senv).validate(env)
            nargs = tuple(venv[k] for k in spec.args)
            if spec.varargs is not None:
                nargs += venv[spec.varargs]
            nkw = dict((venv[spec.keywords].items() if spec.keywords else [])
                    + [(k, v) for k, v in venv.items() if k not in
                       tuple(spec.args) + (spec.varargs, spec.keywords)])
            return oldf(*nargs, **nkw)
        return newf
    return decorator

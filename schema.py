__version__ = '0.3.0'


def unique(seq):
    seen = set()
    unique = []
    for x in seq:
        if x not in seen:
            seen.add(x)
            unique.append(x)
    return unique


class SchemaError(Exception):

    """Error during Schema validation."""

    def __init__(self, autos, errors):
        self.autos = autos if type(autos) is list else [autos]
        self.errors = errors if type(errors) is list else [errors]
        Exception.__init__(self, self.code)

    @property
    def code(self):
        a = unique(i for i in self.autos if i is not None)
        e = unique(i for i in self.errors if i is not None)
        if e:
            return '\n'.join(e)
        return '\n'.join(a)


class SchemaCutError(SchemaError):

    """This exception is used to stop attempting further validation when
    a Cut() object is reached. It can also be manually raised, but the
    recommended way is to include a Cut([error]) in your schema."""
    pass


class SchemaBase(object):
    priority = 4  # default priority for "validatables"

    def validate(self, data):
        raise NotImplementedError("redefine this method in subclasses")


class And(SchemaBase):

    def __init__(self, *args, **kw):
        self._args = args
        assert list(kw) in (['error'], [])
        self._error = kw.get('error')
        priority = kw.get('priority', None)
        if priority is not None:
            self.priority = priority

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__,
                           ', '.join(repr(a) for a in self._args))

    def validate(self, data):
        for s in self._args:
            data = Schema(s, error=self._error).validate(data)
        return data


class Or(And):

    def validate(self, data):
        x = SchemaError([], [])
        for s in self._args:
            try:
                return Schema(s, error=self._error).validate(data)
            except SchemaCutError:
                raise
            except SchemaError as _x:
                x = _x
        raise SchemaError(['%r did not validate %r' % (self, data)] + x.autos,
                          [self._error] + x.errors)


class Use(SchemaBase):

    def __init__(self, callable_, error=None, priority=None):
        if not callable(callable_):
            raise ValueError("callable argument required")
        self._callable = callable_
        self._error = error
        if priority is not None:
            self.priority = priority

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


class Cut(SchemaBase):
    """
    Cut([msg]) allows terminating validation immediately with a given error
    message. This is useful, e.g. when another pattern in the same schema,
    say a dictionary with a 'object: object' rule would accept anything and
    the error produced message would be difficult to understand or an
    exception wouldn't even be raised.

    Example:
        Schema({Optional("foo"): float,
                object: object}).validate({"foo": "a"})

    This would not even raise an exception, and we want it to NOT match "foo"
    with the 'object: object' rule, so we can simply add a custom priority to
    the 'Optional("foo")' key and a cut after 'float', like this:
        Schema({Optional("foo", priority=0): Or(float, Cut("foobar")),
                object: object}).validate({"foo": "a"})

    This way we get the desired behavior: the "foo" rule is tested before
    "object", and the cut will make validation fail immediately.
    """
    def __init__(self, error=None, priority=None):
        self._error = error
        if priority is not None:
            self.priority = priority

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self._error)

    def validate(self, data):
        raise SchemaCutError([None], [self._error])


def priority(s):
    if type(s) in (list, tuple, set, frozenset):
        return 6
    if type(s) is dict:
        return 5
    if isinstance(s, SchemaBase):
        return s.priority
    if isinstance(s, type):
        return 3
    if callable(s):
        return 2
    else:
        return 1


class Schema(SchemaBase):

    def __init__(self, schema, error=None, priority=None):
        self._schema = schema
        self._error = error
        if priority is not None:
            self.priority = priority

    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, self._schema)

    def validate(self, data):
        e = self._error
        s = self._schema
        s_type = type(s)
        if s_type in (list, tuple, set, frozenset):
            Schema(s_type).validate(data)
            return s_type(Or(*s, error=e).validate(d) for d in data)
        if s_type is dict:
            Schema(s_type).validate(data)
            return self._dict_validate(data)
        if isinstance(s, SchemaBase):
            try:
                return s.validate(data)
            except SchemaError as x:
                # we must propagate the exception without losing its type
                # otherwise cuts won't work correctly if we mask them with
                # regular SchemaError exceptions
                raise type(x)([None] + x.autos, [e] + x.errors)
            except BaseException as x:
                raise SchemaError('%r.validate(%r) raised %r' % (s, data, x),
                                  self._error)
        if isinstance(s, type):
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
                raise type(x)([None] + x.autos, [e] + x.errors)
            except BaseException as x:
                raise SchemaError('%s(%r) raised %r' % (f, data, x),
                                  self._error)
            raise SchemaError('%s(%r) should evalutate to True' % (f, data), e)
        if s == data:
            return data
        else:
            raise SchemaError('%r does not match %r' % (s, data), e)

    def _dict_validate(self, data):
        s = self._schema
        e = self._error
        new = type(data)()
        coverage = set()  # non-optional schema keys that were matched
        skeys = sorted(s.keys(), key=priority)
        for key, value in data.items():
            valid = False
            x = SchemaError([], [])
            for skey in skeys:
                # attempt to match the current key to any of the schema's keys
                try:
                    nkey = Schema(skey, error=e).validate(key)
                except SchemaError:
                    continue
                # the key has matched, let's attempt to match the value
                svalue = s[skey]
                try:
                    nvalue = Schema(svalue, error=e).validate(value)
                except SchemaCutError as y:
                    x = type(y)(y.autos + x.autos, y.errors + x.errors)
                    break
                except SchemaError as y:
                    x = type(y)(y.autos + x.autos, y.errors + x.errors)
                    continue
                # both key and value matched, we can stop the loop
                coverage.add(skey)
                valid = True
                break

            if valid:
                new[nkey] = nvalue
            elif len(x.errors) > 0 or len(x.autos) > 0:
                raise x
            else:
                raise SchemaError('unable to match %r to any schema key' % key, e)

        coverage = set(k for k in coverage if type(k) is not Optional)
        required = set(k for k in s if type(k) is not Optional)
        if coverage != required:
            raise SchemaError('missed keys %r' % (required - coverage), e)
        if len(new) != len(data):
            raise SchemaError('wrong keys %r in %r' % (new, data), e)
        return new


class Optional(Schema):

    """Marker for an optional part of Schema."""

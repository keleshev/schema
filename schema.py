__version__ = '0.3.0'

error_messages = {
    'did not validate': '{schema} {reason} {data}',
    'callable raised exception': '{schema}({data}) raised {details}',
    'validate raised exception': '{schema}.validate({data}) raised {details}',
    'invalid value for key': '{reason} {details}',
    'missed keys': '{reason} {details}',
    'wrong keys': '{reason} {details} in {data}',
    'incorrect instance': '{data} should be instance of {schema}',
    'should evaluate to True': '{schema}({data}) {reason}',
    'does not match': '{schema} {reason} {data}'
}

def auto_error(schema, data, reason, details):
    return format_error(error_messages[reason], schema, data, reason, details)

def format_error(error, schema, data, reason, details=None):
    if error is None:
        return
    elif callable(error):
        result = error(schema, data, reason, details)
        assert isinstance(result, basestring), \
            "error function must return a string"
        return result
    if callable(schema) and hasattr(schema, '__name__'):
        schema = schema.__name__
    else:
        schema = repr(schema)
    if not isinstance(details, basestring):
        details = repr(details)
    return error.format(schema=schema, data=repr(data), reason=reason,
                        details=details)

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
        reason = 'did not validate'
        raise SchemaError([format_error(auto_error, self, data, reason)] + 
                          x.autos,
                          [format_error(self._error, self, data, reason)] + 
                          x.errors)


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
            f = self._callable
            reason = 'callable raised exception'
            raise SchemaError(format_error(auto_error, f, data, reason, x),
                              format_error(self._error, f, data, reason, x))


def priority(s):
    """Return priority for a give object."""
    if type(s) in (list, tuple, set, frozenset):
        return 6
    if type(s) is dict:
        return 5
    if hasattr(s, 'validate'):
        return 4
    if issubclass(type(s), type):
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
            new = type(data)()  # new - is a dict of the validated values
            x = None
            coverage = set()  # non-optional schema keys that were matched
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
                            coverage.add(skey)
                            valid = True
                            break
                if valid:
                    new[nkey] = nvalue
                elif skey is not None:
                    if x is not None:
                        reason = 'invalid value for key'
                        details =  '%r' % key
                        raise SchemaError([format_error(auto_error, s, data,
                                                        reason, details)] +
                                          x.autos,
                                          [format_error(e, s, data, reason,
                                                        details)] + 
                                          x.errors)
            coverage = set(k for k in coverage if type(k) is not Optional)
            required = set(k for k in s if type(k) is not Optional)
            if coverage != required:
                reason = 'missed keys'
                details = '%r' % (required - coverage)
                raise SchemaError(format_error(auto_error, s, data, reason,
                                               details),
                                  format_error(e, s, data, reason, details))
            if len(new) != len(data):
                wrong_keys = set(data.keys()) - set(new.keys())
                reason = 'wrong keys'
                details = ', '.join('%r' % k for k in sorted(wrong_keys))
                raise SchemaError(format_error(auto_error, s, data, reason,
                                               details),
                                  format_error(e, s, data, reason, details))
            return new
        if hasattr(s, 'validate'):
            try:
                return s.validate(data)
            except SchemaError as x:
                raise SchemaError([None] + x.autos, [e] + x.errors)
            except BaseException as x:
                reason = 'validate raised exception'
                raise SchemaError(format_error(auto_error, s, data, reason, x),
                                  format_error(self._error, s, data, reason, x))
        if issubclass(type(s), type):
            if isinstance(data, s):
                return data
            else:
                reason = 'incorrect instance'
                raise SchemaError(format_error(auto_error, s, data, reason),
                                  format_error(e, s, data, reason))
        if callable(s):
            try:
                if s(data):
                    return data
            except SchemaError as x:
                raise SchemaError([None] + x.autos, [e] + x.errors)
            except BaseException as x:
                reason = 'callable raised exception'
                raise SchemaError(format_error(auto_error, s, data, reason, x),
                                  format_error(self._error, s, data, reason, x))
            reason = 'should evaluate to True'
            raise SchemaError(format_error(auto_error, s, data, reason),
                              format_error(e, s, data, reason))
        if s == data:
            return data
        else:
            reason = 'does not match'
            raise SchemaError(format_error(auto_error, s, data, reason),
                              format_error(e, s, data, reason))


class Optional(Schema):

    """Marker for an optional part of Schema."""



class SchemaExit(SystemExit):

    pass


class is_a(object):

    def __init__(self, *args):
        self._args = args

    def validate(self, data):
        schemas = map(Schema, self._args)
        for s in schemas:
            data = s.validate(data)
        return data


class either(object):

    def __init__(self, *args):
        self._args = args

    def validate(self, data):
        schemas = map(Schema, self._args)
        for s in schemas:
            try:
                return s.validate(data)
            except SchemaExit:
                pass
        raise SchemaExit('did not validate %r %r' % (self, data))


class strictly(object):

    def __init__(self, type_):
        assert type(type_) is type
        self._type = type_

    def validate(self, data):
        if type(data) is self._type:
            return data
        raise SchemaExit('did not validate %r %r' % (self, data))


class Schema(object):

    def __init__(self, schema):
        self._s = schema

    def validate(self, data):
        if type(self._s) is list:
            data = Schema(list).validate(data)
            return [either(*self._s).validate(d) for d in data]
        if type(self._s) is dict:
            data = Schema(dict).validate(data)
            new = {}
            coverage = set()  # how many non-optional schema keys were matched
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
                elif type(skey) is not optional:
                    raise SchemaExit('key %r is required' % key)
            coverage = set(k for k in coverage if type(k) is not optional)
            required = set(k for k in self._s if type(k) is not optional)
            if coverage != required:
                raise SchemaExit('missed keys %r' % (required - coverage))
            if len(new) != len(data):
                raise SchemaExit('wrong keys %r in %r' % (new, data))
            return new
        if type(self._s) is type:
            try:
                return self._s(data)
            except Exception as e:
                raise SchemaExit('%r riased %r when validating %r'
                                 % (self._s, e, data))
        if hasattr(self._s, 'validate'):
            return self._s.validate(data)
        if hasattr(self._s, '__call__'):
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


class optional(Schema):

    pass

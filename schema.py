

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
            except:
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


class optional(object):

    def __init__(self, key):
        self._key = key

    def validate(self, data):
        raise ValueError('`optional` is expected only as key of a dictionary')


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
            for skey, svalue in self._s.items():
                for key, value in data.items():
                    try:
                        new[Schema(skey).validate(key)] = \
                                Schema(svalue).validate(value)
                    except:
                        pass
            if len(new) != len(data):
                raise SchemaExit('wrong keys %r in %r' % (new, data))
            return new
        if type(self._s) is type:
            try:
                return self._s(data)
            except:
                raise SchemaExit('did not validate %r %r' % (self._s, data))
        if hasattr(self._s, 'validate'):
            return self._s.validate(data)
        if hasattr(self._s, '__call__'):
            if self._s(data):
                return data
            else:
                raise SchemaExit('did not validate %r %r' % (self._s, data))
        if self._s == data:
            return data
        else:
            raise SchemaExit('did not validate %r %r' % (self._s, data))

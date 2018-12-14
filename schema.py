"""schema is a library for validating Python data structures, such as those
obtained from config-files, forms, external services or command-line
parsing, converted from JSON/YAML (or something else) to Python data-types."""

import re

try:
    from contextlib import ExitStack
except ImportError:
    from contextlib2 import ExitStack

__version__ = "0.6.8"
__all__ = [
    "Schema",
    "And",
    "Or",
    "Regex",
    "Optional",
    "Use",
    "Forbidden",
    "Const",
    "SchemaError",
    "SchemaWrongKeyError",
    "SchemaMissingKeyError",
    "SchemaForbiddenKeyError",
    "SchemaUnexpectedTypeError",
    "SchemaOnlyOneAllowedError",
]


class SchemaError(Exception):
    """Error during Schema validation."""

    def __init__(self, autos, errors=None):
        self.autos = autos if type(autos) is list else [autos]
        self.errors = errors if type(errors) is list else [errors]
        Exception.__init__(self, self.code)

    @property
    def code(self):
        """
        Removes duplicates values in auto and error list.
        parameters.
        """

        def uniq(seq):
            """
            Utility function that removes duplicate.
            """
            seen = set()
            seen_add = seen.add
            # This way removes duplicates while preserving the order.
            return [x for x in seq if x not in seen and not seen_add(x)]

        data_set = uniq(i for i in self.autos if i is not None)
        error_list = uniq(i for i in self.errors if i is not None)
        if error_list:
            return "\n".join(error_list)
        return "\n".join(data_set)


class SchemaWrongKeyError(SchemaError):
    """Error Should be raised when an unexpected key is detected within the
    data set being."""

    pass


class SchemaMissingKeyError(SchemaError):
    """Error should be raised when a mandatory key is not found within the
    data set being validated"""

    pass


class SchemaOnlyOneAllowedError(SchemaError):
    """Error should be raised when an only_one Or key has multiple matching candidates"""

    pass


class SchemaForbiddenKeyError(SchemaError):
    """Error should be raised when a forbidden key is found within the
    data set being validated, and its value matches the value that was specified"""

    pass


class SchemaUnexpectedTypeError(SchemaError):
    """Error should be raised when a type mismatch is detected within the
    data set being validated."""

    pass


class Base(object):
    """Base class for all schemas."""

    def __init__(self, error=None):
        self._error = error

    @staticmethod
    def _is_optional_type(s):
        """Return True if the given key is optional (does not have to be found"""
        return any(isinstance(s, optional_type) for optional_type in [Optional, Hook])


# Atomic schemas

class _Type(Base):

    def __init__(self, typ, error=None):
        super(_Type, self).__init__(error=error)
        self._type = typ

    def validate(self, data):
        if isinstance(data, self._type) and not (isinstance(data, bool) and self._type == int):
            return data
        err = self._error
        raise SchemaUnexpectedTypeError(
            "%r should be instance of %r" % (data, self._type.__name__), err.format(data) if err else None
        )


class _Value(Base):

    def __init__(self, value, error=None):
        super(_Value, self).__init__(error=error)
        self._value = value

    def validate(self, data):
        if self._value == data:
            return data
        raise SchemaError("%r does not match %r" % (self._value, data), self._error.format(data) if self._error else None)


class Regex(Base):
    """
    Enables schema.py to validate string using regular expressions.
    """

    # Map all flags bits to a more readable description
    NAMES = [
        "re.ASCII",
        "re.DEBUG",
        "re.VERBOSE",
        "re.UNICODE",
        "re.DOTALL",
        "re.MULTILINE",
        "re.LOCALE",
        "re.IGNORECASE",
        "re.TEMPLATE",
    ]

    def __init__(self, pattern_str, flags=0, error=None):
        super(Regex, self).__init__(error=error)
        self._pattern_str = pattern_str
        flags_list = [Regex.NAMES[i] for i, f in enumerate("{0:09b}".format(flags)) if f != "0"]  # Name for each bit

        if flags_list:
            self._flags_names = ", flags=" + "|".join(flags_list)
        else:
            self._flags_names = ""

        self._pattern = re.compile(pattern_str, flags=flags)

    def __repr__(self):
        return "%s(%r%s)" % (self.__class__.__name__, self._pattern_str, self._flags_names)

    def validate(self, data):
        """
        Validated data using defined regex.
        :param data: data to be validated
        :return: return validated data.
        """
        e = self._error

        try:
            if self._pattern.search(data):
                return data
            raise SchemaError("%r does not match %r" % (self, data), e)
        except TypeError:
            raise SchemaError("%r is not string nor buffer" % data, e)


def _callable_str(callable_):
    if hasattr(callable_, '__name__'):
        return callable_.__name__
    return str(callable_)


class _Check(Base):
    """Validation for callables."""

    def __init__(self, callable_, error=None):
        super(_Check, self).__init__(error=error)
        self._callable = callable_

    def validate(self, data):
        f = _callable_str(self._callable)
        try:
            if self._callable(data):
                return data
        except SchemaError as x:
            raise SchemaError([None] + x.autos, [self._error] + x.errors)
        except BaseException as x:
            raise SchemaError("%s(%r) raised %r" % (f, data, x), self._error.format(data) if self._error else None)
        raise SchemaError("%s(%r) should evaluate to True" % (f, data), self._error)


class Use(Base):
    """
    For more general use cases, you can use the Use class to transform
    the data while it is being validate.
    """

    def __init__(self, callable_, error=None):
        super(Use, self).__init__(error=error)
        if not callable(callable_):
            raise TypeError("Expected a callable, not %r" % callable_)
        self._callable = callable_

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self._callable)

    def validate(self, data):
        try:
            return self._callable(data)
        except SchemaError as x:
            raise SchemaError([None] + x.autos, [self._error.format(data) if self._error else None] + x.errors)
        except BaseException as x:
            f = _callable_str(self._callable)
            raise SchemaError("%s(%r) raised %r" % (f, data, x), self._error.format(data) if self._error else None)


# Mixin schemas

COMPARABLE, CALLABLE, VALIDATOR, TYPE, DICT, ITERABLE = range(6)


def _priority(s):
    """Return priority for a given object."""
    if type(s) in (list, tuple, set, frozenset):
        return ITERABLE
    if type(s) is dict:
        return DICT
    if issubclass(type(s), type):
        return TYPE
    if hasattr(s, "validate"):
        return VALIDATOR
    if callable(s):
        return CALLABLE
    return COMPARABLE


def _flattable(schema):
    """Return if the wrapping can be ommitted."""
    return schema in (schemify, Schema, Forbidden, Optional)


def _empty(schema):
    """Return if a schema can be ommitted."""
    if isinstance(schema, Schema):
        return type(schema).validate == Schema.validate
    return isinstance(schema, _Wrapper) and schema._error is None


def schemify(schema, error=None, ignore_extra_keys=False):
    """Create a minimalistic schema (instance of ``Base``)."""
    # try to avoid unnecessary wrappings
    if isinstance(schema, Base):
        while _empty(schema):
            schema = schema._worker
    if hasattr(schema, 'validate'):
        return _Wrapper(schema, error=error) if error else schema

    flavor = _priority(schema)
    if flavor == ITERABLE:
        return _Iterable(schema, schema=schemify, error=error,
                         ignore_extra_keys=ignore_extra_keys)
    if flavor == DICT:
        return _Dict(schema, schema=schemify, error=error,
                     ignore_extra_keys=ignore_extra_keys)
    if flavor == TYPE:
        return _Type(schema, error=error)
    if flavor == CALLABLE:
        return _Check(schema, error=error)
    return _Value(schema, error=error)


def _schema_args(kw):
    """Parse `schema`, `error` and `ignore_extra_keys`."""
    if not set(kw).issubset({"error", "schema", "ignore_extra_keys"}):
        diff = {"error", "schema", "ignore_extra_keys"}.difference(kw)
        raise TypeError("Unknown keyword arguments %r" % list(diff))
    schema = kw.get("schema", schemify)
    if _flattable(schema):
        schema = schemify
    error = kw.get("error")
    ignore = kw.get("ignore_extra_keys", False)
    return schema, error, ignore


class And(Base):
    """
    Utility function to combine validation directives in AND Boolean fashion.
    """

    def __init__(self, *args, **kw):
        self._args = args
        schema, error, ignore = _schema_args(kw)
        super(And, self).__init__(error=error)
        # You can pass your inherited Schema class.
        self._schema_seq = [schema(s, error=error, ignore_extra_keys=ignore) for s in args]

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, ", ".join(repr(a) for a in self._args))

    def validate(self, data):
        """
        Validate data using defined sub schema/expressions ensuring all
        values are valid.
        :param data: to be validated with sub defined schemas.
        :return: returns validated data
        """
        for schema in self._schema_seq:
            data = schema.validate(data)
        return data


class Or(And):
    """Utility function to combine validation directives in a OR Boolean
    fashion."""

    def __init__(self, *args, **kwargs):
        self.only_one = kwargs.pop("only_one", False)
        self.match_count = 0
        super(Or, self).__init__(*args, **kwargs)

    def reset(self):
        failed = self.match_count > 1 and self.only_one
        self.match_count = 0
        if failed:
            raise SchemaOnlyOneAllowedError(["There are multiple keys present " + "from the %r condition" % self])

    def validate(self, data):
        """
        Validate data using sub defined schema/expressions ensuring at least
        one value is valid.
        :param data: data to be validated by provided schema.
        :return: return validated data if not validation
        """
        autos, errors = [], []
        for schema in self._schema_seq:
            try:
                validation = schema.validate(data)
                self.match_count += 1
                if self.match_count > 1 and self.only_one:
                    break
                return validation
            except SchemaError as _x:
                autos, errors = _x.autos, _x.errors
        raise SchemaError(
            ["%r did not validate %r" % (self, data)] + autos,
            [self._error.format(data) if self._error else None] + errors,
        )


class _Iterable(Base):

    def __init__(self, iterable, **kwargs):
        schema, error, ignore = _schema_args(kwargs)
        super(_Iterable, self).__init__(error=error)
        self._type_check = schema(type(iterable), error=error)
        self._schema = Or(*iterable, error=error, schema=schema,
                          ignore_extra_keys=ignore)

    def validate(self, data):
        data = self._type_check.validate(data)
        return type(data)(self._schema.validate(d) for d in data)


class _Dict(Base):

    def __init__(self, dct, **kwargs):
        schema, error, ignore = _schema_args(kwargs)
        super(_Dict, self).__init__(error=error)
        self._ignore_extra_keys = ignore
        sorted_keys = sorted(dct, key=self._dict_key_priority)
        self._sorted = [(k, schema(k, error=error), schema(dct[k], error=error, ignore_extra_keys=ignore))
                        for k in sorted_keys]
        self._casting = schema(dict, error=error)
        self._required = set(k for k in dct if not self._is_optional_type(k))
        self._defaults = set(k for k in dct if type(k) is Optional and hasattr(k, "default"))
        self._resets = tuple(k for k in sorted_keys if hasattr(k, "reset"))

    @staticmethod
    def _dict_key_priority(s):
        """Return priority for a given key object."""
        if isinstance(s, Hook):
            return _priority(s._schema) - 0.5
        if isinstance(s, Optional):
            return _priority(s._schema) + 0.5
        return _priority(s)

    def validate(self, data):
        exitstack = ExitStack()
        e = self._error
        data = self._casting.validate(data)
        new = type(data)()  # new - is a dict of the validated values
        coverage = set()  # matched schema keys
        # for each key and value find a schema entry matching them, if any
        for skey in self._resets:
            exitstack.callback(skey.reset)
        with exitstack:
            # Evaluate dictionaries last
            data_items = sorted(data.items(), key=lambda value: isinstance(value[1], dict))
            for key, value in data_items:
                for skey, key_sc, val_sc in self._sorted:
                    try:
                        nkey = key_sc.validate(key)
                    except SchemaError:
                        pass
                    else:
                        if isinstance(skey, Hook):
                            # As the content of the value makes little sense for
                            # keys with a hook, we reverse its meaning:
                            # we will only call the handler if the value does match
                            # In the case of the forbidden key hook,
                            # we will raise the SchemaErrorForbiddenKey exception
                            # on match, allowing for excluding a key only if its
                            # value has a certain type, and allowing Forbidden to
                            # work well in combination with Optional.
                            try:
                                nvalue = val_sc.validate(value)
                            except SchemaError:
                                continue
                            skey.handler(nkey, data, e)
                        else:
                            if isinstance(skey, Hook):
                                # As the content of the value makes little sense for
                                # keys with a hook, we reverse its meaning:
                                # we will only call the handler if the value does match
                                # In the case of the forbidden key hook,
                                # we will raise the SchemaErrorForbiddenKey exception
                                # on match, allowing for excluding a key only if its
                                # value has a certain type, and allowing Forbidden to
                                # work well in combination with Optional.
                                try:
                                    nvalue = val_sc.validate(value)
                                except SchemaError:
                                    continue
                                skey.handler(nkey, data, e)
                            else:
                                try:
                                    nvalue = val_sc.validate(value)
                                except SchemaError as x:
                                    k = "Key '%s' error:" % nkey
                                    raise SchemaError([k] + x.autos, [e] + x.errors)
                                else:
                                    new[nkey] = nvalue
                                    coverage.add(skey)
                                    break

            if not self._required.issubset(coverage):
                missing_keys = self._required - coverage
                s_missing_keys = ", ".join(sorted(repr(k) for k in missing_keys))
                raise SchemaMissingKeyError("Missing key%s: %s" % (_plural_s(missing_keys), s_missing_keys), e)
            if not self._ignore_extra_keys and (len(new) != len(data)):
                wrong_keys = set(data.keys()) - set(new.keys())
                s_wrong_keys = ", ".join(sorted(repr(k) for k in wrong_keys))
                raise SchemaWrongKeyError(
                    "Wrong key%s %s in %r" % (_plural_s(wrong_keys), s_wrong_keys, data), e.format(data) if e else None
                )
            # Apply default-having optionals that haven't been used:
            for default in self._defaults - coverage:
                new[default.key] = default.default() if callable(default.default) else default.default

            return new


class _Wrapper(Base):
    """Helper class to wrap a error around a validator."""

    def __init__(self, validator, error=None):
        super(_Wrapper, self).__init__(error=error)
        self._worker = schemify(validator)

    def validate(self, data):
        try:
            return self._worker.validate(data)
        except SchemaError as x:
            raise SchemaError([None] + x.autos, [self._error] + x.errors)
        except BaseException as x:
            raise SchemaError(
                "%r.validate(%r) raised %r" % (self._worker, data, x), self._error.format(data) if self._error else None
            )


class Schema(Base):
    """
    Entry point of the library, use this class to instantiate validation
    schema for the data that will be validated.
    """

    def __init__(self, schema, error=None, ignore_extra_keys=False):
        super(Schema, self).__init__(error=error)
        self._schema = schema
        flavor = _priority(schema)
        if flavor == ITERABLE:
            self._worker = _Iterable(schema, schema=type(self), error=error,
                                     ignore_extra_keys=ignore_extra_keys)
        elif flavor == DICT:
            self._worker = _Dict(schema, schema=type(self), error=error,
                                 ignore_extra_keys=ignore_extra_keys)
        elif flavor == TYPE:
            self._worker = _Type(schema, error=error)
        elif flavor == VALIDATOR:
            self._worker = _Wrapper(schema, error=error)
        elif flavor == CALLABLE:
            self._worker = _Check(schema, error=error)
        else:
            self._worker = _Value(schema, error=error)
        self._ignore_extra_keys = ignore_extra_keys

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self._schema)

    def is_valid(self, data):
        """Return whether the given data has passed all the validations
        that were specified in the given schema.
        """
        try:
            self.validate(data)
            return True
        except SchemaError:
            return False

    def validate(self, data):
        return self._worker.validate(data)

    def json_schema(self, schema_id=None, is_main_schema=True):
        """Generate a draft-07 JSON schema dict representing the Schema.
        This method can only be called when the Schema's value is a dict.
        This method must be called with a schema_id. Calling it without one
        is used in a recursive context for sub schemas."""
        Schema = self.__class__
        s = self._schema
        i = self._ignore_extra_keys
        flavor = _priority(s)

        if flavor != DICT and is_main_schema:
            raise ValueError("The main schema must be a dict.")

        if flavor == TYPE:
            # Handle type
            return {"type": {int: "integer", float: "number", bool: "boolean"}.get(s, "string")}
        elif flavor == ITERABLE and len(s) == 1:
            # Handle arrays of a single type or dict schema
            return {"type": "array", "items": Schema(s[0]).json_schema(is_main_schema=False)}
        elif isinstance(s, Or):
            # Handle Or values
            values = [Schema(or_key).json_schema(is_main_schema=False) for or_key in s._args]
            any_of = []
            for value in values:
                if value not in any_of:
                    any_of.append(value)
            return {"anyOf": any_of}

        if flavor != DICT:
            # If not handled, do not check
            return {}

        if is_main_schema and not schema_id:
            raise ValueError("schema_id is required.")

        # Handle dict
        required_keys = []
        expanded_schema = {}
        for key in s:
            if isinstance(key, Hook):
                continue

            if isinstance(s[key], Schema):
                sub_schema = s[key]
            else:
                sub_schema = Schema(s[key], ignore_extra_keys=i)
            sub_schema_json = sub_schema.json_schema(is_main_schema=False)

            is_optional = False
            if isinstance(key, Optional):
                key = key._schema
                is_optional = True

            if isinstance(key, str):
                if not is_optional:
                    required_keys.append(key)
                expanded_schema[key] = sub_schema_json
            elif isinstance(key, Or):
                for or_key in key._args:
                    expanded_schema[or_key] = sub_schema_json
        schema_dict = {
            "type": "object",
            "properties": expanded_schema,
            "required": required_keys,
            "additionalProperties": i,
        }
        if is_main_schema:
            schema_dict.update({"id": schema_id, "$schema": "http://json-schema.org/draft-07/schema#"})
        return schema_dict


class Optional(Schema):
    """Marker for an optional part of the validation Schema."""

    _MARKER = object()

    def __init__(self, *args, **kwargs):
        default = kwargs.pop("default", self._MARKER)
        super(Optional, self).__init__(*args, **kwargs)
        if default is not self._MARKER:
            # See if I can come up with a static key to use for myself:
            if _priority(self._schema) != COMPARABLE:
                raise TypeError(
                    "Optional keys with defaults must have simple, "
                    "predictable values, like literal strings or ints. "
                    '"%r" is too complex.' % (self._schema,)
                )
            self.default = default
            self.key = self._schema

    def __hash__(self):
        return hash(self._schema)

    def __eq__(self, other):
        return (
            self.__class__ is other.__class__
            and getattr(self, "default", self._MARKER) == getattr(other, "default", self._MARKER)
            and self._schema == other._schema
        )

    def reset(self):
        if hasattr(self._schema, "reset"):
            self._schema.reset()


class Hook(Schema):
    def __init__(self, *args, **kwargs):
        self.handler = kwargs.pop("handler", lambda *args: None)
        super(Hook, self).__init__(*args, **kwargs)
        self.key = self._schema


class Forbidden(Hook):
    def __init__(self, *args, **kwargs):
        kwargs["handler"] = self._default_function
        super(Forbidden, self).__init__(*args, **kwargs)

    @staticmethod
    def _default_function(nkey, data, error):
        raise SchemaForbiddenKeyError("Forbidden key encountered: %r in %r" % (nkey, data), error)


class Const(Schema):
    def validate(self, data):
        super(Const, self).validate(data)
        return data


def _plural_s(sized):
    return "s" if len(sized) > 1 else ""

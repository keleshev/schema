"""schema is a library for validating Python data structures, such as those
obtained from config-files, forms, external services or command-line
parsing, converted from JSON/YAML (or something else) to Python data-types."""

import re

try:
    from contextlib import ExitStack
except ImportError:
    from contextlib2 import ExitStack

__version__ = '0.7.0'
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


class And(object):
    """
    Utility function to combine validation directives in AND Boolean fashion.
    """

    def __init__(self, *args, **kw):
        self._args = args
        if not set(kw).issubset({"error", "schema", "ignore_extra_keys"}):
            diff = {"error", "schema", "ignore_extra_keys"}.difference(kw)
            raise TypeError("Unknown keyword arguments %r" % list(diff))
        self._error = kw.get("error")
        self._ignore_extra_keys = kw.get("ignore_extra_keys", False)
        # You can pass your inherited Schema class.
        self._schema = kw.get("schema", Schema)

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, ", ".join(repr(a) for a in self._args))

    def validate(self, data):
        """
        Validate data using defined sub schema/expressions ensuring all
        values are valid.
        :param data: to be validated with sub defined schemas.
        :return: returns validated data
        """
        for s in [self._schema(s, error=self._error, ignore_extra_keys=self._ignore_extra_keys) for s in self._args]:
            data = s.validate(data)
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
        for s in [self._schema(s, error=self._error, ignore_extra_keys=self._ignore_extra_keys) for s in self._args]:
            try:
                validation = s.validate(data)
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


class Regex(object):
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
        self._pattern_str = pattern_str
        flags_list = [Regex.NAMES[i] for i, f in enumerate("{0:09b}".format(flags)) if f != "0"]  # Name for each bit

        if flags_list:
            self._flags_names = ", flags=" + "|".join(flags_list)
        else:
            self._flags_names = ""

        self._pattern = re.compile(pattern_str, flags=flags)
        self._error = error

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
            else:
                raise SchemaError("%r does not match %r" % (self, data), e)
        except TypeError:
            raise SchemaError("%r is not string nor buffer" % data, e)


class Use(object):
    """
    For more general use cases, you can use the Use class to transform
    the data while it is being validate.
    """

    def __init__(self, callable_, error=None):
        if not callable(callable_):
            raise TypeError("Expected a callable, not %r" % callable_)
        self._callable = callable_
        self._error = error

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
    else:
        return COMPARABLE


class Schema(object):
    """
    Entry point of the library, use this class to instantiate validation
    schema for the data that will be validated.
    """

    def __init__(self, schema, error=None, ignore_extra_keys=False, name=None):
        self._schema = schema
        self._error = error
        self._ignore_extra_keys = ignore_extra_keys
        self._name = name

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self._schema)

    @staticmethod
    def _dict_key_priority(s):
        """Return priority for a given key object."""
        if isinstance(s, Hook):
            return _priority(s._schema) - 0.5
        if isinstance(s, Optional):
            return _priority(s._schema) + 0.5
        return _priority(s)

    @staticmethod
    def _is_optional_type(s):
        """Return True if the given key is optional (does not have to be found"""
        return any(isinstance(s, optional_type) for optional_type in [Optional, Hook])

    def is_valid(self, data):
        """Return whether the given data has passed all the validations
        that were specified in the given schema.
        """
        try:
            self.validate(data)
        except SchemaError:
            return False
        else:
            return True

    def _prepend_schema_name(self, message):
        """
        If a custom schema name has been defined, prepends it to the error
        message that gets raised when a schema error occurs.
        """
        if self._name:
            message = "{0!r} {1!s}".format(self._name, message)
        return message

    def validate(self, data):
        Schema = self.__class__
        s = self._schema
        e = self._error
        i = self._ignore_extra_keys
        flavor = _priority(s)
        if flavor == ITERABLE:
            data = Schema(type(s), error=e).validate(data)
            o = Or(*s, error=e, schema=Schema, ignore_extra_keys=i)
            return type(data)(o.validate(d) for d in data)
        if flavor == DICT:
            exitstack = ExitStack()
            data = Schema(dict, error=e).validate(data)
            new = type(data)()  # new - is a dict of the validated values
            coverage = set()  # matched schema keys
            # for each key and value find a schema entry matching them, if any
            sorted_skeys = sorted(s, key=self._dict_key_priority)
            for skey in sorted_skeys:
                if hasattr(skey, "reset"):
                    exitstack.callback(skey.reset)

            with exitstack:
                # Evaluate dictionaries last
                data_items = sorted(data.items(), key=lambda value: isinstance(value[1], dict))
                for key, value in data_items:
                    for skey in sorted_skeys:
                        svalue = s[skey]
                        try:
                            nkey = Schema(skey, error=e).validate(key)
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
                                    nvalue = Schema(svalue, error=e).validate(value)
                                except SchemaError:
                                    continue
                                skey.handler(nkey, data, e)
                            else:
                                try:
                                    nvalue = Schema(svalue, error=e, ignore_extra_keys=i).validate(value)
                                except SchemaError as x:
                                    k = "Key '%s' error:" % nkey
                                    message = self._prepend_schema_name(k)
                                    raise SchemaError([message] + x.autos, [e] + x.errors)
                                else:
                                    new[nkey] = nvalue
                                    coverage.add(skey)
                                    break
            required = set(k for k in s if not self._is_optional_type(k))
            if not required.issubset(coverage):
                missing_keys = required - coverage
                s_missing_keys = ", ".join(repr(k) for k in sorted(missing_keys, key=repr))
                message = "Missing key%s: %s" % (_plural_s(missing_keys), s_missing_keys)
                message = self._prepend_schema_name(message)
                raise SchemaMissingKeyError(message, e)
            if not self._ignore_extra_keys and (len(new) != len(data)):
                wrong_keys = set(data.keys()) - set(new.keys())
                s_wrong_keys = ", ".join(repr(k) for k in sorted(wrong_keys, key=repr))
                message = "Wrong key%s %s in %r" % (_plural_s(wrong_keys), s_wrong_keys, data)
                message = self._prepend_schema_name(message)
                raise SchemaWrongKeyError(message, e.format(data) if e else None)

            # Apply default-having optionals that haven't been used:
            defaults = set(k for k in s if type(k) is Optional and hasattr(k, "default")) - coverage
            for default in defaults:
                new[default.key] = default.default() if callable(default.default) else default.default

            return new
        if flavor == TYPE:
            if isinstance(data, s) and not (isinstance(data, bool) and s == int):
                return data
            else:
                message = "%r should be instance of %r" % (data, s.__name__)
                message = self._prepend_schema_name(message)
                raise SchemaUnexpectedTypeError(message, e.format(data) if e else None)
        if flavor == VALIDATOR:
            try:
                return s.validate(data)
            except SchemaError as x:
                raise SchemaError([None] + x.autos, [e] + x.errors)
            except BaseException as x:
                message = "%r.validate(%r) raised %r" % (s, data, x)
                message = self._prepend_schema_name(message)
                raise SchemaError(message, self._error.format(data) if self._error else None)
        if flavor == CALLABLE:
            f = _callable_str(s)
            try:
                if s(data):
                    return data
            except SchemaError as x:
                raise SchemaError([None] + x.autos, [e] + x.errors)
            except BaseException as x:
                message = "%s(%r) raised %r" % (f, data, x)
                message = self._prepend_schema_name(message)
                raise SchemaError(message, self._error.format(data) if self._error else None)
            message = "%s(%r) should evaluate to True" % (f, data)
            message = self._prepend_schema_name(message)
            raise SchemaError(message, e)
        if s == data:
            return data
        else:
            message = "%r does not match %r" % (s, data)
            message = self._prepend_schema_name(message)
            raise SchemaError(message, e.format(data) if e else None)

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


def _callable_str(callable_):
    if hasattr(callable_, "__name__"):
        return callable_.__name__
    return str(callable_)


def _plural_s(sized):
    return "s" if len(sized) > 1 else ""

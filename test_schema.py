from __future__ import with_statement

import copy
import json
import os
import platform
import re
import sys
from collections import defaultdict
from collections import namedtuple
from functools import partial
from operator import methodcaller

try:
    from unittest.mock import Mock
except ImportError:
    from mock import Mock
from pytest import mark, raises

from schema import (
    And,
    Const,
    Forbidden,
    Hook,
    Literal,
    Optional,
    Or,
    Regex,
    Schema,
    SchemaError,
    SchemaForbiddenKeyError,
    SchemaMissingKeyError,
    SchemaUnexpectedTypeError,
    SchemaWrongKeyError,
    Use,
)

if sys.version_info[0] == 3:
    basestring = str  # Python 3 does not have basestring
    unicode = str  # Python 3 does not have unicode


SE = raises(SchemaError)


def ve(_):
    raise ValueError()


def se(_):
    raise SchemaError("first auto", "first error")


def sorted_dict(to_sort):
    """Helper function to sort list of string inside dictionaries in order to compare them"""
    if isinstance(to_sort, dict):
        new_dict = {}
        for k in sorted(to_sort.keys()):
            new_dict[k] = sorted_dict(to_sort[k])
        return new_dict
    if isinstance(to_sort, list) and to_sort:
        if isinstance(to_sort[0], str):
            return sorted(to_sort)
        else:
            return [sorted_dict(element) for element in to_sort]
    return to_sort


def test_schema():
    assert Schema(1).validate(1) == 1
    with SE:
        Schema(1).validate(9)

    assert Schema(int).validate(1) == 1
    with SE:
        Schema(int).validate("1")
    assert Schema(Use(int)).validate("1") == 1
    with SE:
        Schema(int).validate(int)
    with SE:
        Schema(int).validate(True)
    with SE:
        Schema(int).validate(False)

    assert Schema(str).validate("hai") == "hai"
    with SE:
        Schema(str).validate(1)
    assert Schema(Use(str)).validate(1) == "1"

    assert Schema(list).validate(["a", 1]) == ["a", 1]
    assert Schema(dict).validate({"a": 1}) == {"a": 1}
    with SE:
        Schema(dict).validate(["a", 1])

    assert Schema(lambda n: 0 < n < 5).validate(3) == 3
    with SE:
        Schema(lambda n: 0 < n < 5).validate(-1)


def test_validate_file():
    assert Schema(Use(open)).validate("LICENSE-MIT").read().startswith("Copyright")
    with SE:
        Schema(Use(open)).validate("NON-EXISTENT")
    assert Schema(os.path.exists).validate(".") == "."
    with SE:
        Schema(os.path.exists).validate("./non-existent/")
    assert Schema(os.path.isfile).validate("LICENSE-MIT") == "LICENSE-MIT"
    with SE:
        Schema(os.path.isfile).validate("NON-EXISTENT")


def test_and():
    assert And(int, lambda n: 0 < n < 5).validate(3) == 3
    with SE:
        And(int, lambda n: 0 < n < 5).validate(3.33)
    assert And(Use(int), lambda n: 0 < n < 5).validate(3.33) == 3
    with SE:
        And(Use(int), lambda n: 0 < n < 5).validate("3.33")


def test_or():
    assert Or(int, dict).validate(5) == 5
    assert Or(int, dict).validate({}) == {}
    with SE:
        Or(int, dict).validate("hai")
    assert Or(int).validate(4)
    with SE:
        Or().validate(2)


def test_or_only_one():
    or_rule = Or("test1", "test2", only_one=True)
    schema = Schema(
        {or_rule: str, Optional("sub_schema"): {Optional(copy.deepcopy(or_rule)): str}}
    )
    assert schema.validate({"test1": "value"})
    assert schema.validate({"test1": "value", "sub_schema": {"test2": "value"}})
    assert schema.validate({"test2": "other_value"})
    with SE:
        schema.validate({"test1": "value", "test2": "other_value"})
    with SE:
        schema.validate(
            {"test1": "value", "sub_schema": {"test1": "value", "test2": "value"}}
        )
    with SE:
        schema.validate({"othertest": "value"})

    extra_keys_schema = Schema({or_rule: str}, ignore_extra_keys=True)
    assert extra_keys_schema.validate({"test1": "value", "other-key": "value"})
    assert extra_keys_schema.validate({"test2": "other_value"})
    with SE:
        extra_keys_schema.validate({"test1": "value", "test2": "other_value"})


def test_test():
    def unique_list(_list):
        return len(_list) == len(set(_list))

    def dict_keys(key, _list):
        return list(map(lambda d: d[key], _list))

    schema = Schema(Const(And(Use(partial(dict_keys, "index")), unique_list)))
    data = [{"index": 1, "value": "foo"}, {"index": 2, "value": "bar"}]
    assert schema.validate(data) == data

    bad_data = [{"index": 1, "value": "foo"}, {"index": 1, "value": "bar"}]
    with SE:
        schema.validate(bad_data)


def test_regex():
    # Simple case: validate string
    assert Regex(r"foo").validate("afoot") == "afoot"
    with SE:
        Regex(r"bar").validate("afoot")

    # More complex case: validate string
    assert Regex(r"^[a-z]+$").validate("letters") == "letters"
    with SE:
        Regex(r"^[a-z]+$").validate("letters + spaces") == "letters + spaces"

    # Validate dict key
    assert Schema({Regex(r"^foo"): str}).validate({"fookey": "value"}) == {
        "fookey": "value"
    }
    with SE:
        Schema({Regex(r"^foo"): str}).validate({"barkey": "value"})

    # Validate dict value
    assert Schema({str: Regex(r"^foo")}).validate({"key": "foovalue"}) == {
        "key": "foovalue"
    }
    with SE:
        Schema({str: Regex(r"^foo")}).validate({"key": "barvalue"})

    # Error if the value does not have a buffer interface
    with SE:
        Regex(r"bar").validate(1)
    with SE:
        Regex(r"bar").validate({})
    with SE:
        Regex(r"bar").validate([])
    with SE:
        Regex(r"bar").validate(None)

    # Validate that the pattern has a buffer interface
    assert Regex(re.compile(r"foo")).validate("foo") == "foo"
    assert Regex(unicode("foo")).validate("foo") == "foo"
    with raises(TypeError):
        Regex(1).validate("bar")
    with raises(TypeError):
        Regex({}).validate("bar")
    with raises(TypeError):
        Regex([]).validate("bar")
    with raises(TypeError):
        Regex(None).validate("bar")


def test_validate_list():
    assert Schema([1, 0]).validate([1, 0, 1, 1]) == [1, 0, 1, 1]
    assert Schema([1, 0]).validate([]) == []
    with SE:
        Schema([1, 0]).validate(0)
    with SE:
        Schema([1, 0]).validate([2])
    assert And([1, 0], lambda lst: len(lst) > 2).validate([0, 1, 0]) == [0, 1, 0]
    with SE:
        And([1, 0], lambda lst: len(lst) > 2).validate([0, 1])


def test_list_tuple_set_frozenset():
    assert Schema([int]).validate([1, 2])
    with SE:
        Schema([int]).validate(["1", 2])
    assert Schema(set([int])).validate(set([1, 2])) == set([1, 2])
    with SE:
        Schema(set([int])).validate([1, 2])  # not a set
    with SE:
        Schema(set([int])).validate(["1", 2])
    assert Schema(tuple([int])).validate(tuple([1, 2])) == tuple([1, 2])
    with SE:
        Schema(tuple([int])).validate([1, 2])  # not a set


def test_strictly():
    assert Schema(int).validate(1) == 1
    with SE:
        Schema(int).validate("1")


def test_dict():
    assert Schema({"key": 5}).validate({"key": 5}) == {"key": 5}
    with SE:
        Schema({"key": 5}).validate({"key": "x"})
    with SE:
        Schema({"key": 5}).validate(["key", 5])
    assert Schema({"key": int}).validate({"key": 5}) == {"key": 5}
    assert Schema({"n": int, "f": float}).validate({"n": 5, "f": 3.14}) == {
        "n": 5,
        "f": 3.14,
    }
    with SE:
        Schema({"n": int, "f": float}).validate({"n": 3.14, "f": 5})
    with SE:
        try:
            Schema({}).validate({"abc": None, 1: None})
        except SchemaWrongKeyError as e:
            assert e.args[0].startswith("Wrong keys 'abc', 1 in")
            raise
    with SE:
        try:
            Schema({"key": 5}).validate({})
        except SchemaMissingKeyError as e:
            assert e.args[0] == "Missing key: 'key'"
            raise
    with SE:
        try:
            Schema({"key": 5}).validate({"n": 5})
        except SchemaMissingKeyError as e:
            assert e.args[0] == "Missing key: 'key'"
            raise
    with SE:
        try:
            Schema({"key": 5, "key2": 5}).validate({"n": 5})
        except SchemaMissingKeyError as e:
            assert e.args[0] == "Missing keys: 'key', 'key2'"
            raise
    with SE:
        try:
            Schema({}).validate({"n": 5})
        except SchemaWrongKeyError as e:
            assert e.args[0] == "Wrong key 'n' in {'n': 5}"
            raise
    with SE:
        try:
            Schema({"key": 5}).validate({"key": 5, "bad": 5})
        except SchemaWrongKeyError as e:
            assert e.args[0] in [
                "Wrong key 'bad' in {'key': 5, 'bad': 5}",
                "Wrong key 'bad' in {'bad': 5, 'key': 5}",
            ]
            raise
    with SE:
        try:
            Schema({}).validate({"a": 5, "b": 5})
        except SchemaError as e:
            assert e.args[0] in [
                "Wrong keys 'a', 'b' in {'a': 5, 'b': 5}",
                "Wrong keys 'a', 'b' in {'b': 5, 'a': 5}",
            ]
            raise

    with SE:
        try:
            Schema({int: int}).validate({"": ""})
        except SchemaUnexpectedTypeError as e:
            assert e.args[0] in ["'' should be instance of 'int'"]


def test_dict_keys():
    assert Schema({str: int}).validate({"a": 1, "b": 2}) == {"a": 1, "b": 2}
    with SE:
        Schema({str: int}).validate({1: 1, "b": 2})
    assert Schema({Use(str): Use(int)}).validate({1: 3.14, 3.14: 1}) == {
        "1": 3,
        "3.14": 1,
    }


def test_ignore_extra_keys():
    assert Schema({"key": 5}, ignore_extra_keys=True).validate(
        {"key": 5, "bad": 4}
    ) == {"key": 5}
    assert Schema({"key": 5, "dk": {"a": "a"}}, ignore_extra_keys=True).validate(
        {"key": 5, "bad": "b", "dk": {"a": "a", "bad": "b"}}
    ) == {"key": 5, "dk": {"a": "a"}}
    assert Schema([{"key": "v"}], ignore_extra_keys=True).validate(
        [{"key": "v", "bad": "bad"}]
    ) == [{"key": "v"}]
    assert Schema([{"key": "v"}], ignore_extra_keys=True).validate(
        [{"key": "v", "bad": "bad"}]
    ) == [{"key": "v"}]


def test_ignore_extra_keys_validation_and_return_keys():
    assert Schema({"key": 5, object: object}, ignore_extra_keys=True).validate(
        {"key": 5, "bad": 4}
    ) == {
        "key": 5,
        "bad": 4,
    }
    assert Schema(
        {"key": 5, "dk": {"a": "a", object: object}}, ignore_extra_keys=True
    ).validate({"key": 5, "dk": {"a": "a", "bad": "b"}}) == {
        "key": 5,
        "dk": {"a": "a", "bad": "b"},
    }


def test_dict_forbidden_keys():
    with raises(SchemaForbiddenKeyError):
        Schema({Forbidden("b"): object}).validate({"b": "bye"})
    with raises(SchemaWrongKeyError):
        Schema({Forbidden("b"): int}).validate({"b": "bye"})
    assert Schema({Forbidden("b"): int, Optional("b"): object}).validate(
        {"b": "bye"}
    ) == {"b": "bye"}
    with raises(SchemaForbiddenKeyError):
        Schema({Forbidden("b"): object, Optional("b"): object}).validate({"b": "bye"})


def test_dict_hook():
    function_mock = Mock(return_value=None)
    hook = Hook("b", handler=function_mock)

    assert Schema({hook: str, Optional("b"): object}).validate({"b": "bye"}) == {
        "b": "bye"
    }
    function_mock.assert_called_once()

    assert Schema({hook: int, Optional("b"): object}).validate({"b": "bye"}) == {
        "b": "bye"
    }
    function_mock.assert_called_once()

    assert Schema({hook: str, "b": object}).validate({"b": "bye"}) == {"b": "bye"}
    assert function_mock.call_count == 2


def test_dict_optional_keys():
    with SE:
        Schema({"a": 1, "b": 2}).validate({"a": 1})
    assert Schema({"a": 1, Optional("b"): 2}).validate({"a": 1}) == {"a": 1}
    assert Schema({"a": 1, Optional("b"): 2}).validate({"a": 1, "b": 2}) == {
        "a": 1,
        "b": 2,
    }
    # Make sure Optionals are favored over types:
    assert Schema({basestring: 1, Optional("b"): 2}).validate({"a": 1, "b": 2}) == {
        "a": 1,
        "b": 2,
    }
    # Make sure Optionals hash based on their key:
    assert len({Optional("a"): 1, Optional("a"): 1, Optional("b"): 2}) == 2


def test_dict_optional_defaults():
    # Optionals fill out their defaults:
    assert Schema(
        {Optional("a", default=1): 11, Optional("b", default=2): 22}
    ).validate({"a": 11}) == {"a": 11, "b": 2}

    # Optionals take precedence over types. Here, the "a" is served by the
    # Optional:
    assert Schema({Optional("a", default=1): 11, basestring: 22}).validate(
        {"b": 22}
    ) == {"a": 1, "b": 22}

    with raises(TypeError):
        Optional(And(str, Use(int)), default=7)


def test_dict_subtypes():
    d = defaultdict(int, key=1)
    v = Schema({"key": 1}).validate(d)
    assert v == d
    assert isinstance(v, defaultdict)
    # Please add tests for Counter and OrderedDict once support for Python2.6
    # is dropped!


def test_dict_key_error():
    try:
        Schema({"k": int}).validate({"k": "x"})
    except SchemaError as e:
        assert e.code == "Key 'k' error:\n'x' should be instance of 'int'"
    try:
        Schema({"k": {"k2": int}}).validate({"k": {"k2": "x"}})
    except SchemaError as e:
        code = "Key 'k' error:\nKey 'k2' error:\n'x' should be instance of 'int'"
        assert e.code == code
    try:
        Schema({"k": {"k2": int}}, error="k2 should be int").validate(
            {"k": {"k2": "x"}}
        )
    except SchemaError as e:
        assert e.code == "k2 should be int"


def test_complex():
    s = Schema(
        {
            "<file>": And([Use(open)], lambda lst: len(lst)),
            "<path>": os.path.exists,
            Optional("--count"): And(int, lambda n: 0 <= n <= 5),
        }
    )
    data = s.validate({"<file>": ["./LICENSE-MIT"], "<path>": "./"})
    assert len(data) == 2
    assert len(data["<file>"]) == 1
    assert data["<file>"][0].read().startswith("Copyright")
    assert data["<path>"] == "./"


def test_nice_errors():
    try:
        Schema(int, error="should be integer").validate("x")
    except SchemaError as e:
        assert e.errors == ["should be integer"]
    try:
        Schema(Use(float), error="should be a number").validate("x")
    except SchemaError as e:
        assert e.code == "should be a number"
    try:
        Schema({Optional("i"): Use(int, error="should be a number")}).validate(
            {"i": "x"}
        )
    except SchemaError as e:
        assert e.code == "should be a number"


def test_use_error_handling():
    try:
        Use(ve).validate("x")
    except SchemaError as e:
        assert e.autos == ["ve('x') raised ValueError()"]
        assert e.errors == [None]
    try:
        Use(ve, error="should not raise").validate("x")
    except SchemaError as e:
        assert e.autos == ["ve('x') raised ValueError()"]
        assert e.errors == ["should not raise"]
    try:
        Use(se).validate("x")
    except SchemaError as e:
        assert e.autos == [None, "first auto"]
        assert e.errors == [None, "first error"]
    try:
        Use(se, error="second error").validate("x")
    except SchemaError as e:
        assert e.autos == [None, "first auto"]
        assert e.errors == ["second error", "first error"]


def test_or_error_handling():
    try:
        Or(ve).validate("x")
    except SchemaError as e:
        assert e.autos[0].startswith("Or(")
        assert e.autos[0].endswith(") did not validate 'x'")
        assert e.autos[1] == "ve('x') raised ValueError()"
        assert len(e.autos) == 2
        assert e.errors == [None, None]
    try:
        Or(ve, error="should not raise").validate("x")
    except SchemaError as e:
        assert e.autos[0].startswith("Or(")
        assert e.autos[0].endswith(") did not validate 'x'")
        assert e.autos[1] == "ve('x') raised ValueError()"
        assert len(e.autos) == 2
        assert e.errors == ["should not raise", "should not raise"]
    try:
        Or("o").validate("x")
    except SchemaError as e:
        assert e.autos == ["Or('o') did not validate 'x'", "'o' does not match 'x'"]
        assert e.errors == [None, None]
    try:
        Or("o", error="second error").validate("x")
    except SchemaError as e:
        assert e.autos == ["Or('o') did not validate 'x'", "'o' does not match 'x'"]
        assert e.errors == ["second error", "second error"]


def test_and_error_handling():
    try:
        And(ve).validate("x")
    except SchemaError as e:
        assert e.autos == ["ve('x') raised ValueError()"]
        assert e.errors == [None]
    try:
        And(ve, error="should not raise").validate("x")
    except SchemaError as e:
        assert e.autos == ["ve('x') raised ValueError()"]
        assert e.errors == ["should not raise"]
    try:
        And(str, se).validate("x")
    except SchemaError as e:
        assert e.autos == [None, "first auto"]
        assert e.errors == [None, "first error"]
    try:
        And(str, se, error="second error").validate("x")
    except SchemaError as e:
        assert e.autos == [None, "first auto"]
        assert e.errors == ["second error", "first error"]


def test_schema_error_handling():
    try:
        Schema(Use(ve)).validate("x")
    except SchemaError as e:
        assert e.autos == [None, "ve('x') raised ValueError()"]
        assert e.errors == [None, None]
    try:
        Schema(Use(ve), error="should not raise").validate("x")
    except SchemaError as e:
        assert e.autos == [None, "ve('x') raised ValueError()"]
        assert e.errors == ["should not raise", None]
    try:
        Schema(Use(se)).validate("x")
    except SchemaError as e:
        assert e.autos == [None, None, "first auto"]
        assert e.errors == [None, None, "first error"]
    try:
        Schema(Use(se), error="second error").validate("x")
    except SchemaError as e:
        assert e.autos == [None, None, "first auto"]
        assert e.errors == ["second error", None, "first error"]


def test_use_json():
    import json

    gist_schema = Schema(
        And(
            Use(json.loads),  # first convert from JSON
            {
                Optional("description"): basestring,
                "public": bool,
                "files": {basestring: {"content": basestring}},
            },
        )
    )
    gist = """{"description": "the description for this gist",
               "public": true,
               "files": {
                   "file1.txt": {"content": "String file contents"},
                   "other.txt": {"content": "Another file contents"}}}"""
    assert gist_schema.validate(gist)


def test_error_reporting():
    s = Schema(
        {
            "<files>": [Use(open, error="<files> should be readable")],
            "<path>": And(os.path.exists, error="<path> should exist"),
            "--count": Or(
                None,
                And(Use(int), lambda n: 0 < n < 5),
                error="--count should be integer 0 < n < 5",
            ),
        },
        error="Error:",
    )
    s.validate({"<files>": [], "<path>": "./", "--count": 3})

    try:
        s.validate({"<files>": [], "<path>": "./", "--count": "10"})
    except SchemaError as e:
        assert e.code == "Error:\n--count should be integer 0 < n < 5"
    try:
        s.validate({"<files>": [], "<path>": "./hai", "--count": "2"})
    except SchemaError as e:
        assert e.code == "Error:\n<path> should exist"
    try:
        s.validate({"<files>": ["hai"], "<path>": "./", "--count": "2"})
    except SchemaError as e:
        assert e.code == "Error:\n<files> should be readable"


def test_schema_repr():  # what about repr with `error`s?
    schema = Schema([Or(None, And(str, Use(float)))])
    repr_ = "Schema([Or(None, And(<type 'str'>, Use(<type 'float'>)))])"
    # in Python 3 repr contains <class 'str'>, not <type 'str'>
    assert repr(schema).replace("class", "type") == repr_


def test_validate_object():
    schema = Schema({object: str})
    assert schema.validate({42: "str"}) == {42: "str"}
    with SE:
        schema.validate({42: 777})


def test_issue_9_prioritized_key_comparison():
    validate = Schema({"key": 42, object: 42}).validate
    assert validate({"key": 42, 777: 42}) == {"key": 42, 777: 42}


def test_issue_9_prioritized_key_comparison_in_dicts():
    # http://stackoverflow.com/questions/14588098/docopt-schema-validation
    s = Schema(
        {
            "ID": Use(int, error="ID should be an int"),
            "FILE": Or(None, Use(open, error="FILE should be readable")),
            Optional(str): object,
        }
    )
    data = {"ID": 10, "FILE": None, "other": "other", "other2": "other2"}
    assert s.validate(data) == data
    data = {"ID": 10, "FILE": None}
    assert s.validate(data) == data


def test_missing_keys_exception_with_non_str_dict_keys():
    s = Schema({And(str, Use(str.lower), "name"): And(str, len)})
    with SE:
        s.validate(dict())
    with SE:
        try:
            Schema({1: "x"}).validate(dict())
        except SchemaMissingKeyError as e:
            assert e.args[0] == "Missing key: 1"
            raise


# PyPy does have a __name__ attribute for its callables.
@mark.skipif(platform.python_implementation() == "PyPy", reason="Running on PyPy")
def test_issue_56_cant_rely_on_callables_to_have_name():
    s = Schema(methodcaller("endswith", ".csv"))
    assert s.validate("test.csv") == "test.csv"
    with SE:
        try:
            s.validate("test.py")
        except SchemaError as e:
            assert "operator.methodcaller" in e.args[0]
            raise


def test_exception_handling_with_bad_validators():
    BadValidator = namedtuple("BadValidator", ["validate"])
    s = Schema(BadValidator("haha"))
    with SE:
        try:
            s.validate("test")
        except SchemaError as e:
            assert "TypeError" in e.args[0]
            raise


def test_issue_83_iterable_validation_return_type():
    TestSetType = type("TestSetType", (set,), dict())
    data = TestSetType(["test", "strings"])
    s = Schema(set([str]))
    assert isinstance(s.validate(data), TestSetType)


def test_optional_key_convert_failed_randomly_while_with_another_optional_object():
    """
    In this test, created_at string "2015-10-10 00:00:00" is expected to be converted
    to a datetime instance.
        - it works when the schema is

            s = Schema({
                    'created_at': _datetime_validator,
                    Optional(basestring): object,
                })

        - but when wrapping the key 'created_at' with Optional, it fails randomly
    :return:
    """
    import datetime

    fmt = "%Y-%m-%d %H:%M:%S"
    _datetime_validator = Or(None, Use(lambda i: datetime.datetime.strptime(i, fmt)))
    # FIXME given tests enough
    for i in range(1024):
        s = Schema(
            {
                Optional("created_at"): _datetime_validator,
                Optional("updated_at"): _datetime_validator,
                Optional("birth"): _datetime_validator,
                Optional(basestring): object,
            }
        )
        data = {"created_at": "2015-10-10 00:00:00"}
        validated_data = s.validate(data)
        # is expected to be converted to a datetime instance, but fails randomly
        # (most of the time)
        assert isinstance(validated_data["created_at"], datetime.datetime)
        # assert isinstance(validated_data['created_at'], basestring)


def test_copy():
    s1 = SchemaError("a", None)
    s2 = copy.deepcopy(s1)
    assert s1 is not s2
    assert type(s1) is type(s2)


def test_inheritance():
    def convert(data):
        if isinstance(data, int):
            return data + 1
        return data

    class MySchema(Schema):
        def validate(self, data):
            return super(MySchema, self).validate(convert(data))

    s = {"k": int, "d": {"k": int, "l": [{"l": [int]}]}}
    v = {"k": 1, "d": {"k": 2, "l": [{"l": [3, 4, 5]}]}}
    d = MySchema(s).validate(v)
    assert d["k"] == 2 and d["d"]["k"] == 3 and d["d"]["l"][0]["l"] == [4, 5, 6]


def test_inheritance_validate_kwargs():
    def convert(data, increment):
        if isinstance(data, int):
            return data + increment
        return data

    class MySchema(Schema):
        def validate(self, data, increment=1):
            return super(MySchema, self).validate(
                convert(data, increment), increment=increment
            )

    s = {"k": int, "d": {"k": int, "l": [{"l": [int]}]}}
    v = {"k": 1, "d": {"k": 2, "l": [{"l": [3, 4, 5]}]}}
    d = MySchema(s).validate(v, increment=1)
    assert d["k"] == 2 and d["d"]["k"] == 3 and d["d"]["l"][0]["l"] == [4, 5, 6]
    d = MySchema(s).validate(v, increment=10)
    assert d["k"] == 11 and d["d"]["k"] == 12 and d["d"]["l"][0]["l"] == [13, 14, 15]


def test_inheritance_validate_kwargs_passed_to_nested_schema():
    def convert(data, increment):
        if isinstance(data, int):
            return data + increment
        return data

    class MySchema(Schema):
        def validate(self, data, increment=1):
            return super(MySchema, self).validate(
                convert(data, increment), increment=increment
            )

    # note only d.k is under MySchema, and all others are under Schema without
    # increment
    s = {"k": int, "d": MySchema({"k": int, "l": [Schema({"l": [int]})]})}
    v = {"k": 1, "d": {"k": 2, "l": [{"l": [3, 4, 5]}]}}
    d = Schema(s).validate(v, increment=1)
    assert d["k"] == 1 and d["d"]["k"] == 3 and d["d"]["l"][0]["l"] == [3, 4, 5]
    d = Schema(s).validate(v, increment=10)
    assert d["k"] == 1 and d["d"]["k"] == 12 and d["d"]["l"][0]["l"] == [3, 4, 5]


def test_optional_callable_default_get_inherited_schema_validate_kwargs():
    def convert(data, increment):
        if isinstance(data, int):
            return data + increment
        return data

    s = {
        "k": int,
        "d": {
            Optional("k", default=lambda **kw: convert(2, kw["increment"])): int,
            "l": [{"l": [int]}],
        },
    }
    v = {"k": 1, "d": {"l": [{"l": [3, 4, 5]}]}}
    d = Schema(s).validate(v, increment=1)
    assert d["k"] == 1 and d["d"]["k"] == 3 and d["d"]["l"][0]["l"] == [3, 4, 5]
    d = Schema(s).validate(v, increment=10)
    assert d["k"] == 1 and d["d"]["k"] == 12 and d["d"]["l"][0]["l"] == [3, 4, 5]


def test_optional_callable_default_ignore_inherited_schema_validate_kwargs():
    def convert(data, increment):
        if isinstance(data, int):
            return data + increment
        return data

    s = {"k": int, "d": {Optional("k", default=lambda: 42): int, "l": [{"l": [int]}]}}
    v = {"k": 1, "d": {"l": [{"l": [3, 4, 5]}]}}
    d = Schema(s).validate(v, increment=1)
    assert d["k"] == 1 and d["d"]["k"] == 42 and d["d"]["l"][0]["l"] == [3, 4, 5]
    d = Schema(s).validate(v, increment=10)
    assert d["k"] == 1 and d["d"]["k"] == 42 and d["d"]["l"][0]["l"] == [3, 4, 5]


def test_inheritance_optional():
    def convert(data, increment):
        if isinstance(data, int):
            return data + increment
        return data

    class MyOptional(Optional):
        """This overrides the default property so it increments according
        to kwargs passed to validate()
        """

        @property
        def default(self):
            def wrapper(**kwargs):
                if "increment" in kwargs:
                    return convert(self._default, kwargs["increment"])
                return self._default

            return wrapper

        @default.setter
        def default(self, value):
            self._default = value

    s = {"k": int, "d": {MyOptional("k", default=2): int, "l": [{"l": [int]}]}}
    v = {"k": 1, "d": {"l": [{"l": [3, 4, 5]}]}}
    d = Schema(s).validate(v, increment=1)
    assert d["k"] == 1 and d["d"]["k"] == 3 and d["d"]["l"][0]["l"] == [3, 4, 5]
    d = Schema(s).validate(v, increment=10)
    assert d["k"] == 1 and d["d"]["k"] == 12 and d["d"]["l"][0]["l"] == [3, 4, 5]


def test_literal_repr():
    assert (
        repr(Literal("test", description="testing"))
        == 'Literal("test", description="testing")'
    )
    assert repr(Literal("test")) == 'Literal("test", description="")'


def test_json_schema():
    s = Schema({"test": str})
    assert s.json_schema("my-id") == {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "my-id",
        "properties": {"test": {"type": "string"}},
        "required": ["test"],
        "additionalProperties": False,
        "type": "object",
    }


def test_json_schema_with_title():
    s = Schema({"test": str}, name="Testing a schema")
    assert s.json_schema("my-id") == {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "my-id",
        "title": "Testing a schema",
        "properties": {"test": {"type": "string"}},
        "required": ["test"],
        "additionalProperties": False,
        "type": "object",
    }


def test_json_schema_types():
    s = Schema(
        {
            Optional("test_str"): str,
            Optional("test_int"): int,
            Optional("test_float"): float,
            Optional("test_bool"): bool,
        }
    )
    assert s.json_schema("my-id") == {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "my-id",
        "properties": {
            "test_str": {"type": "string"},
            "test_int": {"type": "integer"},
            "test_float": {"type": "number"},
            "test_bool": {"type": "boolean"},
        },
        "required": [],
        "additionalProperties": False,
        "type": "object",
    }


def test_json_schema_other_types():
    """Test that data types not supported by JSON schema are returned as strings"""
    s = Schema({Optional("test_other"): bytes})
    assert s.json_schema("my-id") == {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "my-id",
        "properties": {"test_other": {"type": "string"}},
        "required": [],
        "additionalProperties": False,
        "type": "object",
    }


def test_json_schema_nested():
    s = Schema({"test": {"other": str}}, ignore_extra_keys=True)
    assert s.json_schema("my-id") == {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "my-id",
        "properties": {
            "test": {
                "type": "object",
                "properties": {"other": {"type": "string"}},
                "additionalProperties": True,
                "required": ["other"],
            }
        },
        "required": ["test"],
        "additionalProperties": True,
        "type": "object",
    }


def test_json_schema_nested_schema():
    s = Schema({"test": Schema({"other": str}, ignore_extra_keys=True)})
    assert s.json_schema("my-id") == {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "my-id",
        "properties": {
            "test": {
                "type": "object",
                "properties": {"other": {"type": "string"}},
                "additionalProperties": True,
                "required": ["other"],
            }
        },
        "required": ["test"],
        "additionalProperties": False,
        "type": "object",
    }


def test_json_schema_optional_key():
    s = Schema({Optional("test"): str})
    assert s.json_schema("my-id") == {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "my-id",
        "properties": {"test": {"type": "string"}},
        "required": [],
        "additionalProperties": False,
        "type": "object",
    }


def test_json_schema_optional_key_nested():
    s = Schema({"test": {Optional("other"): str}})
    assert s.json_schema("my-id") == {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "my-id",
        "properties": {
            "test": {
                "type": "object",
                "properties": {"other": {"type": "string"}},
                "additionalProperties": False,
                "required": [],
            }
        },
        "required": ["test"],
        "additionalProperties": False,
        "type": "object",
    }


def test_json_schema_or_key():
    s = Schema({Or("test1", "test2"): str})
    assert s.json_schema("my-id") == {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "my-id",
        "properties": {"test1": {"type": "string"}, "test2": {"type": "string"}},
        "required": [],
        "additionalProperties": False,
        "type": "object",
    }


def test_json_schema_or_values():
    s = Schema({"param": Or("test1", "test2")})
    assert s.json_schema("my-id") == {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "my-id",
        "properties": {"param": {"enum": ["test1", "test2"]}},
        "required": ["param"],
        "additionalProperties": False,
        "type": "object",
    }


def test_json_schema_or_values_nested():
    s = Schema({"param": Or([str], [list])})
    assert s.json_schema("my-id") == {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "my-id",
        "properties": {
            "param": {
                "anyOf": [
                    {"type": "array", "items": {"type": "string"}},
                    {"type": "array", "items": {"type": "array"}},
                ]
            }
        },
        "required": ["param"],
        "additionalProperties": False,
        "type": "object",
    }


def test_json_schema_or_values_with_optional():
    s = Schema({Optional("whatever"): Or("test1", "test2")})
    assert s.json_schema("my-id") == {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "my-id",
        "properties": {"whatever": {"enum": ["test1", "test2"]}},
        "required": [],
        "additionalProperties": False,
        "type": "object",
    }


def test_json_schema_regex():
    s = Schema({Optional("username"): Regex("[a-zA-Z][a-zA-Z0-9]{3,}")})
    assert s.json_schema("my-id") == {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "my-id",
        "properties": {
            "username": {"type": "string", "pattern": "[a-zA-Z][a-zA-Z0-9]{3,}"}
        },
        "required": [],
        "additionalProperties": False,
        "type": "object",
    }


def test_json_schema_or_types():
    s = Schema({"test": Or(str, int)})
    assert s.json_schema("my-id") == {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "my-id",
        "properties": {"test": {"anyOf": [{"type": "string"}, {"type": "integer"}]}},
        "required": ["test"],
        "additionalProperties": False,
        "type": "object",
    }


def test_json_schema_or_only_one():
    s = Schema({"test": Or(str, lambda x: len(x) < 5)})
    assert s.json_schema("my-id") == {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "my-id",
        "properties": {"test": {"type": "string"}},
        "required": ["test"],
        "additionalProperties": False,
        "type": "object",
    }


def test_json_schema_and_types():
    # Can't determine the type, it will not be checked
    s = Schema({"test": And(str, lambda x: len(x) < 5)})
    assert s.json_schema("my-id") == {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "my-id",
        "properties": {"test": {"type": "string"}},
        "required": ["test"],
        "additionalProperties": False,
        "type": "object",
    }


def test_json_schema_or_one_value():
    s = Schema({"test": Or(True)})
    assert s.json_schema("my-id") == {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "my-id",
        "properties": {"test": {"const": True}},
        "required": ["test"],
        "additionalProperties": False,
        "type": "object",
    }


def test_json_schema_const_is_none():
    s = Schema({"test": None})
    assert s.json_schema("my-id") == {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "my-id",
        "properties": {"test": {"const": None}},
        "required": ["test"],
        "additionalProperties": False,
        "type": "object",
    }


def test_json_schema_const_is_callable():
    def something_callable(x):
        return x * 2

    s = Schema({"test": something_callable})
    assert s.json_schema("my-id") == {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "my-id",
        "properties": {"test": {}},
        "required": ["test"],
        "additionalProperties": False,
        "type": "object",
    }


def test_json_schema_const_is_custom_type():
    class SomethingSerializable:
        def __str__(self):
            return "Hello!"

    s = Schema({"test": SomethingSerializable()})
    assert s.json_schema("my-id") == {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "my-id",
        "properties": {"test": {"const": "Hello!"}},
        "required": ["test"],
        "additionalProperties": False,
        "type": "object",
    }


def test_json_schema_default_is_custom_type():
    class SomethingSerializable:
        def __str__(self):
            return "Hello!"

    s = Schema({Optional("test", default=SomethingSerializable()): str})
    assert s.json_schema("my-id") == {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "my-id",
        "properties": {"test": {"default": "Hello!", "type": "string"}},
        "required": [],
        "additionalProperties": False,
        "type": "object",
    }


def test_json_schema_default_is_callable():
    def default_func():
        return "Hello!"

    s = Schema({Optional("test", default=default_func): str})
    assert s.json_schema("my-id") == {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "my-id",
        "properties": {"test": {"default": "Hello!", "type": "string"}},
        "required": [],
        "additionalProperties": False,
        "type": "object",
    }


def test_json_schema_default_is_callable_with_args_passed_from_json_schema():
    def default_func(**kwargs):
        return "Hello, " + kwargs["name"]

    s = Schema({Optional("test", default=default_func): str})
    assert s.json_schema("my-id", name="World!") == {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "my-id",
        "properties": {"test": {"default": "Hello, World!", "type": "string"}},
        "required": [],
        "additionalProperties": False,
        "type": "object",
    }


def test_json_schema_object_or_array_of_object():
    # Complex test where "test" accepts either an object or an array of that object
    o = {"param1": "test1", Optional("param2"): "test2"}
    s = Schema({"test": Or(o, [o])})
    assert s.json_schema("my-id") == {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "my-id",
        "properties": {
            "test": {
                "anyOf": [
                    {
                        "additionalProperties": False,
                        "properties": {
                            "param1": {"const": "test1"},
                            "param2": {"const": "test2"},
                        },
                        "required": ["param1"],
                        "type": "object",
                    },
                    {
                        "type": "array",
                        "items": {
                            "additionalProperties": False,
                            "properties": {
                                "param1": {"const": "test1"},
                                "param2": {"const": "test2"},
                            },
                            "required": ["param1"],
                            "type": "object",
                        },
                    },
                ]
            }
        },
        "required": ["test"],
        "additionalProperties": False,
        "type": "object",
    }


def test_json_schema_and_simple():
    s = Schema({"test1": And(str, "test2")})
    assert s.json_schema("my-id") == {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "my-id",
        "properties": {"test1": {"allOf": [{"type": "string"}, {"const": "test2"}]}},
        "required": ["test1"],
        "additionalProperties": False,
        "type": "object",
    }


def test_json_schema_and_list():
    s = Schema({"param1": And(["choice1", "choice2"], list)})
    assert s.json_schema("my-id") == {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "my-id",
        "properties": {
            "param1": {
                "allOf": [
                    {"type": "array", "items": {"enum": ["choice1", "choice2"]}},
                    {"type": "array"},
                ]
            }
        },
        "required": ["param1"],
        "additionalProperties": False,
        "type": "object",
    }


def test_json_schema_forbidden_key_ignored():
    s = Schema({Forbidden("forbidden"): str, "test": str})
    assert s.json_schema("my-id") == {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "my-id",
        "properties": {"test": {"type": "string"}},
        "required": ["test"],
        "additionalProperties": False,
        "type": "object",
    }


@mark.parametrize(
    "input_schema, ignore_extra_keys, additional_properties",
    [
        ({}, False, False),
        ({str: str}, False, True),
        ({Optional(str): str}, False, True),
        ({object: int}, False, True),
        ({}, True, True),
    ],
)
def test_json_schema_additional_properties(
    input_schema, ignore_extra_keys, additional_properties
):
    s = Schema(input_schema, ignore_extra_keys=ignore_extra_keys)
    assert s.json_schema("my-id") == {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "my-id",
        "required": [],
        "properties": {},
        "additionalProperties": additional_properties,
        "type": "object",
    }


def test_json_schema_additional_properties_multiple():
    s = Schema({"named_property": bool, object: int})
    assert s.json_schema("my-id") == {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "my-id",
        "required": ["named_property"],
        "properties": {"named_property": {"type": "boolean"}},
        "additionalProperties": True,
        "type": "object",
    }


@mark.parametrize(
    "input_schema, expected_keyword, expected_value",
    [
        (int, "type", "integer"),
        (float, "type", "number"),
        (list, "type", "array"),
        (bool, "type", "boolean"),
        (dict, "type", "object"),
        ("test", "const", "test"),
        (Or(1, 2, 3), "enum", [1, 2, 3]),
        (Or(str, int), "anyOf", [{"type": "string"}, {"type": "integer"}]),
        (And(str, "value"), "allOf", [{"type": "string"}, {"const": "value"}]),
    ],
)
def test_json_schema_root_not_dict(input_schema, expected_keyword, expected_value):
    """Test generating simple JSON Schemas where the root element is not a dict"""
    json_schema = Schema(input_schema).json_schema("my-id")

    assert json_schema == {
        expected_keyword: expected_value,
        "$id": "my-id",
        "$schema": "http://json-schema.org/draft-07/schema#",
    }


@mark.parametrize(
    "input_schema, expected_keyword, expected_value",
    [([1, 2, 3], "enum", [1, 2, 3]), ([1], "const", 1), ([str], "type", "string")],
)
def test_json_schema_array(input_schema, expected_keyword, expected_value):
    json_schema = Schema(input_schema).json_schema("my-id")

    assert json_schema == {
        "type": "array",
        "items": {expected_keyword: expected_value},
        "$id": "my-id",
        "$schema": "http://json-schema.org/draft-07/schema#",
    }


def test_json_schema_regex_root():
    json_schema = Schema(Regex("^v\\d+")).json_schema("my-id")

    assert json_schema == {
        "type": "string",
        "pattern": "^v\\d+",
        "$id": "my-id",
        "$schema": "http://json-schema.org/draft-07/schema#",
    }


def test_json_schema_dict_type():
    json_schema = Schema({Optional("test1", default={}): dict}).json_schema("my-id")

    assert json_schema == {
        "type": "object",
        "properties": {"test1": {"default": {}, "type": "object"}},
        "required": [],
        "additionalProperties": False,
        "$id": "my-id",
        "$schema": "http://json-schema.org/draft-07/schema#",
    }


def test_json_schema_title_and_description():
    s = Schema(
        {Literal("productId", description="The unique identifier for a product"): int},
        name="Product",
        description="A product in the catalog",
    )
    assert s.json_schema("my-id") == {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "my-id",
        "title": "Product",
        "description": "A product in the catalog",
        "properties": {
            "productId": {
                "description": "The unique identifier for a product",
                "type": "integer",
            }
        },
        "required": ["productId"],
        "additionalProperties": False,
        "type": "object",
    }


def test_json_schema_description_nested():
    s = Schema(
        {
            Optional(
                Literal("test1", description="A description here"), default={}
            ): Or([str], [list])
        }
    )
    assert s.json_schema("my-id") == {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "my-id",
        "properties": {
            "test1": {
                "default": {},
                "description": "A description here",
                "anyOf": [
                    {"items": {"type": "string"}, "type": "array"},
                    {"items": {"type": "array"}, "type": "array"},
                ],
            }
        },
        "required": [],
        "additionalProperties": False,
        "type": "object",
    }


def test_json_schema_description_or_nested():
    s = Schema(
        {
            Optional(
                Or(
                    Literal("test1", description="A description here"),
                    Literal("test2", description="Another"),
                )
            ): Or([str], [list])
        }
    )
    assert s.json_schema("my-id") == {
        "type": "object",
        "properties": {
            "test1": {
                "description": "A description here",
                "anyOf": [
                    {"items": {"type": "string"}, "type": "array"},
                    {"items": {"type": "array"}, "type": "array"},
                ],
            },
            "test2": {
                "description": "Another",
                "anyOf": [
                    {"items": {"type": "string"}, "type": "array"},
                    {"items": {"type": "array"}, "type": "array"},
                ],
            },
        },
        "required": [],
        "additionalProperties": False,
        "$id": "my-id",
        "$schema": "http://json-schema.org/draft-07/schema#",
    }


def test_json_schema_literal_with_enum():
    s = Schema(
        {
            Literal("test", description="A test"): Or(
                Literal("literal1", description="A literal with description"),
                Literal("literal2", description="Another literal with description"),
            )
        }
    )
    assert s.json_schema("my-id") == {
        "type": "object",
        "properties": {
            "test": {"description": "A test", "enum": ["literal1", "literal2"]}
        },
        "required": ["test"],
        "additionalProperties": False,
        "$id": "my-id",
        "$schema": "http://json-schema.org/draft-07/schema#",
    }


def test_json_schema_description_and_nested():
    s = Schema(
        {
            Optional(
                Or(
                    Literal("test1", description="A description here"),
                    Literal("test2", description="Another"),
                )
            ): And([str], [list])
        }
    )
    assert s.json_schema("my-id") == {
        "type": "object",
        "properties": {
            "test1": {
                "description": "A description here",
                "allOf": [
                    {"items": {"type": "string"}, "type": "array"},
                    {"items": {"type": "array"}, "type": "array"},
                ],
            },
            "test2": {
                "description": "Another",
                "allOf": [
                    {"items": {"type": "string"}, "type": "array"},
                    {"items": {"type": "array"}, "type": "array"},
                ],
            },
        },
        "required": [],
        "additionalProperties": False,
        "$id": "my-id",
        "$schema": "http://json-schema.org/draft-07/schema#",
    }


def test_description():
    s = Schema(
        {Optional(Literal("test1", description="A description here"), default={}): dict}
    )
    assert s.validate({"test1": {}})


def test_description_with_default():
    s = Schema(
        {Optional(Literal("test1", description="A description here"), default={}): dict}
    )
    assert s.validate({}) == {"test1": {}}


def test_json_schema_ref_in_list():
    s = Schema(
        Or(
            Schema([str], name="Inner test", as_reference=True),
            Schema([str], name="Inner test2", as_reference=True),
        )
    )
    generated_json_schema = s.json_schema("my-id")

    assert generated_json_schema == {
        "definitions": {
            "Inner test": {"items": {"type": "string"}, "type": "array"},
            "Inner test2": {"items": {"type": "string"}, "type": "array"},
        },
        "anyOf": [
            {"$ref": "#/definitions/Inner test"},
            {"$ref": "#/definitions/Inner test2"},
        ],
        "$id": "my-id",
        "$schema": "http://json-schema.org/draft-07/schema#",
    }


def test_json_schema_refs():
    s = Schema({"test1": str, "test2": str, "test3": str})
    hashed = "#" + str(hash(repr(sorted({"type": "string"}.items()))))
    generated_json_schema = s.json_schema("my-id", use_refs=True)

    # The order can change, so let's check indirectly
    assert generated_json_schema["type"] == "object"
    assert sorted(generated_json_schema["required"]) == ["test1", "test2", "test3"]
    assert generated_json_schema["additionalProperties"] is False
    assert generated_json_schema["$id"] == "my-id"
    assert generated_json_schema["$schema"] == "http://json-schema.org/draft-07/schema#"

    # There will be one of the property being the id and 2 referencing it, but which one is random
    id_schema_part = {"type": "string", "$id": hashed}
    ref_schema_part = {"$ref": hashed}

    nb_id_schema = 0
    nb_ref_schema = 0
    for v in generated_json_schema["properties"].values():
        if v == id_schema_part:
            nb_id_schema += 1
        elif v == ref_schema_part:
            nb_ref_schema += 1
    assert nb_id_schema == 1
    assert nb_ref_schema == 2


def test_json_schema_refs_is_smaller():
    key_names = [
        "a",
        "b",
        "c",
        "d",
        "e",
        "f",
        "g",
        "h",
        "i",
        "j",
        "k",
        "l",
        "m",
        "n",
        "o",
        "p",
        "q",
        "r",
        "s",
        "t",
    ]
    key_values = [
        1,
        2,
        3,
        4,
        5,
        6,
        7,
        8,
        9,
        10,
        "value1",
        "value2",
        "value3",
        "value4",
        "value5",
        None,
    ]
    s = Schema(
        {
            Literal(
                Or(*key_names), description="A key that can have many names"
            ): key_values
        }
    )
    assert len(json.dumps(s.json_schema("my-id", use_refs=False))) > len(
        json.dumps(s.json_schema("my-id", use_refs=True))
    )


def test_json_schema_refs_no_missing():
    key_names = [
        "a",
        "b",
        "c",
        "d",
        "e",
        "f",
        "g",
        "h",
        "i",
        "j",
        "k",
        "l",
        "m",
        "n",
        "o",
        "p",
        "q",
        "r",
        "s",
        "t",
    ]
    key_values = [
        1,
        2,
        3,
        4,
        5,
        6,
        7,
        8,
        9,
        10,
        "value1",
        "value2",
        "value3",
        "value4",
        "value5",
        None,
    ]
    s = Schema(
        {
            Literal(
                Or(*key_names), description="A key that can have many names"
            ): key_values
        }
    )
    json_s = s.json_schema("my-id", use_refs=True)
    schema_ids = []
    refs = []

    def _get_ids_and_refs(schema_dict):
        for k, v in schema_dict.items():
            if isinstance(v, dict):
                _get_ids_and_refs(v)
                continue

            if k == "$id" and v != "my-id":
                schema_ids.append(v)
            elif k == "$ref":
                refs.append(v)

    _get_ids_and_refs(json_s)

    # No ID is repeated
    assert len(schema_ids) == len(set(schema_ids))

    # All IDs are used in a ref
    for schema_id in schema_ids:
        assert schema_id in refs

    # All refs have an associated ID
    for ref in refs:
        assert ref in schema_ids


def test_json_schema_definitions():
    sub_schema = Schema({"sub_key1": int}, name="sub_schema", as_reference=True)
    main_schema = Schema({"main_key1": str, "main_key2": sub_schema})

    json_schema = main_schema.json_schema("my-id")
    assert sorted_dict(json_schema) == {
        "type": "object",
        "properties": {
            "main_key1": {"type": "string"},
            "main_key2": {"$ref": "#/definitions/sub_schema"},
        },
        "required": ["main_key1", "main_key2"],
        "additionalProperties": False,
        "$id": "my-id",
        "$schema": "http://json-schema.org/draft-07/schema#",
        "definitions": {
            "sub_schema": {
                "type": "object",
                "properties": {"sub_key1": {"type": "integer"}},
                "required": ["sub_key1"],
                "additionalProperties": False,
            }
        },
    }


def test_json_schema_definitions_and_literals():
    sub_schema = Schema(
        {Literal("sub_key1", description="Sub key 1"): int},
        name="sub_schema",
        as_reference=True,
        description="Sub Schema",
    )
    main_schema = Schema(
        {
            Literal("main_key1", description="Main Key 1"): str,
            Literal("main_key2", description="Main Key 2"): sub_schema,
            Literal("main_key3", description="Main Key 3"): sub_schema,
        }
    )

    json_schema = main_schema.json_schema("my-id")
    assert sorted_dict(json_schema) == {
        "type": "object",
        "properties": {
            "main_key1": {"description": "Main Key 1", "type": "string"},
            "main_key2": {
                "$ref": "#/definitions/sub_schema",
                "description": "Main Key 2",
            },
            "main_key3": {
                "$ref": "#/definitions/sub_schema",
                "description": "Main Key 3",
            },
        },
        "required": ["main_key1", "main_key2", "main_key3"],
        "additionalProperties": False,
        "$id": "my-id",
        "$schema": "http://json-schema.org/draft-07/schema#",
        "definitions": {
            "sub_schema": {
                "description": "Sub Schema",
                "type": "object",
                "properties": {
                    "sub_key1": {"description": "Sub key 1", "type": "integer"}
                },
                "required": ["sub_key1"],
                "additionalProperties": False,
            }
        },
    }


def test_json_schema_definitions_nested():
    sub_sub_schema = Schema(
        {"sub_sub_key1": int}, name="sub_sub_schema", as_reference=True
    )
    sub_schema = Schema(
        {"sub_key1": int, "sub_key2": sub_sub_schema},
        name="sub_schema",
        as_reference=True,
    )
    main_schema = Schema({"main_key1": str, "main_key2": sub_schema})

    json_schema = main_schema.json_schema("my-id")
    assert sorted_dict(json_schema) == {
        "type": "object",
        "properties": {
            "main_key1": {"type": "string"},
            "main_key2": {"$ref": "#/definitions/sub_schema"},
        },
        "required": ["main_key1", "main_key2"],
        "additionalProperties": False,
        "$id": "my-id",
        "$schema": "http://json-schema.org/draft-07/schema#",
        "definitions": {
            "sub_schema": {
                "type": "object",
                "properties": {
                    "sub_key1": {"type": "integer"},
                    "sub_key2": {"$ref": "#/definitions/sub_sub_schema"},
                },
                "required": ["sub_key1", "sub_key2"],
                "additionalProperties": False,
            },
            "sub_sub_schema": {
                "type": "object",
                "properties": {"sub_sub_key1": {"type": "integer"}},
                "required": ["sub_sub_key1"],
                "additionalProperties": False,
            },
        },
    }


def test_json_schema_definitions_recursive():
    """Create a JSON schema with an object that refers to itself

    This is the example from here: https://json-schema.org/understanding-json-schema/structuring.html#recursion
    """
    children = []
    person = Schema(
        {Optional("name"): str, Optional("children"): children},
        name="person",
        as_reference=True,
    )
    children.append(person)

    json_schema = person.json_schema("my-id")
    assert json_schema == {
        "$ref": "#/definitions/person",
        "$id": "my-id",
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "person",
        "definitions": {
            "person": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "children": {
                        "type": "array",
                        "items": {"$ref": "#/definitions/person"},
                    },
                },
                "required": [],
                "additionalProperties": False,
            }
        },
    }


def test_json_schema_definitions_invalid():
    with raises(ValueError):
        _ = Schema({"test1": str}, as_reference=True)


def test_json_schema_default_value():
    s = Schema({Optional("test1", default=42): int})
    assert s.json_schema("my-id") == {
        "type": "object",
        "properties": {"test1": {"type": "integer", "default": 42}},
        "required": [],
        "additionalProperties": False,
        "$id": "my-id",
        "$schema": "http://json-schema.org/draft-07/schema#",
    }


def test_json_schema_default_value_with_literal():
    s = Schema({Optional(Literal("test1"), default=False): bool})
    assert s.json_schema("my-id") == {
        "type": "object",
        "properties": {"test1": {"type": "boolean", "default": False}},
        "required": [],
        "additionalProperties": False,
        "$id": "my-id",
        "$schema": "http://json-schema.org/draft-07/schema#",
    }


def test_json_schema_default_is_none():
    s = Schema({Optional("test1", default=None): str})
    assert s.json_schema("my-id") == {
        "type": "object",
        "properties": {"test1": {"type": "string", "default": None}},
        "required": [],
        "additionalProperties": False,
        "$id": "my-id",
        "$schema": "http://json-schema.org/draft-07/schema#",
    }


def test_json_schema_default_is_tuple():
    s = Schema({Optional("test1", default=(1, 2)): list})
    assert s.json_schema("my-id") == {
        "type": "object",
        "properties": {"test1": {"type": "array", "default": [1, 2]}},
        "required": [],
        "additionalProperties": False,
        "$id": "my-id",
        "$schema": "http://json-schema.org/draft-07/schema#",
    }


def test_json_schema_default_is_literal():
    s = Schema({Optional("test1", default=Literal("Hello!")): str})
    assert s.json_schema("my-id") == {
        "type": "object",
        "properties": {"test1": {"type": "string", "default": "Hello!"}},
        "required": [],
        "additionalProperties": False,
        "$id": "my-id",
        "$schema": "http://json-schema.org/draft-07/schema#",
    }


def test_prepend_schema_name():
    try:
        Schema({"key1": int}).validate({"key1": "a"})
    except SchemaError as e:
        assert str(e) == "Key 'key1' error:\n'a' should be instance of 'int'"

    try:
        Schema({"key1": int}, name="custom_schemaname").validate({"key1": "a"})
    except SchemaError as e:
        assert (
            str(e)
            == "'custom_schemaname' Key 'key1' error:\n'a' should be instance of 'int'"
        )

    try:
        Schema(int, name="custom_schemaname").validate("a")
    except SchemaUnexpectedTypeError as e:
        assert str(e) == "'custom_schemaname' 'a' should be instance of 'int'"


def test_dict_literal_error_string():
    # this is a simplified regression test of the bug in github issue #240
    assert Schema(Or({"a": 1}, error="error: {}")).is_valid(dict(a=1))


def test_callable_error():
    # this tests for the behavior desired in github pull request #238
    e = None
    try:
        Schema(lambda d: False, error="{}").validate("This is the error message")
    except SchemaError as ex:
        e = ex
    assert e.errors == ["This is the error message"]

"""Single-type list validation preserves the general validator's semantics."""

from pytest import mark, raises

from schema import Or, Schema, SchemaError, SchemaUnexpectedTypeError


@mark.parametrize(
    "item_type, values", [(str, ["a", "b"]), (int, [1, 2]), (bool, [True, False])]
)
def test_single_type_list_returns_a_new_list(item_type, values):
    original = list(values)
    validated = Schema([item_type]).validate(values)
    assert validated == original
    assert validated is not values
    assert values == original
    assert all(actual is expected for actual, expected in zip(validated, values))
    assert Schema([item_type]).validate([]) == []


def test_single_type_list_accepts_element_subclasses_without_conversion():
    class Text(str):
        pass

    value = Text("text")
    assert Schema([str]).validate(["plain", value])[1] is value


def test_single_type_list_keeps_container_subclass():
    class Values(list):
        pass

    values = Values(["a", "b"])
    validated = Schema([str]).validate(values)
    assert type(validated) is Values
    assert validated == values
    assert validated is not values


@mark.parametrize("error", [None, "invalid: {}"])
@mark.parametrize("item_type, invalid", [(str, 42), (int, True), (int, False)])
def test_single_type_list_keeps_error_details(item_type, invalid, error):
    with raises(SchemaError) as general:
        Or(item_type, error=error).validate(invalid)
    with raises(SchemaError) as optimized:
        Schema([item_type], error=error).validate([item_type(), invalid])
    assert optimized.value.__class__ is general.value.__class__
    assert optimized.value.autos == general.value.autos
    assert optimized.value.errors == general.value.errors
    assert optimized.value.code == general.value.code


def test_single_type_list_checks_the_outer_container():
    with raises(SchemaUnexpectedTypeError):
        Schema([str]).validate(("a", "b"))


def test_single_type_list_honors_schema_subclass_and_kwargs():
    class IncrementingSchema(Schema):
        def validate(self, data, increment=1):
            if isinstance(data, int):
                data += increment
            return super().validate(data, increment=increment)

    assert IncrementingSchema([int]).validate([1, 2], increment=10) == [11, 12]


def test_single_type_list_honors_instance_checks():
    calls = []

    class TextMeta(type):
        def __instancecheck__(cls, value):
            calls.append(value)
            return isinstance(value, str)

    class Text(metaclass=TextMeta):
        pass

    assert Schema([Text]).validate(["a", "b"]) == ["a", "b"]
    assert calls == ["a", "b"]


def test_single_type_list_accepts_ordinary_user_types():
    class Value:
        pass

    value = Value()
    assert Schema([Value]).validate([value])[0] is value

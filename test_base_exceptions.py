import pytest

from schema import Schema, SchemaError, Use


class _Validator:
    def __init__(self, error):
        self.error = error

    def validate(self, value, **kwargs):
        raise self.error


def _raise(error):
    def raise_error(value):
        raise error

    return raise_error


def _schema_for(mode, error):
    if mode == "use":
        return Use(_raise(error))
    if mode == "validator":
        return Schema(_Validator(error))
    if mode == "callable":
        return Schema(_raise(error))
    return Schema({"value": Use(_raise(error))})


@pytest.mark.parametrize("mode", ["use", "validator", "callable", "nested"])
@pytest.mark.parametrize("error_type", [KeyboardInterrupt, SystemExit, GeneratorExit])
def test_control_flow_exceptions_propagate_unchanged(mode, error_type):
    error = error_type("stop")
    schema = _schema_for(mode, error)
    data = {"value": 1} if mode == "nested" else 1
    with pytest.raises(error_type) as raised:
        schema.validate(data)
    assert raised.value is error


@pytest.mark.parametrize("mode", ["use", "validator", "callable", "nested"])
@pytest.mark.parametrize("error_type", [ValueError, TypeError, RuntimeError])
def test_ordinary_exceptions_still_become_schema_errors(mode, error_type):
    schema = _schema_for(mode, error_type("invalid"))
    data = {"value": 1} if mode == "nested" else 1
    with pytest.raises(SchemaError, match=error_type.__name__):
        schema.validate(data)

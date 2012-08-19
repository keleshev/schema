from pytest import raises

from schema import Schema, is_a, either, strictly, SchemaExit


def test_schema():

    assert Schema(1).validate(1) == 1
    with raises(SchemaExit):
        Schema(1).validate(9)

    assert Schema(int).validate(1) == 1
    assert Schema(int).validate('1') == 1
    with raises(SchemaExit):
        Schema(int).validate(int)

    assert Schema(str).validate('hai') == 'hai'
    assert Schema(str).validate(1) == '1'

    assert Schema(list).validate(['a', 1]) == ['a', 1]
    assert Schema(dict).validate({'a': 1}) == {'a': 1}
    with raises(SchemaExit):
        Schema(dict).validate(['a', 1])

    assert Schema(lambda n: 0 < n < 5).validate(3) == 3
    with raises(SchemaExit):
        Schema(lambda n: 0 < n < 5).validate(-1)


def test_validate_file():
    assert Schema(file).validate('LICENSE-MIT').read().startswith('Copyright')
    with raises(SchemaExit):
        Schema(file).validate('NON-EXISTENT')
    import os
    assert Schema(os.path.exists).validate('.') == '.'
    with raises(SchemaExit):
        Schema(os.path.exists).validate('./non-existent/')
    assert Schema(os.path.isfile).validate('LICENSE-MIT') == 'LICENSE-MIT'
    with raises(SchemaExit):
        Schema(os.path.isfile).validate('NON-EXISTENT')


def test_is_a():

    assert Schema(is_a(int, lambda n: 0 < n < 5)).validate(3) == 3
    assert Schema(is_a(int, lambda n: 0 < n < 5)).validate(3.33) == 3
    with raises(SchemaExit):
        Schema(is_a(str, int, lambda n: 0 < n < 5)).validate(3.33)


def test_either():
    assert Schema(either(int, dict)).validate(5) == 5
    assert Schema(either(int, dict)).validate({}) == {}
    with raises(SchemaExit):
        Schema(either(int, dict)).validate('hai')


def test_validate_list():
    assert Schema([1, 0]).validate([1, 0, 1, 1]) == [1, 0, 1, 1]
    assert Schema([1, 0]).validate([]) == []
    with raises(SchemaExit):
        Schema([1, 0]).validate(0)
    with raises(SchemaExit):
        Schema([1, 0]).validate([2])

SE = raises(SchemaExit)

def test_strictly():
    assert strictly(int).validate(1) == 1
    with SE: strictly(int).validate('1')

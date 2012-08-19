from pytest import raises

from schema import Schema, is_a, either, strictly, SchemaExit


SE = raises(SchemaExit)


def test_schema():

    assert Schema(1).validate(1) == 1
    with SE: Schema(1).validate(9)

    assert Schema(int).validate(1) == 1
    assert Schema(int).validate('1') == 1
    with SE: Schema(int).validate(int)

    assert Schema(str).validate('hai') == 'hai'
    assert Schema(str).validate(1) == '1'

    assert Schema(list).validate(['a', 1]) == ['a', 1]
    assert Schema(dict).validate({'a': 1}) == {'a': 1}
    with SE: Schema(dict).validate(['a', 1])

    assert Schema(lambda n: 0 < n < 5).validate(3) == 3
    with SE: Schema(lambda n: 0 < n < 5).validate(-1)


def test_validate_file():
    assert Schema(file).validate('LICENSE-MIT').read().startswith('Copyright')
    with SE: Schema(file).validate('NON-EXISTENT')
    import os
    assert Schema(os.path.exists).validate('.') == '.'
    with SE: Schema(os.path.exists).validate('./non-existent/')
    assert Schema(os.path.isfile).validate('LICENSE-MIT') == 'LICENSE-MIT'
    with SE: Schema(os.path.isfile).validate('NON-EXISTENT')


def test_is_a():
    assert is_a(int, lambda n: 0 < n < 5).validate(3) == 3
    assert is_a(int, lambda n: 0 < n < 5).validate(3.33) == 3
    with SE: is_a(str, int, lambda n: 0 < n < 5).validate(3.33)


def test_either():
    assert either(int, dict).validate(5) == 5
    assert either(int, dict).validate({}) == {}
    with SE: either(int, dict).validate('hai')


def test_validate_list():
    assert Schema([1, 0]).validate([1, 0, 1, 1]) == [1, 0, 1, 1]
    assert Schema([1, 0]).validate([]) == []
    with SE: Schema([1, 0]).validate(0)
    with SE: Schema([1, 0]).validate([2])


def test_strictly():
    assert strictly(int).validate(1) == 1
    with SE: strictly(int).validate('1')

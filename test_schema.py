from __future__ import with_statement
import os

from pytest import raises

from schema import Schema, Use, And, Or, Optional, SchemaExit


SE = raises(SchemaExit)


def test_schema():

    assert Schema(1).validate(1) == 1
    with SE: Schema(1).validate(9)

    assert Schema(int).validate(1) == 1
    with SE: Schema(int).validate('1')
    assert Schema(Use(int)).validate('1') == 1
    with SE: Schema(int).validate(int)

    assert Schema(str).validate('hai') == 'hai'
    with SE: Schema(str).validate(1)
    assert Schema(Use(str)).validate(1) == '1'

    assert Schema(list).validate(['a', 1]) == ['a', 1]
    assert Schema(dict).validate({'a': 1}) == {'a': 1}
    with SE: Schema(dict).validate(['a', 1])

    assert Schema(lambda n: 0 < n < 5).validate(3) == 3
    with SE: Schema(lambda n: 0 < n < 5).validate(-1)


def test_validate_file():
    assert Schema(Use(open)).validate('LICENSE-MIT').read().startswith('Copyright')
    with SE: Schema(Use(open)).validate('NON-EXISTENT')
    assert Schema(os.path.exists).validate('.') == '.'
    with SE: Schema(os.path.exists).validate('./non-existent/')
    assert Schema(os.path.isfile).validate('LICENSE-MIT') == 'LICENSE-MIT'
    with SE: Schema(os.path.isfile).validate('NON-EXISTENT')


def test_and():
    assert And(int, lambda n: 0 < n < 5).validate(3) == 3
    with SE: And(int, lambda n: 0 < n < 5).validate(3.33)
    assert And(Use(int), lambda n: 0 < n < 5).validate(3.33) == 3
    with SE: And(Use(int), lambda n: 0 < n < 5).validate('3.33')


def test_or():
    assert Or(int, dict).validate(5) == 5
    assert Or(int, dict).validate({}) == {}
    with SE: Or(int, dict).validate('hai')


def test_validate_list():
    assert Schema([1, 0]).validate([1, 0, 1, 1]) == [1, 0, 1, 1]
    assert Schema([1, 0]).validate([]) == []
    with SE: Schema([1, 0]).validate(0)
    with SE: Schema([1, 0]).validate([2])
    assert And([1, 0], lambda l: len(l) > 2).validate([0, 1, 0]) == [0, 1, 0]
    with SE: And([1, 0], lambda l: len(l) > 2).validate([0, 1])


def test_list_tuple_set_frozenset():
    assert Schema([int]).validate([1, 2])
    with SE: Schema([int]).validate(['1', 2])
    assert Schema(set([int])).validate(set([1, 2])) == set([1, 2])
    with SE: Schema(set([int])).validate([1, 2])  # not a set
    with SE: Schema(set([int])).validate(['1', 2])
    assert Schema(tuple([int])).validate(tuple([1, 2])) == tuple([1, 2])
    with SE: Schema(tuple([int])).validate([1, 2])  # not a set


def test_strictly():
    assert Schema(int).validate(1) == 1
    with SE: Schema(int).validate('1')


def test_dict():
    assert Schema({'key': 5}).validate({'key': 5}) == {'key': 5}
    with SE: Schema({'key': 5}).validate({'key': 'x'})
    assert Schema({'key': int}).validate({'key': 5}) == {'key': 5}
    assert Schema({'n': int, 'f': float}).validate(
            {'n': 5, 'f': 3.14}) == {'n': 5, 'f': 3.14}
    with SE: Schema({'n': int, 'f': float}).validate(
            {'n': 3.14, 'f': 5})


def test_dict_keys():
    assert Schema({str: int}).validate(
            {'a': 1, 'b': 2}) == {'a': 1, 'b': 2}
    with SE: Schema({str: int}).validate({1: 1, 'b': 2})
    assert Schema({Use(str): Use(int)}).validate(
            {1: 3.14, 3.14: 1}) == {'1': 3, '3.14': 1}


def test_dict_optional_keys():
    with SE: Schema({'a': 1, 'b': 2}).validate({'a': 1})
    assert Schema({'a': 1, Optional('b'): 2}).validate({'a': 1}) == {'a': 1}
    assert Schema({'a': 1, Optional('b'): 2}).validate(
            {'a': 1, 'b': 2}) == {'a': 1, 'b': 2}


def test_complex():
    s = Schema({'<file>': And([Use(open)], lambda l: len(l)),
                '<path>': os.path.exists,
                Optional('--count'): And(int, lambda n: 0 <= n <= 5)})
    data = s.validate({'<file>': ['./LICENSE-MIT'], '<path>': './'})
    assert len(data) == 2
    assert len(data['<file>']) == 1
    assert data['<file>'][0].read().startswith('Copyright')
    assert data['<path>'] == './'


def test_nice_errors():
    try:
        Schema(int, error='should be integer').validate('x')
    except SchemaExit as e:
        assert e.errors == ['should be integer']
    #try:
    #    Schema(Use(float), error='should be a number').validate('x')
    #except SchemaExit as e:
    #    assert e.errors == ['should be a number']


def test_use_error_handling():
    def ve(_): raise ValueError()
    try:
        Use(ve).validate('x')
    except SchemaExit as e:
        assert e.autos == ["ve('x') raised ValueError()"]
        assert e.errors == [None]
    try:
        Use(ve, error='should not raise').validate('x')
    except SchemaExit as e:
        assert e.autos == ["ve('x') raised ValueError()"]
        assert e.errors == ['should not raise']
    def se(_): raise SchemaExit('first auto', 'first error')
    try:
        Use(se).validate('x')
    except SchemaExit as e:
        assert e.autos == ['first auto', None]
        assert e.errors == ['first error', None]
    try:
        Use(se, error='second error').validate('x')
    except SchemaExit as e:
        assert e.autos == ['first auto', None]
        assert e.errors == ['first error', 'second error']

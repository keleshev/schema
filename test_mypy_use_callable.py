"""Test that mypy no longer reports "incompatible type Use" errors.

This test actually runs mypy as a subprocess and verifies that the specific
error about Use being incompatible with And/Or is NOT present.
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


# Check if mypy is available
def is_mypy_available():
    """Check if mypy is available in the environment."""
    return shutil.which("mypy") is not None or _can_import_mypy()


def _can_import_mypy():
    """Check if mypy can be imported as a module."""
    try:
        __import__("mypy")
        return True
    except ImportError:
        return False


# Skip all tests in this module if mypy is not available
pytestmark = pytest.mark.skipif(
    not is_mypy_available(), reason="mypy is not available in the environment"
)


def test_mypy_use_with_and_no_error():
    """Test that mypy doesn't report 'incompatible type Use' error with And."""
    # Create a temporary test file with the problematic code
    test_code = """
from schema import And, Use

# This used to fail with: Argument 2 to "And" has incompatible type "Use"
schema = And(int, Use(int))
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(test_code)
        temp_file = f.name

    try:
        # Run mypy on the test file
        result = subprocess.run(
            [sys.executable, "-m", "mypy", "--no-error-summary", temp_file],
            capture_output=True,
            text=True,
        )

        # Check that the specific error about Use is NOT present
        output = result.stdout + result.stderr

        # The error we're looking for (should NOT be present)
        error_pattern = 'incompatible type "Use"'

        assert (
            error_pattern.lower() not in output.lower()
        ), f"Found 'incompatible type Use' error in mypy output:\n{output}"

        print("✓ mypy does not report 'incompatible type Use' error")

    finally:
        Path(temp_file).unlink(missing_ok=True)


def test_mypy_use_with_or_no_error():
    """Test that mypy doesn't report 'incompatible type Use' error with Or."""
    test_code = """
from schema import Or, Use

# This used to fail with: Argument to "Or" has incompatible type "Use"
schema = Or(Use(int), Use(float))
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(test_code)
        temp_file = f.name

    try:
        result = subprocess.run(
            [sys.executable, "-m", "mypy", "--no-error-summary", temp_file],
            capture_output=True,
            text=True,
        )

        output = result.stdout + result.stderr
        error_pattern = 'incompatible type "Use"'

        assert (
            error_pattern.lower() not in output.lower()
        ), f"Found 'incompatible type Use' error in mypy output:\n{output}"

        print("✓ mypy does not report 'incompatible type Use' error with Or")

    finally:
        Path(temp_file).unlink(missing_ok=True)


def test_mypy_use_with_and_complex_no_error():
    """Test complex And/Or combinations with Use don't produce mypy errors."""
    test_code = """
from schema import And, Or, Use, Schema, Optional

# Complex cases that used to fail
schema1 = And(str, Use(int))
schema2 = Or(int, Use(str))
schema3 = Schema({
    "age": And(Use(int), lambda n: 0 <= n <= 120),
    "name": Use(str.title),
    Optional("email"): Use(str.lower),
})
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(test_code)
        temp_file = f.name

    try:
        result = subprocess.run(
            [sys.executable, "-m", "mypy", "--no-error-summary", temp_file],
            capture_output=True,
            text=True,
        )

        output = result.stdout + result.stderr
        error_pattern = 'incompatible type "Use"'

        assert (
            error_pattern.lower() not in output.lower()
        ), f"Found 'incompatible type Use' error in mypy output:\n{output}"

        print("✓ mypy does not report 'incompatible type Use' error in complex schemas")

    finally:
        Path(temp_file).unlink(missing_ok=True)


def test_mypy_use_callable_recognized():
    """Test that Use is recognized as callable by mypy."""
    test_code = """
from schema import Use

use_int = Use(int)

# This should work - Use should be callable
assert callable(use_int)
result = use_int("123")
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(test_code)
        temp_file = f.name

    try:
        result = subprocess.run(
            [sys.executable, "-m", "mypy", "--no-error-summary", temp_file],
            capture_output=True,
            text=True,
        )

        output = result.stdout + result.stderr

        # Should not have any "not callable" errors
        assert (
            "not callable" not in output.lower()
        ), f"mypy thinks Use is not callable:\n{output}"

        print("✓ mypy recognizes Use as callable")

    finally:
        Path(temp_file).unlink(missing_ok=True)


if __name__ == "__main__":
    if not is_mypy_available():
        print("⚠️  mypy is not available in the environment.")
        print("These tests require mypy to be installed.")
        print("Install with: pip install mypy")
        sys.exit(1)

    print("Running mypy verification tests...\n")

    test_mypy_use_with_and_no_error()
    test_mypy_use_with_or_no_error()
    test_mypy_use_with_and_complex_no_error()
    test_mypy_use_callable_recognized()

    print("\n✅ All mypy verification tests passed!")
    print("The 'incompatible type Use' error has been fixed.")

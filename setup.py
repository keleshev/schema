"""`schema` lives on `GitHub <http://github.com/halst/schema/>`_."""
from setuptools import setup


setup(
    name = "schema",
    version = "0.1.1",
    author = "Vladimir Keleshev",
    author_email = "vladimir@keleshev.com",
    description = "Simple data validation library",
    license = "MIT",
    keywords = "schema json validation",
    url = "http://github.com/halst/schema",
    py_modules=['schema'],
    long_description=__doc__,
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Topic :: Utilities",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "License :: OSI Approved :: MIT License",
    ],
)

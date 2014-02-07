from setuptools import setup

import schema


setup(
    name=schema.__name__,
    version=schema.__version__,
    author="Vladimir Keleshev",
    author_email="vladimir@keleshev.com",
    description="Simple data validation library",
    license="MIT",
    keywords="schema json validation",
    url="http://github.com/halst/schema",
    py_modules=['schema'],
    long_description=open('README.rst').read(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Topic :: Utilities",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "License :: OSI Approved :: MIT License",
    ],
)

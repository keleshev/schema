import codecs
import sys

from setuptools import setup

version_file = "schema.py"
with open(version_file) as f:
    for line in f.read().split("\n"):
        if line.startswith("__version__ ="):
            version = eval(line.split("=", 1)[1])
            break
    else:
        print("No __version__ attribute found in %r" % version_file)
        sys.exit(1)

setup(
    name="schema",
    version=version,
    author="Vladimir Keleshev",
    author_email="vladimir@keleshev.com",
    description="Simple data validation library",
    license="MIT",
    keywords="schema json validation",
    url="https://github.com/keleshev/schema",
    py_modules=["schema"],
    long_description=codecs.open("README.rst", "r", "utf-8").read(),
    install_requires=open("requirements.txt", "r").read().split("\n"),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Topic :: Utilities",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.2",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: Implementation :: PyPy",
        "License :: OSI Approved :: MIT License",
    ],
)

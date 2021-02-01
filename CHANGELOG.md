# Changelog


## Unreleased

### Fixes

* Don't double-format errors. fixes #240 (#247) [Leif Ryge]

* Fix "Unknown format code" in Python 3.8 (#245) [Denis Blanchette]

* JSON Schema: Allow using $ref when schema is not a dict (#244) [Denis Blanchette]

* JSON Schema: Set additionalProperties true when dict contains str as key (#243) [Denis Blanchette]


## v0.7.3 (2020-07-31)

### Fixes

* JSON Schema: Support schemas where the root is not a dict. [Stavros Korokithakis]

* Do not drop previous errors within an Or criterion. [Stavros Korokithakis]


## v0.7.1 (2019-09-09)

### Features

* JSON Schema: Include default values. [Stavros Korokithakis]

* JSON schema with common definitions + Update README. [Stavros Korokithakis]

* Add references to JSON schema rendering. [Stavros Korokithakis]

* Add the "Literal" type for JSONSchema. [Stavros Korokithakis]

* Improve JSON schema generation (#206) [Denis Blanchette]

### Fixes

* JSON Schema: Fix allOf and oneOf with only one condition. [Stavros Korokithakis]

* Fix readme code block typo. [Stavros Korokithakis]

* JSON Schema: Don't add a description in a ref. [Stavros Korokithakis]

* JSON Schema: Fix using `dict` as type. [Stavros Korokithakis]

* Fix using Literal in enum in JSON Schema. [Stavros Korokithakis]


## v0.7.0 (2019-02-25)

### Features

* Add Hook class. Allows to introduce custom handlers (#175) [Julien Duchesne]

### Fixes

* Add pre-commit to CI (#187) [Stavros Korokithakis]

* Use correct singular/plural form of “key(s)” in error messages (#184) [Joel Rosdahl]

* When ignoring extra keys,  Or's only_one should still be handled (#181) [Julien Duchesne]

* Fix Or reset() when Or is Optional (#178) [Julien Duchesne]

* Don't accept boolens as instances of ints (#176) [Brandon Skari]

* Remove assert statements (#170) [Ryan Morshead]


## v0.6.8 (2018-06-14)

### Features

* Add an is_valid method to the schema (as in #134) (#150) [Shailyn Ortiz]

### Fixes

* Fix typo in schema.py: vaidated->validated (#151) [drootnar]

* Fix callable check under PyPy2 (#149) [cfs-pure]


## v0.6.6 (2017-04-26)

### Fixes

* Schema can be inherited (#127) [Hiroyuki Ishii]

* Show a key error if a dict error happens. [Stavros Korokithakis]


## v0.6.4 (2016-09-19)

### Fixes

* Revert the optional error commit. [Stavros Korokithakis]


## v0.6.3 (2016-09-19)

### Fixes

* Sort missing keys. [Stavros Korokithakis]


## v0.6.2 (2016-07-27)

### Fixes

* Add SchemaError SubClasses: SchemaWrongKey, SchemaMissingKeyError (#111) [Stavros Korokithakis]


## v0.6.1 (2016-07-27)

### Fixes

* Handle None as the error message properly. [Stavros Korokithakis]


## v0.6.0 (2016-07-18)

### Features

* Add the "Regex" class. [Stavros Korokithakis]



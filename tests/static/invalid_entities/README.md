# About invalid entities

## `Person.json`

`Person.json` is an invalid SOFT7 entity because it has a SOFT5-type `dimensions` value (a list instead of a dictionary).
`Person.json` is an invalid SOFT5 entity because:

- it has a SOFT7-type `dimensions` value (a dictionary instead of a list).
- it has a wrong `dimensions` value (a string instead of a dictionary).

Error message from pydantic as of 15.12.2023 (pydantic==2.5.2):

```console
1 validation error for SOFT7Entity
dimensions
  Input should be a valid dictionary [type=dict_type, input_value=['n_skills'], input_type=list]
    For further information visit https://errors.pydantic.dev/2.5/v/dict_type

2 validation errors for SOFT5Entity
dimensions.0
  Input should be a valid dictionary or instance of SOFT5Dimension [type=model_type, input_value='n_skills', input_type=str]
    For further information visit https://errors.pydantic.dev/2.5/v/model_type
properties
  Input should be a valid list [type=list_type, input_value={'skills': {'type': 'stri...: 'Age of the person.'}}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.5/v/list_type
```

## `Dog.json`

`Dog.json` is an invalid SOFT entity because it is missing the `uri` field and does not have a complete set of the (`namespace`, `version`, `name`) fields - `version` is missing.

Error message from pydantic as of 18.12.2023 (pydantic==2.5.2):

```console
1 validation error for SOFT7Entity
  Value error, Either all of `name`, `version`, and `namespace` must be set or all must be unset.
 [type=value_error, input_value={'namespace': 'http://ont...: 'Breed of the dog.'}}}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.5/v/value_error

1 validation error for SOFT5Entity
  Value error, Either all of `name`, `version`, and `namespace` must be set or all must be unset.
 [type=value_error, input_value={'namespace': 'http://ont...: 'Breed of the dog.'}}}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.5/v/value_error
```

## `Cat.json`

`Cat.json` is an invalid SOFT entity because the `uri` is malformed.

Since it is a SOFT7 entity, it will also show extra validation errors for the SOFT5Entity model.

Error message from pydantic as of 18.12.2023 (pydantic==2.5.2):

```console
1 validation error for SOFT7Entity
uri
  Value error, The 'uri' is not a valid SOFT7 entity URI. It must be of the form http://onto-ns.com/meta/{version}/{name}.
 [type=value_error, input_value='http://onto-ns.com/meta/Cat', input_type=str]
    For further information visit https://errors.pydantic.dev/2.5/v/value_error

3 validation errors for SOFT5Entity
uri
  Value error, The 'uri' is not a valid SOFT7 entity URI. It must be of the form http://onto-ns.com/meta/{version}/{name}.
 [type=value_error, input_value='http://onto-ns.com/meta/Cat', input_type=str]
    For further information visit https://errors.pydantic.dev/2.5/v/value_error
dimensions
  Input should be a valid list [type=list_type, input_value={}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.5/v/list_type
properties
  Input should be a valid list [type=list_type, input_value={'name': {'type': 'string...': 'Color of the cat.'}}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.5/v/list_type
```

## `Cat5.json`

`Cat5.json` _is_ a valid SOFT5 entity.
But it will not pass validation, because the `uri` uses the wrong namespace, and the `meta` value does not use v0.3 of the EntitySchema.

Error message from pydantic as of 19.12.2023 (pydantic==2.5.2):

```console
4 validation errors for SOFT7Entity
uri
  Value error, This service only works with entities at http://onto-ns.com/meta.
 [type=value_error, input_value='http://onto-ns.com/0.1/Cat', input_type=str]
    For further information visit https://errors.pydantic.dev/2.5/v/value_error
meta
  Value error, This service only works with entities using EntitySchema v0.3 at onto-ns.com as the metadata entity.
 [type=value_error, input_value='http://onto-ns.com/meta/0.4/EntitySchema', input_type=str]
    For further information visit https://errors.pydantic.dev/2.5/v/value_error
dimensions
  Input should be a valid dictionary [type=dict_type, input_value=[], input_type=list]
    For further information visit https://errors.pydantic.dev/2.5/v/dict_type
properties
  Input should be a valid dictionary [type=dict_type, input_value=[{'name': 'name', 'type':...': 'Color of the cat.'}], input_type=list]
    For further information visit https://errors.pydantic.dev/2.5/v/dict_type

2 validation errors for SOFT5Entity
uri
  Value error, This service only works with entities at http://onto-ns.com/meta.
 [type=value_error, input_value='http://onto-ns.com/0.1/Cat', input_type=str]
    For further information visit https://errors.pydantic.dev/2.5/v/value_error
meta
  Value error, This service only works with entities using EntitySchema v0.3 at onto-ns.com as the metadata entity.
 [type=value_error, input_value='http://onto-ns.com/meta/0.4/EntitySchema', input_type=str]
    For further information visit https://errors.pydantic.dev/2.5/v/value_error
```

## `Dog5.json`

`Dog5.json` is an invalid SOFT entity because it is missing the `uri` field as well as the `namespace`, `version`, and `name` fields.

Error message from pydantic as of 19.12.2023 (pydantic==2.5.2):

```console
1 validation error for SOFT7Entity
  Value error, Either `name`, `version`, and `namespace` or `uri` must be set.
 [type=value_error, input_value={'meta': 'http://onto-ns....: 'Breed of the dog.'}]}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.5/v/value_error

1 validation error for SOFT5Entity
  Value error, Either `name`, `version`, and `namespace` or `uri` must be set.
 [type=value_error, input_value={'meta': 'http://onto-ns....: 'Breed of the dog.'}]}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.5/v/value_error
```

## `Person5.json`

`Person5.json` is an invalid SOFT entity because the `namespace` value does not match the namespace part of the `uri`, i.e., the set of (`namespace`, `version`, `name`) does not match the `uri`.

Error message from pydantic as of 19.12.2023 (pydantic==2.5.2):

```console
1 validation error for SOFT7Entity
  Value error, The `uri` is not consistent with `name`, `version`, and `namespace`:

  - http://onto-ns.com/meta/0.1/Person
  ?                    -----

  + http://onto-ns.com/0.1/Person

 [type=value_error, input_value={'namespace': 'http://ont... 'Age of the person.'}]}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.5/v/value_error

1 validation error for SOFT5Entity
  Value error, The `uri` is not consistent with `name`, `version`, and `namespace`:

  - http://onto-ns.com/meta/0.1/Person
  ?                    -----

  + http://onto-ns.com/0.1/Person

 [type=value_error, input_value={'namespace': 'http://ont... 'Age of the person.'}]}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.5/v/value_error
```

## `Owl.json`

`Owl.json` is an invalid SOFT7 entity with a specific namespace given in the `uri` value.
It is invalid because the specific namespace contains the invalid character dollar sign (`$`).

Error message from pydantic as of 19.03.2024 (pydantic==2.6.4):

```console
1 validation error for SOFT7Entity
uri
  Value error, The namespace part of the URI is invalid: 1 validation error for
function-after[_ensure_url_encodeable(), function-after[_disallowed_namespace_characters(), str]]
  Value error, Invalid specific namespace - may not contain a '$' character.
    For further information visit https://errors.pydantic.dev/2.6/v/value_error

    For further information visit https://errors.pydantic.dev/2.6/v/value_error

2 validation errors for SOFT5Entity
uri
  Value error, The namespace part of the URI is invalid: 1 validation error for
function-after[_ensure_url_encodeable(), function-after[_disallowed_namespace_characters(), str]]
  Value error, Invalid specific namespace - may not contain a '$' character.
    For further information visit https://errors.pydantic.dev/2.6/v/value_error

    For further information visit https://errors.pydantic.dev/2.6/v/value_error
properties
  Input should be a valid list
    For further information visit https://errors.pydantic.dev/2.6/v/list_type

1 validation error for DLiteSOFT7Entity
uri
  Value error, The namespace part of the URI is invalid: 1 validation error for
function-after[_ensure_url_encodeable(), function-after[_disallowed_namespace_characters(), str]]
  Value error, Invalid specific namespace - may not contain a '$' character.
    For further information visit https://errors.pydantic.dev/2.6/v/value_error

    For further information visit https://errors.pydantic.dev/2.6/v/value_error

2 validation errors for DLiteSOFT5Entity
uri
  Value error, The namespace part of the URI is invalid: 1 validation error for
function-after[_ensure_url_encodeable(), function-after[_disallowed_namespace_characters(), str]]
  Value error, Invalid specific namespace - may not contain a '$' character.
    For further information visit https://errors.pydantic.dev/2.6/v/value_error

    For further information visit https://errors.pydantic.dev/2.6/v/value_error
properties
  Input should be a valid list
    For further information visit https://errors.pydantic.dev/2.6/v/list_type
```

## `Owl5.json`

`Owl5.json` is an invalid SOFT5 entity with a specific namespace given in the `namespace` value.
It is invalid because the specific namespace contains the invalid character dollar sign (`$`).

Error message from pydantic as of 19.03.2024 (pydantic==2.6.4):

```console
2 validation errors for SOFT7Entity
namespace
  Value error, Invalid specific namespace - may not contain a '$' character.
    For further information visit https://errors.pydantic.dev/2.6/v/value_error
properties
  Input should be a valid dictionary [type=dict_type, input_value=[{'name': 'specific-speci...': 'Color
of the owl.'}], input_type=list]
    For further information visit https://errors.pydantic.dev/2.6/v/dict_type

1 validation error for SOFT5Entity
namespace
  Value error, Invalid specific namespace - may not contain a '$' character.
    For further information visit https://errors.pydantic.dev/2.6/v/value_error

2 validation errors for DLiteSOFT7Entity
namespace
  Value error, Invalid specific namespace - may not contain a '$' character.
    For further information visit https://errors.pydantic.dev/2.6/v/value_error
properties
  Input should be a valid dictionary [type=dict_type, input_value=[{'name': 'specific-speci...': 'Color
of the owl.'}], input_type=list]
    For further information visit https://errors.pydantic.dev/2.6/v/dict_type

1 validation error for DLiteSOFT5Entity
namespace
  Value error, Invalid specific namespace - may not contain a '$' character.
    For further information visit https://errors.pydantic.dev/2.6/v/value_error
```

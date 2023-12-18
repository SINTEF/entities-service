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
  Input should be a valid dictionary or instance of SOFT5Dimension
    For further information visit https://errors.pydantic.dev/2.5/v/model_type
properties
  Input should be a valid list
    For further information visit https://errors.pydantic.dev/2.5/v/list_type
```

## `Dog.json`

`Dog.json` is an invalid SOFT entity because it is missing the `uri` field and does not have a complete set of the (`namespace`, `version`, `name`) fields - `version` is missing.

Error message from pydantic as of 18.12.2023 (pydantic==2.5.2):

```console
1 validation error for SOFT7Entity
  Value error, Either all of `name`, `version`, and `namespace` must be set or all must be unset. [type=value_error, input_value={'namespace': 'http://ont...: 'Breed of the dog.'}}}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.5/v/value_error

1 validation error for SOFT5Entity
  Value error, Either all of `name`, `version`, and `namespace` must be set or all must be unset. [type=value_error, input_value={'namespace': 'http://ont...: 'Breed of the dog.'}}}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.5/v/value_error
```

## `Cat.json`

`Cat.json` is an invalid SOFT entity because the `uri` is malformed.

Since it is a SOFT7 entity, it will also show extra validation errors for the SOFT5Entity model.

Error message from pydantic as of 18.12.2023 (pydantic==2.5.2):

```console
1 validation error for SOFT7Entity
uri
  Value error, The 'uri' is not a valid SOFT7 entity URI. It must be of the form http://onto-ns.com/meta/{version}/{name}. [type=value_error, input_value='http://onto-ns.com/meta/Cat', input_type=str]
    For further information visit https://errors.pydantic.dev/2.5/v/value_error

3 validation errors for SOFT5Entity
uri
  Value error, The 'uri' is not a valid SOFT7 entity URI. It must be of the form http://onto-ns.com/meta/{version}/{name}. [type=value_error, input_value='http://onto-ns.com/meta/Cat', input_type=str]
    For further information visit https://errors.pydantic.dev/2.5/v/value_error
dimensions
  Input should be a valid list [type=list_type, input_value={}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.5/v/list_type
properties
  Input should be a valid list [type=list_type, input_value={'name': {'type': 'string...': 'Color of the cat.'}}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.5/v/list_type
```

# About invalid entities

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

"""SOFT models."""
from __future__ import annotations

from typing import get_args

from pydantic import ValidationError

from .soft5 import SOFT5Entity
from .soft7 import SOFT7Entity

VersionedSOFTEntity = SOFT7Entity | SOFT5Entity


def soft_entity(
    *args, return_errors: bool = False, **kwargs
) -> VersionedSOFTEntity | list[ValidationError]:
    """Return the correct version of the SOFT Entity."""
    errors = []
    for versioned_entity_cls in get_args(VersionedSOFTEntity):
        try:
            new_object = versioned_entity_cls(*args, **kwargs)
            break
        except ValidationError as exc:
            errors.append(exc)
            continue
    else:
        if return_errors:
            return errors

        raise ValueError(
            "Cannot instantiate entity. Errors:\n"
            + "\n".join(str(error) for error in errors)
        )
    return new_object  # type: ignore[return-value]

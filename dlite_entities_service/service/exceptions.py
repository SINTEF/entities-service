"""Service-specific exceptions."""
from __future__ import annotations

from pymongo.errors import WriteConcernError, WriteError

BackendAnyWriteError = (WriteError, WriteConcernError)
"""Any write error exception from the backend."""

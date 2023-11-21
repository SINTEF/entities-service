"""Test the service's only route to retrieve DLite/SOFT entities."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from typing import Any


pytestmark = pytest.mark.asyncio


async def test_get_entity(static_dir: Path, get_version_name: Callable[[str], tuple[str, str]], get_uri: Callable[[dict[str, Any], str]]) -> None:
    """Test the route to retrieve a DLite/SOFT entity."""
    import yaml
    from httpx import AsyncClient
    from fastapi import status

    from dlite_entities_service.config import CONFIG
    from dlite_entities_service.main import APP

    for entity in yaml.safe_load((static_dir / "entities.yaml").read_text()):
        uri = entity.get("uri", get_uri(entity))

        version, name = get_version_name(uri)

        async with AsyncClient(app=APP, base_url=str(CONFIG.base_url)) as aclient:
            response = await aclient.get(f"/{version}/{name}", timeout=5)

        assert response.is_success
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == entity

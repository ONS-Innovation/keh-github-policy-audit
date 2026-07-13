"""Unit tests for repository listing handler."""

import importlib
from unittest.mock import create_autospec, patch

import pytest


# ---------------------------------------------------------------------------
# handler
# ---------------------------------------------------------------------------


class TestListRepositoriesHandler:
    module = importlib.import_module("functions.list_repositories.handler")

    def test_fetches_paginated_repositories(self) -> None:
        """The handler should pass the correct endpoint and result_key to get_paginated_list."""
        client = object()
        captured: dict[str, object] = {}

        def fake_get_paginated_list(
            check_client: object,
            endpoint: str,
            result_key: str,
        ) -> list[dict[str, object]]:
            captured["client"] = check_client
            captured["endpoint"] = endpoint
            captured["result_key"] = result_key
            return [{"name": "keh-github-policy-audit"}]

        mock_paginated = create_autospec(
            self.module.get_paginated_list, side_effect=fake_get_paginated_list
        )

        with (
            patch.object(self.module, "get_github_client", return_value=client),
            patch.object(self.module, "get_paginated_list", mock_paginated),
        ):
            result = self.module.handler({"owner": "ONS-Innovation"}, None)

        assert captured == {
            "client": client,
            "endpoint": "/orgs/ONS-Innovation/repos?per_page=100",
            "result_key": "repositories",
        }
        assert result == [
            {
                "name": "keh-github-policy-audit",
                "data": {
                    "updated_at": None,
                    "security_and_analysis": None,
                },
            }
        ]

    def test_raises_for_missing_owner(self) -> None:
        """A missing owner key in the event should raise a KeyError."""
        with pytest.raises(KeyError, match="owner"):
            self.module.handler({}, None)

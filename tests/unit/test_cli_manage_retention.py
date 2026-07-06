"""Unit tests for CLI retention cleanup metadata handling."""

from unittest.mock import MagicMock, PropertyMock, patch

from click.testing import CliRunner

from powermem.cli.main import cli


def test_cleanup_uses_intelligence_retention_when_top_level_score_is_missing():
    memory = MagicMock()
    memory.get_all.return_value = {
        "results": [
            {
                "id": 1,
                "memory": "low retention memory",
                "metadata": {
                    "retention_score": None,
                    "intelligence": {"current_retention": 0.05},
                },
            },
            {
                "id": 2,
                "memory": "archive retention memory",
                "metadata": {
                    "intelligence": {"current_retention": 0.2},
                },
            },
            {
                "id": 3,
                "memory": "healthy retention memory",
                "metadata": {
                    "intelligence": {"current_retention": 0.8},
                },
            },
        ],
    }

    with patch(
        "powermem.cli.commands.manage.CLIContext.memory",
        new_callable=PropertyMock,
        return_value=memory,
    ):
        result = CliRunner().invoke(
            cli,
            ["manage", "cleanup", "--dry-run", "--json"],
        )

    assert result.exit_code == 0
    assert '"would_delete": 1' in result.output
    assert '"would_archive": 1' in result.output

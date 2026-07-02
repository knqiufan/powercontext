import pytest

from scripts import check_pypi_release as checker


def _pypi_data(version: str, filenames: list[str]) -> dict:
    return {
        "releases": {
            version: [{"filename": filename} for filename in filenames],
        }
    }


def test_parse_version_accepts_plain_version_and_v_tag() -> None:
    assert checker.parse_version("1.1.6") == "1.1.6"
    assert checker.parse_version("v1.1.6") == "1.1.6"


def test_check_package_release_accepts_wheel_and_sdist() -> None:
    data = _pypi_data(
        "1.1.6",
        [
            "powermem_mcp-1.1.6-py3-none-any.whl",
            "powermem_mcp-1.1.6.tar.gz",
        ],
    )

    checker.check_package_release("powermem-mcp", "1.1.6", data)


def test_check_package_release_reports_missing_version() -> None:
    data = _pypi_data("0.2.0", ["powermem_mcp-0.2.0-py3-none-any.whl"])

    with pytest.raises(checker.ReleaseCheckError) as error:
        checker.check_package_release("powermem-mcp", "1.1.6", data)

    message = str(error.value)
    assert "powermem-mcp" in message
    assert "1.1.6" in message


def test_check_package_release_requires_wheel_and_sdist() -> None:
    data = _pypi_data("1.1.6", ["powermem_mcp-1.1.6-py3-none-any.whl"])

    with pytest.raises(checker.ReleaseCheckError) as error:
        checker.check_package_release("powermem-mcp", "1.1.6", data)

    assert "sdist" in str(error.value)


def test_check_package_release_rejects_wrong_filename_prefix() -> None:
    data = _pypi_data(
        "1.1.6",
        [
            "powermem-1.1.6-py3-none-any.whl",
            "powermem-1.1.6.tar.gz",
        ],
    )

    with pytest.raises(checker.ReleaseCheckError) as error:
        checker.check_package_release("powermem-mcp", "1.1.6", data)

    assert "powermem_mcp-1.1.6" in str(error.value)


def test_check_packages_fetches_every_requested_package() -> None:
    requested: list[str] = []

    def fetcher(package: str) -> dict:
        requested.append(package)
        normalized = package.replace("-", "_")
        return _pypi_data(
            "1.1.6",
            [
                f"{normalized}-1.1.6-py3-none-any.whl",
                f"{normalized}-1.1.6.tar.gz",
            ],
        )

    checker.check_packages(
        ["powermem", "powermem-mcp"],
        "1.1.6",
        fetcher=fetcher,
        retries=1,
        delay_seconds=0,
    )

    assert requested == ["powermem", "powermem-mcp"]


def test_check_packages_retries_until_release_is_visible() -> None:
    attempts = 0

    def fetcher(package: str) -> dict:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return _pypi_data("0.2.0", ["powermem_mcp-0.2.0-py3-none-any.whl"])
        return _pypi_data(
            "1.1.6",
            [
                "powermem_mcp-1.1.6-py3-none-any.whl",
                "powermem_mcp-1.1.6.tar.gz",
            ],
        )

    checker.check_packages(
        ["powermem-mcp"],
        "1.1.6",
        fetcher=fetcher,
        retries=2,
        delay_seconds=0,
    )

    assert attempts == 2


def test_check_packages_rejects_non_positive_retries() -> None:
    with pytest.raises(checker.ReleaseCheckError) as error:
        checker.check_packages(
            ["powermem-mcp"],
            "1.1.6",
            fetcher=lambda package: {},
            retries=0,
            delay_seconds=0,
        )

    assert "retries" in str(error.value)


def test_main_returns_failure_for_invalid_retries(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = checker.main(
        ["--version", "1.1.6", "--retries", "0", "--delay-seconds", "0"]
    )

    assert exit_code == 1
    assert "retries" in capsys.readouterr().err

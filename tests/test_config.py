import pytest

from g_market_azeroth.config import load_settings


ENV_NAMES = ("BOT_TOKEN", "ADMIN_IDS", "DATABASE_PATH", "LOG_LEVEL")


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    tmp_path.joinpath(".env").write_text("", encoding="utf-8")

    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def set_required_env(
    monkeypatch: pytest.MonkeyPatch,
    *,
    bot_token: str = "123456:test-token",
    admin_ids: str = "1001",
    database_path: str = "data/g_market_azeroth.sqlite3",
) -> None:
    monkeypatch.setenv("BOT_TOKEN", bot_token)
    monkeypatch.setenv("ADMIN_IDS", admin_ids)
    monkeypatch.setenv("DATABASE_PATH", database_path)


def test_load_settings_reads_required_and_optional_env(
    clean_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_required_env(monkeypatch)
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    settings = load_settings()

    assert settings.bot_token == "123456:test-token"
    assert settings.admin_ids == {1001}
    assert settings.database_path == "data/g_market_azeroth.sqlite3"
    assert settings.log_level == "DEBUG"


def test_load_settings_trims_admin_ids(
    clean_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_required_env(monkeypatch, admin_ids=" 1001 ")

    settings = load_settings()

    assert settings.admin_ids == {1001}


def test_load_settings_reads_multiple_admin_ids(
    clean_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_required_env(monkeypatch, admin_ids="1001,2002,3003")

    settings = load_settings()

    assert settings.admin_ids == {1001, 2002, 3003}


def test_load_settings_rejects_empty_bot_token(
    clean_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_required_env(monkeypatch, bot_token=" ")

    with pytest.raises(RuntimeError, match="BOT_TOKEN must not be empty"):
        load_settings()


def test_load_settings_rejects_empty_admin_ids(
    clean_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_required_env(monkeypatch, admin_ids=" ")

    with pytest.raises(RuntimeError, match="ADMIN_IDS must not be empty"):
        load_settings()


def test_load_settings_rejects_non_numeric_admin_ids(
    clean_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_required_env(monkeypatch, admin_ids="1001,not-a-number")

    with pytest.raises(
        RuntimeError,
        match="ADMIN_IDS must contain Telegram user IDs separated by commas",
    ):
        load_settings()


def test_load_settings_rejects_empty_database_path(
    clean_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_required_env(monkeypatch, database_path=" ")

    with pytest.raises(RuntimeError, match="DATABASE_PATH must not be empty"):
        load_settings()


def test_load_settings_uses_default_log_level(
    clean_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_required_env(monkeypatch)

    settings = load_settings()

    assert settings.log_level == "INFO"

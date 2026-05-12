from aiogram.types import User

from g_market_azeroth.config import Settings
from g_market_azeroth.handlers import (
    _is_valid_character_nickname,
    _normalize_character_nickname,
    _parse_gold_amount,
    main_menu_keyboard,
)


def make_settings(*, admin_ids: set[int]) -> Settings:
    return Settings(
        bot_token="123456:test-token",
        admin_ids=admin_ids,
        database_path=":memory:",
        log_level="INFO",
        message_cooldown_seconds=1.0,
        callback_cooldown_seconds=0.5,
        support_cooldown_seconds=10.0,
    )


def keyboard_buttons(settings: Settings, user: User) -> list[tuple[str, str]]:
    keyboard = main_menu_keyboard(settings, user)
    return [
        (button.text, button.callback_data or "")
        for row in keyboard.inline_keyboard
        for button in row
    ]


def test_main_menu_hides_admin_entry_for_regular_user() -> None:
    buttons = keyboard_buttons(
        make_settings(admin_ids={1001}),
        User(id=2002, is_bot=False, first_name="Client"),
    )

    assert ("⚙️ Админка", "admin:home") not in buttons


def test_main_menu_shows_admin_entry_for_admin_user() -> None:
    buttons = keyboard_buttons(
        make_settings(admin_ids={1001}),
        User(id=1001, is_bot=False, first_name="Admin"),
    )

    assert ("⚙️ Админка", "admin:home") in buttons


def test_character_nickname_is_trimmed() -> None:
    assert _normalize_character_nickname("  Thrall  ") == "Thrall"


def test_character_nickname_validation_rejects_empty_and_short_values() -> None:
    assert not _is_valid_character_nickname("")
    assert not _is_valid_character_nickname("A")


def test_character_nickname_validation_accepts_boundaries() -> None:
    assert _is_valid_character_nickname("Ab")
    assert _is_valid_character_nickname("A" * 32)


def test_character_nickname_validation_rejects_long_values() -> None:
    assert not _is_valid_character_nickname("A" * 33)


def test_gold_amount_parser_accepts_plain_numbers() -> None:
    assert _parse_gold_amount("10000") == 10000


def test_gold_amount_parser_accepts_spaces() -> None:
    assert _parse_gold_amount("10 000") == 10000


def test_gold_amount_parser_accepts_k_suffix() -> None:
    assert _parse_gold_amount("10k") == 10000
    assert _parse_gold_amount("15K") == 15000


def test_gold_amount_parser_rejects_invalid_values() -> None:
    assert _parse_gold_amount("abc") is None
    assert _parse_gold_amount("-5") is None
    assert _parse_gold_amount("0") is None


def test_gold_amount_parser_rejects_too_large_values() -> None:
    assert _parse_gold_amount("10000001") is None

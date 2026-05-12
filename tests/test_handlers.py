from decimal import Decimal

from aiogram.types import User

from g_market_azeroth.config import Settings
from g_market_azeroth.handlers import (
    _calculate_total_price,
    _format_money,
    _format_number,
    _is_valid_character_nickname,
    _normalize_character_nickname,
    _product_card_text,
    _parse_price_per_1000,
    _parse_gold_amount,
    _side_button_text,
    _sorted_products,
    _sorted_servers,
    _sorted_sides,
    main_menu_keyboard,
)
from g_market_azeroth.repositories.products import Product


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


def test_price_parser_accepts_readable_price_values() -> None:
    assert _parse_price_per_1000("120 ₽") == Decimal("120")
    assert _parse_price_per_1000("1 200,50 ₽") == Decimal("1200.50")


def test_price_parser_rejects_invalid_price_values() -> None:
    assert _parse_price_per_1000("abc") is None
    assert _parse_price_per_1000("0") is None


def test_total_price_calculation_uses_price_per_1000() -> None:
    assert _calculate_total_price(10000, Decimal("120")) == Decimal("1200")


def test_number_and_money_formatting_are_readable() -> None:
    assert _format_number(10000) == "10 000"
    assert _format_money(Decimal("1200")) == "1 200 ₽"


def make_product(*, product_id: int, server: str, side: str, price: str) -> Product:
    return Product(
        id=product_id,
        game_type="off",
        server=server,
        faction=side,
        price=price,
        is_active=True,
        created_at="2026-01-01",
        updated_at="2026-01-01",
    )


def test_servers_are_sorted_readably() -> None:
    assert _sorted_servers(["Soulseeker", "Nek'Rosh"]) == ["Nek'Rosh", "Soulseeker"]


def test_sides_are_sorted_readably() -> None:
    assert _sorted_sides(["Horde", "Alliance"]) == ["Alliance", "Horde"]
    assert _side_button_text("Alliance") == "⚔️ Alliance"


def test_products_are_sorted_by_price_then_name() -> None:
    products = [
        make_product(product_id=1, server="Soulseeker", side="Alliance", price="120 ₽"),
        make_product(product_id=2, server="Nek'Rosh", side="Horde", price="110 ₽"),
    ]

    assert [product.id for product in _sorted_products(products)] == [2, 1]


def test_product_card_text_is_compact_and_readable() -> None:
    product = make_product(product_id=1, server="Soulseeker", side="Alliance", price="120 ₽")

    assert _product_card_text(product) == "🟡 Soulseeker\n⚔️ Alliance\n💰 120 ₽ / 1000 gold"

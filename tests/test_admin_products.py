from g_market_azeroth.admin import (
    _format_product,
    _parser_preview_text,
    _product_visibility_notice,
    _products_text,
    admin_keyboard,
    admin_products_keyboard,
)
from g_market_azeroth.repositories.products import Product
from g_market_azeroth.services.parsers import ParserPreviewSummary


def make_product(*, product_id: int, is_active: bool) -> Product:
    return Product(
        id=product_id,
        game_type="off",
        server="Soulseeker",
        faction="Alliance",
        price="120 ₽",
        is_active=is_active,
        created_at="2026-01-01",
        updated_at="2026-01-01",
    )


def test_admin_product_text_shows_active_status() -> None:
    product = make_product(product_id=1, is_active=True)

    assert "Статус: активен" in _format_product(product)


def test_admin_product_text_shows_hidden_status() -> None:
    product = make_product(product_id=1, is_active=False)

    assert "Статус: скрыт" in _format_product(product)


def test_admin_products_keyboard_shows_hide_for_active_product() -> None:
    keyboard = admin_products_keyboard([make_product(product_id=1, is_active=True)])
    button = keyboard.inline_keyboard[0][0]

    assert button.text == "Скрыть #1"
    assert button.callback_data == "admin:product_active:1:0"


def test_admin_products_keyboard_shows_restore_for_hidden_product() -> None:
    keyboard = admin_products_keyboard([make_product(product_id=2, is_active=False)])
    button = keyboard.inline_keyboard[0][0]

    assert button.text == "Показать #2"
    assert button.callback_data == "admin:product_active:2:1"


def test_products_text_can_include_visibility_confirmation() -> None:
    product = make_product(product_id=3, is_active=False)
    text = _products_text([product], notice=_product_visibility_notice(product))

    assert "Готово: товар #3 скрыт из каталога." in text
    assert "Статус: скрыт" in text


def test_admin_keyboard_has_parser_preview_action() -> None:
    buttons = [
        (button.text, button.callback_data)
        for row in admin_keyboard().inline_keyboard
        for button in row
    ]

    assert ("Обновить каталог", "admin:parser_preview") in buttons


def test_parser_preview_text_formats_counts() -> None:
    text = _parser_preview_text(
        ParserPreviewSummary(
            fetched_count=24,
            new_count=3,
            update_count=12,
            hidden_count=2,
            error_count=0,
        )
    )

    assert "Найдено товаров: 24" in text
    assert "Новых: 3" in text
    assert "Обновятся: 12" in text
    assert "Скрытых: 2" in text
    assert "Ошибок: 0" in text

from decimal import Decimal, InvalidOperation

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, User

from g_market_azeroth.admin import is_admin_user
from g_market_azeroth.catalog import (
    REALM_TYPE_LABELS,
    is_valid_realm_type,
    realm_type_label,
    support_status_label,
)
from g_market_azeroth.config import Settings
from g_market_azeroth.constants import (
    REQUEST_STATUS_CANCELLED,
    REQUEST_STATUS_DONE,
    REQUEST_STATUS_IN_PROGRESS,
)
from g_market_azeroth.database import (
    MarketRepository,
    Product,
    PurchaseRequest,
    SellRequestDetails,
    SupportTicket,
)
from g_market_azeroth.logging import log_metric, log_user_action
from g_market_azeroth.services.statuses import format_request_status

router = Router(name="client")
MAX_BUY_GOLD_AMOUNT = 10_000_000


WELCOME_TEXT = (
    "👋 Добро пожаловать в GoldExpress\n\n"
    "Здесь можно быстро купить или продать золото World of Warcraft.\n\n"
    "✅ Актуальные предложения\n"
    "✅ Заявка за пару кликов\n"
    "✅ Поддержка внутри бота\n"
    "✅ Статус заявки всегда под рукой\n\n"
    "Выберите действие ниже:"
)


class BuyRequestFlow(StatesGroup):
    waiting_for_character_nickname = State()
    waiting_for_gold_amount = State()


class SellRequestFlow(StatesGroup):
    waiting_for_realm_type = State()
    waiting_for_server = State()
    waiting_for_side = State()
    waiting_for_amount = State()
    waiting_for_price = State()
    waiting_for_comment = State()


class SupportFlow(StatesGroup):
    waiting_for_question = State()


@router.message(CommandStart())
async def handle_start(
    message: Message,
    database: MarketRepository,
    settings: Settings,
    state: FSMContext,
) -> None:
    await state.clear()
    if message.from_user:
        await _save_client(message.from_user, database)
        log_metric("registration", user_id=message.from_user.id)

    await message.answer(WELCOME_TEXT, reply_markup=main_menu_keyboard(settings, message.from_user))


@router.message(Command("menu"))
async def handle_menu(message: Message, settings: Settings, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Главное меню:", reply_markup=main_menu_keyboard(settings, message.from_user))


@router.message(Command("support"))
async def handle_support_command(message: Message, state: FSMContext) -> None:
    await state.set_state(SupportFlow.waiting_for_question)
    await message.answer(
        "Опишите вопрос одним сообщением. Администратор ответит вам здесь.",
        reply_markup=client_cancel_keyboard(),
    )


@router.message(Command("my_requests"))
async def handle_my_requests_command(
    message: Message,
    database: MarketRepository,
    settings: Settings,
) -> None:
    if not message.from_user:
        return

    await message.answer(
        await _my_requests_text(database, message.from_user.id),
        reply_markup=main_menu_keyboard(settings, message.from_user),
    )


@router.callback_query(F.data == "shop:home")
async def handle_shop_home(callback: CallbackQuery, settings: Settings, state: FSMContext) -> None:
    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.edit_text("Главное меню:", reply_markup=main_menu_keyboard(settings, callback.from_user))
    await callback.answer()


@router.callback_query(F.data == "shop:buy")
async def handle_buy(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.edit_text("Выберите тип сервера:", reply_markup=buy_realm_type_keyboard())
    await callback.answer()


@router.callback_query(F.data == "shop:sell")
async def handle_sell(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SellRequestFlow.waiting_for_realm_type)
    if isinstance(callback.message, Message):
        await callback.message.edit_text("Что хотите продать?", reply_markup=sell_realm_type_keyboard())
    await callback.answer()


@router.callback_query(F.data == "shop:support")
async def handle_support(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SupportFlow.waiting_for_question)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "Опишите вопрос одним сообщением. Администратор ответит вам здесь.",
            reply_markup=client_cancel_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data == "shop:my_requests")
async def handle_my_requests(
    callback: CallbackQuery,
    database: MarketRepository,
    settings: Settings,
) -> None:
    text = await _my_requests_text(database, callback.from_user.id)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=main_menu_keyboard(settings, callback.from_user))
    await callback.answer()


@router.callback_query(F.data.startswith("shop:realm:"))
async def handle_realm_type(callback: CallbackQuery, database: MarketRepository) -> None:
    realm_type = callback.data.rsplit(":", maxsplit=1)[-1] if callback.data else ""
    if not is_valid_realm_type(realm_type):
        await callback.answer("Неизвестный тип.", show_alert=True)
        return

    servers = _sorted_servers(await database.list_servers(realm_type))
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _servers_text(realm_type, servers),
            reply_markup=servers_keyboard(realm_type, servers),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("shop:server:"))
async def handle_server(callback: CallbackQuery, database: MarketRepository) -> None:
    parsed = _parse_catalog_index_callback(callback.data, expected_prefix="shop:server")
    if not parsed:
        await callback.answer("Не удалось открыть сервер.", show_alert=True)
        return

    realm_type, server_index = parsed
    servers = _sorted_servers(await database.list_servers(realm_type))
    if server_index >= len(servers):
        await callback.answer("Сервер больше не доступен.", show_alert=True)
        return

    server = servers[server_index]
    sides = _sorted_sides(await database.list_sides(realm_type, server))

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _sides_text(realm_type, server, sides),
            reply_markup=sides_keyboard(realm_type, server_index, sides),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("shop:side:"))
async def handle_side(callback: CallbackQuery, database: MarketRepository, state: FSMContext) -> None:
    parsed = _parse_side_callback(callback.data)
    if not parsed:
        await callback.answer("Не удалось открыть сторону.", show_alert=True)
        return

    realm_type, server_index, side_index = parsed
    servers = _sorted_servers(await database.list_servers(realm_type))
    if server_index >= len(servers):
        await callback.answer("Сервер больше не доступен.", show_alert=True)
        return

    server = servers[server_index]
    sides = _sorted_sides(await database.list_sides(realm_type, server))
    if side_index >= len(sides):
        await callback.answer("Сторона больше не доступна.", show_alert=True)
        return

    side = sides[side_index]
    await state.update_data(
        buy_realm_type=realm_type,
        buy_server_index=server_index,
        buy_side_index=side_index,
        buy_server=server,
        buy_side=side,
    )
    await state.set_state(BuyRequestFlow.waiting_for_character_nickname)

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _character_nickname_prompt(realm_type, server, side),
            reply_markup=client_cancel_keyboard(),
        )
    await callback.answer()


@router.message(BuyRequestFlow.waiting_for_character_nickname)
async def handle_buy_character_nickname(
    message: Message,
    state: FSMContext,
) -> None:
    nickname = _normalize_character_nickname(message.text)
    if not _is_valid_character_nickname(nickname):
        await message.answer(
            "Введите ник персонажа от 2 до 32 символов.",
            reply_markup=client_cancel_keyboard(),
        )
        return

    await state.update_data(buy_character_nickname=nickname)
    await state.set_state(BuyRequestFlow.waiting_for_gold_amount)

    await message.answer(
        "Введите количество золота:",
        reply_markup=client_cancel_keyboard(),
    )


@router.message(BuyRequestFlow.waiting_for_gold_amount)
async def handle_buy_gold_amount(
    message: Message,
    database: MarketRepository,
    state: FSMContext,
) -> None:
    gold_amount = _parse_gold_amount(message.text)
    if gold_amount is None:
        await message.answer(
            "Введите количество золота числом больше 0. Можно так: 10000, 10 000 или 10k.",
            reply_markup=client_cancel_keyboard(),
        )
        return

    data = await state.get_data()
    realm_type = str(data["buy_realm_type"])
    server = str(data["buy_server"])
    side = str(data["buy_side"])
    server_index = int(data["buy_server_index"])
    nickname = str(data["buy_character_nickname"])

    await state.update_data(buy_gold_amount=gold_amount)
    products = _sorted_products(
        await database.list_catalog_products(
            realm_type=realm_type,
            server=server,
            side=side,
        )
    )

    await message.answer(
        _products_text(
            realm_type,
            server,
            side,
            products,
            character_nickname=nickname,
            gold_amount=gold_amount,
        ),
        reply_markup=products_keyboard(products, realm_type, server_index),
    )


@router.callback_query(F.data.startswith("shop:purchase:"))
async def handle_purchase(
    callback: CallbackQuery,
    database: MarketRepository,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    character_nickname = str(data.get("buy_character_nickname") or "")
    if not _is_valid_character_nickname(character_nickname):
        await callback.answer("Введите ник персонажа перед созданием заявки.", show_alert=True)
        return
    gold_amount = data.get("buy_gold_amount")
    if not isinstance(gold_amount, int) or not _is_valid_gold_amount(gold_amount):
        await callback.answer("Введите количество золота перед созданием заявки.", show_alert=True)
        return

    product_id = _parse_product_id(callback.data)
    if product_id is None:
        await callback.answer("Не удалось создать заявку.", show_alert=True)
        return

    product = await database.get_catalog_product(product_id)
    if product is None:
        await callback.answer("Товар больше не доступен.", show_alert=True)
        return
    price_per_1000 = _parse_price_per_1000(product.price)
    if price_per_1000 is None:
        await callback.answer("Не удалось рассчитать итоговую стоимость.", show_alert=True)
        return

    total_price = _calculate_total_price(gold_amount, price_per_1000)
    await state.update_data(
        buy_product_id=product.id,
        buy_price_per_1000=str(price_per_1000),
        buy_total_price=str(total_price),
    )

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _purchase_confirmation_text(
                product,
                character_nickname=character_nickname,
                gold_amount=gold_amount,
                price_per_1000=price_per_1000,
                total_price=total_price,
            ),
            reply_markup=purchase_confirmation_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data == "shop:confirm_purchase")
async def handle_purchase_confirmation(
    callback: CallbackQuery,
    bot: Bot,
    settings: Settings,
    database: MarketRepository,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    character_nickname = str(data.get("buy_character_nickname") or "")
    gold_amount = data.get("buy_gold_amount")
    product_id = data.get("buy_product_id")
    if (
        not _is_valid_character_nickname(character_nickname)
        or not isinstance(gold_amount, int)
        or not _is_valid_gold_amount(gold_amount)
        or not isinstance(product_id, int)
    ):
        await callback.answer("Заявка устарела. Начните покупку заново.", show_alert=True)
        return

    product = await database.get_catalog_product(product_id)
    if product is None:
        await callback.answer("Товар больше не доступен.", show_alert=True)
        return
    price_per_1000 = _parse_price_per_1000(product.price)
    if price_per_1000 is None:
        await callback.answer("Не удалось рассчитать итоговую стоимость.", show_alert=True)
        return

    total_price = _calculate_total_price(gold_amount, price_per_1000)
    request = await database.create_purchase_request(
        product_id=product.id,
        telegram_id=callback.from_user.id,
    )
    log_user_action(
        callback.from_user.id,
        "purchase_request_created",
        request_id=request.id,
        product_id=product.id,
    )
    log_metric(
        "purchase_request_created",
        user_id=callback.from_user.id,
        request_id=request.id,
        product_id=product.id,
    )
    await _notify_admins_about_purchase(
        bot,
        settings,
        request,
        product,
        callback.from_user,
        character_nickname=character_nickname,
        gold_amount=gold_amount,
        total_price=total_price,
    )
    await state.clear()

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "Заявка на покупку создана.\n\n"
            f"Номер заявки: #{request.id}\n"
            "Администратор увидит её и свяжется с вами.",
            reply_markup=main_menu_keyboard(settings, callback.from_user),
        )
    await callback.answer("Заявка создана.")


@router.callback_query(F.data == "shop:cancel_purchase")
async def handle_purchase_cancel(callback: CallbackQuery, settings: Settings, state: FSMContext) -> None:
    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "Заявка отменена.",
            reply_markup=main_menu_keyboard(settings, callback.from_user),
        )
    await callback.answer("Заявка отменена.")


@router.callback_query(SellRequestFlow.waiting_for_realm_type, F.data.startswith("sell:realm:"))
async def handle_sell_realm_type(callback: CallbackQuery, state: FSMContext) -> None:
    realm_type = callback.data.rsplit(":", maxsplit=1)[-1] if callback.data else ""
    if not is_valid_realm_type(realm_type):
        await callback.answer("Неизвестный тип.", show_alert=True)
        return

    await state.update_data(realm_type=realm_type)
    await state.set_state(SellRequestFlow.waiting_for_server)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            f"Тип: {realm_type_label(realm_type)}\n\nВведите сервер:",
            reply_markup=client_cancel_keyboard(),
        )
    await callback.answer()


@router.message(SellRequestFlow.waiting_for_server)
async def handle_sell_server(message: Message, state: FSMContext) -> None:
    server = _clean_text(message.text)
    if not server:
        await message.answer("Введите сервер текстом.")
        return

    await state.update_data(server=server)
    await state.set_state(SellRequestFlow.waiting_for_side)
    await message.answer("Введите сторону:", reply_markup=client_cancel_keyboard())


@router.message(SellRequestFlow.waiting_for_side)
async def handle_sell_side(message: Message, state: FSMContext) -> None:
    side = _clean_text(message.text)
    if not side:
        await message.answer("Введите сторону текстом.")
        return

    await state.update_data(side=side)
    await state.set_state(SellRequestFlow.waiting_for_amount)
    await message.answer("Введите количество золота:", reply_markup=client_cancel_keyboard())


@router.message(SellRequestFlow.waiting_for_amount)
async def handle_sell_amount(message: Message, state: FSMContext) -> None:
    amount = _clean_text(message.text)
    if not amount:
        await message.answer("Введите количество текстом или числом.")
        return

    await state.update_data(amount=amount)
    await state.set_state(SellRequestFlow.waiting_for_price)
    await message.answer("Введите желаемую цену:", reply_markup=client_cancel_keyboard())


@router.message(SellRequestFlow.waiting_for_price)
async def handle_sell_price(message: Message, state: FSMContext) -> None:
    price = _clean_text(message.text)
    if not price:
        await message.answer("Введите цену текстом или числом.")
        return

    await state.update_data(price=price)
    await state.set_state(SellRequestFlow.waiting_for_comment)
    await message.answer(
        "Добавьте комментарий или напишите `-`, если комментарий не нужен.",
        reply_markup=client_cancel_keyboard(),
    )


@router.message(SellRequestFlow.waiting_for_comment)
async def handle_sell_comment(
    message: Message,
    bot: Bot,
    settings: Settings,
    state: FSMContext,
    database: MarketRepository,
) -> None:
    if not message.from_user:
        return

    comment = _clean_text(message.text)
    if not comment:
        await message.answer("Напишите комментарий или `-`.")
        return

    data = await state.get_data()
    sell_request = await database.create_sell_request(
        telegram_id=message.from_user.id,
        realm_type=str(data["realm_type"]),
        server=str(data["server"]),
        side=str(data["side"]),
        amount=str(data["amount"]),
        price=str(data["price"]),
        comment=None if comment == "-" else comment,
    )
    await state.clear()
    log_user_action(
        message.from_user.id,
        "sell_request_created",
        request_id=sell_request.id,
        realm_type=sell_request.realm_type,
        server=sell_request.server,
        side=sell_request.side,
    )
    log_metric(
        "sell_request_created",
        user_id=message.from_user.id,
        request_id=sell_request.id,
        realm_type=sell_request.realm_type,
    )
    await _notify_admins_about_sell_request(bot, settings, sell_request, message.from_user)

    await message.answer(
        "Заявка на продажу создана.\n\n"
        f"Номер заявки: #{sell_request.id}\n"
        "Администратор проверит данные и свяжется с вами.",
        reply_markup=main_menu_keyboard(settings, message.from_user),
    )


@router.message(SupportFlow.waiting_for_question)
async def handle_support_question(
    message: Message,
    bot: Bot,
    settings: Settings,
    state: FSMContext,
    database: MarketRepository,
) -> None:
    if not message.from_user:
        return

    question = _clean_text(message.text)
    if not question:
        await message.answer("Опишите вопрос текстом.")
        return

    await _save_client(message.from_user, database)
    ticket = await database.create_support_ticket(
        telegram_id=message.from_user.id,
        question=question,
    )
    await state.clear()
    log_user_action(
        message.from_user.id,
        "support_request_created",
        ticket_id=ticket.id,
    )
    log_metric(
        "support_request_created",
        user_id=message.from_user.id,
        ticket_id=ticket.id,
    )
    await _notify_admins_about_support_ticket(bot, settings, ticket, message.from_user)

    await message.answer(
        "Вопрос отправлен в поддержку.\n\n"
        f"Номер обращения: #{ticket.id}",
        reply_markup=main_menu_keyboard(settings, message.from_user),
    )


def main_menu_keyboard(settings: Settings, user: User | None) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="Купить", callback_data="shop:buy"),
            InlineKeyboardButton(text="Продать", callback_data="shop:sell"),
        ],
        [
            InlineKeyboardButton(text="Мои заявки", callback_data="shop:my_requests"),
            InlineKeyboardButton(text="Поддержка", callback_data="shop:support"),
        ],
    ]
    user_id = user.id if user else None
    if is_admin_user(user_id, settings):
        rows.append([InlineKeyboardButton(text="⚙️ Админка", callback_data="admin:home")])

    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


def client_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Главное меню", callback_data="shop:home")]]
    )


def buy_realm_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=label, callback_data=f"shop:realm:{value}")
                for value, label in REALM_TYPE_LABELS.items()
            ],
            [InlineKeyboardButton(text="Назад", callback_data="shop:home")],
        ]
    )


def sell_realm_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=label, callback_data=f"sell:realm:{value}")
                for value, label in REALM_TYPE_LABELS.items()
            ],
            [InlineKeyboardButton(text="Назад", callback_data="shop:home")],
        ]
    )


def servers_keyboard(realm_type: str, servers: list[str]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=_server_button_text(server), callback_data=f"shop:server:{realm_type}:{index}")]
        for index, server in enumerate(_sorted_servers(servers))
    ]
    rows.append([InlineKeyboardButton(text="Назад", callback_data="shop:buy")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def sides_keyboard(realm_type: str, server_index: int, sides: list[str]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=_side_button_text(side), callback_data=f"shop:side:{realm_type}:{server_index}:{index}")]
        for index, side in enumerate(_sorted_sides(sides))
    ]
    rows.append([InlineKeyboardButton(text="Назад", callback_data=f"shop:realm:{realm_type}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def products_keyboard(products: list[Product], realm_type: str, server_index: int) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"Выбрать #{product.id} · {_product_price_label(product)}",
                callback_data=f"shop:purchase:{product.id}",
            )
        ]
        for product in _sorted_products(products)
    ]
    rows.append([InlineKeyboardButton(text="Назад", callback_data=f"shop:server:{realm_type}:{server_index}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def purchase_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Создать заявку", callback_data="shop:confirm_purchase")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="shop:cancel_purchase")],
        ]
    )


def admin_purchase_keyboard(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="В работу", callback_data=f"admin:purchase_status:{request_id}:{REQUEST_STATUS_IN_PROGRESS}"),
                InlineKeyboardButton(text="Закрыть", callback_data=f"admin:purchase_status:{request_id}:{REQUEST_STATUS_DONE}"),
            ],
            [InlineKeyboardButton(text="Отменить", callback_data=f"admin:purchase_status:{request_id}:{REQUEST_STATUS_CANCELLED}")],
        ]
    )


def admin_sell_keyboard(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="В работу", callback_data=f"admin:sell_status:{request_id}:{REQUEST_STATUS_IN_PROGRESS}"),
                InlineKeyboardButton(text="Закрыть", callback_data=f"admin:sell_status:{request_id}:{REQUEST_STATUS_DONE}"),
            ],
            [InlineKeyboardButton(text="Отменить", callback_data=f"admin:sell_status:{request_id}:{REQUEST_STATUS_CANCELLED}")],
        ]
    )


def admin_support_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Ответить", callback_data=f"admin:support_answer:{ticket_id}"),
                InlineKeyboardButton(text="Закрыть", callback_data=f"admin:support_close:{ticket_id}"),
            ]
        ]
    )


async def _save_client(user: User, database: MarketRepository) -> None:
    await database.upsert_client(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        language_code=user.language_code,
        is_bot=user.is_bot,
    )


async def _notify_admins_about_purchase(
    bot: Bot,
    settings: Settings,
    request: PurchaseRequest,
    product: Product,
    user: User,
    *,
    character_nickname: str,
    gold_amount: int,
    total_price: Decimal,
) -> None:
    username = _username(user.username)
    full_name = _user_full_name(user)
    text = (
        f"Новая заявка на покупку #{request.id}\n\n"
        f"Клиент: {full_name}\n"
        f"Username: {username}\n"
        f"Telegram ID: {user.id}\n"
        f"Ник персонажа: {character_nickname}\n"
        f"Количество золота: {_format_number(gold_amount)}\n"
        f"Итого: {_format_money(total_price)}\n\n"
        f"{_format_product(product)}"
    )
    await _send_to_admins(bot, settings, text, admin_purchase_keyboard(request.id))


async def _notify_admins_about_sell_request(
    bot: Bot,
    settings: Settings,
    sell_request: SellRequestDetails,
    user: User,
) -> None:
    text = (
        f"Новая заявка на продажу #{sell_request.id}\n\n"
        f"Клиент: {_user_full_name(user)}\n"
        f"Username: {_username(user.username)}\n"
        f"Telegram ID: {user.id}\n\n"
        f"{_format_sell_request(sell_request)}"
    )
    await _send_to_admins(bot, settings, text, admin_sell_keyboard(sell_request.id))


async def _notify_admins_about_support_ticket(
    bot: Bot,
    settings: Settings,
    ticket: SupportTicket,
    user: User,
) -> None:
    text = (
        f"Новое обращение в поддержку #{ticket.id}\n\n"
        f"Клиент: {_user_full_name(user)}\n"
        f"Username: {_username(user.username)}\n"
        f"Telegram ID: {user.id}\n\n"
        f"Вопрос:\n{ticket.question}"
    )
    await _send_to_admins(bot, settings, text, admin_support_keyboard(ticket.id))


async def _send_to_admins(
    bot: Bot,
    settings: Settings,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    for admin_id in settings.admin_ids:
        try:
            await bot.send_message(admin_id, text, reply_markup=reply_markup)
        except TelegramAPIError:
            continue


async def _my_requests_text(database: MarketRepository, telegram_id: int) -> str:
    purchases = await database.latest_purchase_requests_by_user(telegram_id, limit=5)
    sells = await database.latest_sell_requests_by_user(telegram_id, limit=5)
    tickets = await database.latest_support_tickets_by_user(telegram_id, limit=5)

    lines = ["Мои заявки"]

    lines.append("")
    lines.append("Покупки:")
    if purchases:
        for request in purchases:
            lines.append(
                f"#{request.id} - {format_request_status(request.status, compact=True)} - "
                f"{realm_type_label(request.product.realm_type)}, {request.product.server}, "
                f"{request.product.side}, {request.price_snapshot or request.product.price}"
            )
    else:
        lines.append("Пока нет заявок на покупку.")

    lines.append("")
    lines.append("Продажи:")
    if sells:
        for request in sells:
            lines.append(
                f"#{request.id} - {format_request_status(request.status, compact=True)} - "
                f"{realm_type_label(request.realm_type)}, {request.server}, "
                f"{request.side}, {request.amount}, {request.price}"
            )
    else:
        lines.append("Пока нет заявок на продажу.")

    lines.append("")
    lines.append("Поддержка:")
    if tickets:
        for ticket in tickets:
            lines.append(f"#{ticket.id} - {support_status_label(ticket.status)} - {ticket.created_at}")
    else:
        lines.append("Пока нет обращений.")

    return "\n".join(lines)


def _servers_text(realm_type: str, servers: list[str]) -> str:
    if not servers:
        return f"{realm_type_label(realm_type)}\n\nПока нет товаров."

    return f"{realm_type_label(realm_type)}\n\nВыберите сервер:"


def _sides_text(realm_type: str, server: str, sides: list[str]) -> str:
    if not sides:
        return (
            f"{realm_type_label(realm_type)}\n"
            f"Сервер: {server}\n\n"
            "Пока нет доступных сторон."
        )

    return (
        f"{realm_type_label(realm_type)}\n"
        f"Сервер: {server}\n\n"
        "Выберите сторону:"
    )


def _character_nickname_prompt(realm_type: str, server: str, side: str) -> str:
    return (
        f"{realm_type_label(realm_type)}\n"
        f"Сервер: {server}\n"
        f"Сторона: {side}\n\n"
        "Введите ник персонажа:"
    )


def _products_text(
    realm_type: str,
    server: str,
    side: str,
    products: list[Product],
    *,
    character_nickname: str | None = None,
    gold_amount: int | None = None,
) -> str:
    nickname_lines = [f"Ник персонажа: {character_nickname}"] if character_nickname else []
    amount_lines = [f"Количество золота: {_format_number(gold_amount)}"] if gold_amount is not None else []
    if not products:
        lines = [
            realm_type_label(realm_type),
            f"Сервер: {server}",
            f"Сторона: {side}",
            *nickname_lines,
            *amount_lines,
            "",
            "Пока нет товаров.",
        ]
        return "\n".join(lines)

    lines = [
        realm_type_label(realm_type),
        f"Сервер: {server}",
        f"Сторона: {side}",
        *nickname_lines,
        *amount_lines,
        "",
        "Доступные предложения:",
    ]
    for product in _sorted_products(products):
        lines.append("")
        lines.append(_product_card_text(product))

    return "\n".join(lines)


def _purchase_confirmation_text(
    product: Product,
    *,
    character_nickname: str,
    gold_amount: int,
    price_per_1000: Decimal,
    total_price: Decimal,
) -> str:
    return (
        "Проверьте заявку:\n\n"
        f"Сервер: {product.server}\n"
        f"Фракция: {product.side}\n"
        f"Ник: {character_nickname}\n"
        f"Количество: {_format_number(gold_amount)} золота\n"
        f"Цена за 1000: {_format_money(price_per_1000)}\n"
        f"Итого: {_format_money(total_price)}\n\n"
        "Создать заявку?"
    )


def _product_card_text(product: Product) -> str:
    return (
        f"🟡 {product.server}\n"
        f"⚔️ {product.side}\n"
        f"💰 {_product_price_label(product)}"
    )


def _product_price_label(product: Product) -> str:
    price = _parse_price_per_1000(product.price)
    if price is None:
        return f"{product.price} / 1000 gold"

    return f"{_format_money(price)} / 1000 gold"


def _format_product(product: Product) -> str:
    return (
        f"Товар #{product.id}\n"
        f"Тип: {realm_type_label(product.realm_type)}\n"
        f"Сервер: {product.server}\n"
        f"Сторона: {product.side}\n"
        f"Цена: {product.price}"
    )


def _format_sell_request(request: SellRequestDetails) -> str:
    comment = request.comment or "без комментария"
    return (
        f"Продажа #{request.id}\n"
        f"{format_request_status(request.status)}\n"
        f"Тип: {realm_type_label(request.realm_type)}\n"
        f"Сервер: {request.server}\n"
        f"Сторона: {request.side}\n"
        f"Количество: {request.amount}\n"
        f"Цена: {request.price}\n"
        f"Комментарий: {comment}"
    )


def _parse_catalog_index_callback(data: str | None, *, expected_prefix: str) -> tuple[str, int] | None:
    if not data:
        return None

    parts = data.split(":")
    if len(parts) != 4 or ":".join(parts[:2]) != expected_prefix:
        return None

    realm_type = parts[2]
    if not is_valid_realm_type(realm_type):
        return None

    try:
        return realm_type, int(parts[3])
    except ValueError:
        return None


def _parse_side_callback(data: str | None) -> tuple[str, int, int] | None:
    if not data:
        return None

    parts = data.split(":")
    if len(parts) != 5 or ":".join(parts[:2]) != "shop:side":
        return None

    realm_type = parts[2]
    if not is_valid_realm_type(realm_type):
        return None

    try:
        return realm_type, int(parts[3]), int(parts[4])
    except ValueError:
        return None


def _parse_product_id(data: str | None) -> int | None:
    if not data:
        return None

    parts = data.split(":")
    if len(parts) != 3 or ":".join(parts[:2]) != "shop:purchase":
        return None

    try:
        return int(parts[2])
    except ValueError:
        return None


def _clean_text(value: str | None) -> str:
    return value.strip() if value else ""


def _normalize_character_nickname(value: str | None) -> str:
    return _clean_text(value)


def _is_valid_character_nickname(value: str) -> bool:
    return 2 <= len(value) <= 32


def _parse_gold_amount(value: str | None) -> int | None:
    normalized = "".join(_clean_text(value).split())
    if not normalized:
        return None

    multiplier = 1
    if normalized.lower().endswith("k"):
        multiplier = 1000
        normalized = normalized[:-1]

    if not normalized.isdigit():
        return None

    amount = int(normalized) * multiplier
    return amount if _is_valid_gold_amount(amount) else None


def _is_valid_gold_amount(value: int) -> bool:
    return 0 < value <= MAX_BUY_GOLD_AMOUNT


def _parse_price_per_1000(value: str) -> Decimal | None:
    normalized = _clean_text(value).replace(" ", "").replace(",", ".")
    normalized = "".join(character for character in normalized if character.isdigit() or character == ".")
    if not normalized or normalized == ".":
        return None

    try:
        price = Decimal(normalized)
    except InvalidOperation:
        return None

    return price if price > 0 else None


def _calculate_total_price(gold_amount: int, price_per_1000: Decimal) -> Decimal:
    return (Decimal(gold_amount) / Decimal(1000)) * price_per_1000


def _format_number(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def _format_money(value: Decimal) -> str:
    if value == value.to_integral_value():
        amount = _format_number(int(value))
    else:
        amount = f"{value.quantize(Decimal('0.01')):,.2f}".replace(",", " ")
    return f"{amount} ₽"


def _sorted_servers(servers: list[str]) -> list[str]:
    return sorted(servers, key=_readable_sort_key)


def _sorted_sides(sides: list[str]) -> list[str]:
    return sorted(sides, key=_side_sort_key)


def _sorted_products(products: list[Product]) -> list[Product]:
    return sorted(
        products,
        key=lambda product: (
            _price_sort_key(product.price),
            product.server.casefold(),
            product.side.casefold(),
            product.id,
        ),
    )


def _server_button_text(server: str) -> str:
    return f"🟡 {server}"


def _side_button_text(side: str) -> str:
    return f"⚔️ {side}"


def _readable_sort_key(value: str) -> str:
    return value.casefold().strip()


def _side_sort_key(side: str) -> tuple[int, str]:
    normalized = side.casefold().strip()
    order = {
        "alliance": 0,
        "альянс": 0,
        "horde": 1,
        "орда": 1,
    }
    return order.get(normalized, 10), normalized


def _price_sort_key(price: str) -> Decimal:
    return _parse_price_per_1000(price) or Decimal("999999999")


def _username(username: str | None) -> str:
    return f"@{username}" if username else "без username"


def _user_full_name(user: User) -> str:
    return " ".join(part for part in (user.first_name, user.last_name) if part) or "Без имени"

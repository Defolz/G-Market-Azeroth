from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from g_market_azeroth.catalog import (
    REALM_TYPE_LABELS,
    is_valid_request_status,
    realm_type_label,
    support_status_label,
)
from g_market_azeroth.config import Settings
from g_market_azeroth.constants import (
    REQUEST_STATUS_CANCELLED,
    REQUEST_STATUS_DONE,
    REQUEST_STATUS_IN_PROGRESS,
    REQUEST_STATUS_NEW,
)
from g_market_azeroth.database import (
    Client,
    MarketRepository,
    Product,
    PurchaseRequestDetails,
    SellRequestDetails,
    SupportTicket,
)
from g_market_azeroth.logging import log_admin_action
from g_market_azeroth.services.statuses import format_request_status

router = Router(name="admin")
ADMIN_REQUEST_PAGE_SIZE = 5
REQUEST_STATUS_FILTERS = (
    REQUEST_STATUS_NEW,
    REQUEST_STATUS_IN_PROGRESS,
    REQUEST_STATUS_DONE,
    REQUEST_STATUS_CANCELLED,
)


class AddProduct(StatesGroup):
    waiting_for_realm_type = State()
    waiting_for_server = State()
    waiting_for_side = State()
    waiting_for_price = State()


class ChangeProductPrice(StatesGroup):
    waiting_for_product_id = State()
    waiting_for_price = State()


class AnswerSupportTicket(StatesGroup):
    waiting_for_answer = State()


def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Статистика", callback_data="admin:stats"),
                InlineKeyboardButton(text="Клиенты", callback_data="admin:clients"),
            ],
            [
                InlineKeyboardButton(text="Товары", callback_data="admin:products"),
                InlineKeyboardButton(text="Добавить товар", callback_data="admin:add_product"),
            ],
            [
                InlineKeyboardButton(text="Покупки", callback_data="admin:requests"),
                InlineKeyboardButton(text="Продажи", callback_data="admin:sell_requests"),
            ],
            [
                InlineKeyboardButton(text="Поддержка", callback_data="admin:support"),
                InlineKeyboardButton(text="Изменить цену", callback_data="admin:change_price"),
            ],
        ]
    )


def realm_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=label, callback_data=f"admin:add:realm:{value}")
                for value, label in REALM_TYPE_LABELS.items()
            ],
            [InlineKeyboardButton(text="Отмена", callback_data="admin:cancel_action")],
        ]
    )


def action_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="admin:cancel_action")]]
    )


@router.message(Command("admin"))
async def handle_admin(message: Message, settings: Settings) -> None:
    if not await _ensure_admin_message(message, settings):
        return

    await message.answer(_admin_home_text(), reply_markup=admin_keyboard())


@router.message(Command("stats"))
async def handle_stats(message: Message, settings: Settings, database: MarketRepository) -> None:
    if not await _ensure_admin_message(message, settings):
        return

    await message.answer(await _stats_text(database), reply_markup=admin_keyboard())


@router.message(Command("clients"))
async def handle_clients(message: Message, settings: Settings, database: MarketRepository) -> None:
    if not await _ensure_admin_message(message, settings):
        return

    await message.answer(await _clients_text(database), reply_markup=admin_keyboard())


@router.message(Command("products"))
async def handle_products(message: Message, settings: Settings, database: MarketRepository) -> None:
    if not await _ensure_admin_message(message, settings):
        return

    await message.answer(await _products_text(database), reply_markup=admin_keyboard())


@router.message(Command("requests"))
async def handle_requests(message: Message, settings: Settings, database: MarketRepository) -> None:
    if not await _ensure_admin_message(message, settings):
        return

    requests, page, page_count, total_count = await _purchase_requests_page(database, page=0, status=None)
    await message.answer(
        _purchase_requests_list_text(requests, page=page, page_count=page_count, total_count=total_count, status=None),
        reply_markup=purchase_requests_keyboard(requests, page=page, page_count=page_count, status=None),
    )


@router.message(Command("sell_requests"))
async def handle_sell_requests(message: Message, settings: Settings, database: MarketRepository) -> None:
    if not await _ensure_admin_message(message, settings):
        return

    requests, page, page_count, total_count = await _sell_requests_page(database, page=0, status=None)
    await message.answer(
        _sell_requests_list_text(requests, page=page, page_count=page_count, total_count=total_count, status=None),
        reply_markup=sell_requests_keyboard(requests, page=page, page_count=page_count, status=None),
    )


@router.message(Command("support_tickets"))
async def handle_support_tickets(message: Message, settings: Settings, database: MarketRepository) -> None:
    if not await _ensure_admin_message(message, settings):
        return

    tickets = await database.latest_support_tickets(limit=10)
    await message.answer(_support_tickets_list_text(tickets), reply_markup=support_tickets_keyboard(tickets))


@router.message(Command("add_product"))
async def handle_add_product_command(
    message: Message,
    settings: Settings,
    state: FSMContext,
) -> None:
    if not await _ensure_admin_message(message, settings):
        return

    await state.set_state(AddProduct.waiting_for_realm_type)
    await message.answer("Выберите тип товара:", reply_markup=realm_type_keyboard())


@router.message(Command("change_price"))
async def handle_change_price_command(
    message: Message,
    settings: Settings,
    state: FSMContext,
) -> None:
    if not await _ensure_admin_message(message, settings):
        return

    await state.set_state(ChangeProductPrice.waiting_for_product_id)
    await message.answer(
        "Введите ID товара, у которого нужно изменить цену:",
        reply_markup=action_cancel_keyboard(),
    )


@router.message(Command("cancel"))
async def handle_cancel(message: Message, settings: Settings, state: FSMContext) -> None:
    if not await _ensure_admin_message(message, settings):
        return

    await state.clear()
    await message.answer("Действие отменено.", reply_markup=admin_keyboard())


@router.callback_query(F.data == "admin:home")
async def handle_admin_home(callback: CallbackQuery, settings: Settings) -> None:
    if not await _ensure_admin_callback(callback, settings):
        return

    if isinstance(callback.message, Message):
        await callback.message.edit_text(_admin_home_text(), reply_markup=admin_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:stats")
async def handle_admin_stats(
    callback: CallbackQuery,
    settings: Settings,
    database: MarketRepository,
) -> None:
    if not await _ensure_admin_callback(callback, settings):
        return

    if isinstance(callback.message, Message):
        await callback.message.edit_text(await _stats_text(database), reply_markup=admin_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:clients")
async def handle_admin_clients(
    callback: CallbackQuery,
    settings: Settings,
    database: MarketRepository,
) -> None:
    if not await _ensure_admin_callback(callback, settings):
        return

    if isinstance(callback.message, Message):
        await callback.message.edit_text(await _clients_text(database), reply_markup=admin_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:products")
async def handle_admin_products(
    callback: CallbackQuery,
    settings: Settings,
    database: MarketRepository,
) -> None:
    if not await _ensure_admin_callback(callback, settings):
        return

    if isinstance(callback.message, Message):
        await callback.message.edit_text(await _products_text(database), reply_markup=admin_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:requests")
async def handle_admin_requests(
    callback: CallbackQuery,
    settings: Settings,
    database: MarketRepository,
) -> None:
    if not await _ensure_admin_callback(callback, settings):
        return

    requests, page, page_count, total_count = await _purchase_requests_page(database, page=0, status=None)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _purchase_requests_list_text(requests, page=page, page_count=page_count, total_count=total_count, status=None),
            reply_markup=purchase_requests_keyboard(requests, page=page, page_count=page_count, status=None),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:requests_page:"))
async def handle_admin_requests_page(
    callback: CallbackQuery,
    settings: Settings,
    database: MarketRepository,
) -> None:
    if not await _ensure_admin_callback(callback, settings):
        return

    page, status = _parse_page_filter_callback(callback.data, "admin:requests_page")
    requests, page, page_count, total_count = await _purchase_requests_page(database, page=page, status=status)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _purchase_requests_list_text(requests, page=page, page_count=page_count, total_count=total_count, status=status),
            reply_markup=purchase_requests_keyboard(requests, page=page, page_count=page_count, status=status),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:requests_filter:"))
async def handle_admin_requests_filter(
    callback: CallbackQuery,
    settings: Settings,
    database: MarketRepository,
) -> None:
    if not await _ensure_admin_callback(callback, settings):
        return

    status = _parse_status_filter_callback(callback.data, "admin:requests_filter")
    requests, page, page_count, total_count = await _purchase_requests_page(database, page=0, status=status)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _purchase_requests_list_text(requests, page=page, page_count=page_count, total_count=total_count, status=status),
            reply_markup=purchase_requests_keyboard(requests, page=page, page_count=page_count, status=status),
        )
    await callback.answer()


@router.callback_query(F.data == "admin:sell_requests")
async def handle_admin_sell_requests(
    callback: CallbackQuery,
    settings: Settings,
    database: MarketRepository,
) -> None:
    if not await _ensure_admin_callback(callback, settings):
        return

    requests, page, page_count, total_count = await _sell_requests_page(database, page=0, status=None)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _sell_requests_list_text(requests, page=page, page_count=page_count, total_count=total_count, status=None),
            reply_markup=sell_requests_keyboard(requests, page=page, page_count=page_count, status=None),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:sell_requests_page:"))
async def handle_admin_sell_requests_page(
    callback: CallbackQuery,
    settings: Settings,
    database: MarketRepository,
) -> None:
    if not await _ensure_admin_callback(callback, settings):
        return

    page, status = _parse_page_filter_callback(callback.data, "admin:sell_requests_page")
    requests, page, page_count, total_count = await _sell_requests_page(database, page=page, status=status)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _sell_requests_list_text(requests, page=page, page_count=page_count, total_count=total_count, status=status),
            reply_markup=sell_requests_keyboard(requests, page=page, page_count=page_count, status=status),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:sell_requests_filter:"))
async def handle_admin_sell_requests_filter(
    callback: CallbackQuery,
    settings: Settings,
    database: MarketRepository,
) -> None:
    if not await _ensure_admin_callback(callback, settings):
        return

    status = _parse_status_filter_callback(callback.data, "admin:sell_requests_filter")
    requests, page, page_count, total_count = await _sell_requests_page(database, page=0, status=status)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _sell_requests_list_text(requests, page=page, page_count=page_count, total_count=total_count, status=status),
            reply_markup=sell_requests_keyboard(requests, page=page, page_count=page_count, status=status),
        )
    await callback.answer()


@router.callback_query(F.data == "admin:noop")
async def handle_admin_noop(callback: CallbackQuery, settings: Settings) -> None:
    if not await _ensure_admin_callback(callback, settings):
        return

    await callback.answer()


@router.callback_query(F.data == "admin:support")
async def handle_admin_support(
    callback: CallbackQuery,
    settings: Settings,
    database: MarketRepository,
) -> None:
    if not await _ensure_admin_callback(callback, settings):
        return

    tickets = await database.latest_support_tickets(limit=10)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _support_tickets_list_text(tickets),
            reply_markup=support_tickets_keyboard(tickets),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:purchase_view:"))
async def handle_purchase_view(
    callback: CallbackQuery,
    settings: Settings,
    database: MarketRepository,
) -> None:
    if not await _ensure_admin_callback(callback, settings):
        return

    request_id = _parse_callback_int(callback.data, "admin:purchase_view")
    request = await database.get_purchase_request(request_id) if request_id is not None else None
    if request is None:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _format_purchase_request(request),
            reply_markup=purchase_request_actions_keyboard(request.id),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:sell_view:"))
async def handle_sell_view(
    callback: CallbackQuery,
    settings: Settings,
    database: MarketRepository,
) -> None:
    if not await _ensure_admin_callback(callback, settings):
        return

    request_id = _parse_callback_int(callback.data, "admin:sell_view")
    request = await database.get_sell_request(request_id) if request_id is not None else None
    if request is None:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _format_sell_request(request),
            reply_markup=sell_request_actions_keyboard(request.id),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:support_view:"))
async def handle_support_view(
    callback: CallbackQuery,
    settings: Settings,
    database: MarketRepository,
) -> None:
    if not await _ensure_admin_callback(callback, settings):
        return

    ticket_id = _parse_callback_int(callback.data, "admin:support_view")
    ticket = await database.get_support_ticket(ticket_id) if ticket_id is not None else None
    if ticket is None:
        await callback.answer("Обращение не найдено.", show_alert=True)
        return

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _format_support_ticket(ticket),
            reply_markup=support_ticket_actions_keyboard(ticket.id),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:purchase_status:"))
async def handle_purchase_status(
    callback: CallbackQuery,
    bot: Bot,
    settings: Settings,
    database: MarketRepository,
) -> None:
    if not await _ensure_admin_callback(callback, settings):
        return

    parsed = _parse_status_callback(callback.data, "admin:purchase_status")
    if parsed is None:
        await callback.answer("Не удалось изменить статус.", show_alert=True)
        return

    request_id, status = parsed
    request = await database.update_purchase_request_status(request_id=request_id, status=status)
    if request is None:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return
    log_admin_action(
        callback.from_user.id,
        "purchase_request_status_changed",
        request_id=request.id,
        status=request.status,
    )

    await _notify_user(
        bot,
        request.telegram_id,
        "Статус заявки на покупку обновлён.\n\n"
        f"Заявка #{request.id}\n{format_request_status(request.status)}",
    )

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _format_purchase_request(request),
            reply_markup=purchase_request_actions_keyboard(request.id),
        )
    await callback.answer("Статус обновлён.")


@router.callback_query(F.data.startswith("admin:sell_status:"))
async def handle_sell_status(
    callback: CallbackQuery,
    bot: Bot,
    settings: Settings,
    database: MarketRepository,
) -> None:
    if not await _ensure_admin_callback(callback, settings):
        return

    parsed = _parse_status_callback(callback.data, "admin:sell_status")
    if parsed is None:
        await callback.answer("Не удалось изменить статус.", show_alert=True)
        return

    request_id, status = parsed
    request = await database.update_sell_request_status(request_id=request_id, status=status)
    if request is None:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return
    log_admin_action(
        callback.from_user.id,
        "sell_request_status_changed",
        request_id=request.id,
        status=request.status,
    )

    await _notify_user(
        bot,
        request.telegram_id,
        "Статус заявки на продажу обновлён.\n\n"
        f"Заявка #{request.id}\n{format_request_status(request.status)}",
    )

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _format_sell_request(request),
            reply_markup=sell_request_actions_keyboard(request.id),
        )
    await callback.answer("Статус обновлён.")


@router.callback_query(F.data.startswith("admin:support_answer:"))
async def handle_support_answer_start(
    callback: CallbackQuery,
    settings: Settings,
    state: FSMContext,
    database: MarketRepository,
) -> None:
    if not await _ensure_admin_callback(callback, settings):
        return

    ticket_id = _parse_callback_int(callback.data, "admin:support_answer")
    ticket = await database.get_support_ticket(ticket_id) if ticket_id is not None else None
    if ticket is None:
        await callback.answer("Обращение не найдено.", show_alert=True)
        return

    await state.set_state(AnswerSupportTicket.waiting_for_answer)
    await state.update_data(ticket_id=ticket.id)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _format_support_ticket(ticket)
            + "\n\nВведите ответ клиенту одним сообщением:",
            reply_markup=action_cancel_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:support_close:"))
async def handle_support_close(
    callback: CallbackQuery,
    bot: Bot,
    settings: Settings,
    database: MarketRepository,
) -> None:
    if not await _ensure_admin_callback(callback, settings):
        return

    ticket_id = _parse_callback_int(callback.data, "admin:support_close")
    ticket = await database.close_support_ticket(
        ticket_id=ticket_id,
        admin_id=callback.from_user.id,
    ) if ticket_id is not None else None
    if ticket is None:
        await callback.answer("Обращение не найдено.", show_alert=True)
        return
    log_admin_action(
        callback.from_user.id,
        "support_ticket_closed",
        ticket_id=ticket.id,
    )

    await _notify_user(
        bot,
        ticket.telegram_id,
        f"Обращение в поддержку #{ticket.id} закрыто.",
    )

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _format_support_ticket(ticket),
            reply_markup=support_ticket_actions_keyboard(ticket.id),
        )
    await callback.answer("Обращение закрыто.")


@router.callback_query(F.data == "admin:add_product")
async def handle_add_product_callback(
    callback: CallbackQuery,
    settings: Settings,
    state: FSMContext,
) -> None:
    if not await _ensure_admin_callback(callback, settings):
        return

    await state.set_state(AddProduct.waiting_for_realm_type)
    if isinstance(callback.message, Message):
        await callback.message.edit_text("Выберите тип товара:", reply_markup=realm_type_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:change_price")
async def handle_change_price_callback(
    callback: CallbackQuery,
    settings: Settings,
    state: FSMContext,
) -> None:
    if not await _ensure_admin_callback(callback, settings):
        return

    await state.set_state(ChangeProductPrice.waiting_for_product_id)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "Введите ID товара, у которого нужно изменить цену:",
            reply_markup=action_cancel_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data == "admin:cancel_action")
async def handle_cancel_action_callback(
    callback: CallbackQuery,
    settings: Settings,
    state: FSMContext,
) -> None:
    if not await _ensure_admin_callback(callback, settings):
        return

    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.edit_text("Действие отменено.", reply_markup=admin_keyboard())
    await callback.answer()


@router.callback_query(AddProduct.waiting_for_realm_type, F.data.startswith("admin:add:realm:"))
async def handle_product_realm_type(
    callback: CallbackQuery,
    settings: Settings,
    state: FSMContext,
) -> None:
    if not await _ensure_admin_callback(callback, settings):
        return

    realm_type = callback.data.rsplit(":", maxsplit=1)[-1] if callback.data else ""
    if realm_type not in REALM_TYPE_LABELS:
        await callback.answer("Неизвестный тип товара.", show_alert=True)
        return

    await state.update_data(realm_type=realm_type)
    await state.set_state(AddProduct.waiting_for_server)

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            f"Тип: {realm_type_label(realm_type)}\n\nВведите сервер:"
        )
    await callback.answer()


@router.message(AddProduct.waiting_for_server)
async def handle_product_server(message: Message, settings: Settings, state: FSMContext) -> None:
    if not await _ensure_admin_message(message, settings):
        return

    server = _clean_text(message.text)
    if not server:
        await message.answer("Введите сервер текстом.")
        return

    await state.update_data(server=server)
    await state.set_state(AddProduct.waiting_for_side)
    await message.answer("Введите сторону:")


@router.message(AddProduct.waiting_for_side)
async def handle_product_side(message: Message, settings: Settings, state: FSMContext) -> None:
    if not await _ensure_admin_message(message, settings):
        return

    side = _clean_text(message.text)
    if not side:
        await message.answer("Введите сторону текстом.")
        return

    await state.update_data(side=side)
    await state.set_state(AddProduct.waiting_for_price)
    await message.answer("Введите цену:")


@router.message(AddProduct.waiting_for_price)
async def handle_product_price(
    message: Message,
    settings: Settings,
    state: FSMContext,
    database: MarketRepository,
) -> None:
    if not await _ensure_admin_message(message, settings):
        return

    price = _clean_text(message.text)
    if not price:
        await message.answer("Введите цену текстом или числом.")
        return

    data = await state.get_data()
    product = await database.create_catalog_product(
        realm_type=str(data["realm_type"]),
        server=str(data["server"]),
        side=str(data["side"]),
        price=price,
    )
    await state.clear()
    if message.from_user:
        log_admin_action(
            message.from_user.id,
            "product_created",
            product_id=product.id,
            realm_type=product.realm_type,
            server=product.server,
            side=product.side,
        )

    await message.answer(
        "Товар добавлен.\n\n" + _format_product(product),
        reply_markup=admin_keyboard(),
    )


@router.message(ChangeProductPrice.waiting_for_product_id)
async def handle_change_price_product_id(
    message: Message,
    settings: Settings,
    state: FSMContext,
    database: MarketRepository,
) -> None:
    if not await _ensure_admin_message(message, settings):
        return

    product_id = _parse_int(message.text)
    if product_id is None:
        await message.answer("Введите ID товара числом.")
        return

    product = await database.get_catalog_product(product_id)
    if product is None:
        await message.answer("Товар с таким ID не найден. Введите другой ID или /cancel.")
        return

    await state.update_data(product_id=product.id)
    await state.set_state(ChangeProductPrice.waiting_for_price)
    await message.answer(
        "Текущий товар:\n\n"
        f"{_format_product(product)}\n\n"
        "Введите новую цену:",
        reply_markup=action_cancel_keyboard(),
    )


@router.message(ChangeProductPrice.waiting_for_price)
async def handle_change_price_value(
    message: Message,
    settings: Settings,
    state: FSMContext,
    database: MarketRepository,
) -> None:
    if not await _ensure_admin_message(message, settings):
        return

    price = _clean_text(message.text)
    if not price:
        await message.answer("Введите новую цену текстом или числом.")
        return

    data = await state.get_data()
    product = await database.change_product_price(
        product_id=int(data["product_id"]),
        price=price,
    )
    await state.clear()

    if product is None:
        await message.answer("Товар не найден. Цена не изменена.", reply_markup=admin_keyboard())
        return
    if message.from_user:
        log_admin_action(
            message.from_user.id,
            "product_price_changed",
            product_id=product.id,
        )

    await message.answer(
        "Цена обновлена.\n\n" + _format_product(product),
        reply_markup=admin_keyboard(),
    )


@router.message(AnswerSupportTicket.waiting_for_answer)
async def handle_support_answer_message(
    message: Message,
    bot: Bot,
    settings: Settings,
    state: FSMContext,
    database: MarketRepository,
) -> None:
    if not await _ensure_admin_message(message, settings):
        return

    answer = _clean_text(message.text)
    if not answer:
        await message.answer("Введите ответ текстом.")
        return

    data = await state.get_data()
    ticket = await database.answer_support_ticket(
        ticket_id=int(data["ticket_id"]),
        admin_id=message.from_user.id if message.from_user else 0,
        answer=answer,
    )
    await state.clear()

    if ticket is None:
        await message.answer("Обращение не найдено.", reply_markup=admin_keyboard())
        return

    await _notify_user(
        bot,
        ticket.telegram_id,
        f"Ответ поддержки по обращению #{ticket.id}:\n\n{ticket.answer}",
    )
    await message.answer(
        "Ответ отправлен клиенту.\n\n" + _format_support_ticket(ticket),
        reply_markup=support_ticket_actions_keyboard(ticket.id),
    )


async def _ensure_admin_message(message: Message, settings: Settings) -> bool:
    if not settings.admin_ids:
        await message.answer("Админка не настроена. Добавьте ADMIN_IDS в .env.")
        return False

    if not message.from_user or message.from_user.id not in settings.admin_ids:
        await message.answer("Эта команда доступна только администратору.")
        return False

    return True


async def _ensure_admin_callback(callback: CallbackQuery, settings: Settings) -> bool:
    if not settings.admin_ids:
        await callback.answer("Админка не настроена.", show_alert=True)
        return False

    if not callback.from_user or callback.from_user.id not in settings.admin_ids:
        await callback.answer("Нет доступа.", show_alert=True)
        return False

    return True


def purchase_requests_keyboard(
    requests: list[PurchaseRequestDetails],
    *,
    page: int,
    page_count: int,
    status: str | None,
) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"Покупка #{request.id}", callback_data=f"admin:purchase_view:{request.id}")]
        for request in requests
    ]
    rows.append(_request_filter_row("admin:requests_filter", selected_status=status))
    rows.append(_pagination_row("admin:requests_page", page=page, page_count=page_count, status=status))
    rows.append([InlineKeyboardButton(text="Назад", callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def purchase_request_actions_keyboard(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="В работу", callback_data=f"admin:purchase_status:{request_id}:{REQUEST_STATUS_IN_PROGRESS}"),
                InlineKeyboardButton(text="Закрыть", callback_data=f"admin:purchase_status:{request_id}:{REQUEST_STATUS_DONE}"),
            ],
            [
                InlineKeyboardButton(text="Отменить", callback_data=f"admin:purchase_status:{request_id}:{REQUEST_STATUS_CANCELLED}"),
                InlineKeyboardButton(text="К списку", callback_data="admin:requests"),
            ],
        ]
    )


def sell_requests_keyboard(
    requests: list[SellRequestDetails],
    *,
    page: int,
    page_count: int,
    status: str | None,
) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"Продажа #{request.id}", callback_data=f"admin:sell_view:{request.id}")]
        for request in requests
    ]
    rows.append(_request_filter_row("admin:sell_requests_filter", selected_status=status))
    rows.append(_pagination_row("admin:sell_requests_page", page=page, page_count=page_count, status=status))
    rows.append([InlineKeyboardButton(text="Назад", callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def sell_request_actions_keyboard(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="В работу", callback_data=f"admin:sell_status:{request_id}:{REQUEST_STATUS_IN_PROGRESS}"),
                InlineKeyboardButton(text="Закрыть", callback_data=f"admin:sell_status:{request_id}:{REQUEST_STATUS_DONE}"),
            ],
            [
                InlineKeyboardButton(text="Отменить", callback_data=f"admin:sell_status:{request_id}:{REQUEST_STATUS_CANCELLED}"),
                InlineKeyboardButton(text="К списку", callback_data="admin:sell_requests"),
            ],
        ]
    )


def support_tickets_keyboard(tickets: list[SupportTicket]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"Обращение #{ticket.id}", callback_data=f"admin:support_view:{ticket.id}")]
        for ticket in tickets
    ]
    rows.append([InlineKeyboardButton(text="Назад", callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def support_ticket_actions_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Ответить", callback_data=f"admin:support_answer:{ticket_id}"),
                InlineKeyboardButton(text="Закрыть", callback_data=f"admin:support_close:{ticket_id}"),
            ],
            [InlineKeyboardButton(text="К списку", callback_data="admin:support")],
        ]
    )


async def _stats_text(database: MarketRepository) -> str:
    clients_count = await database.count_clients()
    products_count = await database.count_products()
    purchase_count = await database.count_purchase_requests()
    purchase_new_count = await database.count_purchase_requests(status=REQUEST_STATUS_NEW)
    sell_count = await database.count_sell_requests()
    sell_new_count = await database.count_sell_requests(status=REQUEST_STATUS_NEW)
    support_count = await database.count_support_tickets()
    support_new_count = await database.count_support_tickets(status=REQUEST_STATUS_NEW)

    return (
        "Статистика\n\n"
        f"Клиентов в базе: {clients_count}\n"
        f"Активных товаров: {products_count}\n"
        f"Покупок всего: {purchase_count}\n"
        f"Новых покупок: {purchase_new_count}\n"
        f"Продаж всего: {sell_count}\n"
        f"Новых продаж: {sell_new_count}\n"
        f"Обращений всего: {support_count}\n"
        f"Новых обращений: {support_new_count}"
    )


async def _clients_text(database: MarketRepository) -> str:
    latest_clients = await database.latest_clients(limit=10)
    if not latest_clients:
        return "Клиенты\n\nВ базе пока нет клиентов."

    lines = ["Клиенты", "", "Последние 10:"]
    for index, client in enumerate(latest_clients, start=1):
        lines.append("")
        lines.append(_format_client(index, client))

    return "\n".join(lines)


async def _products_text(database: MarketRepository) -> str:
    latest_products = await database.list_catalog_products(limit=10)
    if not latest_products:
        return "Товары\n\nВ базе пока нет товаров. Нажмите `Добавить товар`."

    lines = ["Товары", "", "Последние 10:"]
    for product in latest_products:
        lines.append("")
        lines.append(_format_product(product))

    return "\n".join(lines)


async def _purchase_requests_page(
    database: MarketRepository,
    *,
    page: int,
    status: str | None,
) -> tuple[list[PurchaseRequestDetails], int, int, int]:
    total_count = await database.count_purchase_requests(status=status)
    page_count = _page_count(total_count)
    page = _clamp_page(page, page_count)
    if status is None:
        fetch_limit = (page + 1) * ADMIN_REQUEST_PAGE_SIZE
    else:
        fetch_limit = await database.count_purchase_requests()
    requests = await database.latest_purchase_requests(limit=fetch_limit)
    if status is not None:
        requests = [request for request in requests if request.status == status]
    start_index = page * ADMIN_REQUEST_PAGE_SIZE
    return requests[start_index : start_index + ADMIN_REQUEST_PAGE_SIZE], page, page_count, total_count


async def _sell_requests_page(
    database: MarketRepository,
    *,
    page: int,
    status: str | None,
) -> tuple[list[SellRequestDetails], int, int, int]:
    total_count = await database.count_sell_requests(status=status)
    page_count = _page_count(total_count)
    page = _clamp_page(page, page_count)
    if status is None:
        fetch_limit = (page + 1) * ADMIN_REQUEST_PAGE_SIZE
    else:
        fetch_limit = await database.count_sell_requests()
    requests = await database.latest_sell_requests(limit=fetch_limit)
    if status is not None:
        requests = [request for request in requests if request.status == status]
    start_index = page * ADMIN_REQUEST_PAGE_SIZE
    return requests[start_index : start_index + ADMIN_REQUEST_PAGE_SIZE], page, page_count, total_count


def _purchase_requests_list_text(
    requests: list[PurchaseRequestDetails],
    *,
    page: int,
    page_count: int,
    total_count: int,
    status: str | None,
) -> str:
    if not requests:
        filter_line = _request_filter_text(status)
        return f"Заявки на покупку\n\n{filter_line}\nЗаявок пока нет."

    lines = [
        "Заявки на покупку",
        "",
        _request_filter_text(status),
        f"Страница {page + 1}/{page_count}. Всего: {total_count}",
    ]
    for request in requests:
        lines.append(
            f"#{request.id} - {format_request_status(request.status, compact=True)} - "
            f"{request.client_username or request.telegram_id} - "
            f"{request.product.server}, {request.product.side}, {request.price_snapshot or request.product.price}"
        )
    return "\n".join(lines)


def _sell_requests_list_text(
    requests: list[SellRequestDetails],
    *,
    page: int,
    page_count: int,
    total_count: int,
    status: str | None,
) -> str:
    if not requests:
        filter_line = _request_filter_text(status)
        return f"Заявки на продажу\n\n{filter_line}\nЗаявок пока нет."

    lines = [
        "Заявки на продажу",
        "",
        _request_filter_text(status),
        f"Страница {page + 1}/{page_count}. Всего: {total_count}",
    ]
    for request in requests:
        lines.append(
            f"#{request.id} - {format_request_status(request.status, compact=True)} - "
            f"{request.client_username or request.telegram_id} - "
            f"{request.server}, {request.side}, {request.amount}, {request.price}"
        )
    return "\n".join(lines)


def _support_tickets_list_text(tickets: list[SupportTicket]) -> str:
    if not tickets:
        return "Поддержка\n\nОбращений пока нет."

    lines = ["Поддержка", "", "Последние 10:"]
    for ticket in tickets:
        lines.append(
            f"#{ticket.id} - {support_status_label(ticket.status)} - "
            f"{ticket.client_username or ticket.telegram_id} - {ticket.created_at}"
        )
    return "\n".join(lines)


def _admin_home_text() -> str:
    return "Админ панель G-Market Azeroth\n\nВыберите действие:"


def _format_client(index: int, client: Client) -> str:
    full_name = " ".join(
        part for part in (client.first_name, client.last_name) if part
    ) or "Без имени"
    username = f"@{client.username}" if client.username else "без username"

    return (
        f"{index}. {full_name}\n"
        f"ID: {client.telegram_id}\n"
        f"Username: {username}\n"
        f"/start: {client.start_count}\n"
        f"Последний визит: {client.last_seen_at}"
    )


def _format_product(product: Product) -> str:
    return (
        f"#{product.id} {realm_type_label(product.realm_type)}\n"
        f"Сервер: {product.server}\n"
        f"Сторона: {product.side}\n"
        f"Цена: {product.price}"
    )


def _format_purchase_request(request: PurchaseRequestDetails) -> str:
    full_name = _client_full_name(
        request.client_first_name,
        request.client_last_name,
    )
    username = f"@{request.client_username}" if request.client_username else "без username"
    price = request.price_snapshot or request.product.price

    return (
        f"Заявка на покупку #{request.id}\n"
        f"{format_request_status(request.status)}\n"
        f"Дата: {request.created_at}\n"
        f"Клиент: {full_name}\n"
        f"Username: {username}\n"
        f"Telegram ID: {request.telegram_id}\n\n"
        f"Товар #{request.product.id}\n"
        f"Тип: {realm_type_label(request.product.realm_type)}\n"
        f"Сервер: {request.product.server}\n"
        f"Сторона: {request.product.side}\n"
        f"Цена в заявке: {price}"
    )


def _format_sell_request(request: SellRequestDetails) -> str:
    full_name = _client_full_name(request.client_first_name, request.client_last_name)
    username = f"@{request.client_username}" if request.client_username else "без username"
    comment = request.comment or "без комментария"

    return (
        f"Заявка на продажу #{request.id}\n"
        f"{format_request_status(request.status)}\n"
        f"Дата: {request.created_at}\n"
        f"Клиент: {full_name}\n"
        f"Username: {username}\n"
        f"Telegram ID: {request.telegram_id}\n\n"
        f"Тип: {realm_type_label(request.realm_type)}\n"
        f"Сервер: {request.server}\n"
        f"Сторона: {request.side}\n"
        f"Количество: {request.amount}\n"
        f"Цена: {request.price}\n"
        f"Комментарий: {comment}"
    )


def _format_support_ticket(ticket: SupportTicket) -> str:
    full_name = _client_full_name(ticket.client_first_name, ticket.client_last_name)
    username = f"@{ticket.client_username}" if ticket.client_username else "без username"
    answer = ticket.answer or "ответа пока нет"

    return (
        f"Обращение #{ticket.id}\n"
        f"Статус: {support_status_label(ticket.status)}\n"
        f"Дата: {ticket.created_at}\n"
        f"Клиент: {full_name}\n"
        f"Username: {username}\n"
        f"Telegram ID: {ticket.telegram_id}\n\n"
        f"Вопрос:\n{ticket.question}\n\n"
        f"Ответ:\n{answer}"
    )


async def _notify_user(bot: Bot, telegram_id: int, text: str) -> None:
    try:
        await bot.send_message(telegram_id, text)
    except TelegramAPIError:
        return


def _client_full_name(first_name: str | None, last_name: str | None) -> str:
    return " ".join(part for part in (first_name, last_name) if part) or "Без имени"


def _clean_text(value: str | None) -> str:
    return value.strip() if value else ""


def _parse_int(value: str | None) -> int | None:
    if not value:
        return None

    try:
        return int(value.strip())
    except ValueError:
        return None


def _parse_callback_int(data: str | None, prefix: str) -> int | None:
    if not data:
        return None

    parts = data.split(":")
    if len(parts) != 3 or ":".join(parts[:2]) != prefix:
        return None

    try:
        return int(parts[2])
    except ValueError:
        return None


def _parse_page_filter_callback(data: str | None, prefix: str) -> tuple[int, str | None]:
    if not data:
        return 0, None

    parts = data.split(":")
    if len(parts) not in {3, 4} or ":".join(parts[:2]) != prefix:
        return 0, None

    try:
        page = int(parts[2])
    except ValueError:
        page = 0

    status = parts[3] if len(parts) == 4 else None
    if status is not None and not is_valid_request_status(status):
        status = None

    return page, status


def _parse_status_filter_callback(data: str | None, prefix: str) -> str | None:
    if not data:
        return None

    parts = data.split(":")
    if len(parts) != 3 or ":".join(parts[:2]) != prefix:
        return None

    status = parts[2]
    return status if is_valid_request_status(status) else None


def _pagination_row(
    prefix: str,
    *,
    page: int,
    page_count: int,
    status: str | None,
) -> list[InlineKeyboardButton]:
    previous_callback = _page_callback(prefix, page - 1, status) if page > 0 else "admin:noop"
    next_callback = _page_callback(prefix, page + 1, status) if page < page_count - 1 else "admin:noop"
    return [
        InlineKeyboardButton(text="⬅️ Back", callback_data=previous_callback),
        InlineKeyboardButton(text=f"{page + 1}/{page_count}", callback_data="admin:noop"),
        InlineKeyboardButton(text="Next ➡️", callback_data=next_callback),
    ]


def _request_filter_row(prefix: str, *, selected_status: str | None) -> list[InlineKeyboardButton]:
    all_text = "✓ Все" if selected_status is None else "Все"
    row = [InlineKeyboardButton(text=all_text, callback_data=prefix.rsplit("_filter", maxsplit=1)[0])]
    for status in REQUEST_STATUS_FILTERS:
        label = format_request_status(status, compact=True)
        if status == selected_status:
            label = f"✓ {label}"
        row.append(InlineKeyboardButton(text=label, callback_data=f"{prefix}:{status}"))

    return row


def _request_filter_text(status: str | None) -> str:
    if status is None:
        return "Фильтр: все"

    return f"Фильтр: {format_request_status(status, compact=True)}"


def _page_callback(prefix: str, page: int, status: str | None) -> str:
    if status is None:
        return f"{prefix}:{page}"

    return f"{prefix}:{page}:{status}"


def _page_count(total_count: int) -> int:
    if total_count <= 0:
        return 1

    return (total_count + ADMIN_REQUEST_PAGE_SIZE - 1) // ADMIN_REQUEST_PAGE_SIZE


def _clamp_page(page: int, page_count: int) -> int:
    if page < 0:
        return 0

    return min(page, page_count - 1)


def _parse_status_callback(data: str | None, prefix: str) -> tuple[int, str] | None:
    if not data:
        return None

    parts = data.split(":")
    if len(parts) != 4 or ":".join(parts[:2]) != prefix:
        return None

    try:
        request_id = int(parts[2])
    except ValueError:
        return None

    status = parts[3]
    if not is_valid_request_status(status):
        return None

    return request_id, status

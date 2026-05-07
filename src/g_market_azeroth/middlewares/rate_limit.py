from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject


Handler = Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]]
MAX_TRACKED_USERS = 1000
STALE_TTL_MULTIPLIER = 10.0


class UserCooldownMiddleware(BaseMiddleware):
    def __init__(
        self,
        *,
        cooldown_seconds: float,
        answer_callbacks: bool = False,
        skip_when_state_set: bool = False,
        max_tracked_users: int = MAX_TRACKED_USERS,
    ) -> None:
        self._cooldown_seconds = cooldown_seconds
        self._answer_callbacks = answer_callbacks
        self._skip_when_state_set = skip_when_state_set
        self._max_tracked_users = max_tracked_users
        self._last_seen_by_user: dict[int, float] = {}

    async def __call__(
        self,
        handler: Handler,
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id = _event_user_id(event)
        if user_id is None or self._cooldown_seconds <= 0:
            return await handler(event, data)

        if self._skip_when_state_set and await _current_state(data) is not None:
            return await handler(event, data)

        now = time.monotonic()
        _cleanup_stale_entries(
            self._last_seen_by_user,
            now=now,
            ttl_seconds=_ttl_seconds(self._cooldown_seconds),
            max_tracked_users=self._max_tracked_users,
        )
        last_seen_at = self._last_seen_by_user.get(user_id)
        if last_seen_at is not None and now - last_seen_at < self._cooldown_seconds:
            if self._answer_callbacks and isinstance(event, CallbackQuery):
                await event.answer(cache_time=1)
            return None

        self._last_seen_by_user[user_id] = now
        return await handler(event, data)


class SupportCooldownMiddleware(BaseMiddleware):
    def __init__(
        self,
        *,
        cooldown_seconds: float,
        state_suffixes: tuple[str, ...] = ("SupportFlow:waiting_for_question",),
        max_tracked_users: int = MAX_TRACKED_USERS,
    ) -> None:
        self._cooldown_seconds = cooldown_seconds
        self._state_suffixes = state_suffixes
        self._max_tracked_users = max_tracked_users
        self._last_seen_by_user: dict[int, float] = {}

    async def __call__(
        self,
        handler: Handler,
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id = _event_user_id(event)
        if user_id is None or self._cooldown_seconds <= 0:
            return await handler(event, data)

        current_state = await _current_state(data)
        if current_state is None or not current_state.endswith(self._state_suffixes):
            return await handler(event, data)

        now = time.monotonic()
        _cleanup_stale_entries(
            self._last_seen_by_user,
            now=now,
            ttl_seconds=_ttl_seconds(self._cooldown_seconds),
            max_tracked_users=self._max_tracked_users,
        )
        last_seen_at = self._last_seen_by_user.get(user_id)
        if last_seen_at is not None and now - last_seen_at < self._cooldown_seconds:
            return None

        self._last_seen_by_user[user_id] = now
        return await handler(event, data)


def _event_user_id(event: TelegramObject) -> int | None:
    if isinstance(event, Message) and event.from_user:
        return event.from_user.id
    if isinstance(event, CallbackQuery):
        return event.from_user.id
    return None


async def _current_state(data: dict[str, Any]) -> str | None:
    raw_state = data.get("raw_state")
    if isinstance(raw_state, str):
        return raw_state

    state = data.get("state")
    get_state = getattr(state, "get_state", None)
    if get_state is None:
        return None

    current_state = await get_state()
    return current_state if isinstance(current_state, str) else None


def _cleanup_stale_entries(
    storage: dict[int, float],
    *,
    now: float,
    ttl_seconds: float,
    max_tracked_users: int,
) -> None:
    if len(storage) <= max_tracked_users:
        return

    stale_before = now - ttl_seconds
    for user_id, last_seen_at in tuple(storage.items()):
        if last_seen_at < stale_before:
            storage.pop(user_id, None)


def _ttl_seconds(cooldown_seconds: float) -> float:
    return max(cooldown_seconds * STALE_TTL_MULTIPLIER, 60.0)

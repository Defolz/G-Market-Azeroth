from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from g_market_azeroth.catalog import realm_type_label
from g_market_azeroth.config import load_settings
from g_market_azeroth.database import Client, MarketRepository, Product, PurchaseRequestDetails


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        payload = asyncio.run(_run(args))
    except Exception as exc:
        _write_json({"ok": False, "error": str(exc)})
        raise SystemExit(1) from exc

    _write_json({"ok": True, "data": payload})


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    settings = load_settings()
    database = MarketRepository(Path(settings.database_path))
    await database.init()

    if args.command == "summary":
        return await _summary(database)

    if args.command == "add-product":
        product = await database.add_product(
            realm_type=args.realm_type,
            server=args.server.strip(),
            side=args.side.strip(),
            price=args.price.strip(),
        )
        return {"product": _product_to_dict(product)}

    if args.command == "update-price":
        product = await database.update_product_price(
            product_id=args.product_id,
            price=args.price.strip(),
        )
        if product is None:
            raise RuntimeError(f"Product #{args.product_id} was not found.")

        return {"product": _product_to_dict(product)}

    raise RuntimeError(f"Unknown command: {args.command}")


async def _summary(database: MarketRepository) -> dict[str, Any]:
    clients_count, products_count, requests_count = await asyncio.gather(
        database.count_clients(),
        database.count_products(),
        database.count_purchase_requests(),
    )
    products, requests, clients = await asyncio.gather(
        database.latest_products(limit=50),
        database.latest_purchase_requests(limit=50),
        database.latest_clients(limit=25),
    )

    return {
        "stats": {
            "clients": clients_count,
            "products": products_count,
            "requests": requests_count,
        },
        "products": [_product_to_dict(product) for product in products],
        "requests": [_request_to_dict(request) for request in requests],
        "clients": [_client_to_dict(client) for client in clients],
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local Electron admin API for G-Market Azeroth.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("summary")

    add_product = subparsers.add_parser("add-product")
    add_product.add_argument("--realm-type", choices=["off", "pirate"], required=True)
    add_product.add_argument("--server", required=True)
    add_product.add_argument("--side", required=True)
    add_product.add_argument("--price", required=True)

    update_price = subparsers.add_parser("update-price")
    update_price.add_argument("--product-id", type=int, required=True)
    update_price.add_argument("--price", required=True)

    return parser


def _product_to_dict(product: Product) -> dict[str, Any]:
    return {
        "id": product.id,
        "realmType": product.realm_type,
        "realmTypeLabel": realm_type_label(product.realm_type),
        "server": product.server,
        "side": product.side,
        "price": product.price,
        "isActive": product.is_active,
        "createdAt": product.created_at,
        "updatedAt": product.updated_at,
    }


def _request_to_dict(request: PurchaseRequestDetails) -> dict[str, Any]:
    full_name = " ".join(
        part for part in (request.client_first_name, request.client_last_name) if part
    )

    return {
        "id": request.id,
        "status": request.status,
        "createdAt": request.created_at,
        "telegramId": request.telegram_id,
        "priceSnapshot": request.price_snapshot,
        "client": {
            "username": request.client_username,
            "firstName": request.client_first_name,
            "lastName": request.client_last_name,
            "fullName": full_name or "Без имени",
        },
        "product": _product_to_dict(request.product),
    }


def _client_to_dict(client: Client) -> dict[str, Any]:
    full_name = " ".join(part for part in (client.first_name, client.last_name) if part)

    return {
        "telegramId": client.telegram_id,
        "username": client.username,
        "firstName": client.first_name,
        "lastName": client.last_name,
        "fullName": full_name or "Без имени",
        "languageCode": client.language_code,
        "isBot": client.is_bot,
        "startCount": client.start_count,
        "createdAt": client.created_at,
        "updatedAt": client.updated_at,
        "lastSeenAt": client.last_seen_at,
    }


def _write_json(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()

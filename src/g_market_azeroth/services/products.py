from __future__ import annotations

from g_market_azeroth.repositories.products import Product, ProductsRepository


class ProductService:
    def __init__(self, products: ProductsRepository) -> None:
        self._products = products

    def list_catalog_products(
        self,
        *,
        realm_type: str | None = None,
        server: str | None = None,
        side: str | None = None,
        limit: int | None = None,
    ) -> list[Product]:
        if limit is not None:
            return self._products.latest_products(_positive_limit(limit))

        if realm_type is None or server is None or side is None:
            raise ValueError("realm_type, server, and side are required without limit")

        return self._products.list_products(
            _required_text(realm_type, "realm_type"),
            _required_text(server, "server"),
            _required_text(side, "side"),
        )

    def get_catalog_product(self, product_id: int) -> Product | None:
        if product_id <= 0:
            return None

        return self._products.get_product(product_id)

    def list_admin_products(self, *, limit: int) -> list[Product]:
        return self._products.latest_products(_positive_limit(limit), include_inactive=True)

    def change_product_price(self, *, product_id: int, price: str) -> Product | None:
        if product_id <= 0:
            return None

        return self._products.update_price(
            product_id=product_id,
            price=_required_text(price, "price"),
        )

    def set_product_active(self, *, product_id: int, is_active: bool) -> Product | None:
        if product_id <= 0:
            return None

        return self._products.set_active(product_id=product_id, is_active=is_active)

    def create_catalog_product(
        self,
        *,
        realm_type: str,
        server: str,
        side: str,
        price: str,
    ) -> Product:
        return self._products.create_product(
            game_type=_required_text(realm_type, "realm_type"),
            server=_required_text(server, "server"),
            faction=_required_text(side, "side"),
            price=_required_text(price, "price"),
        )


def _required_text(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field_name} is required")

    return cleaned


def _positive_limit(limit: int) -> int:
    if limit <= 0:
        raise ValueError("limit must be positive")

    return limit

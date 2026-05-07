# FunPay Parser Tables

The FunPay parser layer is isolated from the Telegram bot database.

- `funpay_offers_raw` stores every parsed offer, including generic `Любой` / `Любая` rows.
- `funpay_market_min_price` stores only concrete `server` / `faction` market rows.
- `funpay_market_best_entry` stores only concrete `server` / `faction` market rows.
- Generic `Любой` / `Любая` offers are kept in raw history, but are not used for future bot auto-import.

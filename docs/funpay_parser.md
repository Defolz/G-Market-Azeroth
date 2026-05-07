# FunPay Parser Tables

The FunPay parser layer is isolated from the Telegram bot database.

- `funpay_offers_raw` stores every parsed offer, including generic `Любой` / `Любая` rows.
- `funpay_market_min_price` stores only concrete `server` / `faction` market rows.
- `funpay_market_best_entry` stores only concrete `server` / `faction` market rows.
- Generic `Любой` / `Любая` offers are kept in raw history, but are not used for future bot auto-import.

Use `python scripts/parse_funpay_prices.py --export-unique-servers` to export the current
`funpay_market_best_entry` server/faction combinations to
`exports/funpay_unique_servers.json`. The JSON includes empty `normalized_server`,
`normalized_faction`, and `product_id` fields for manual catalog mapping.

## Normalization Preview

Use `python scripts/parse_funpay_prices.py --export-normalization-preview` to export a
rules-based normalization preview to `exports/funpay_normalization_preview.json`.

The preview reads only `funpay_market_best_entry` and does not change any existing
tables or exports. Each row contains raw `source_type`, `server`, and `faction` values
plus `normalized_server` and `normalized_faction` candidates.

Current server normalization is intentionally conservative:

- lowercases values;
- trims leading and trailing spaces;
- removes domain-like tokens such as `Warmane.com` and `Stormforge.gg`;
- removes known leading provider tokens such as `Warmane` and `Stormforge`;
- removes `(цена за 1 золотой)`;
- collapses duplicate spaces.

Examples:

- `Warmane.com Onyxia` -> `onyxia`
- `Warmane Onyxia` -> `onyxia`
- `Stormforge.gg Frostmourne (цена за 1 золотой)` -> `frostmourne`

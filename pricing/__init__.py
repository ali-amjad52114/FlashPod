"""FlashPod pricing — Bright Data scraper + symbol→SKU mapping + cached catalog.

Offline tooling that turns detected electrical symbols into real, sourced prices:
    symbol_sku  -> what we price (symbol type -> product + search query)
    scraper     -> Bright Data SERP API -> multi-supplier Google Shopping offers
    catalog     -> offer selection + cached catalog.json + worker pricebook

The takeoff worker never imports this package (Flash ships only the function body); it carries
an EMBEDDED_PRICEBOOK generated from catalog.json by `python -m pricing.embed_pricebook`.
"""
from .catalog import Offer, build_pricebook, load_catalog, select_best_offer
from .symbol_sku import SKU_BY_TYPE, SKU_SPECS, SkuSpec

__all__ = [
    "Offer",
    "SkuSpec",
    "SKU_SPECS",
    "SKU_BY_TYPE",
    "select_best_offer",
    "build_pricebook",
    "load_catalog",
]

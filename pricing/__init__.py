"""FlashPod pricing — dynamic, description-driven material pricing via Bright Data SERP.

The vision LLM emits variable line items ({type, count, description}); this package turns each
into a Google Shopping query, returns every supplier offer, and totals the line. No fixed catalog.

    from pricing import price_line_items
    priced = price_line_items([{ "type": "DGPO Outlet", "count": 107,
                                 "description": "General double power outlet" }])
"""
from .pricing import PriceCache, build_query, price_line_items
from .scraper import Offer, parse_offers, scrape_query

__all__ = [
    "price_line_items",
    "build_query",
    "PriceCache",
    "Offer",
    "scrape_query",
    "parse_offers",
]

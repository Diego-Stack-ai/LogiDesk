"""Parser candidato per prospetti giro test; produce solo proposte locali."""
from __future__ import annotations

import re
from typing import Any


SEPARATOR = re.compile(r"^-{20,}\s*$", re.MULTILINE)
HEADER = re.compile(r"^\s*(\d+)\s*\|\s*\|\s*(\d+)\s+(.+?)\s*\|", re.MULTILINE)
DESTINATION = re.compile(r"^\s*([A-Z0-9]{1,3})\s+(\d{6})(?:\s+(\d+)\s+(.+?))?\s*\|\s*([\d.,]+)\|", re.MULTILINE)


def _clean(value: str | None) -> str | None:
    value = re.sub(r"\s+", " ", value or "").strip(" |")
    return value or None


def extract_route_sheet(pages: list[tuple[int, str]]) -> dict[str, Any]:
    joined = "\n".join(text for _, text in pages)
    route = re.search(r"^\s*(\d{5,})\s*\|.*?Assemblatore", joined, re.MULTILINE)
    departure = re.search(r"Data partenza\s+(\d{2}/\d{2}/\d{4})", joined)
    start = re.search(r"Ora\s+part\.\s+(\d{1,2}:\d{2})", joined)
    driver = re.search(r"Autista\s+([^|\n]+)", joined)
    stops = []
    for page_number, text in pages:
        for block in SEPARATOR.split(text):
            header = HEADER.search(block)
            destination = DESTINATION.search(block)
            if not header or not destination:
                continue
            address = re.search(r"^\s*\|\s{5,}([^|\n]+?)\s*\|", block[destination.end():], re.MULTILINE)
            after_address = block[destination.end() + (address.end() if address else 0):]
            city = re.search(r"^\s*\|\s{5,}(.+?)\s{2,}([A-Z]{2})\s*\|", after_address, re.MULTILINE)
            phone = re.search(r"Telefono\s*:\s*([^|\n]*)", block)
            windows = re.findall(r"(?:Apertura dalle|e dalle)\s+([^|\n]+?)\s+alle\s+([^|\n]+?)\s*(?:\||$)", block)
            flags_match = re.search(r"\|\s*([SFG](?:\s+[SFG])*)\s*\|", block[destination.start():])
            stops.append({
                "sequence": int(header.group(1)),
                "customer_code": header.group(2),
                "customer_name": _clean(header.group(3)),
                "service_type": destination.group(1),
                "document_or_service_code": destination.group(2),
                "delivery_point_code": destination.group(3) or None,
                "denomination": _clean(destination.group(4)) or _clean(header.group(3)),
                "delivery_point_code_requires_confirmation": not bool(destination.group(3)),
                "address": _clean(address.group(1) if address else None),
                "city": _clean(city.group(1) if city else None),
                "province": city.group(2) if city else None,
                "phone": _clean(phone.group(1) if phone else None),
                "delivery_windows": [{"from": _clean(a), "to": _clean(b)} for a, b in windows],
                "gross_weight": destination.group(5),
                "service_flags": (flags_match.group(1).split() if flags_match else []),
                "source_page": page_number,
                "review_status": "PENDING",
            })
    return {
        "document_type": "route_sheet" if route and stops else "unknown",
        "route_code": route.group(1) if route else None,
        "departure_date": departure.group(1) if departure else None,
        "start_time": start.group(1) if start else None,
        "driver_or_route_label": _clean(driver.group(1) if driver else None),
        "stops": stops,
        "writes_performed": 0,
    }

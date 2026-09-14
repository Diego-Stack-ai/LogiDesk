"""Estrattori deterministici e privi di accesso Firebase per l'ingestion."""

from __future__ import annotations

import re
from typing import Any


DDT_RE = re.compile(r"DDT\s*n[°º.]?\s*([A-Z0-9/-]+)\s+del\s+(\d{2}/\d{2}/\d{4})", re.I)
DESTINATION_RE = re.compile(r"(?:Luogo di destinazione|Codice destinazione)\s*:\s*([A-Z0-9_-]+)", re.I)
ZONE_RE = re.compile(r"^\s*([A-Z])\s*(\d{4})\b(.*)$", re.I)
POSTAL_CITY_RE = re.compile(r"\b(\d{5})\s+(.+?)\s*\(([A-Z]{2})\)\s*$", re.I)
ARTICLE_CODE_RE = re.compile(r"^[A-Z0-9]{2,}(?:-[A-Z0-9]{1,})+-?$", re.I)
OPERATIONAL_CODE_RE = re.compile(r"^Codice\s*:\s*([A-Z0-9./-]+)\s*$", re.I)
PHONE_RE = re.compile(r"^Tel\s*:\s*(.+)$", re.I)
CONTACT_RE = re.compile(r"^Referente\s*:\s*(.+)$", re.I)
DATE_DISTRIBUTION_RE = re.compile(r"Data\s+distribuzione\s*:\s*(\d{2}/\d{2}/\d{4})", re.I)
EXPIRY_RE = re.compile(r"Scad\.\s*min\.\s*(\d{2}/\d{2}/\d{4})", re.I)


def _nonempty_lines(text: str) -> list[str]:
    return [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]


def extract_ddt(text: str) -> dict[str, Any]:
    lines = _nonempty_lines(text)
    joined = "\n".join(lines)
    ddt_match = DDT_RE.search(joined)
    destination_match = DESTINATION_RE.search(joined)

    result: dict[str, Any] = {
        "numero_ddt": ddt_match.group(1).upper() if ddt_match else None,
        "data_ddt": ddt_match.group(2) if ddt_match else None,
        "codice_punto_committente": destination_match.group(1).lower() if destination_match else None,
        "denominazione_punto": None,
        "indirizzo": None,
        "cap": None,
        "localita": None,
        "provincia": None,
        "telefono": None,
        "referente": None,
        "codice_zona_originale": None,
        "codice_zona_logistica": None,
        "codice_agente": None,
        "orario_operativo_raw": None,
        "orario_operativo_proposto": None,
        "articoli": [],
    }

    destination_index = next(
        (index for index, line in enumerate(lines) if DESTINATION_RE.search(line)),
        None,
    )
    if destination_index is not None:
        following = lines[destination_index + 1 : destination_index + 6]
        if following:
            result["denominazione_punto"] = following[0]
        if len(following) > 1:
            result["indirizzo"] = following[1]
        for line in following[2:]:
            location_match = POSTAL_CITY_RE.search(line)
            if location_match:
                result["cap"] = location_match.group(1)
                result["localita"] = location_match.group(2).strip()
                result["provincia"] = location_match.group(3).upper()
                break
        for line in lines[destination_index + 1 : destination_index + 9]:
            phone_match = PHONE_RE.match(line)
            contact_match = CONTACT_RE.match(line)
            if phone_match:
                result["telefono"] = phone_match.group(1).strip()
            if contact_match:
                result["referente"] = contact_match.group(1).strip()

    cause_index = next(
        (index for index, line in enumerate(lines) if "CAUSALE DEL TRASPORTO" in line.upper()),
        None,
    )
    if cause_index is not None:
        for line in lines[cause_index + 1 : cause_index + 4]:
            zone_match = ZONE_RE.match(line)
            if zone_match:
                result["codice_zona_originale"] = f"{zone_match.group(1).upper()}{zone_match.group(2)}"
                result["codice_agente"] = zone_match.group(1).upper()
                result["codice_zona_logistica"] = zone_match.group(2)
                numeric_tokens = re.findall(r"\b(\d{3,4})\b", zone_match.group(3))
                if numeric_tokens:
                    raw_time = numeric_tokens[-1]
                    hours, minutes = (raw_time[:-2], raw_time[-2:])
                    if int(hours) < 24 and int(minutes) < 60:
                        result["orario_operativo_raw"] = raw_time
                        result["orario_operativo_proposto"] = f"{int(hours):02d}:{minutes}"
                break

    result["articoli"] = extract_articles(lines)
    return result


def extract_articles(lines: list[str]) -> list[dict[str, Any]]:
    articles: list[dict[str, Any]] = []
    index = 0
    while index < len(lines):
        raw_code = lines[index].upper()
        if not ARTICLE_CODE_RE.fullmatch(raw_code):
            index += 1
            continue
        base_code = raw_code
        cursor = index + 1
        if base_code.endswith("-") and cursor < len(lines):
            continuation = lines[cursor].upper()
            if re.fullmatch(r"[A-Z0-9]{1,8}", continuation):
                base_code += continuation
                cursor += 1
        operational_code = None
        if cursor < len(lines):
            operational_match = OPERATIONAL_CODE_RE.fullmatch(lines[cursor])
            if operational_match:
                operational_code = operational_match.group(1).upper()
                cursor += 1
                if operational_code.endswith("-") and cursor < len(lines) and re.fullmatch(r"[A-Z0-9]{2,12}", lines[cursor], re.I):
                    operational_code += lines[cursor].upper()
                    cursor += 1
        # Evita di classificare come articolo intestazioni o codici senza un
        # contesto successivo; conserva comunque articoli speciali come 10-GEL.
        block_end = cursor
        while block_end < len(lines) and block_end < cursor + 12:
            if block_end > cursor and ARTICLE_CODE_RE.fullmatch(lines[block_end].upper()):
                break
            if lines[block_end].startswith("___"):
                break
            block_end += 1
        block = " ".join(lines[cursor:block_end])
        description = lines[cursor] if cursor < len(lines) else None
        distribution_match = DATE_DISTRIBUTION_RE.search(block)
        expiry_match = EXPIRY_RE.search(block)
        articles.append(
            {
                "codice_articolo_committente": base_code,
                "codice_articolo_operativo": operational_code,
                "descrizione_riga_iniziale": description,
                "data_distribuzione": distribution_match.group(1) if distribution_match else None,
                "scadenza_minima": expiry_match.group(1) if expiry_match else None,
            }
        )
        index = max(cursor, index + 1)
    return articles

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

import httpx

from app.config import VIN_DECODE_LIVE

# ISO 3779: позиции 1–3 WMI, 4–8 описание модели/мотора, 10 год, 11 завод.
_YEAR_LETTERS = "ABCDEFGHJKLMNPRSTVWXY"  # без I, O, Q, U, Z

WMI_MAKE: dict[str, str] = {
    "1G1": "Chevrolet", "1G6": "Cadillac", "1GC": "Chevrolet", "1FA": "Ford", "1FM": "Ford",
    "1FT": "Ford", "1HG": "Honda", "1J4": "Jeep", "1N4": "Nissan", "1VW": "Volkswagen",
    "2HG": "Honda", "2T1": "Toyota", "3N1": "Nissan", "3VW": "Volkswagen",
    "4T1": "Toyota", "5YJ": "Tesla", "5NP": "Hyundai",
    "JHM": "Honda", "JTD": "Toyota", "JT2": "Toyota", "JT3": "Toyota", "JT4": "Toyota",
    "JT6": "Toyota", "JT8": "Toyota", "JTE": "Toyota", "JTH": "Lexus", "JTJ": "Lexus",
    "JTN": "Toyota", "JF1": "Subaru", "JF2": "Subaru", "JM1": "Mazda", "JM3": "Mazda",
    "JM6": "Mazda", "JM7": "Mazda", "JN1": "Nissan", "JN8": "Nissan", "JNK": "Infiniti",
    "JA3": "Mitsubishi", "JA4": "Mitsubishi", "JS1": "Suzuki", "JS2": "Suzuki", "JS3": "Suzuki",
    "JSA": "Suzuki", "JDA": "Daihatsu", "KMH": "Hyundai", "KNA": "Kia", "KND": "Kia",
    "KNM": "Kia", "KPT": "SsangYong", "KL1": "Chevrolet", "KL8": "Chevrolet",
    "WBA": "BMW", "WBS": "BMW", "WBY": "BMW", "WDB": "Mercedes", "WDD": "Mercedes",
    "WDF": "Mercedes", "WDC": "Mercedes", "WAU": "Audi", "WA1": "Audi", "WVW": "Volkswagen",
    "WV1": "Volkswagen", "WV2": "Volkswagen", "WVG": "Volkswagen", "W0L": "Opel",
    "WF0": "Ford", "VF1": "Renault", "VF3": "Peugeot", "VF7": "Citroen", "VSS": "SEAT",
    "TMB": "Skoda", "TRU": "Audi", "SAJ": "Jaguar", "SAL": "Land Rover", "SAR": "Rover",
    "ZFA": "Fiat", "ZAR": "Alfa Romeo", "ZFF": "Ferrari", "ZAM": "Maserati",
    "YV1": "Volvo", "YS3": "Saab", "UU1": "Dacia", "U5Y": "Kia", "TMA": "Hyundai",
    "XTA": "Lada", "XTB": "Lada", "XTC": "Lada", "X7L": "Renault", "X7D": "Renault",
    "X7M": "Renault", "X96": "GAZ", "X89": "UAZ", "XTT": "UAZ", "XUS": "UAZ",
    "XWB": "Uz-Daewoo", "XWF": "Volkswagen", "XW8": "Volkswagen", "X9F": "Ford",
    "XMC": "Mazda", "X4X": "BMW", "Z94": "Hyundai", "Z8T": "Kia", "Z8N": "Nissan",
    "Z9M": "Mercedes", "Y6D": "ZAZ", "Y6L": "ZAZ", "XU5": "Hyundai", "XU3": "Hyundai",
    "XUF": "Chevrolet", "XL9": "Kia", "X89": "UAZ",
}


def spec_key_from_vin(vin: str | None) -> str:
    compact = _compact_vin(vin)
    if len(compact) < 11:
        return compact
    return compact[:8] + compact[9]


def decode_vin(vin: str, *, live: bool | None = None) -> dict[str, str]:
    """Разобрать VIN: префикс комплектации, год, марка; при сети — модель и мотор (NHTSA)."""
    data = decode_vin_local(vin)
    use_live = VIN_DECODE_LIVE if live is None else live
    if use_live and data.get("vin") and not data.get("model"):
        extra = _nhtsa_decode(data["vin"])
        if extra:
            data = _merge(data, extra)
    return data


def decode_vin_local(vin: str | None) -> dict[str, str]:
    compact = _compact_vin(vin)
    if len(compact) != 17:
        return {}
    wmi = compact[:3]
    year = _model_year(compact[9])
    make = _make_from_wmi(wmi)
    prefix = compact[:8] + compact[9]
    return {
        "vin": compact,
        "wmi": wmi,
        "vin_prefix": prefix,
        "spec_key": prefix,
        "year": str(year) if year else "",
        "make": make,
        "plant": compact[10],
        "model": "",
        "engine": "",
        "engine_code": "",
        "displacement": "",
        "body": "",
        "drive": "",
        "fuel": "",
        "series": "",
    }


def _compact_vin(vin: str | None) -> str:
    return "".join(ch.upper() for ch in (vin or "") if ch.isalnum())


def _make_from_wmi(wmi: str) -> str:
    if wmi in WMI_MAKE:
        return WMI_MAKE[wmi]
    for size in (3, 2):
        if wmi[:size] in WMI_MAKE:
            return WMI_MAKE[wmi[:size]]
    return ""


def _model_year(code: str, now: int | None = None) -> Optional[int]:
    code = (code or "").upper()
    now = now or datetime.now().year
    idx = _YEAR_LETTERS.find(code)
    if idx >= 0:
        early, late = 1980 + idx, 2010 + idx
    elif code.isdigit() and code != "0":
        n = int(code)
        early, late = 2000 + n, 2030 + n
    else:
        return None
    lo, hi = now - 30, now + 1
    if lo <= late <= hi:
        return late
    if lo <= early <= hi:
        return early
    return late if abs(late - now) <= abs(early - now) else early


def _clean(value: Any) -> str:
    text = str(value or "").strip()
    if not text or text.lower() in {"not applicable", "null", "none", "0", "-", "n/a"}:
        return ""
    return text


def _nhtsa_decode(vin: str) -> dict[str, str]:
    url = f"https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/{vin}?format=json"
    try:
        with httpx.Client(timeout=6.0, follow_redirects=True) as http:
            response = http.get(url)
            response.raise_for_status()
            rows = (response.json() or {}).get("Results") or []
    except Exception:
        return {}
    if not rows:
        return {}
    row = rows[0]
    displacement = _clean(row.get("DisplacementL"))
    cylinders = _clean(row.get("EngineCylinders"))
    engine_code = _clean(row.get("EngineModel"))
    engine_bits = [p for p in [engine_code, f"{displacement} л" if displacement else "", f"{cylinders} цил." if cylinders else ""] if p]
    make = _clean(row.get("Make"))
    if make:
        try:
            from app.garage import extract_make

            make = extract_make(make) or make.title()
        except Exception:
            make = make.title()
    year = _clean(row.get("ModelYear"))
    return {
        "make": make,
        "model": _clean(row.get("Model")),
        "year": year,
        "engine": " ".join(engine_bits),
        "engine_code": engine_code,
        "displacement": displacement,
        "body": _clean(row.get("BodyClass")),
        "drive": _clean(row.get("DriveType")),
        "fuel": _clean(row.get("FuelTypePrimary")),
        "series": " ".join(p for p in [_clean(row.get("Series")), _clean(row.get("Trim"))] if p),
        "plant": " ".join(p for p in [_clean(row.get("PlantCity")), _clean(row.get("PlantCountry"))] if p),
    }


def _merge(base: dict[str, str], extra: dict[str, str]) -> dict[str, str]:
    out = dict(base)
    for key, value in extra.items():
        if value and not out.get(key):
            out[key] = value
        elif value and key in {"make", "model", "year", "engine", "engine_code", "displacement", "body", "drive", "fuel", "series", "plant"}:
            if not out.get(key):
                out[key] = value
    return out

"""Каталог из Doc1.docx (BMW, Mercedes, Audi, Volkswagen)."""

from __future__ import annotations

from typing import Iterable


def _expand(
    make: str,
    model: str,
    year: str,
    bodies: Iterable[str],
    engines: Iterable[str],
) -> list[tuple[str, str, str, str, str]]:
    out: list[tuple[str, str, str, str, str]] = []
    for body in bodies:
        for engine in engines:
            out.append((make, model, year, engine, body))
    return out


DOC1_GROUPS: list[dict] = [
    # BMW 3 Series
    {"make": "BMW", "model": "3 Series E90", "year": "2005-2013", "bodies": ["седан", "универсал", "купе", "кабриолет"], "engines": ["N43", "N45", "N46", "N52", "N53", "N54", "N55", "M47", "M57", "N47"]},
    {"make": "BMW", "model": "3 Series F30", "year": "2011-2020", "bodies": ["седан", "универсал", "лифтбек GT"], "engines": ["N20", "N55", "B48", "N47", "B47"]},
    {"make": "BMW", "model": "3 Series G20", "year": "2018-2024", "bodies": ["седан", "универсал"], "engines": ["B48", "B58", "B47", "B57"]},
    # BMW 5 Series
    {"make": "BMW", "model": "5 Series E60", "year": "2003-2010", "bodies": ["седан", "универсал"], "engines": ["M54", "N52", "N53", "N62", "M57", "N57", "S85"]},
    {"make": "BMW", "model": "5 Series F10", "year": "2010-2017", "bodies": ["седан", "универсал"], "engines": ["N55", "N63", "N57", "B57"]},
    {"make": "BMW", "model": "5 Series G30", "year": "2017-2024", "bodies": ["седан", "универсал"], "engines": ["B48", "B58", "B57"]},
    # BMW 7 Series
    {"make": "BMW", "model": "7 Series E65", "year": "2001-2008", "bodies": ["седан", "длиннобазный"], "engines": ["M54", "N62", "M67", "M57"]},
    {"make": "BMW", "model": "7 Series F01", "year": "2008-2015", "bodies": ["седан", "длиннобазный"], "engines": ["N62", "N63", "S63", "N57", "M57"]},
    {"make": "BMW", "model": "7 Series G11", "year": "2015-2024", "bodies": ["седан", "длиннобазный"], "engines": ["B58", "N63", "S63", "B57"]},
    # BMW X3
    {"make": "BMW", "model": "X3 E83", "year": "2003-2010", "bodies": ["кроссовер"], "engines": ["M54", "N52", "M47", "N47"]},
    {"make": "BMW", "model": "X3 F25", "year": "2011-2017", "bodies": ["кроссовер"], "engines": ["N20", "N55", "N47"]},
    {"make": "BMW", "model": "X3 G01", "year": "2017-2024", "bodies": ["кроссовер"], "engines": ["B48", "B58", "B47", "B57"]},
    # BMW X5
    {"make": "BMW", "model": "X5 E53", "year": "1999-2006", "bodies": ["кроссовер"], "engines": ["M54", "M62", "M57"]},
    {"make": "BMW", "model": "X5 E70", "year": "2006-2013", "bodies": ["кроссовер"], "engines": ["N52", "N62", "N63", "M57", "N57"]},
    {"make": "BMW", "model": "X5 F15", "year": "2013-2018", "bodies": ["кроссовер"], "engines": ["N55", "N63", "N57"]},
    {"make": "BMW", "model": "X5 G05", "year": "2018-2024", "bodies": ["кроссовер"], "engines": ["B58", "S63", "B57"]},
    # BMW X6
    {"make": "BMW", "model": "X6 E71", "year": "2008-2014", "bodies": ["кроссовер"], "engines": ["N54", "N63", "M57", "N57"]},
    {"make": "BMW", "model": "X6 F16", "year": "2014-2019", "bodies": ["кроссовер"], "engines": ["N55", "N63", "N57"]},
    {"make": "BMW", "model": "X6 G06", "year": "2019-2024", "bodies": ["кроссовер"], "engines": ["B58", "S63", "B57"]},
    # BMW 1 Series
    {"make": "BMW", "model": "1 Series E87", "year": "2004-2013", "bodies": ["хэтчбек", "купе", "кабриолет"], "engines": ["N43", "N45", "N46", "N52", "M47", "N47"]},
    {"make": "BMW", "model": "1 Series F20", "year": "2011-2019", "bodies": ["хэтчбек"], "engines": ["N13", "N20", "N47"]},
    {"make": "BMW", "model": "1 Series F40", "year": "2019-2024", "bodies": ["хэтчбек"], "engines": ["B38", "B48", "B47"]},
    # BMW 2 Series
    {"make": "BMW", "model": "2 Series F22", "year": "2013-2021", "bodies": ["купе", "кабриолет"], "engines": ["N13", "N20", "B48", "N47", "B47"]},
    {"make": "BMW", "model": "2 Series F45", "year": "2014-2021", "bodies": ["минивэн"], "engines": ["B38", "B47"]},
    # BMW 4 Series / M
    {"make": "BMW", "model": "4 Series G22", "year": "2020-2024", "bodies": ["купе", "кабриолет", "лифтбек"], "engines": ["B48", "B58", "B47", "B57"]},
    {"make": "BMW", "model": "M3 E90", "year": "2007-2013", "bodies": ["седан", "купе", "кабриолет"], "engines": ["S65"]},
    {"make": "BMW", "model": "M3 F80", "year": "2014-2020", "bodies": ["седан"], "engines": ["S55"]},
    {"make": "BMW", "model": "M3 G80", "year": "2020-2024", "bodies": ["седан"], "engines": ["S58"]},
    {"make": "BMW", "model": "M5 E60", "year": "2005-2010", "bodies": ["седан"], "engines": ["S85"]},
    {"make": "BMW", "model": "M5 F90", "year": "2017-2023", "bodies": ["седан"], "engines": ["S63"]},
    {"make": "BMW", "model": "M5 G90", "year": "2024-2024", "bodies": ["седан"], "engines": ["S68"]},
    # Mercedes
    {"make": "Mercedes", "model": "C-Class W203", "year": "2000-2007", "bodies": ["седан", "универсал", "хэтчбек"], "engines": ["M111", "M271", "OM611"]},
    {"make": "Mercedes", "model": "C-Class W204", "year": "2007-2015", "bodies": ["седан", "универсал", "купе"], "engines": ["M271", "M274", "OM642", "OM651"]},
    {"make": "Mercedes", "model": "C-Class W205", "year": "2013-2018", "bodies": ["седан", "универсал", "купе", "кабриолет"], "engines": ["M274", "M254", "OM651"]},
    {"make": "Mercedes", "model": "C-Class W206", "year": "2021-2024", "bodies": ["седан", "универсал"], "engines": ["M254", "OM654"]},
    {"make": "Mercedes", "model": "E-Class W211", "year": "2002-2009", "bodies": ["седан", "универсал"], "engines": ["M113", "M271", "OM642", "OM651"]},
    {"make": "Mercedes", "model": "E-Class W212", "year": "2009-2016", "bodies": ["седан", "универсал", "купе"], "engines": ["M271", "M276", "OM642", "OM651"]},
    {"make": "Mercedes", "model": "E-Class W213", "year": "2016-2023", "bodies": ["седан", "универсал", "кабриолет"], "engines": ["M276", "M256", "OM642", "OM651"]},
    {"make": "Mercedes", "model": "E-Class W214", "year": "2023-2024", "bodies": ["седан", "универсал"], "engines": ["M256", "OM654"]},
    {"make": "Mercedes", "model": "S-Class W220", "year": "1998-2005", "bodies": ["седан"], "engines": ["M113", "M137", "OM628"]},
    {"make": "Mercedes", "model": "S-Class W221", "year": "2005-2014", "bodies": ["седан", "купе"], "engines": ["M273", "M276", "OM642"]},
    {"make": "Mercedes", "model": "S-Class W222", "year": "2013-2020", "bodies": ["седан", "купе", "кабриолет"], "engines": ["M276", "M176", "OM642"]},
    {"make": "Mercedes", "model": "S-Class W223", "year": "2020-2024", "bodies": ["седан"], "engines": ["M256", "M176", "OM656"]},
    # Audi
    {"make": "Audi", "model": "A3 8P", "year": "2003-2012", "bodies": ["хэтчбек", "седан", "кабриолет"], "engines": ["1.6", "1.8 TFSI", "2.0 TFSI", "1.9 TDI", "2.0 TDI"]},
    {"make": "Audi", "model": "A3 8V", "year": "2012-2020", "bodies": ["хэтчбек", "седан", "кабриолет"], "engines": ["1.4 TFSI", "2.0 TFSI", "1.6 TDI", "2.0 TDI"]},
    {"make": "Audi", "model": "A4 B8", "year": "2007-2015", "bodies": ["седан", "универсал", "кабриолет"], "engines": ["1.8 TFSI", "2.0 TFSI", "3.2 FSI", "1.9 TDI", "2.0 TDI", "3.0 TDI"]},
    {"make": "Audi", "model": "A4 B9", "year": "2015-2020", "bodies": ["седан", "универсал"], "engines": ["1.4 TFSI", "2.0 TFSI", "2.0 TDI", "3.0 TDI"]},
    {"make": "Audi", "model": "A5 8T", "year": "2007-2016", "bodies": ["купе", "кабриолет", "лифтбек"], "engines": ["1.8 TFSI", "2.0 TFSI", "3.2 FSI", "2.0 TDI", "3.0 TDI"]},
    {"make": "Audi", "model": "A5 F5", "year": "2017-2024", "bodies": ["купе", "кабриолет", "лифтбек"], "engines": ["2.0 TFSI", "2.0 TDI", "3.0 TDI"]},
    {"make": "Audi", "model": "A6 C7", "year": "2011-2018", "bodies": ["седан", "универсал"], "engines": ["2.0 TFSI", "3.0 TFSI", "2.0 TDI", "3.0 TDI"]},
    {"make": "Audi", "model": "A6 C8", "year": "2018-2024", "bodies": ["седан", "универсал"], "engines": ["2.0 TFSI", "3.0 TFSI", "2.0 TDI", "3.0 TDI"]},
    {"make": "Audi", "model": "A8 D4", "year": "2009-2017", "bodies": ["седан"], "engines": ["3.0 TFSI", "4.2 FSI", "3.0 TDI", "4.2 TDI"]},
    {"make": "Audi", "model": "A8 D5", "year": "2017-2024", "bodies": ["седан"], "engines": ["3.0 TFSI", "4.0 TFSI", "3.0 TDI"]},
    # Volkswagen
    {"make": "Volkswagen", "model": "Golf VII", "year": "2012-2020", "bodies": ["хэтчбек", "универсал", "кабриолет"], "engines": ["1.4 TSI", "1.8 TSI", "2.0 TSI", "1.6 TDI", "2.0 TDI"]},
    {"make": "Volkswagen", "model": "Golf VIII", "year": "2019-2024", "bodies": ["хэтчбек"], "engines": ["1.5 TSI", "2.0 TSI", "2.0 TDI"]},
    {"make": "Volkswagen", "model": "Passat B7", "year": "2011-2015", "bodies": ["седан", "универсал"], "engines": ["1.8 TSI", "2.0 TSI", "1.6 TDI", "2.0 TDI"]},
    {"make": "Volkswagen", "model": "Passat B8", "year": "2014-2020", "bodies": ["седан", "универсал"], "engines": ["1.4 TSI", "2.0 TSI", "2.0 TDI"]},
    {"make": "Volkswagen", "model": "Polo V", "year": "2009-2020", "bodies": ["хэтчбек", "седан"], "engines": ["1.6", "1.4 TSI", "1.6 TDI"]},
    {"make": "Volkswagen", "model": "Tiguan I", "year": "2007-2016", "bodies": ["кроссовер"], "engines": ["1.4 TSI", "2.0 TSI", "2.0 TDI"]},
    {"make": "Volkswagen", "model": "Tiguan II", "year": "2016-2024", "bodies": ["кроссовер"], "engines": ["1.4 TSI", "2.0 TSI", "2.0 TDI"]},
    {"make": "Volkswagen", "model": "Touareg II", "year": "2010-2018", "bodies": ["кроссовер"], "engines": ["3.6 VR6", "4.2 V8", "3.0 TDI"]},
    {"make": "Volkswagen", "model": "Touareg III", "year": "2018-2024", "bodies": ["кроссовер"], "engines": ["3.0 TSI", "3.0 TDI"]},
    {"make": "Volkswagen", "model": "Multivan T6", "year": "2015-2024", "bodies": ["минивэн"], "engines": ["2.0 TSI", "2.0 TDI"]},
    {"make": "Volkswagen", "model": "ID.3", "year": "2020-2024", "bodies": ["хэтчбек"], "engines": ["электро"]},
]


def doc1_trims() -> list[tuple[str, str, str, str, str]]:
    rows: list[tuple[str, str, str, str, str]] = []
    for group in DOC1_GROUPS:
        rows.extend(
            _expand(
                group["make"],
                group["model"],
                group["year"],
                group["bodies"],
                group["engines"],
            )
        )
    return rows

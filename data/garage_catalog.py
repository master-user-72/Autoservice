"""Vehicle references transcribed from the garage tables.

Model-wide codes are kept separate from generation-specific information when
the source does not associate them with a generation.
"""

# Make, model, generation and production years. A trailing hyphen is open-ended.
GENERATIONS = {
    "Audi": {
        "A3": {"8L": "2000-2003", "8P": "2003-2012", "8V": "2012-2020"},
        "A4": {"B6": "2000-2005", "B7": "2004-2008", "B8": "2007-2015", "B9": "2015-2020"},
        "A5": {"8T": "2007-2016", "F5": "2017-2024"},
        "A6": {"C5": "1997-2005", "C6": "2004-2011", "C7": "2011-2018", "C8": "2018-"},
        "A8": {"D2": "1994-2002", "D3": "2002-2009", "D4": "2009-2017", "D5": "2017-"},
    },
    "Volkswagen": {
        "Golf": {"IV": "1997-2004", "V": "2003-2012", "VI": "2008-2017", "VII": "2012-2020", "VIII": "2019-"},
        "Passat": {"B5": "1996-2001", "B6": "2005-2010", "B7": "2011-2015", "B8": "2014-2020", "B9": "2024-"},
        "Polo": {"IV": "2002-2009", "V": "2009-"},
        "Tiguan": {"I": "2007-2016", "II": "2016-"},
        "Touareg": {"I": "2002-2010", "II": "2010-2018", "III": "2018-"},
        "Multivan": {"T5": "2003-2015", "T6": "2015-"},
        "ID.3": {"I": "2020-"},
    },
}

# The images list these options by model, without a generation or a model year.
MODEL_OPTIONS = {
    "BMW": {
        "i3": ((), ("электрический",)),
        "i5": ((), ("электрический",)),
        "i7": ((), ("электрический",)),
        "iX": ((), ("электрический",)),
        "iX3": ((), ("электрический",)),
    },
    "Audi": {
        "A3": (("хэтчбек (5 дв.)", "седан", "кабриолет"), "AGN AXX BUB CZPB CZEA DBKA CLHA".split()),
        "A4": (("седан", "универсал", "кабриолет"), ("1.8 TFSI", "2.0 TFSI", "3.2 FSI", "1.9 TDI", "2.0 TDI", "3.0 TDI")),
        "A5": (("купе", "кабриолет", "лифтбек (Sportback)"), ("1.8 TFSI", "2.0 TFSI", "3.2 FSI", "2.0 TDI", "3.0 TDI")),
        "A6": (("седан", "универсал (Avant)"), ("2.0 TFSI", "3.0 TFSI", "4.2 FSI", "2.5 TDI", "3.0 TDI", "4.2 TDI")),
        "A8": (("седан",), ("2.8 FSI", "4.2 FSI", "6.3 W12", "4.2 TDI", "3.0 TDI")),
    },
    "Volkswagen": {
        "Golf": (("хэтчбек (3/5 дв.)", "универсал", "кабриолет"), ("AWT 1.8 Turbo", "EA113", "EA888", "TDI", "гибридный", "электрический")),
        "Passat": (("седан", "универсал", "хэтчбек"), ("AXX", "BWA", "BPY", "CDG", "BSE", "BSF", "TDI", "гибридный", "СУГ")),
        "Polo": (("хэтчбек (3/5 дв.)", "седан"), ("CFNB", "CFNA", "CLSA", "TDI")),
        "Tiguan": (("кроссовер",), ("TSI", "TDI")),
        "Touareg": (("кроссовер",), ("W12", "VR6", "TDI")),
        "Multivan": (("минивэн",), ("EA113", "EA888", "TDI")),
        "ID.3": (("хэтчбек",), ("электрический",)),
    },
    "Mercedes": {
        "C-Class": ((), "M111 M271 M274 M254 OM611 OM642 OM651".split() + ["C300 e", "C350 e"]),
        "E-Class": (("лимузин",), "M113 M271 M276 M256 OM642 OM651".split() + ["E300 e", "E400 e", "E200 NGT"]),
        "S-Class": ((), "M113 M273 M276 M176 OM628 OM642".split() + ["S500 e", "S560 e"]),
    },
}

# Within these groups, body codes are explicit and engine options are listed for the group.
BMW_GROUPS = [
    ("3 Series", "2005-2013", {"E90": "седан", "E91": "универсал", "E92": "купе", "E93": "кабриолет"},
     "N43 N45 N46 N52 N53 N54 N55 M47 M57 N47"),
    ("3 Series", "2011-2020", {"F30": "седан", "F31": "универсал", "F34": "лифтбек GT"},
     "N20 N55 B48 N47 B47 330e"),
    ("3 Series", "2018-", {"G20": "седан", "G21": "универсал"}, "B48 B58 B47 B57 гибридный"),
    ("5 Series", "2003-2010", {"E60": "седан", "E61": "универсал"}, "M54 N52 N53 N62 M57 N57 S85"),
    ("5 Series", "2010-2017", {"F10": "седан", "F11": "универсал"}, "N55 N63 N57 B57 гибридный"),
    ("5 Series", "2017-", {"G30": "седан", "G31": "универсал"}, "B48 B58 B57 гибридный"),
    ("7 Series", "2001-2008", {"E65": "седан", "E66": "длиннобазный"}, "M54 N62 M67 M57"),
    ("7 Series", "2008-2015", {"F01": "седан", "F02": "длиннобазный"}, "N62 N63 S63 N57 M57"),
    ("7 Series", "2015-", {"G11": "седан", "G12": "длиннобазный"}, "B58 N63 S63 B57 гибридный"),
    ("X3", "2003-2010", {"E83": "кроссовер"}, "M54 N52 M47 N47"),
    ("X3", "2011-2017", {"F25": "кроссовер"}, "N20 N55 N47"),
    ("X3", "2017-", {"G01": "кроссовер"}, "B48 B58 B47 B57"),
    ("X5", "1999-2006", {"E53": "кроссовер"}, "M54 M62 M57"),
    ("X5", "2006-2013", {"E70": "кроссовер"}, "N52 N62 N63 M57 N57 гибридный"),
    ("X5", "2013-2018", {"F15": "кроссовер"}, "N55 N63 N57 гибридный"),
    ("X5", "2018-", {"G05": "кроссовер"}, "B58 S63 B57"),
    ("X6", "2008-2014", {"E71": "SAC"}, "N54 N63 M57 N57"),
    ("X6", "2014-2019", {"F16": "SAC"}, "N55 N63 N57 гибридный"),
    ("X6", "2019-", {"G06": "SAC"}, "B58 S63 B57"),
    ("1 Series", "2004-2013", {"E81": "хэтчбек (3 дв.)", "E87": "хэтчбек (5 дв.)", "E82": "купе", "E88": "кабриолет"},
     "N43 N45 N46 N52 M47 N47"),
    ("1 Series", "2011-2019", {"F20": "хэтчбек", "F21": "хэтчбек"}, "N13 N20 N47"),
    ("1 Series", "2019-", {"F40": "хэтчбек"}, "B38 B48 B47"),
    ("2 Series", "2013-2021", {"F22": "купе", "F23": "кабриолет"}, "N13 N20 B48 N47 B47"),
    ("2 Series", "2014-2021", {"F45": "Active Tourer", "F46": "Gran Tourer"}, "B38 B47"),
    ("4 Series", "2020-", {"G22": "купе", "G23": "кабриолет", "G26": "Gran Coupe"}, "B48 B58 B47 B57 гибридный"),
    ("M3", "2007-2013", {"E90": "седан", "E92": "купе", "E93": "кабриолет"}, "S65"),
    ("M3", "2014-2020", {"F80": "седан"}, "S55"),
    ("M3", "2020-", {"G80": "седан"}, "S58"),
    ("M5", "2005-2010", {"E60": "седан"}, "S85"),
    ("M5", "2017-2023", {"F90": "седан"}, "S63"),
    ("M5", "2024-", {"G90": "седан"}, "S68"),
]

MERCEDES_GROUPS = [
    ("C-Class", "W202", "", ("седан", "универсал")),
    ("C-Class", "W203", "2000-2004", ("седан", "универсал", "хэтчбек")),
    ("C-Class", "W204", "2007-2015", ("седан", "универсал", "купе")),
    ("C-Class", "W205", "2013-2018", ("седан", "универсал", "купе", "кабриолет")),
    ("C-Class", "W206", "2021-", ("седан",)),
    ("E-Class", "W124", "", ("седан", "универсал")),
    ("E-Class", "W210", "", ("седан", "универсал")),
    ("E-Class", "W211", "2002-2009", ("седан", "универсал")),
    ("E-Class", "W212", "2009-2016", ("седан", "универсал")),
    ("E-Class", "W213", "2016-2023", ("седан", "универсал")),
    ("E-Class", "W214", "2023-", ("седан",)),
    ("E-Class", "C207", "", ("купе-хардтоп",)),
    ("E-Class", "C212", "", ("купе-хардтоп",)),
    ("E-Class", "A207", "", ("кабриолет",)),
    ("E-Class", "A238", "", ("кабриолет",)),
    ("S-Class", "W116", "", ("седан",)),
    ("S-Class", "W126", "", ("седан",)),
    ("S-Class", "W140", "", ("седан",)),
    ("S-Class", "W220", "1998-2005", ("седан",)),
    ("S-Class", "W221", "2005-2014", ("седан",)),
    ("S-Class", "W222", "2013-2020", ("седан",)),
    ("S-Class", "W223", "2020-", ("седан",)),
    ("S-Class", "C215", "", ("кабриолет",)),
    ("S-Class", "C217", "", ("кабриолет",)),
    ("S-Class", "C126", "", ("купе",)),
    ("S-Class", "C140", "", ("купе",)),
    ("S-Class", "C216", "", ("купе",)),
]


def generation_trims():
    for make, models in GENERATIONS.items():
        for model, generations in models.items():
            for generation, years in generations.items():
                yield make, model, generation, years, "", ""
    for model, years, bodies, engines in BMW_GROUPS:
        for generation, body in bodies.items():
            yield "BMW", model, generation, years, "", body
            for engine in engines.split():
                yield "BMW", model, generation, years, engine, ""
    for model, generation, years, bodies in MERCEDES_GROUPS:
        for body in bodies:
            yield "Mercedes", model, generation, years, "", body


def garage_trims():
    for make, model, generation, years, engine, body in generation_trims():
        yield make, f"{model} {generation}", years, engine, body
    for make, models in MODEL_OPTIONS.items():
        for model, (bodies, engines) in models.items():
            for body in bodies:
                yield make, model, "", "", body
            for engine in engines:
                yield make, model, "", engine, ""

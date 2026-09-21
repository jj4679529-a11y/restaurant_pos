from __future__ import annotations

MENU_GROUPS = {
    "Milliy taomlar": [
        "Osh",
        "Osh qo‘shimchalari",
        "Shurva",
        "Ko‘za shurva",
        "Jizz",
        "Mastava",
        "Manti",
    ],
    "Salatlar": [],
    "Choy va Novot": [],
    "Nonlar": [],
    "Kompot va Ayron": [],
    "Salqin ichimliklar": [],
}


LITER_CHOICES = [
    ("0.5 L", "0.5"),
    ("1 L", "1"),
    ("1.5 L", "1.5"),
    ("2 L", "2"),
]


BREAD_CHOICES = [
    ("Butun", "1"),
    ("Yarim", "0.5"),
    ("Chorak", "0.25"),
]


OSH_ADDONS = [
    "Tuxum",
    "Bedana tuxum",
    "Qazi",
    "Go‘sht",
]


STRICT_RULES = {
    "Osh": {
        "resource": "product",
        "unit": "PORTION",
        "unit_label": "Porsiyada",
        "manual_price": False,
        "fields": ["name", "price", "image"],
    },

    "Tuxum": {
        "resource": "addon",
        "unit": "PIECE",
        "unit_label": "Donada",
        "manual_price": False,
        "fields": ["price", "image"],
    },

    "Bedana tuxum": {
        "resource": "addon",
        "unit": "PIECE",
        "unit_label": "Donada",
        "manual_price": False,
        "fields": ["price", "image"],
    },

    "Qazi": {
        "resource": "addon",
        "unit": "PIECE",
        "unit_label": "Donada",
        "manual_price": False,
        "fields": ["price", "image"],
    },

    "Go‘sht": {
        "resource": "addon",
        "unit": "AMOUNT",
        "unit_label": "Kassir qo‘lda narx kiritadi",
        "manual_price": True,
        "fields": ["presets"],
        "preset_count": 4,
    },

    "Shurva": {
        "resource": "product",
        "unit": "PORTION",
        "unit_label": "Porsiyada",
        "manual_price": False,
        "fields": ["name", "price", "image"],
    },

    "Ko‘za shurva": {
        "resource": "product",
        "unit": "PORTION",
        "unit_label": "Porsiyada",
        "manual_price": False,
        "fields": ["name", "price", "image"],
    },

    "Jizz": {
        "resource": "product",
        "unit": "AMOUNT",
        "unit_label": "Kassir qo‘lda narx kiritadi",
        "manual_price": True,
        "fields": ["name", "presets"],
        "preset_count": 4,
    },

    "Mastava": {
        "resource": "product",
        "unit": "PORTION",
        "unit_label": "Porsiyada",
        "manual_price": False,
        "fields": ["name", "price", "image"],
    },

    "Manti": {
        "resource": "product",
        "unit": "PIECE",
        "unit_label": "Donada",
        "manual_price": False,
        "fields": ["name", "price", "image"],
    },

    "Salatlar": {
        "resource": "product",
        "unit": "PIECE",
        "unit_label": "Donada",
        "manual_price": False,
        "fields": ["name", "price", "image"],
    },

    "Choy va Novot": {
        "resource": "product",
        "unit": "PIECE",
        "unit_label": "Donada",
        "manual_price": False,
        "fields": ["name", "price", "image"],
    },

    "Nonlar": {
        "resource": "product",
        "unit": "PIECE",
        "unit_label": "Butun / Yarim / Chorak",
        "manual_price": False,
        "fields": ["name", "bread_size", "price", "image"],
    },

    "Kompot va Ayron": {
        "resource": "product",
        "unit": "LITER",
        "unit_label": "Litrda",
        "manual_price": False,
        "fields": ["name", "volume", "price", "image"],
    },

    "Salqin ichimliklar": {
        "resource": "product",
        "unit": "LITER",
        "unit_label": "Litrda",
        "manual_price": False,
        "fields": ["name", "volume", "price", "image"],
    },
}

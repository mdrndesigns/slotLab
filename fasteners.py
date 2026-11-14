"""
Fastener tables for SLOTLAB. All values in millimetres.

Sources (checked 2026-10-22):
    ISO 261 / 262   coarse pitch, basic minor diameter D1 = D - 1.0825 p
    ISO 273         clearance holes, medium series
    ISO 4032        hex nut style 1, s across flats (max), m height (max)
    DIN 439 / ISO 4035  thin (jam) nut
    ISO 4762        socket head cap screw, dk head Ø (max), k head height
    heat-set inserts: common brass inserts as sold for FDM; the hole
                     column is a CAD starting point (CNC Kitchen: 4.2 for M3)
                     - check the datasheet of the inserts you actually hold.

Printed-thread limits (3D Printer Stuff, CNC Kitchen, maker reports):
    M3 / M4   tooth height under the extrusion width  -> refused
    M5        works in PETG at 0.10-0.12 mm layers      -> warned
    M6 / M8   practical with a 0.4 nozzle               -> allowed
"""

import math

SIZES = [3, 4, 5, 6, 8, 10, 12]
PITCH = {3: 0.5, 4: 0.7, 5: 0.8, 6: 1.0, 8: 1.25, 10: 1.5, 12: 1.75}
CLEARANCE = {3: 3.4, 4: 4.5, 5: 5.5, 6: 6.6, 8: 9.0, 10: 11.0, 12: 13.5}   # ISO 273 medium

# hex nuts, s = across flats, m = height
NUT_ISO4032 = {3: (5.5, 2.4), 4: (7.0, 3.2), 5: (8.0, 4.7), 6: (10.0, 5.2),
               8: (13.0, 6.8), 10: (16.0, 8.4), 12: (18.0, 10.8)}
NUT_DIN934  = {3: (5.5, 2.4), 4: (7.0, 3.2), 5: (8.0, 4.0), 6: (10.0, 5.0),
               8: (13.0, 6.5), 10: (17.0, 8.0), 12: (19.0, 10.0)}
NUT_THIN    = {3: (5.5, 1.8), 4: (7.0, 2.2), 5: (8.0, 2.7), 6: (10.0, 3.2),
               8: (13.0, 4.0), 10: (17.0, 5.0), 12: (19.0, 6.0)}        # DIN 439

NUTS = {
    "iso4032": {"label": "Hex nut ISO 4032", "t": NUT_ISO4032},
    "din934":  {"label": "Hex nut DIN 934",  "t": NUT_DIN934},
    "thin":    {"label": "Thin nut DIN 439", "t": NUT_THIN},
}

# socket head cap screw ISO 4762: dk, k, hex key
SHCS = {3: (5.5, 3.0, 2.5), 4: (7.0, 4.0, 3.0), 5: (8.5, 5.0, 4.0), 6: (10.0, 6.0, 5.0),
        8: (13.0, 8.0, 6.0), 10: (16.0, 10.0, 8.0), 12: (18.0, 12.0, 10.0)}

# countersunk head ISO 10642: dk head Ø (max), 90° included angle
CSK = {3: 6.72, 4: 8.96, 5: 11.2, 6: 13.44, 8: 17.92, 10: 22.4, 12: 26.88}

# metric hex (Allen) keys, across flats, ascending - for the key holder
HEX_KEYS = [1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0]

# heat-set inserts: (insert OD, standard length, short length, CAD hole Ø)
INSERTS = {3: (4.6, 5.7, 4.0, 4.2), 4: (5.6, 6.4, 4.6, 5.3), 5: (6.4, 8.0, 5.8, 6.1),
           6: (8.0, 10.0, 8.0, 7.6), 8: (10.0, 12.7, 10.0, 9.6)}

# material presets: extra space the printer needs. All are diametral /
# across-flats totals except `neck`, `wide` (per side pairs) - see model.py
MATERIALS = {
    "petg":   {"label": "PETG",         "hex": 0.30, "depth": 0.30, "wide": 0.40, "neck": 0.20, "hole": 0.20, "thread": 0.25},
    "abs":    {"label": "ABS / ASA / GF", "hex": 0.25, "depth": 0.30, "wide": 0.35, "neck": 0.20, "hole": 0.20, "thread": 0.30},
    "pla":    {"label": "PLA",          "hex": 0.20, "depth": 0.25, "wide": 0.30, "neck": 0.15, "hole": 0.15, "thread": 0.30},
}


def across_corners(s):
    return s / math.cos(math.radians(30))


def minor_d(size):
    return size - 1.0825 * PITCH[size]


def thread_status(size):
    """'ok' | 'warn' | 'no' for a printed internal thread of this size."""
    if size <= 4:
        return "no"
    if size == 5:
        return "warn"
    return "ok"

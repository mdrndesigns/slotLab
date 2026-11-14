"""
Extrusion profile tables for SLOTLAB. All values in millimetres.

A profile name does not fix the slot geometry: a "4040" can carry a
slot 8 or a slot 10, and a "2020" core is Ø4.2 (Misumi, V-slot, most
Chinese stock) or Ø5.5 (Bosch, Motedis, Alux B-type). So every profile
is a full parameter set, and every field is a slider in the UI. Pick the
nearest preset, then measure your stock and correct the sliders.

Fields (see the sketch):

            opening
          ┌───┐           face (z = size/2)
    ──────┘   └──────     lip      : thickness of the lip, face to cavity ceiling
    │   cavity_w    │     cavity_w : width under the lips
    └───────────────┘     cavity_d : depth under the lips to the cavity floor
                          core     : centre bore diameter (end-tap size `tap`)
                          corner_r : outer corner radius
                          v_chamfer: V-slot lip bevel (45°), 0 for a T-slot
                          floor_ch : cavity floor corner chamfer (nut lower edges)

`verified` = taken from a manufacturer drawing (Misumi catalogue PDFs,
checked 2026-10-22). Unverified entries are typical vendor figures and
are the ones most worth measuring.

Slot load limits (Bosch Rexroth, start of plastic deformation, steel
hardware): slot 6 T-nut 1700 N, slot 8 T-nut 4000 N. With printed
hardware the plastic is the weak link, never the lip.
"""

PROFILES = {
    "hfs5_2020": dict(
        label="2020 · Misumi HFS5 · slot 6", size=20.0, slot=6,
        opening=6.0, lip=2.0, cavity_w=12.0, cavity_d=4.0, core=4.2,
        corner_r=1.0, v_chamfer=0.0, floor_ch=0.5, tap=5, kg_m=0.50,
        verified=True,
        note="Opening 6 +0.3/0. Slot depth 6, 1.5 walls, 120° slot bottom.",
    ),
    "eu_2020": dict(
        label="2020 · generic European · slot 6", size=20.0, slot=6,
        opening=6.2, lip=1.8, cavity_w=11.0, cavity_d=4.3, core=4.2,
        corner_r=1.0, v_chamfer=0.0, floor_ch=0.5, tap=5, kg_m=0.50,
        verified=False,
        note="Typical Chinese stock. Vendors quote slot 6.2 and ~0.5 kg/m. Measure yours.",
    ),
    "btype_2020": dict(
        label="2020 · B-type (Bosch/Motedis/Alux) · slot 6", size=20.0, slot=6,
        opening=6.0, lip=2.0, cavity_w=11.0, cavity_d=3.5, core=5.5,
        corner_r=1.0, v_chamfer=0.0, floor_ch=0.5, tap=6, kg_m=0.50,
        verified=False,
        note="Groove depth 5.5, core Ø5.5 for M6 (Motedis). Cavity figures typical.",
    ),
    "vslot_2020": dict(
        label="2020 · OpenBuilds V-slot", size=20.0, slot=6,
        opening=6.2, lip=1.8, cavity_w=11.0, cavity_d=4.4, core=4.2,
        corner_r=1.0, v_chamfer=1.5, floor_ch=0.5, tap=5, kg_m=0.45,
        verified=False,
        note="Secondary sources only; throat quoted 6.25 or 6.77. 45° lip bevel modelled.",
    ),
    "hfs6_3030": dict(
        label="3030 · Misumi HFS6 · slot 8", size=30.0, slot=8,
        opening=8.0, lip=2.0, cavity_w=16.5, cavity_d=7.0, core=6.8,
        corner_r=2.0, v_chamfer=0.0, floor_ch=0.8, tap=8, kg_m=0.92,
        verified=True,
        note="Slot depth 9, 12 mm core square, 4×Ø4.2 corner holes.",
    ),
    "eu_3030": dict(
        label="3030 · generic European · slot 8", size=30.0, slot=8,
        opening=8.2, lip=2.0, cavity_w=16.5, cavity_d=6.5, core=6.8,
        corner_r=2.0, v_chamfer=0.0, floor_ch=0.8, tap=8, kg_m=0.90,
        verified=False,
        note="Typical Chinese stock. Measure the opening; 8.0–8.3 is common.",
    ),
    "i_4040": dict(
        label="4040 · I-type (Alux/Motedis) · slot 8", size=40.0, slot=8,
        opening=8.0, lip=2.5, cavity_w=20.5, cavity_d=9.5, core=6.8,
        corner_r=2.0, v_chamfer=0.0, floor_ch=0.8, tap=8, kg_m=1.40,
        verified=False,
        note="Opening 8 −0/+0.3, core Ø6.8 −0.2/0 (Alux). Slot depth 12 (Motedis). Lip typical.",
    ),
    "hfs8_4040": dict(
        label="4040 · Misumi HFS8 · slot 10", size=40.0, slot=10,
        opening=10.0, lip=3.0, cavity_w=20.0, cavity_d=7.0, core=10.5,
        corner_r=3.0, v_chamfer=0.0, floor_ch=1.0, tap=12, kg_m=1.73,
        verified=False,
        note="Opening, cavity 20, core Ø10.5, R3 verified; lip and depth inferred from drawing callouts (5.5 / 7).",
    ),
}

ORDER = list(PROFILES)
GEOM_KEYS = ("size", "opening", "lip", "cavity_w", "cavity_d", "core",
             "corner_r", "v_chamfer", "floor_ch")

# nominal slot -> threads that commercial slide-in / drop-in nuts carry
SLOT_THREADS = {6: [3, 4, 5], 8: [3, 4, 5, 6, 8], 10: [4, 5, 6, 8]}
SLOT_DEFAULT_THREAD = {6: 5, 8: 6, 10: 8}

# Misumi steel nut references (verified) - neck A, head B, body E, length L
STEEL_NUTS = {
    6:  {"slide": dict(A=5.8, B=10.0, E=3.3, L=10), "drop": dict(A=5.8, B=8.3,  E=2.5, L=15)},
    8:  {"slide": dict(A=7.8, B=15.0, E=5.5, L=14), "drop": dict(A=7.8, B=11.5, E=5.5, L=17)},
    10: {"slide": dict(A=9.8, B=17.0, E=6.0, L=17), "drop": dict(A=9.8, B=14.5, E=4.5, L=20)},
}

# Bosch Rexroth slot limits, start of plastic deformation, N (steel hardware)
SLOT_LIMITS = {
    6:  dict(tnut=1700, centre_bolt=2000, torque_nm=3.0),
    8:  dict(tnut=4000, centre_bolt=5000, torque_nm=10.0),
    10: dict(tnut=6000, centre_bolt=7000, torque_nm=12.0),
}


def nominal_slot(opening):
    """Nearest nominal slot for an opening width."""
    return min(SLOT_THREADS, key=lambda s: abs(s - opening))


def geometry(p):
    """The nine geometry numbers from a parameter dict."""
    return {k: float(p[k]) for k in GEOM_KEYS}

"""
SLOTLAB - parametric hardware for T-slot aluminium extrusions
(2020 / 3030 / 4040, slot 6 / 8 / 10), printed in PETG or ABS.

Four families, one parameter dict:

    tnut     slide-in or drop-in T-nut. Fastening: captive hex nut,
             printed ISO thread, heat-set insert, or a plain bore.
    plate    gusset plate on the planar faces of two members meeting at
             any angle (180 = splice). Slot tongues + T-nut bolts.
    elbow    mitre-elbow block for square-cut members, bolted into the
             end-tapped core (the strongest joint class). Slot keys stop
             rotation. Optional third arm along Z (corner cube at 90).
    bracket  inside-corner angle bracket at any angle, for T-joints and
             mid-span joints. Tongues, T-nut bolts, side or full webs.

Frames (all mm):
    tnut     X along the slot, Z up toward the extrusion face, z = 0 at
             the cavity floor side of the head.
    plate    members lie in the XY plane, their top faces at z = 0,
             member 1 along +X from the vertex, member 2 at `angle`.
             Plate occupies z in [0, thick].
    elbow    same axes as plate, block centred on the member axes.
    bracket  inside corner line is the Z axis. Face 1 is y = 0 (x > 0),
             face 2 is the plane at `angle` from it. Width runs along Z.

Everything the browser shows is the solid the server built: what you
see is what exports.
"""

import math

import cadquery as cq

import branding as B
import fasteners as F
import profiles as P

DEFAULTS = {
    # --- profile -------------------------------------------------------
    "profile": "hfs6_3030",
    "size": 30.0, "opening": 8.0, "lip": 2.0, "cavity_w": 16.5, "cavity_d": 7.0,
    "core": 6.8, "corner_r": 2.0, "v_chamfer": 0.0, "floor_ch": 0.8,
    "material": "petg",
    # --- fit (filled from the material preset) ----------------------------
    "clear_hex": 0.30,      # hex pocket across flats, total
    "clear_depth": 0.30,    # pocket depth / head height
    "clear_wide": 0.40,     # head width vs cavity, total
    "clear_neck": 0.20,     # neck / tongue / key width vs opening, total
    "clear_hole": 0.20,     # added to ISO 273 clearance holes
    "clear_thread": 0.25,   # printed thread, radial
    # --- family and bolt ----------------------------------------------------
    "family": "tnut",       # tnut | plate | elbow | bracket
    "thread": 6,            # M size of the bolt / nut / thread
    # --- tnut ---------------------------------------------------------------
    "tn_type": "slide",     # slide | drop
    "tn_len": 14.0,
    "tn_holes": 1,
    "tn_pitch": 0.0,        # 0 = spread evenly
    "tn_fix": "hex",        # hex | thread | insert | plain
    "tn_nut": "iso4032",    # iso4032 | din934 | thin
    "tn_load": "bottom",    # bottom | end  (hex pocket entry)
    "tn_floor": 0.8,        # end-loaded pocket: floor under the nut
    "tn_neck": 1.8,         # neck height, 0 = no neck
    "tn_neck_len": 0.0,     # 0 = full length
    "tn_lead": 0.6,         # chamfer on the head ends
    "tn_boss": 0.0,         # drop-in: centring boss height (cylinder), 0 = none
    "tn_insert_len": 0.0,   # 0 = auto (standard, else short)
    "tn_corner_r": 0.4,     # hex pocket corner radius
    "tn_retain": 0.0,       # bottom-loaded hex: snap lip at the pocket mouth, per side
    "tn_thread_preview": False,
    # --- joints (plate / elbow / bracket) ------------------------------------
    "angle": 90.0,          # interior angle between members
    "member_len": 60.0,     # context stubs in the viewport
    "ends": "mitre",        # mitre | square  (plate context + hole limits)
    "holes": 2,             # per leg
    "hole_offset": 0.0,     # first hole from the vertex / corner, 0 = auto
    "hole_pitch": 20.0,
    "leg": 0.0,             # leg length, 0 = auto from holes
    "thick": 5.0,           # plate / bracket thickness
    "width": 0.0,           # plate / bracket width, 0 = profile size
    "cbore": True,          # counterbore for a socket head
    "cbore_depth": 0.0,     # 0 = auto (head height, keeping 2 mm under it)
    "tongue": True,
    "tongue_h": 0.0,        # 0 = lip - 0.2
    "tn_ref_len": 0.0,      # T-nut length the tongues are windowed for, 0 = auto
    "gusset": 0.5,          # plate: inner corner fill, fraction of leg
    "outer_cut": 0.0,       # plate: clip the outer corner at this distance, 0 = none
    # --- elbow --------------------------------------------------------------
    "arm": 0.0,             # arm length from the vertex, 0 = auto
    "bolt_wall": 6.0,       # material under the bolt head
    "keys": True,           # slot keys on the end faces
    "key_len": 6.0,
    "z_arm": "none",        # none | up | down
    # --- bracket ------------------------------------------------------------
    "web": "sides",         # none | sides | full
    "web_len": 0.0,         # 0 = 0.6 × leg
    "web_t": 3.0,
    "br_rot": 0,            # rotate the bracket about the corner line, 0 | 90 | 180 | 270
    # --- end cap ------------------------------------------------------------
    "cap_t": 3.0,           # plate thickness
    "cap_edge": "chamfer",  # none | chamfer | fillet   (outer face edges)
    "cap_edge_s": 1.0,      # chamfer / fillet size
    "cap_corner_r": 0.0,    # plan corner radius, 0 = follow the profile corner
    "cap_oversize": 0.0,    # plate beyond the profile, per side (covers the sharp edge)
    "cap_plug": "keys",     # none | keys | tee   (slot plugs)
    "cap_core": True,       # core plug into the centre bore (off when there is a hole)
    "cap_plug_len": 6.0,
    "cap_grip": 0.15,       # press-fit interference added to the plug widths, total
    "cap_hole": "none",     # none | plain | cbore | csk   (centre bolt into the tapped core)
    # --- accessory ----------------------------------------------------------
    "acc_type": "hook",     # hook | peg | drivers | hexkeys | wrenches
    "acc_turn": "along",    # along | across  (which way the hook / shelf faces)
    "acc_reach": 30.0,      # arm length / shelf depth from the face
    "acc_w": 0.0,           # head width, 0 = auto (hook / peg: base width; racks: from the features)
    "acc_t": 6.0,           # arm / shelf thickness
    "acc_tip": 14.0,        # hook tip rise / peg stop lip
    "acc_bend_r": 8.0,      # hook inner bend radius
    "acc_n": 4,             # rack features
    "acc_pitch": 18.0,      # rack feature pitch
    "acc_d": 8.0,           # rack hole Ø / wrench slot width
    "acc_rib": 12.0,        # rib height along the base, 0 = none
    "acc_root_r": 2.0,      # cove fillet at the head root
    "acc_mag_d": 8.0,       # tray: magnet Ø
    "acc_mag_t": 3.0,       # tray: magnet thickness
    "acc_rim": 6.0,         # tray: rim height
    "acc_wire": "round",    # clip: round | flat
    "acc_wire_d": 4.0,      # clip: wire Ø, or flat cable thickness
    "acc_wire_w": 10.0,     # clip: flat cable width
    "acc_wall": 2.0,        # clip: wall around the wire
    "acc_snap": 0.5,        # clip: snap lip per side at the mouth (0 = open U)
    "acc_clip": "snap",     # clip: snap | loop | comb
    # --- branding (cap, sign) ------------------------------------------------
    "brand_src": "none",    # none | text | svg
    "brand_text": "SLOTLAB",
    "brand_font": "sans",   # sans | serif | mono
    "brand_bold": False,
    "brand_size": 0.0,      # text height / artwork longest side, 0 = fit the face
    "brand_depth": 0.6,
    "brand_mode": "recess", # recess | emboss | through
    "brand_rot": 0.0,
    "brand_x": 0.0,
    "brand_y": 0.0,
    "brand_line": 1.2,      # line spacing, × text size
    "brand_svg": "",        # upload key (or a file path when run from the script)
    "brand_dual": False,    # branding as a separate part for a second filament (3MF with two parts)
    # --- sign (name plate) -------------------------------------------------
    "sg_w": 90.0,
    "sg_h": 40.0,
    "sg_t": 4.0,
    "sg_corner_r": 3.0,
    "sg_edge": "chamfer",   # none | chamfer | fillet
    "sg_edge_s": 0.8,
    "sg_mount": "slot",     # none | bolts | slot
    "sg_holes": "inside",   # bolts: inside (holes in the plate) | ears (round tabs outside the edge)
    "sg_where": "bottom",   # bolts: bottom (rail along the bottom edge) | sides (one bolt at each end, rail
                            #        behind the centre line) | both (rails top and bottom)
    "sg_margin": 0.0,       # inside: hole centre from the edge, 0 = auto (head + 1.5 mm wall)
    "sg_inset": 0.0,        # hole centres from the plate ends, 0 = centred at the pitch
    "sg_ear_wall": 3.0,     # ears: wall around the bolt head
    "sg_offset": 0.0,       # inside, one rail: slot line from the sign centre, 0 = auto (near the edge)
    "sg_lip": "none",       # border lip on the show face: none | raised | groove
    "sg_lip_h": 1.0,        # lip height / groove depth
    "sg_lip_w": 2.0,        # lip width
    "sg_lip_inset": 2.0,    # lip from the plate edge
    "brand_align": "band",  # sign: band (free of the bolt heads) | centre (plate centre)
    # --- splice (inline extension) ------------------------------------------
    "sp_kind": "sleeve",    # sleeve | bar
    "sp_faces": 4,          # sleeve: faces covered 1..4
    "sp_len": 0.0,          # 0 = auto
    "sp_t": 4.0,            # sleeve wall
    "sp_fit": 0.15,         # sleeve: clearance to the profile, per side
    "sp_fix": "hex",        # bar: hex | thread (grub screws)
    # --- pivot (movable joint) ----------------------------------------------
    "pv_part": "both",      # both | a | b
    "pv_setback": 0.0,      # member end from the pivot, 0 = auto
    "pv_lug_d": 0.0,        # lug Ø, 0 = auto
    "pv_gap": 0.5,          # axial gap between the lugs (washer)
    "pv_clear": 0.2,        # pivot bore / arc slot clearance on top of ISO 273
    "pv_lock": "none",      # none | arc
    "pv_range": 90.0,       # arc lock: swing covered by the slot
    "pv_knob": 0.0,         # flat clear area wanted around the bolt heads (knob Ø), 0 = none
}

STR_KEYS = ("profile", "material", "family", "tn_type", "tn_fix", "tn_nut",
            "tn_load", "ends", "z_arm", "web", "cap_edge", "cap_plug", "cap_hole",
            "acc_type", "acc_turn", "acc_wire", "acc_clip", "brand_src", "brand_text",
            "brand_font", "brand_mode", "brand_svg", "brand_align", "sg_edge", "sg_mount", "sg_holes", "sg_where", "sg_lip",
            "sp_kind", "sp_fix", "pv_part", "pv_lock")
INT_KEYS = ("thread", "tn_holes", "holes", "br_rot", "acc_n", "sp_faces")
FAMILIES = ("tnut", "plate", "elbow", "bracket", "cap", "acc", "sign", "splice", "pivot")
EPS = 0.01


# ---------------------------------------------------------------------
# parameters
# ---------------------------------------------------------------------

def merge_params(raw):
    p = dict(DEFAULTS)
    for k, v in raw.items():
        if k not in p:
            continue
        if k in STR_KEYS:
            p[k] = str(v)
        elif isinstance(p[k], bool):
            p[k] = str(v).lower() in ("1", "true", "yes", "on")
        elif k in INT_KEYS:
            p[k] = int(float(v))
        else:
            p[k] = float(v)
    return p


def apply_profile(p, key):
    """Copy a preset's geometry into the parameter dict."""
    pr = P.PROFILES[key]
    for k in P.GEOM_KEYS:
        p[k] = float(pr[k])
    p["profile"] = key
    return p


def apply_material(p, key):
    m = F.MATERIALS[key]
    p["material"] = key
    p["clear_hex"], p["clear_depth"], p["clear_wide"] = m["hex"], m["depth"], m["wide"]
    p["clear_neck"], p["clear_hole"], p["clear_thread"] = m["neck"], m["hole"], m["thread"]
    return p


def slot_of(p):
    return P.nominal_slot(p["opening"])


# ---------------------------------------------------------------------
# small geometry helpers
# ---------------------------------------------------------------------

def box(x0, x1, y0, y1, z0, z1):
    return (cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False)
            .translate((x0, y0, z0)))


def halfspace(nx, ny, nz, size=2000.0):
    """Solid filling n·p <= 0, plane through the origin. For the other
    side pass -n."""
    n = cq.Vector(nx, ny, nz).normalized()
    b = cq.Workplane("XY").box(size, size, size).translate((0, 0, -size / 2))  # z <= 0
    # rotate so that the box's outward normal (+Z) lands on n
    z = cq.Vector(0, 0, 1)
    axis = z.cross(n)
    ang = math.degrees(math.acos(max(-1.0, min(1.0, z.dot(n)))))
    if axis.Length > 1e-9:
        b = b.rotate((0, 0, 0), (axis.x, axis.y, axis.z), ang)
    elif ang > 90:
        b = b.rotate((0, 0, 0), (1, 0, 0), 180)
    return b


def hex_prism(af, z0, z1, corner_r=0.4):
    """Hex pocket, flats facing ±Y, corners along ±X."""
    d = F.across_corners(af)
    h = cq.Workplane("XY").polygon(6, d).extrude(z1 - z0).translate((0, 0, z0))
    if corner_r > 0:
        try:
            h = h.edges("|Z").fillet(corner_r)
        except Exception:
            pass
    return h


def cyl(r, z0, z1, x=0.0, y=0.0):
    return cq.Workplane("XY").circle(r).extrude(z1 - z0).translate((x, y, z0))


def rotz(obj, deg):
    return obj.rotate((0, 0, 0), (0, 0, 1), deg)


def rotx(obj, deg):
    return obj.rotate((0, 0, 0), (1, 0, 0), deg)


def roty(obj, deg):
    return obj.rotate((0, 0, 0), (0, 1, 0), deg)


def union_all(objs):
    out = objs[0]
    for o in objs[1:]:
        out = out.union(o)
    return out


def cut_all(obj, cutters):
    for c in cutters:
        obj = obj.cut(c)
    return obj


# ---------------------------------------------------------------------
# printed internal thread
# ---------------------------------------------------------------------

def thread_groove(size, height, clear, overlap=0.25):
    """
    Helical groove solid for an internal ISO 60° thread along Z, running
    from z = -p to z = height + p. ISO basic form: groove 0.75 p wide at
    the minor diameter, root flat 0.125 p at the major; `clear` is added
    radially so the printed thread is oversize. Cut this BEFORE the minor
    bore - OpenCascade silently fails the boolean the other way round.
    """
    pch = F.PITCH[size]
    r_minor = F.minor_d(size) / 2 + clear
    r_major = size / 2 + clear
    w_in = 0.75 * pch                 # must stay under the pitch or the sweep self-intersects
    w_out = 0.125 * pch
    r_in = r_minor - overlap          # inner extension has vertical flanks (keeps w_in)
    pts = [(r_in, -w_in / 2), (r_minor, -w_in / 2), (r_major, -w_out / 2),
           (r_major, w_out / 2), (r_minor, w_in / 2), (r_in, w_in / 2)]
    helix = cq.Wire.makeHelix(pitch=pch, height=height + 2 * pch, radius=r_minor)
    groove = cq.Workplane("XZ").polyline(pts).close().sweep(cq.Workplane().add(helix), isFrenet=True)
    return groove.translate((0, 0, -pch)), r_minor


# ---------------------------------------------------------------------
# extrusion member (context geometry, also used to cope square joints)
# ---------------------------------------------------------------------

def member_prism(g, x0, x1, solid=False):
    """
    Extrusion along +X from x0 to x1, axis through the origin, section
    centred on the YZ plane. solid=True returns the plain square (used
    for the elbow block).
    """
    s = g["size"]
    m = box(x0, x1, -s / 2, s / 2, -s / 2, s / 2)
    if g["corner_r"] > 0:
        m = m.edges("|X").fillet(g["corner_r"])
    if solid:
        return m
    o, lip, cw, cd = g["opening"], g["lip"], g["cavity_w"], g["cavity_d"]
    L0, L1 = x0 - 1, x1 + 1
    cutters = []
    opening = box(L0, L1, -o / 2, o / 2, s / 2 - lip - EPS, s / 2 + 1)
    cavity = box(L0, L1, -cw / 2, cw / 2, s / 2 - lip - cd, s / 2 - lip + EPS)
    if g["floor_ch"] > 0:
        cavity = cavity.edges("|X and <Z").chamfer(min(g["floor_ch"], cd * 0.45, cw * 0.2))
    one = opening.union(cavity)
    if g["v_chamfer"] > 0:
        v = min(g["v_chamfer"], lip)
        wedge = (cq.Workplane("YZ")
                 .polyline([(-o / 2 - v, s / 2 + EPS), (o / 2 + v, s / 2 + EPS),
                            (o / 2, s / 2 - v), (-o / 2, s / 2 - v)]).close()
                 .extrude(L1 - L0).translate((L0, 0, 0)))
        one = one.union(wedge)
    for k in range(4):
        cutters.append(rotx(one, 90 * k))
    cutters.append(cq.Workplane("YZ").circle(g["core"] / 2).extrude(L1 - L0).translate((L0, 0, 0)))
    return cut_all(m, cutters)


def bisector_normal(angle):
    """Normal of the mitre plane between member 1 (+X) and member 2 (at
    `angle`), pointing toward member 2's side."""
    h = math.radians(angle / 2)
    return (-math.sin(h), math.cos(h), 0.0)


def side1(angle):
    nx, ny, nz = bisector_normal(angle)
    return halfspace(nx, ny, nz)


def side2(angle):
    nx, ny, nz = bisector_normal(angle)
    return halfspace(-nx, -ny, -nz)


def trimmed_prism(g, length, angle, which, solid=False, back=None):
    """Member stub from the vertex outward, mitred at the bisector."""
    s = g["size"]
    back = -3 * s if back is None else back        # covers the outer mitre spike down to 25°
    pr = member_prism(g, back, length, solid=solid)
    if which == 1:
        return pr.intersect(side1(angle))
    return rotz(pr, angle).intersect(side2(angle))


# ---------------------------------------------------------------------
# T-NUT
# ---------------------------------------------------------------------

def tnut_spec(p):
    g = P.geometry(p)
    size = p["thread"]
    slot = slot_of(p)
    sp = {"slot": slot, "size": size, "g": g, "errors": [], "warnings": []}

    Hh = g["cavity_d"] - p["clear_depth"]                      # head height
    if p["tn_type"] == "slide":
        Wh = g["cavity_w"] - p["clear_wide"]
        L = p["tn_len"]
    else:                                                       # drop-in
        Wh = g["opening"] - p["clear_neck"]                     # passes the opening
        L = g["cavity_w"] - p["clear_wide"]                     # spans the cavity
    Wn = g["opening"] - p["clear_neck"]
    Hn = max(0.0, min(p["tn_neck"], g["lip"] - 0.1)) if p["tn_type"] == "slide" else 0.0
    Ln = p["tn_neck_len"] if p["tn_neck_len"] > 0 else L
    Ln = min(Ln, L)
    sp.update(Hh=Hh, Wh=Wh, L=L, Wn=Wn, Hn=Hn, Ln=Ln, H=Hh + Hn)

    if Hh < 1.6:
        sp["errors"].append(f"Head height {Hh:.2f} mm is under 1.6 mm (cavity depth minus depth clearance).")
    if Wh < 3:
        sp["errors"].append("Head width under 3 mm.")

    # drop-in: corner radius so it rotates in the cavity
    if p["tn_type"] == "drop":
        C = g["cavity_w"]
        r_ok = None
        r = 0.0
        while r <= Wh / 2 + 1e-9:
            ext = math.hypot((L - 2 * r) / 2, (Wh - 2 * r) / 2) + r
            if ext <= C / 2 - 0.15:
                r_ok = r
                break
            r += 0.05
        if r_ok is None:
            sp["errors"].append("Drop-in body cannot rotate inside the cavity; widen the cavity clearance.")
            r_ok = Wh / 2
        sp["drop_r"] = r_ok

    # holes
    n = max(1, p["tn_holes"])
    pitch = p["tn_pitch"] if p["tn_pitch"] > 0 else L / n
    xs = [(i - (n - 1) / 2) * pitch for i in range(n)]
    sp["xs"] = xs
    sp["pitch"] = pitch

    d_clear = F.CLEARANCE[size] + p["clear_hole"]
    sp["d_clear"] = d_clear
    fix = p["tn_fix"]
    sp["fix"] = fix
    wall_side = wall_end = ceiling = None

    if fix == "hex":
        af, m = F.NUTS[p["tn_nut"]]["t"][size]
        af_p = af + p["clear_hex"]
        ac_p = F.across_corners(af_p)
        h_p = m + p["clear_depth"]
        sp.update(af=af, nut_h=m, af_p=af_p, ac_p=ac_p, h_p=h_p)
        wall_side = (Wh - af_p) / 2
        if p["tn_load"] == "bottom":
            ceiling = Hh - h_p
            wall_end = min(L / 2 - abs(x) - ac_p / 2 for x in xs)
            sp["pocket_z"] = (0.0, h_p)
        else:
            ceiling = Hh - p["tn_floor"] - h_p
            wall_end = None
            sp["pocket_z"] = (p["tn_floor"], p["tn_floor"] + h_p)
        if ceiling < 0.6:
            sp["errors"].append(f"Only {ceiling:.2f} mm of plastic above the nut; use a thin nut or a smaller size.")
        elif ceiling < 1.0:
            sp["warnings"].append(f"Thin ceiling above the nut: {ceiling:.2f} mm.")
        if wall_side < 0.8:
            sp["errors"].append(f"Side wall beside the nut is {wall_side:.2f} mm (min 0.8).")
        elif wall_side < 1.2:
            sp["warnings"].append(f"Side wall beside the nut is {wall_side:.2f} mm.")
        if wall_end is not None and wall_end < 0.8:
            sp["errors"].append(f"End wall beyond the nut is {wall_end:.2f} mm; lengthen the nut.")
        if n > 1:
            gap = pitch - ac_p
            if gap < 0.8:
                sp["errors"].append("Hex pockets overlap; increase the pitch or length.")
    elif fix == "thread":
        st = F.thread_status(size)
        if st == "no":
            sp["errors"].append(f"A printed M{size} thread falls under the extrusion width. Use a captive nut or an insert.")
        elif st == "warn":
            sp["warnings"].append("Printed M5: print at 0.10-0.12 mm layers and tap-chase it.")
        wall_side = (Wh - (size + 2 * p["clear_thread"])) / 2
        if wall_side < 1.0:
            sp["errors"].append(f"Wall beside the thread is {wall_side:.2f} mm (min 1.0).")
        sp["engagement"] = Hh + Hn
    elif fix == "insert":
        if size not in F.INSERTS:
            sp["errors"].append(f"No insert table for M{size}.")
        else:
            od, l_std, l_short, hole = F.INSERTS[size]
            wall_side = (Wh - hole) / 2
            neck_ok = Hn > 0 and (Wn - hole) / 2 >= 0.6
            avail = Hh + (Hn if neck_ok else 0.0) - 0.3
            want = p["tn_insert_len"]
            if want <= 0:
                want = l_std if l_std + 0.4 <= avail else l_short
            if want + 0.4 > avail:
                sp["errors"].append(f"Insert {want:.1f} mm needs {want + 0.4:.1f} mm; only {avail:.1f} mm available.")
            if wall_side < 0.8:
                sp["errors"].append(f"Wall beside the insert hole is {wall_side:.2f} mm.")
            sp.update(ins_hole=hole, ins_len=want, ins_od=od)
    else:
        wall_side = (Wh - d_clear) / 2

    if fix == "plain" and wall_side < 0.8:
        sp["errors"].append(f"Wall beside the bore is {wall_side:.2f} mm (min 0.8); use a smaller bolt.")

    # neck wall around the bolt: a printed neck needs 0.5 mm per side or
    # it is two slivers. Drop it rather than refuse - the connector's
    # tongue does the alignment job instead.
    if Hn > 0:
        d_neck = (F.minor_d(size) + 2 * p["clear_thread"]) if fix == "thread" else d_clear
        nw = (Wn - d_neck) / 2
        if nw < 0.5:
            sp["warnings"].append(f"Neck removed: M{size} leaves {nw:.2f} mm per side in a {Wn:.1f} neck. "
                                  f"Use a tongue on the connector, or M{size - 1 if size > 3 else 3}.")
            Hn = 0.0
            sp["Hn"] = 0.0
            sp["H"] = Hh
            if fix == "thread":
                sp["engagement"] = Hh
                if Hh < 0.8 * size:
                    sp["warnings"].append(f"Thread engagement {Hh:.1f} mm is under 0.8 × D.")
        elif nw < 0.8:
            sp["warnings"].append(f"Neck is thin beside the bolt: {nw:.2f} mm per side.")

    if fix == "thread" and "engagement" in sp and sp["engagement"] < 0.8 * size and Hn > 0:
        sp["warnings"].append(f"Thread engagement {sp['engagement']:.1f} mm is under 0.8 × D.")
    sp.update(wall_side=wall_side, wall_end=wall_end, ceiling=ceiling)
    lim = P.SLOT_LIMITS.get(slot, {})
    sp["limit_note"] = (f"Steel T-nut limit in slot {slot}: {lim.get('tnut', '?')} N (Bosch). "
                        f"Printed: expect well under that; torque ≤ {lim.get('torque_nm', '?')} Nm.")
    return sp


def build_tnut(p, sp, export=False):
    g = sp["g"]
    L, Wh, Hh, Wn, Hn, Ln = sp["L"], sp["Wh"], sp["Hh"], sp["Wn"], sp["Hn"], sp["Ln"]

    if p["tn_type"] == "slide":
        head = box(-L / 2, L / 2, -Wh / 2, Wh / 2, 0, Hh)
        fc = min(g["floor_ch"] + 0.2, Hh * 0.4, Wh * 0.2)
        if fc > 0.05:
            head = head.edges("|X and <Z").chamfer(fc)
        lead = min(p["tn_lead"], Hh * 0.4, Wh * 0.2)
        if lead > 0.05:
            try:
                head = head.edges("|Z").chamfer(lead)
            except Exception:
                pass
        body = head
        if Hn > 0:
            neck = box(-Ln / 2, Ln / 2, -Wn / 2, Wn / 2, Hh - EPS, Hh + Hn)
            body = body.union(neck)
    else:
        r = sp["drop_r"]
        head = cq.Workplane("XY").rect(L, Wh).extrude(Hh)
        if r > 0.05:
            head = head.edges("|Z").fillet(min(r, Wh / 2 - 0.01, L / 2 - 0.01))
        fc = min(g["floor_ch"] + 0.2, Hh * 0.4, Wh * 0.2)
        if fc > 0.05:
            try:
                head = head.faces("<Z").chamfer(fc)
            except Exception:
                pass
        body = head
        if p["tn_boss"] > 0:
            body = body.union(cyl(Wn / 2, Hh - EPS, Hh + min(p["tn_boss"], g["lip"] - 0.1)))

    Htot = Hh + max(Hn, p["tn_boss"] if p["tn_type"] == "drop" else 0.0) + 1

    cutters = []
    for x in sp["xs"]:
        fix = sp["fix"]
        if fix == "hex":
            z0, z1 = sp["pocket_z"]
            if p["tn_load"] == "bottom" and p["tn_retain"] > 0:
                rt = min(p["tn_retain"], 0.5)
                pocket = hex_prism(sp["af_p"], rt, z1, p["tn_corner_r"]) \
                    .union(hex_prism(sp["af_p"] - 2 * rt, -1, rt + EPS, p["tn_corner_r"]))
                pocket = pocket.translate((x, 0, 0))
            else:
                pocket = hex_prism(sp["af_p"], z0 - (1 if z0 == 0 else 0), z1, p["tn_corner_r"]).translate((x, 0, 0))
            if p["tn_load"] == "end":
                sgn = 1 if x >= 0 else -1
                xe = sgn * (L / 2 + 1)
                lane = box(min(x, xe), max(x, xe), -sp["af_p"] / 2, sp["af_p"] / 2, z0, z1)
                pocket = pocket.union(lane)
            cutters.append(pocket)
            cutters.append(cyl(sp["d_clear"] / 2, -1, Htot, x=x))
        elif fix == "insert":
            d = sp["ins_hole"]
            depth = sp["ins_len"] + 0.4
            hole = cyl(d / 2, -1, depth, x=x)
            ch = cq.Workplane("XY").circle(d / 2 + 0.5).workplane(offset=0.5).circle(d / 2).loft() \
                .translate((x, 0, -EPS))
            cutters.append(hole.union(ch))
            cutters.append(cyl(sp["d_clear"] / 2, -1, Htot, x=x))
        elif fix == "plain":
            cutters.append(cyl(sp["d_clear"] / 2, -1, Htot, x=x))
        else:  # thread
            if export or p["tn_thread_preview"]:
                groove, r_minor = thread_groove(sp["size"], Htot, p["clear_thread"])
                v0 = body.val().Volume()
                body = body.cut(groove.translate((x, 0, 0)))
                if body.val().Volume() > v0 - 1.0:
                    raise RuntimeError("thread groove boolean failed; try a different clearance")
                # bore 0.03 larger than the groove's inner vertex: a vertex
                # lying exactly on the bore surface breaks the boolean
                cutters.append(cyl(r_minor + 0.03, -1, Htot, x=x))
            else:
                r_minor = F.minor_d(sp["size"]) / 2 + p["clear_thread"]
                cutters.append(cyl(r_minor, -1, Htot, x=x))
    body = cut_all(body, cutters)
    return body


# ---------------------------------------------------------------------
# shared joint helpers
# ---------------------------------------------------------------------

def joint_common(p):
    g = P.geometry(p)
    size = p["thread"]
    slot = slot_of(p)
    sp = {"g": g, "size": size, "slot": slot, "errors": [], "warnings": []}
    th = p["angle"]
    sp["angle"] = th
    sp["mitre"] = (180 - th) / 2            # cut from square, each member
    sp["turn"] = 180 - th                   # exterior turn
    sp["d_clear"] = F.CLEARANCE[size] + p["clear_hole"]
    dk, k, key = F.SHCS[size]
    sp.update(dk=dk, k=k, hexkey=key)
    ref = P.STEEL_NUTS.get(slot, P.STEEL_NUTS[8])["slide"]["L"]
    sp["tn_ref_len"] = p["tn_ref_len"] if p["tn_ref_len"] > 0 else float(ref)
    sp["tongue_w"] = g["opening"] - p["clear_neck"]
    sp["tongue_h"] = p["tongue_h"] if p["tongue_h"] > 0 else max(0.6, g["lip"] - 0.2)
    if g["lip"] < 0.9:
        # an open channel has no lip to key into: no tongue at all
        sp["tongue_h"] = 0.0
        if p["tongue"] and p["family"] != "elbow":
            sp["warnings"].append("No lip on this profile: the slot tongue is dropped.")
    elif sp["tongue_h"] > g["lip"] - 0.1:
        sp["warnings"].append("Tongue clipped to the lip thickness so the plate seats on the face.")
        sp["tongue_h"] = g["lip"] - 0.2
    if size not in P.SLOT_THREADS.get(slot, []):
        sp["warnings"].append(f"M{size} is not a standard T-nut size for slot {slot} "
                              f"({', '.join('M%d' % t for t in P.SLOT_THREADS.get(slot, []))}).")
    lim = P.SLOT_LIMITS.get(slot, {})
    sp["limit_note"] = f"Torque the T-nut bolts to ≤ {lim.get('torque_nm', '?')} Nm (slot {slot}, printed flange)."
    return sp


def cbore_depth(p, sp, t):
    if not p["cbore"]:
        return 0.0
    want = p["cbore_depth"] if p["cbore_depth"] > 0 else sp["k"]
    return max(0.0, min(want, t - 2.0))


# ---------------------------------------------------------------------
# PLATE (gusset on the planar faces)
# ---------------------------------------------------------------------

def plate_spec(p):
    sp = joint_common(p)
    g, th = sp["g"], sp["angle"]
    s = g["size"]
    w = p["width"] if p["width"] > 0 else s
    w = min(w, s)
    t = p["thick"]
    sp.update(w=w, t=t)
    h = math.radians(th / 2)
    Ln = sp["tn_ref_len"]
    cw = g["cavity_w"]
    Wt = sp["tongue_w"]
    if th >= 179.5:
        x_hole_min = Ln / 2 + 1.0
        x_t0 = 1.0
    elif p["ends"] == "mitre":
        # whole T-nut head on this side of the mitre
        x_hole_min = Ln / 2 + (math.cos(h) * cw / 2 + 0.5) / math.sin(h)
        x_t0 = (math.cos(h) * Wt / 2 + 0.6) / math.sin(h)
    else:
        sth = math.sin(math.radians(th))
        x_hole_min = max(Ln / 2 - s / 2 + 1.0,
                         (s / 2 + (cw / 2) * abs(math.cos(math.radians(th)))) / max(sth, 0.2) + Ln / 2 + 1.0)
        x_t0 = max(-s / 2 + 1.0, (s / 2 + (Wt / 2) * abs(math.cos(math.radians(th)))) / max(sth, 0.2) + 1.0)
    x_hole_min = math.ceil(x_hole_min * 2) / 2
    off = p["hole_offset"] if p["hole_offset"] > 0 else x_hole_min
    if off < x_hole_min:
        sp["warnings"].append(f"First hole moved out to {x_hole_min:.1f} mm so the T-nut clears the joint.")
        off = x_hole_min
    n = max(1, p["holes"])
    xs = [off + i * p["hole_pitch"] for i in range(n)]
    leg = p["leg"] if p["leg"] > 0 else xs[-1] + max(Ln / 2 + 2.0, sp["dk"] / 2 + 3.0)
    if xs[-1] + sp["dk"] / 2 + 1.5 > leg:
        sp["warnings"].append("Leg is shorter than the last hole; lengthened.")
        leg = xs[-1] + sp["dk"] / 2 + 1.5
    sp.update(xs=xs, leg=leg, x_t0=x_t0, cb=cbore_depth(p, sp, t))
    if t < 3:
        sp["warnings"].append("Plate under 3 mm; 5 mm is the recommended minimum for a load-bearing gusset.")
    if p["tongue"] and p["tn_ref_len"] == 0:
        pass
    return sp


def leg_outline(angle, w, length, t, which):
    """Plate leg: prism of width w trimmed at the bisector, z in [0, t]."""
    big = 3 * w + 10
    pr = box(-big, length, -w / 2, w / 2, 0, t)
    if which == 1:
        return pr.intersect(side1(angle))
    return rotz(pr, angle).intersect(side2(angle))


def build_plate(p, sp, export=False):
    th, w, t, leg = sp["angle"], sp["w"], sp["t"], sp["leg"]
    g = sp["g"]
    if th >= 179.5:
        body = box(-leg, leg, -w / 2, w / 2, 0, t)
        legs = [(0.0, 1), (180.0, 2)]
    else:
        body = leg_outline(th, w, leg, t, 1).union(leg_outline(th, w, leg, t, 2))
        legs = [(0.0, 1), (th, 2)]
        # gusset: fill the inner corner
        gl = p["gusset"] * leg
        if gl > 1.0:
            h = math.radians(th / 2)
            p0 = ((w / 2) / math.sin(h) * math.cos(h), (w / 2) / math.sin(h) * math.sin(h))
            p1 = (gl, w / 2)
            c, s_ = math.cos(math.radians(th)), math.sin(math.radians(th))
            p2 = (gl * c + (w / 2) * s_, gl * s_ - (w / 2) * c)
            tri = cq.Workplane("XY").polyline([p0, p1, p2]).close().extrude(t)
            body = body.union(tri)
        if p["outer_cut"] > 0:
            h = math.radians(th / 2)
            d = p["outer_cut"]
            n = (-math.cos(h), -math.sin(h))                      # outer bisector direction
            cutter = halfspace(n[0], n[1], 0).translate((n[0] * d, n[1] * d, 0))
            body = body.cut(cutter)

    cutters = []
    Wt, Ht, Ln = sp["tongue_w"], sp["tongue_h"], sp["tn_ref_len"]
    for ang, which in legs:
        feats_cut = []
        for x in sp["xs"]:
            feats_cut.append(cyl(sp["d_clear"] / 2, -Ht - 2, t + 1, x=x))
            if sp["cb"] > 0:
                feats_cut.append(cyl(sp["dk"] / 2 + 0.3, t - sp["cb"], t + 1, x=x))
        tongue = None
        if p["tongue"] and Ht > 0.05:
            x0 = sp["x_t0"] if th < 179.5 else 1.0
            x1 = leg - 1.5
            if x1 - x0 > 3:
                tongue = box(x0, x1, -Wt / 2, Wt / 2, -Ht, EPS)
                for x in sp["xs"]:
                    tongue = tongue.cut(box(x - Ln / 2 - 0.5, x + Ln / 2 + 0.5, -Wt, Wt, -Ht - 1, 1))
        if tongue is not None:
            body = body.union(rotz(tongue, ang))
        cutters += [rotz(c, ang) for c in feats_cut]
    body = cut_all(body, cutters)
    return body


def plate_context(p, sp):
    g, th = sp["g"], sp["angle"]
    s = g["size"]
    L = p["member_len"]
    if th >= 179.5:
        m1 = member_prism(g, 0, L)
        m2 = rotz(member_prism(g, 0, L), 180)
    elif p["ends"] == "mitre":
        m1 = trimmed_prism(g, L, th, 1)
        m2 = trimmed_prism(g, L, th, 2)
    else:
        m1 = member_prism(g, -s / 2, L)
        m2 = rotz(member_prism(g, 0, L), th).cut(box(-s / 2 - EPS, L + 1, -s / 2 - EPS, s / 2 + EPS, -s, s))
    return m1.union(m2).translate((0, 0, -s / 2))


# ---------------------------------------------------------------------
# ELBOW block (square-cut members, end-tapped bolts)
# ---------------------------------------------------------------------

def elbow_spec(p):
    sp = joint_common(p)
    g, th = sp["g"], sp["angle"]
    s = g["size"]
    if th > 170:
        sp["errors"].append("Elbow needs an angle of 170° or less (a straight splice has no bolt access).")
    if th < 35:
        sp["errors"].append("Elbow angle under 35°: the mitre spike is too thin for the bores.")
    size = sp["size"]
    sp["tap_note"] = (f"Core Ø{g['core']:.1f}; bolt M{size}. Tap the member end M{size} "
                      f"(core must be the right tap drill for M{size}).")
    sp["key_w"] = g["opening"] - p["clear_neck"]
    sp["key_h"] = max(0.6, g["lip"] - 0.3)
    sp["head_d"] = sp["dk"] + 1.0
    # the access bore of one arm runs on through the other arm and out of
    # the outer face; this is how far along the axis it travels before the
    # whole bore is clear of the block
    sth = max(math.sin(math.radians(th)), 0.05)
    exit_len = (s / 2 + sp["head_d"] / 2) / sth
    sp["access_len"] = exit_len
    sp["bore_len"] = exit_len + 2.0
    arm = p["arm"] if p["arm"] > 0 else s
    arm = max(arm, p["bolt_wall"] + 2.0)
    if th > 90:
        # past 90° the other arm's bore crosses this arm's end region;
        # the arm must be long enough for that bore to leave the block first
        need = exit_len * abs(math.cos(math.radians(th))) + sp["head_d"] / 2 + 2.0
        if arm < need:
            if p["arm"] > 0:
                sp["warnings"].append(f"Arm lengthened to {need:.0f} mm so the bolt access bore exits before the end face.")
            arm = need
    sp["arm"] = arm
    return sp


def build_elbow(p, sp, export=False):
    g, th, arm = sp["g"], sp["angle"], sp["arm"]
    s = g["size"]
    a1 = trimmed_prism(g, arm, th, 1, solid=True)
    a2 = trimmed_prism(g, arm, th, 2, solid=True)
    body = a1.union(a2)
    arms = [(0.0, 1)]
    arms.append((th, 2))
    if p["z_arm"] in ("up", "down"):
        sgn = 1 if p["z_arm"] == "up" else -1
        za = box(-s / 2, s / 2, -s / 2, s / 2, 0, arm * sgn if sgn > 0 else 0)
        if sgn < 0:
            za = box(-s / 2, s / 2, -s / 2, s / 2, -arm, 0)
        if g["corner_r"] > 0:
            za = za.edges("|Z").fillet(g["corner_r"])
        body = body.union(za)

    cutters = []
    kw, kh, kl = sp["key_w"], sp["key_h"], p["key_len"]
    keys = []

    def arm_features(axis_rot=None, zarm=0):
        """Bolt bores and keys for an arm along +X; returns (cutters, keys)."""
        cs, ks = [], []
        bl = sp["bore_len"]
        through = cq.Workplane("YZ").circle(sp["d_clear"] / 2).extrude(arm + bl + 1).translate((-bl, 0, 0))
        head = cq.Workplane("YZ").circle(sp["head_d"] / 2).extrude(arm - p["bolt_wall"] + bl).translate((-bl, 0, 0))
        cs += [through, head]
        if p["keys"]:
            k0 = box(arm - EPS, arm + kl, -kw / 2, kw / 2, s / 2 - kh, s / 2 - 0.2)
            k0 = k0.edges(">X").chamfer(min(0.4, kh * 0.3))
            for q in range(4):
                ks.append(rotx(k0, 90 * q))
        return cs, ks

    for ang, which in arms:
        cs, ks = arm_features()
        cutters += [rotz(c, ang) for c in cs]
        keys += [rotz(k, ang) for k in ks]
    if p["z_arm"] in ("up", "down"):
        cs, ks = arm_features()
        rot = -90 if p["z_arm"] == "up" else 90        # +X -> +Z or -Z
        cutters += [roty(c, rot) for c in cs]
        keys += [roty(k, rot) for k in ks]
    for k in keys:
        body = body.union(k)
    body = cut_all(body, cutters)
    return body


def elbow_context(p, sp):
    g, th, arm = sp["g"], sp["angle"], sp["arm"]
    L = p["member_len"]
    m1 = member_prism(g, arm + 0.2, arm + L)
    m2 = rotz(member_prism(g, arm + 0.2, arm + L), th)
    ctx = m1.union(m2)
    if p["z_arm"] in ("up", "down"):
        m3 = roty(member_prism(g, arm + 0.2, arm + L), -90 if p["z_arm"] == "up" else 90)
        ctx = ctx.union(m3)
    return ctx


# ---------------------------------------------------------------------
# BRACKET (inside corner, face to face)
# ---------------------------------------------------------------------

def bracket_spec(p):
    sp = joint_common(p)
    g, th = sp["g"], sp["angle"]
    s = g["size"]
    if th < 30:
        sp["errors"].append("Bracket angle under 30° leaves no room for the bolt heads.")
    w = p["width"] if p["width"] > 0 else s
    w = min(w, s)
    t = p["thick"]
    Ln = sp["tn_ref_len"]
    x_hole_min = math.ceil((sp["dk"] / 2 + t + 1.5) * 2) / 2
    if th < 90:
        # the other leg's plate leans over: keep the head clear of it
        x_hole_min = max(x_hole_min, math.ceil(((t + sp["dk"] / 2 + 1.0) / math.tan(math.radians(th))) * 2) / 2 + 1)
    off = p["hole_offset"] if p["hole_offset"] > 0 else x_hole_min
    if off < x_hole_min:
        sp["warnings"].append(f"First hole moved out to {x_hole_min:.1f} mm to clear the corner.")
        off = x_hole_min
    n = max(1, p["holes"])
    xs = [off + i * p["hole_pitch"] for i in range(n)]
    leg = p["leg"] if p["leg"] > 0 else xs[-1] + max(Ln / 2 + 2.0, sp["dk"] / 2 + 3.0)
    if xs[-1] + sp["dk"] / 2 + 1.5 > leg:
        leg = xs[-1] + sp["dk"] / 2 + 1.5
        sp["warnings"].append("Leg lengthened to fit the last hole.")
    web = p["web"] if th <= 150 else "none"
    if th > 150 and p["web"] != "none":
        sp["warnings"].append("Webs disabled above 150°.")
    web_len = p["web_len"] if p["web_len"] > 0 else 0.6 * leg
    web_len = min(web_len, leg)
    if web == "full" and web_len > xs[0] - sp["dk"] / 2 - 0.5:
        sp["warnings"].append("Full web covers the first bolt head; shortened to clear it.")
        web_len = max(t + 1, xs[0] - sp["dk"] / 2 - 0.5)
    web_t = min(p["web_t"], (w - sp["dk"] - 1.0) / 2) if web == "sides" else p["web_t"]
    if web == "sides" and web_t < 1.2:
        sp["warnings"].append("Side webs too thin beside the bolt heads; disabled.")
        web = "none"
    sp.update(w=w, t=t, xs=xs, leg=leg, web=web, web_len=web_len, web_t=web_t, cb=cbore_depth(p, sp, t),
              rot=bracket_rot(p))
    if t < 4:
        sp["warnings"].append("Bracket legs under 4 mm; 5 mm recommended.")
    return sp


def build_bracket(p, sp, export=False):
    th, w, t, leg = sp["angle"], sp["w"], sp["t"], sp["leg"]
    Wt, Ht, Ln = sp["tongue_w"], sp["tongue_h"], sp["tn_ref_len"]

    def leg_solid():
        return box(0, leg, 0, t, -w / 2, w / 2)

    def leg_cutters():
        cs = []
        for x in sp["xs"]:
            cs.append(cq.Workplane("XZ").circle(sp["d_clear"] / 2).extrude(-(t + Ht + 3)).translate((x, -Ht - 1.5, 0)))
            if sp["cb"] > 0:
                cs.append(cq.Workplane("XZ").circle(sp["dk"] / 2 + 0.3).extrude(-(sp["cb"] + 1)).translate((x, t - sp["cb"], 0)))
        return cs

    def leg_tongue():
        x0, x1 = 1.0, leg - 1.5
        if not p["tongue"] or Ht < 0.05 or x1 - x0 < 3:
            return None
        tg = box(x0, x1, -Ht, EPS, -Wt / 2, Wt / 2)
        for x in sp["xs"]:
            tg = tg.cut(box(x - Ln / 2 - 0.5, x + Ln / 2 + 0.5, -Ht - 1, 1, -Wt, Wt))
        return tg

    # leg 1 on face 1 (y = 0), thickness +y ; leg 2 = mirror in y, rotated by angle
    l1 = leg_solid()
    l2 = rotz(leg_solid().mirror("XZ"), th)
    if th < 89.5:
        # acute corner: each leg stops at the other member's face
        sth, cth = math.sin(math.radians(th)), math.cos(math.radians(th))
        l1 = l1.intersect(halfspace(-sth, cth, 0))     # below the face-2 plane
        l2 = l2.intersect(halfspace(0, -1, 0))         # above face 1
    body = l1.union(l2)
    if sp["web"] != "none":
        gl = sp["web_len"]
        c, s_ = math.cos(math.radians(th)), math.sin(math.radians(th))
        tri = cq.Workplane("XY").polyline([(0, 0), (gl, 0), (gl * c, gl * s_)]).close()
        if sp["web"] == "full":
            body = body.union(tri.extrude(w).translate((0, 0, -w / 2)))
        else:
            wt = sp["web_t"]
            body = body.union(tri.extrude(wt).translate((0, 0, w / 2 - wt)))
            body = body.union(cq.Workplane("XY").polyline([(0, 0), (gl, 0), (gl * c, gl * s_)]).close()
                              .extrude(wt).translate((0, 0, -w / 2)))
    tg = leg_tongue()
    if tg is not None:
        body = body.union(tg).union(rotz(tg.mirror("XZ"), th))
    cutters = leg_cutters()
    cutters += [rotz(c.mirror("XZ"), th) for c in leg_cutters()]
    body = cut_all(body, cutters)
    if sp["rot"]:
        body = rotz(body, sp["rot"])
    return body


def bracket_rot(p):
    """Bracket rotation about the corner line, snapped to 90° steps."""
    return int(round(float(p["br_rot"]) / 90.0) * 90) % 360


def bracket_context(p, sp):
    g, th = sp["g"], sp["angle"]
    s = g["size"]
    L = p["member_len"]
    if th >= 179.5:                       # splice: two members end to end
        m1 = member_prism(g, 0.2, L).translate((0, -s / 2, 0))
        m2 = member_prism(g, -L, -0.2).translate((0, -s / 2, 0))
        ctx = m1.union(m2)
    else:
        # member 1 along X, its +Y face on y = 0, slot centred on z = 0
        m1 = member_prism(g, -L, L).translate((0, -s / 2, 0))
        # member 2 along `angle`, its face toward the corner on the plane at th
        m2 = member_prism(g, -2 * s, L).translate((0, s / 2, 0))
        m2 = rotz(m2, th).intersect(halfspace(0, -1, 0))   # y >= 0
        ctx = m1.union(m2)
    if sp["rot"]:
        ctx = rotz(ctx, sp["rot"])
    return ctx


# ---------------------------------------------------------------------
# END CAP (square-cut member end). z = 0 is the outer face and the print
# side; the plate is z in [0, t]; plugs run on into z > t; the member
# continues along +Z.
# ---------------------------------------------------------------------

def cap_spec(p):
    g = P.geometry(p)
    size = p["thread"]
    slot = slot_of(p)
    sp = {"g": g, "size": size, "slot": slot, "errors": [], "warnings": []}
    s = g["size"]
    t = p["cap_t"]
    ov = p["cap_oversize"]
    plan = s + 2 * ov
    cr = p["cap_corner_r"] if p["cap_corner_r"] > 0 else max(0.0, g["corner_r"] + ov)
    cr = min(cr, plan / 2 - 0.5)
    if p["cap_corner_r"] > 0 and cr < g["corner_r"] + ov - 1e-6:
        sp["warnings"].append(f"Corner radius under the profile's R{g['corner_r']:.1f} + oversize: the aluminium corner shows past the cap.")
    e = p["cap_edge_s"] if p["cap_edge"] != "none" else 0.0
    e = min(e, t - 0.8, plan / 4)
    if cr > 0.05 and e > cr - 0.2:
        # an edge break as large as the corner radius collapses the corner face
        e = cr - 0.2
        sp["warnings"].append(f"Edge break clipped to {e:.1f} mm (corner radius − 0.2); raise the corner radius for more.")
    if p["cap_edge"] != "none" and e < 0.2:
        e = 0.0
        sp["warnings"].append("Edge treatment dropped: the plate is too thin or the corners too tight for it.")
    if t < 1.2:
        sp["errors"].append("Cap under 1.2 mm thick.")
    if plan < 8:
        sp["errors"].append("Cap plan under 8 mm.")
    sp.update(t=t, plan=plan, cr=cr, e=e, ov=ov)

    # plugs: slot keys in the lips, optional tee head in the cavity, core plug
    grip = p["cap_grip"]
    L = p["cap_plug_len"]
    sp["key_w"] = g["opening"] - p["clear_neck"] + grip
    sp["key_h"] = max(0.6, g["lip"] - 0.3)
    sp["tee_w"] = g["cavity_w"] - p["clear_wide"]
    sp["tee_h"] = g["cavity_d"] - p["clear_depth"]
    plug = p["cap_plug"] if p["cap_plug"] in ("none", "keys", "tee") else "keys"
    if plug == "tee" and sp["tee_h"] < 1.2:
        sp["warnings"].append("Cavity too shallow for a tee plug; using keys.")
        plug = "keys"
    if plug != "none" and L < 2:
        sp["warnings"].append("Plugs under 2 mm long hold nothing; lengthen them.")
    sp["plug"] = plug
    sp["plug_len"] = L
    hole = p["cap_hole"] if p["cap_hole"] in ("none", "plain", "cbore", "csk") else "none"
    core = bool(p["cap_core"])
    if hole != "none" and core:
        core = False
        sp["warnings"].append("Core plug removed: the centre bolt goes into the core.")
    core_d = g["core"] - p["clear_hole"] + grip
    if core and core_d < 2.5:
        core = False
        sp["warnings"].append("Core plug under 2.5 mm; dropped.")
    sp["core"] = core
    sp["core_d"] = core_d
    if plug == "none" and not core and hole == "none":
        sp["warnings"].append("Nothing holds this cap on: add plugs or a centre bolt.")

    # centre bolt into the end-tapped core
    sp["hole"] = hole
    d_clear = F.CLEARANCE[size] + p["clear_hole"]
    sp["d_clear"] = d_clear
    dk, k, hexkey = F.SHCS[size]
    sp.update(dk=dk, k=k, hexkey=hexkey, cb=0.0, csk_d=0.0, csk_depth=0.0, protrude=0.0)
    if hole == "cbore":
        cb = min(k, t - 1.2)
        if cb < 0.5:
            cb = 0.0
            sp["warnings"].append("No room for a counterbore; plain hole, the head sits proud.")
        sp["cb"] = cb
        sp["protrude"] = max(0.0, k - cb)
        if sp["protrude"] > 0.05:
            sp["warnings"].append(f"Socket head stands {sp['protrude']:.1f} mm proud; thicken the cap or use a button head.")
    elif hole == "csk":
        dcs = F.CSK[size] + 0.4
        depth = (dcs - d_clear) / 2                      # 90° cone
        if depth > t - 1.0:
            depth = t - 1.0
            dcs = d_clear + 2 * depth
            sp["warnings"].append(f"Countersink clipped to {depth:.1f} mm; the flat head stands proud.")
        sp["csk_d"] = dcs
        sp["csk_depth"] = depth
    if hole != "none":
        if plan < dk + 4:
            sp["errors"].append("Cap too small for the bolt head.")
        tap = P.PROFILES.get(p["profile"], {}).get("tap")
        if tap and tap != size:
            sp["warnings"].append(f"Preset core Ø{g['core']:.1f} is the tap drill for M{tap}, not M{size}.")
        sp["tap_note"] = f"Tap the member end M{size} (core Ø{g['core']:.1f}); Ø{d_clear:.1f} clearance in the cap."
    # branding on the outer face
    sp["brand"] = None
    if p["brand_src"] in ("text", "svg"):
        mode = p["brand_mode"] if p["brand_mode"] in ("recess", "emboss", "through") else "recess"
        depth = p["brand_depth"]
        if mode == "recess" and depth > t - 0.8:
            depth = max(0.2, t - 0.8)
            sp["warnings"].append(f"Recess clipped to {depth:.1f} mm to leave 0.8 mm of plate.")
        if hole != "none":
            sp["warnings"].append("Branding sits over the centre bolt: offset it with X / Y or drop the hole.")
        if mode == "emboss":
            sp["warnings"].append("Embossed cap: print outer face up on supports, or use a recess.")
        sp["brand"] = dict(mode=mode, depth=depth, avail=plan - 2 * e - 2.0)
    sp["limit_note"] = (f"Keys {sp['key_w']:.2f} wide in a {g['opening']:.1f} slot (+{grip:.2f} grip): friction fit only. "
                        "A centre bolt into the tapped core makes the cap captive.")
    return sp


def rounded_rect(wx, wy, r, z0, z1):
    pl = cq.Workplane("XY").rect(wx, wy).extrude(z1 - z0).translate((0, 0, z0))
    if r > 0.05:
        pl = pl.edges("|Z").fillet(min(r, min(wx, wy) / 2 - 0.05))
    return pl


def rounded_plate(plan, cr, z0, z1):
    pl = cq.Workplane("XY").rect(plan, plan).extrude(z1 - z0).translate((0, 0, z0))
    if cr > 0.05:
        pl = pl.edges("|Z").fillet(cr)
    return pl


def build_cap(p, sp, export=False):
    g = sp["g"]
    s = g["size"]
    t, plan, cr, e = sp["t"], sp["plan"], sp["cr"], sp["e"]
    body = rounded_plate(plan, cr, 0, t)
    if e > 0.05:
        try:
            if p["cap_edge"] == "fillet":
                body = body.faces("<Z").edges().fillet(e)
            else:
                body = body.faces("<Z").edges().chamfer(e)
        except Exception:
            sp["warnings"].append("Edge treatment failed on this shape; plate left square.")
    if sp.get("brand"):
        body = brand_face(p, sp, body, sp["brand"]["avail"], sp["brand"]["avail"], 0.0, -1, t, mirror=True)
    L = sp["plug_len"]
    z0, z1 = t - EPS, t + L
    if sp["plug"] != "none" and L > 0.5:
        kw, kh = sp["key_w"], sp["key_h"]
        lead = min(0.5, kw * 0.25, L * 0.3)
        key = box(s / 2 - kh, s / 2 - 0.2, -kw / 2, kw / 2, z0, z1)
        try:
            key = key.faces(">Z").edges().chamfer(lead)
        except Exception:
            pass
        if sp["plug"] == "tee":
            tw, th_ = sp["tee_w"], sp["tee_h"]
            head = box(s / 2 - g["lip"] - th_, s / 2 - g["lip"] + EPS, -tw / 2, tw / 2, z0, z1)
            fc = min(g["floor_ch"] + 0.2, th_ * 0.4, tw * 0.2)
            if fc > 0.05:
                try:
                    head = head.edges("|Z and <X").chamfer(fc)
                except Exception:
                    pass
            try:
                head = head.faces(">Z").edges().chamfer(lead)
            except Exception:
                pass
            key = key.union(head)
        for q in range(4):
            body = body.union(rotz(key, 90 * q))
    if sp["core"] and L > 0.5:
        r = sp["core_d"] / 2
        plug = cyl(r, z0, z1)
        try:
            plug = plug.faces(">Z").chamfer(min(0.6, r * 0.4))
        except Exception:
            pass
        body = body.union(plug)
    if sp["hole"] != "none":
        cutters = [cyl(sp["d_clear"] / 2, -1, t + L + 1)]
        if sp["cb"] > 0:
            cutters.append(cyl(sp["dk"] / 2 + 0.3, -1, sp["cb"]))
        if sp["csk_d"] > 0:
            dcs, dep = sp["csk_d"], sp["csk_depth"]
            cone = (cq.Workplane("XY").circle(dcs / 2).workplane(offset=dep).circle(sp["d_clear"] / 2).loft()
                    .union(cyl(dcs / 2, -1, EPS)))
            cutters.append(cone)
        body = cut_all(body, cutters)
    return body


def cap_context(p, sp):
    g = sp["g"]
    L = p["member_len"]
    t = sp["t"]
    return roty(member_prism(g, t + 0.1, t + L), -90)      # +X -> +Z


def brand_face(p, sp, body, avail_w, avail_h, z_face, outward, thick, mirror=False, y_shift=0.0):
    """
    Recess / emboss / cut the branding artwork into a flat face of `body`.
    With `brand_dual` the artwork becomes its own solid (sp["brand_solid"])
    for a second filament: an inlay that fills the recess, raised letters
    standing on the face, or a full-thickness insert in a through cut.
    """
    br = sp["brand"]
    mode, depth = br["mode"], br["depth"]
    dual = bool(p["brand_dual"])
    try:
        art, info, warns = B.artwork(p, avail_w, avail_h, mirror=mirror,
                                     height=B.art_height(mode, depth, thick))
    except Exception as e:
        sp["warnings"].append(f"Branding failed: {e}")
        return body
    sp["warnings"] += warns
    sp["brand_info"] = info
    if art is None:
        return body
    if abs(y_shift) > 1e-9:
        art = art.translate(cq.Vector(0, y_shift, 0))
    try:
        if dual:
            # the second-filament body: exactly the branding volume, clipped to the face
            d = thick if mode == "through" else depth
            if mode == "emboss":
                z0, z1 = (z_face, z_face + d) if outward > 0 else (z_face - d, z_face)
            else:
                z0, z1 = (z_face - d, z_face) if outward > 0 else (z_face, z_face + d)
            placed = B.place(art, z_face, outward, mode, depth, thick)
            slab = cq.Workplane("XY").box(4000, 4000, z1 - z0, centered=(True, True, False)).translate((0, 0, z0))
            solid = cq.Workplane("XY").add(placed).intersect(slab)
            bits = [s for s in solid.solids().vals() if s.Volume() > 0.05]
            if not bits:
                raise RuntimeError("branding body is empty")
            sp["brand_solid"] = cq.Compound.makeCompound(bits)
            sp["brand_info"]["parts"] = len(bits)
            if mode == "emboss":
                return body                      # the base stays plain; the letters are the other part
        out = B.apply(body, art, z_face, outward, mode, depth, thick)
        n = out.solids().size()
        if n < 1 or not out.val().isValid():
            raise RuntimeError("boolean produced an invalid solid")
        if n > 1:
            # a through cut frees the counters of A, B, O...: keep the plate, drop the islands
            keep = max(out.solids().vals(), key=lambda s: s.Volume())
            out = cq.Workplane("XY").newObject([keep])
            if not dual:
                sp["warnings"].append(f"Through cut: {n - 1} enclosed island(s) dropped (letter counters). "
                                      "Use a recess, a stencil font, or bridges in the SVG to keep them.")
        return out
    except Exception as e:
        sp.pop("brand_solid", None)
        sp["warnings"].append(f"Branding failed: {e}")
        return body


def assembly(part, sp):
    """The part plus its second-filament branding body as one compound (stats, STEP)."""
    brand = sp.get("brand_solid")
    if brand is None:
        return part
    return cq.Workplane("XY").newObject([cq.Compound.makeCompound(part.solids().vals() + list(brand.Solids()))])


def tessellate(shape, tolerance=0.01, angular=0.1):
    """Indexed triangle mesh of a shape with vertices merged across faces
    (OCC tessellates face by face), so the mesh is closed as written."""
    verts, tris = shape.tessellate(tolerance, angular)
    index, out_v, remap = {}, [], []
    for v in verts:
        key = (round(v.x, 5), round(v.y, 5), round(v.z, 5))
        i = index.get(key)
        if i is None:
            i = len(out_v)
            index[key] = i
            out_v.append((v.x, v.y, v.z))
        remap.append(i)
    out_t = []
    for a, b, c in tris:
        a, b, c = remap[a], remap[b], remap[c]
        if a != b and b != c and a != c:
            out_t.append((a, b, c))
    return out_v, out_t


def stl_bytes(shape, tolerance=0.01, angular=0.1):
    """Binary STL of one shape (compounds included)."""
    import struct
    verts, tris = tessellate(shape, tolerance, angular)
    out = bytearray(b"SLOTLAB".ljust(80, b" "))
    out += struct.pack("<I", len(tris))
    for a, b, c in tris:
        p0, p1, p2 = verts[a], verts[b], verts[c]
        u = (p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2])
        v = (p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2])
        n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        ln = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2) or 1.0
        out += struct.pack("<12fH", n[0] / ln, n[1] / ln, n[2] / ln, *p0, *p1, *p2, 0)
    return bytes(out), len(tris)


def stl_merge(a, b):
    """Two binary STLs -> one; the triangles of `a` come first."""
    import struct
    na = struct.unpack("<I", a[80:84])[0]
    nb = struct.unpack("<I", b[80:84])[0]
    return a[:80] + struct.pack("<I", na + nb) + a[84:84 + 50 * na] + b[84:84 + 50 * nb]


def write_3mf(parts, title="part", tolerance=0.005, angular=0.05):
    """
    A standard 3MF (bytes) holding one build item made of several
    components, one per (name, shape): slicers such as Bambu Studio and
    PrusaSlicer open it as one object with one part per component, each
    of which can be given its own filament.
    """
    import io
    import zipfile
    from xml.sax.saxutils import escape
    xml = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<model unit="millimeter" xml:lang="en-US" '
           'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">',
           f'<metadata name="Title">{escape(title)}</metadata>',
           '<metadata name="Application">SLOTLAB</metadata>',
           '<resources>']
    ids = []
    for i, (name, shape) in enumerate(parts, start=1):
        verts, tris = tessellate(shape, tolerance, angular)
        xml.append(f'<object id="{i}" name="{escape(name)}" type="model"><mesh><vertices>')
        xml += [f'<vertex x="{x:.5f}" y="{y:.5f}" z="{z:.5f}"/>' for x, y, z in verts]
        xml.append('</vertices><triangles>')
        xml += [f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in tris]
        xml.append('</triangles></mesh></object>')
        ids.append(i)
    root = len(parts) + 1
    xml.append(f'<object id="{root}" name="{escape(title)}" type="model"><components>')
    xml += [f'<component objectid="{i}"/>' for i in ids]
    xml.append('</components></object></resources>')
    xml.append(f'<build><item objectid="{root}"/></build></model>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8"?>'
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
                   '</Types>')
        z.writestr("_rels/.rels",
                   '<?xml version="1.0" encoding="UTF-8"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Target="/3D/3dmodel.model" Id="rel0" '
                   'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>'
                   '</Relationships>')
        z.writestr("3D/3dmodel.model", "\n".join(xml))
    return buf.getvalue()


# ---------------------------------------------------------------------
# SIGN (name plate): w × h × t in the XY plane, show face at z = t.
# Mount: none; bolts into slide-in T-nuts (member along X under the
# plate, slot line at y = y_slot); or a slot key on the bottom edge
# (y = -h/2) that slides into a member whose face is the plane y = -h/2.
# ---------------------------------------------------------------------

def sign_spec(p):
    sp = joint_common(p)
    g = sp["g"]
    s = g["size"]
    w, h, t = p["sg_w"], p["sg_h"], p["sg_t"]
    if w < 10 or h < 8:
        sp["errors"].append("Sign under 10 × 8 mm.")
    if t < 1.5:
        sp["errors"].append("Sign under 1.5 mm thick.")
    cr = max(0.0, min(p["sg_corner_r"], min(w, h) / 2 - 0.5))
    e = p["sg_edge_s"] if p["sg_edge"] in ("chamfer", "fillet") else 0.0
    e = min(e, t - 1.0, min(w, h) / 4)
    if cr > 0.05 and e > cr - 0.2:
        e = cr - 0.2
    if e < 0.2:
        e = 0.0
    mount = p["sg_mount"] if p["sg_mount"] in ("none", "bolts", "slot") else "slot"
    sp.update(w=w, h=h, t=t, cr=cr, e=e, mount=mount)
    band_y0, band_y1 = -h / 2 + e + 1.0, h / 2 - e - 1.0
    x_lim = None
    if mount == "bolts":
        dk = sp["dk"]
        ears = p["sg_holes"] == "ears"
        where = p["sg_where"] if p["sg_where"] in ("bottom", "sides", "both") else "bottom"
        head_r = dk / 2 + 0.3                                    # counterbore radius
        er = head_r + max(1.5, p["sg_ear_wall"])                 # ear radius
        ov = 2.0                                                 # ear overlap into the plate
        margin = p["sg_margin"] if p["sg_margin"] > 0 else math.ceil((head_r + 1.5) * 2) / 2
        margin = max(head_r + 1.0, margin)
        n = max(1, p["holes"])
        pitch = p["hole_pitch"]
        bolts, rails = [], []
        if where == "sides":
            # one bolt at each end on a rail behind the centre line: the face stays free between them
            y0 = max(-h / 2 + 2.0, min(h / 2 - 2.0, p["sg_offset"]))
            rails = [y0]
            if ears:
                xe = w / 2 + er - ov
            else:
                inset = p["sg_inset"] if p["sg_inset"] > 0 else margin
                inset = max(head_r + 1.0, min(inset, w / 2 - head_r - 1.0))
                xe = w / 2 - inset
                x_lim = xe - head_r - 1.5
                if x_lim < 5:
                    sp["warnings"].append("Little room between the end bolts: widen the sign or use ears.")
            bolts = [(-xe, y0), (xe, y0)]
            if n != 2:
                sp["warnings"].append("Sides: one bolt at each end (2 bolts).")
        else:
            if ears:
                y_rows = [-h / 2 - er + ov] if where == "bottom" else [-h / 2 - er + ov, h / 2 + er - ov]
            else:
                margin = min(margin, h / 2 - 2.0)
                if where == "bottom":
                    y0 = p["sg_offset"] if abs(p["sg_offset"]) > 1e-6 else (-h / 2 + margin)
                    y_rows = [max(-h / 2 + 2.0, min(h / 2 - 2.0, y0))]
                else:
                    y_rows = [-h / 2 + margin, h / 2 - margin]
                    if 2 * margin + dk + 8 > h:
                        sp["warnings"].append("Two rails: the sign is too short for both rows of heads plus branding.")
            inset = p["sg_inset"] if p["sg_inset"] > 0 else (er + 1.0 if ears else 0.0)
            if inset > 0:
                inset = min(inset, w / 2 - (er if ears else head_r + 1.0))
                span = w - 2 * inset
                if n > 1 and span / (n - 1) < dk + 4:
                    n = max(2, int(span / (dk + 4)) + 1)
                    sp["warnings"].append(f"Only {n} bolts fit between the ends at this inset.")
                xs = [0.0] if n == 1 else [-span / 2 + span * i / (n - 1) for i in range(n)]
            else:
                if (n - 1) * pitch + dk + 6 > w:
                    n = max(1, int((w - dk - 6) / pitch) + 1)
                    sp["warnings"].append(f"Only {n} bolt(s) fit along {w:.0f} mm at this pitch.")
                xs = [(i - (n - 1) / 2) * pitch for i in range(n)]
            rails = y_rows
            bolts = [(x, y) for y in y_rows for x in xs]
            if not ears:
                # the free band for branding: beside one row of heads, or between two
                top, bot = y_rows[0] + dk / 2 + 1.5, y_rows[0] - dk / 2 - 1.5
                if len(y_rows) == 2:
                    band_y0, band_y1 = max(band_y0, y_rows[0] + dk / 2 + 1.5), min(band_y1, y_rows[1] - dk / 2 - 1.5)
                elif band_y1 - top >= bot - band_y0:
                    band_y0 = max(band_y0, top)
                else:
                    band_y1 = min(band_y1, bot)
                if band_y1 - band_y0 < 6:
                    sp["warnings"].append("Little room for branding beside the bolt heads: raise the sign height, use ears, or put the bolts at the sides.")
        sp.update(bolts=bolts, rails=rails, ears=ears, where=where, er=er, ov=ov,
                  cb=cbore_depth(p, sp, t), head_r=head_r)
        if t < 4:
            sp["warnings"].append("Bolted sign under 4 mm: little counterbore left for the heads.")
    elif mount == "slot":
        Wn = g["opening"] - p["clear_neck"]
        Wh = g["cavity_w"] - p["clear_wide"]
        Hh = g["cavity_d"] - p["clear_depth"]
        sp.update(Wn=Wn, Wh=Wh, Hh=Hh, kl=w - 6.0)
        if Hh < 1.6:
            sp["errors"].append("Cavity too shallow for the slot key.")
    centre = p["brand_align"] == "centre"
    if centre:
        band_y0, band_y1 = -h / 2 + e + 1.0, h / 2 - e - 1.0
    # border lip on the show face: a raised rim or a groove, inset from the edge
    lip = p["sg_lip"] if p["sg_lip"] in ("none", "raised", "groove") else "none"
    lip_h = lip_w = lip_in = 0.0
    if lip != "none":
        lip_h, lip_w, lip_in = max(0.2, p["sg_lip_h"]), max(0.6, p["sg_lip_w"]), max(0.0, p["sg_lip_inset"])
        lip_in = max(lip_in, e + 0.3)                       # clear of the edge break
        if lip_in + lip_w > min(w, h) / 4:
            lip_w = max(0.6, min(w, h) / 4 - lip_in)
            sp["warnings"].append(f"Lip narrowed to {lip_w:.1f} mm to leave a face inside it.")
        if lip == "groove" and lip_h > t - 0.8:
            lip_h = max(0.2, t - 0.8)
            sp["warnings"].append(f"Groove clipped to {lip_h:.1f} mm to leave 0.8 mm of plate.")
        keep = lip_in + lip_w + 1.0
        band_y0, band_y1 = max(band_y0, -h / 2 + keep), min(band_y1, h / 2 - keep)
    sp.update(lip=lip, lip_h=lip_h, lip_w=lip_w, lip_in=lip_in)
    avail_w = w - 2 * max(e + 1.0, lip_in + lip_w + 1.0 if lip != "none" else 0.0)
    if x_lim is not None:
        avail_w = min(avail_w, 2 * x_lim)
    sp.update(band=(band_y0, band_y1), avail_w=avail_w, centre=centre)
    sp["brand"] = None
    if p["brand_src"] in ("text", "svg"):
        mode = p["brand_mode"] if p["brand_mode"] in ("recess", "emboss", "through") else "recess"
        depth = p["brand_depth"]
        if mode == "recess" and depth > t - 0.8:
            depth = max(0.2, t - 0.8)
            sp["warnings"].append(f"Recess clipped to {depth:.1f} mm to leave 0.8 mm of plate.")
        sp["brand"] = dict(mode=mode, depth=depth)
        if centre and mount == "bolts" and not sp.get("ears") and sp.get("where") != "sides":
            sp["warnings"].append("Centred branding runs over the bolt heads: set a size, use ears, or the free band.")
    else:
        sp["warnings"].append("No branding yet: pick Text or SVG in the Branding group.")
    if mount == "slot":
        sp["limit_note"] = (f"Slot key: neck {sp['Wn']:.1f} in the {g['opening']:.1f} opening, head {sp['Wh']:.1f}×{sp['Hh']:.1f} "
                            f"in the cavity, slid in from the member end. Print standing on the key.")
    elif mount == "none":
        sp["limit_note"] = "Free plate: no mount. Print flat, show face up."
    return sp


def build_sign(p, sp, export=False):
    g = sp["g"]
    w, h, t, cr, e = sp["w"], sp["h"], sp["t"], sp["cr"], sp["e"]
    body = cq.Workplane("XY").rect(w, h).extrude(t)
    if cr > 0.05:
        body = body.edges("|Z").fillet(cr)
    if e > 0.05:
        try:
            if p["sg_edge"] == "fillet":
                body = body.faces(">Z").edges().fillet(e)
            else:
                body = body.faces(">Z").edges().chamfer(e)
        except Exception:
            sp["warnings"].append("Edge treatment failed; left square.")
    if sp["lip"] != "none":
        li, lw, lh = sp["lip_in"], sp["lip_w"], sp["lip_h"]
        ro = max(cr - li, 0.3)
        ri = max(ro - lw, 0.2)
        if sp["lip"] == "raised":
            ring = rounded_rect(w - 2 * li, h - 2 * li, ro, t - EPS, t + lh).cut(
                rounded_rect(w - 2 * (li + lw), h - 2 * (li + lw), ri, t - 1, t + lh + 1))
            body = body.union(ring)
        else:
            ring = rounded_rect(w - 2 * li, h - 2 * li, ro, t - lh, t + 1).cut(
                rounded_rect(w - 2 * (li + lw), h - 2 * (li + lw), ri, t - lh - 1, t + 2))
            body = body.cut(ring)
    if sp.get("brand"):
        y0, y1 = sp["band"]
        body = brand_face(p, sp, body, sp["avail_w"], y1 - y0, t, 1, t, mirror=False, y_shift=(y0 + y1) / 2)
    if sp["mount"] == "bolts":
        Wt, Ht, Ln = sp["tongue_w"], sp["tongue_h"], sp["tn_ref_len"]
        er = sp["er"]
        cutters = []
        if sp["ears"]:
            # D-shaped tab per bolt: a bridge from the edge to the hole centre plus a half-round beyond
            for x, y in sp["bolts"]:
                if sp["where"] == "sides":
                    sgn = -1 if x < 0 else 1
                    edge = sgn * w / 2
                    bridge = box(min(edge - sgn * 2.0, x), max(edge - sgn * 2.0, x), y - er, y + er, 0, t)
                else:
                    sgn = -1 if y < 0 else 1
                    edge = sgn * h / 2
                    bridge = box(x - er, x + er, min(edge - sgn * 2.0, y), max(edge - sgn * 2.0, y), 0, t)
                tab = cyl(er, 0, t, x=x, y=y).union(bridge)
                if e > 0.05:
                    try:
                        tab = tab.faces(">Z").edges().chamfer(min(e, er * 0.3))
                    except Exception:
                        pass
                body = body.union(tab)
        elif p["tongue"] and Ht > 0.05 and w - 3.0 > 3:
            for ys in sp["rails"]:
                tg = box(-w / 2 + 1.5, w / 2 - 1.5, ys - Wt / 2, ys + Wt / 2, -Ht, EPS)
                for x, y in sp["bolts"]:
                    if abs(y - ys) < 1e-6:
                        tg = tg.cut(box(x - Ln / 2 - 0.5, x + Ln / 2 + 0.5, ys - Wt, ys + Wt, -Ht - 1, 1))
                body = body.union(tg)
        for x, y in sp["bolts"]:
            cutters.append(cyl(sp["d_clear"] / 2, -Ht - 2, t + 1, x=x, y=y))
            if sp["cb"] > 0:
                cutters.append(cyl(sp["head_r"], t - sp["cb"], t + 1, x=x, y=y))
        body = cut_all(body, cutters)
    elif sp["mount"] == "slot":
        Wn, Wh, Hh, kl = sp["Wn"], sp["Wh"], sp["Hh"], sp["kl"]
        lip = g["lip"]
        zc = t / 2
        neck = box(-kl / 2, kl / 2, -h / 2 - lip - EPS, -h / 2 + EPS, zc - Wn / 2, zc + Wn / 2)
        head = box(-kl / 2, kl / 2, -h / 2 - lip - Hh, -h / 2 - lip + EPS, zc - Wh / 2, zc + Wh / 2)
        fc = min(g["floor_ch"] + 0.2, Hh * 0.4, Wh * 0.2)
        if fc > 0.05:
            try:
                head = head.edges("|X and <Y").chamfer(fc)
            except Exception:
                pass
        key = neck.union(head)
        lead = min(0.8, Hh * 0.3, Wn * 0.3)
        for sel in (">X", "<X"):
            try:
                key = key.faces(sel).chamfer(lead)
            except Exception:
                pass
        body = body.union(key)
    return body


def sign_context(p, sp):
    g = sp["g"]
    s = g["size"]
    L = max(p["member_len"], sp["w"] + 20.0)
    if sp["mount"] == "bolts":
        ctx = None
        for ys in sp["rails"]:
            m = member_prism(g, -L / 2, L / 2).translate((0, ys, -s / 2))
            ctx = m if ctx is None else ctx.union(m)
        return ctx
    if sp["mount"] == "slot":
        return member_prism(g, -L / 2, L / 2).translate((0, -sp["h"] / 2 - s / 2, sp["t"] / 2))
    return None


# ---------------------------------------------------------------------
# ACCESSORY: a base plate on the member face (z = 0, bolts into slide-in
# T-nuts, tongue in the slot) carrying a head out along +Z. "Along"
# means the hook tip / shelf normal points along the slot (+X): a
# vertical member with X up. "Across" turns the head toward +Y: a
# horizontal member with the slot facing you.
# ---------------------------------------------------------------------

ACC_TYPES = ("hook", "peg", "drivers", "hexkeys", "wrenches", "pliers", "tray", "clip")
RACKS = ("drivers", "hexkeys", "wrenches", "pliers", "tray")
RIB_T = 3.0
RIM_T = 2.0


def xz_poly(pts, y0, y1):
    """Polygon in the XZ plane ((x, z) points) extruded over y in [y0, y1]."""
    return (cq.Workplane("XZ").polyline(pts).close().extrude(-(y1 - y0))
            .translate((0, y0, 0)))


def yz_poly(pts, x0, x1):
    """Polygon in the YZ plane ((y, z) points) extruded over x in [x0, x1]."""
    return (cq.Workplane("YZ").polyline(pts).close().extrude(x1 - x0)
            .translate((x0, 0, 0)))


def acc_spec(p):
    sp = joint_common(p)
    g = sp["g"]
    s = g["size"]
    typ = p["acc_type"] if p["acc_type"] in ACC_TYPES else "hook"
    turn = "across" if p["acc_turn"] == "across" else "along"
    rack = typ in RACKS
    sp.update(type=typ, turn=turn, rack=rack)
    w = p["width"] if p["width"] > 0 else s
    t = p["thick"]
    reach, at = p["acc_reach"], p["acc_t"]
    dk = sp["dk"]
    sp.update(w=w, t=t, cb=cbore_depth(p, sp, t), reach=reach, at=at,
              tip=p["acc_tip"], bend_r=p["acc_bend_r"], root_r=p["acc_root_r"])
    if t < 4:
        sp["warnings"].append("Base under 4 mm; 5 mm recommended.")

    # --- head sizes ---------------------------------------------------
    rib = max(0.0, p["acc_rib"])
    if typ == "tray":
        # floor `at` thick, rim around, magnets let in from the top
        mag_d, mag_t = max(0.0, p["acc_mag_d"]), max(0.0, p["acc_mag_t"])
        if mag_d > 0 and at < mag_t + 1.0:
            at = mag_t + 1.0
            sp["at"] = at
            sp["warnings"].append(f"Floor thickened to {at:.1f} mm to keep 0.8 mm under the magnets.")
        hw = p["acc_w"] if p["acc_w"] > 0 else max(2 * w, 60.0)
        rim = max(2.0, p["acc_rim"])
        sp.update(hw=hw, rim=rim, mag_d=mag_d, mag_t=mag_t, n=0, ds=[], ys=[], pitch=0.0)
        if reach < 12:
            sp["errors"].append("Tray needs a reach of 12 mm or more.")
        if turn == "across":
            sp["warnings"].append("Across tray: print floor down with support under the base, or choose Along.")
        rib = 0.0                                   # nothing under the floor: it prints floor down
    elif rack:
        n = max(1, p["acc_n"])
        if typ == "hexkeys":
            keys = F.HEX_KEYS[:n]
            n = len(keys)
            ds = [F.across_corners(k) + 0.5 for k in keys]
            sp["hex_keys"] = keys
        elif typ == "pliers":
            gap = p["acc_d"]
            if gap < 10:
                sp["warnings"].append("Plier gap under 10 mm: thick handles will not pass.")
            ds = [gap]
        else:
            ds = [p["acc_d"]] * n
        auto = max(ds) + 6.0 if typ != "pliers" else max(24.0, max(ds) + 8.0)
        pitch = p["acc_pitch"] if p["acc_pitch"] > 0 else auto
        need = max(ds) + 3.0 if typ != "pliers" else 12.0
        if pitch < need:
            sp["warnings"].append(f"Pitch raised to {need:.1f} mm.")
            pitch = need
        if typ == "pliers":
            ys = [0.0]
            hw = p["acc_w"] if p["acc_w"] > 0 else n * pitch + 8.0
            hw = max(hw, 24.0)
            sp["win_len"] = hw - 12.0
            if reach < ds[0] + 11:
                sp["errors"].append(f"Reach must be at least gap + 11 = {ds[0] + 11:.0f} mm for the plier window.")
        else:
            ys = [(i - (n - 1) / 2) * pitch for i in range(n)]
            hw = p["acc_w"] if p["acc_w"] > 0 else (n - 1) * pitch + max(ds) + 8.0
            hw = max(hw, (n - 1) * pitch + max(ds) + 4.0)
        sp.update(n=n, ds=ds, pitch=pitch, ys=ys, hw=hw)
        if typ == "wrenches":
            depth = reach - 6.0
            sp["slot_depth"] = depth
            if depth < 6:
                sp["errors"].append("Wrench rack needs a reach of 12 mm or more.")
        elif typ != "pliers" and reach < max(ds) + 6:
            sp["errors"].append(f"Reach must be at least Ø + 6 = {max(ds) + 6:.1f} mm for the holes.")
        if at < 3:
            sp["warnings"].append("Shelf under 3 mm; 5-6 mm recommended.")
    elif typ == "clip":
        wire = "flat" if p["acc_wire"] == "flat" else "round"
        d = max(0.5, p["acc_wire_d"])
        cw = max(d, p["acc_wire_w"]) if wire == "flat" else d
        wall = max(1.0, p["acc_wall"])
        kind = p["acc_clip"] if p["acc_clip"] in ("snap", "loop", "comb") else "snap"
        snap = max(0.0, min(p["acc_snap"], cw * 0.3)) if kind == "snap" else 0.0
        n = max(1, p["acc_n"])
        pitch = p["acc_pitch"] if p["acc_pitch"] > 0 else cw + wall
        if pitch < cw + wall:
            sp["warnings"].append(f"Pitch raised to {cw + wall:.1f} mm so {wall:.1f} mm stays between the wires.")
            pitch = cw + wall
        ys = [(i - (n - 1) / 2) * pitch for i in range(n)]
        hw = p["acc_w"] if p["acc_w"] > 0 else w
        hw = max(hw, (n - 1) * pitch + cw + 2 * wall)
        H = wall + d + wall
        sp.update(n=n, pitch=pitch, ys=ys, hw=hw, wire=wire, wire_d=d, wire_w=cw, wall=wall,
                  clip=kind, snap=snap, reach=H, ds=[cw] * n)
        if kind == "snap" and snap < 0.2:
            sp["warnings"].append("Snap lip under 0.2 mm: the wire will not be retained; use Loop or raise the lip.")
        rib = 0.0
        sp["root_r"] = 0.0
    else:
        hw = p["acc_w"] if p["acc_w"] > 0 else w
        sp["hw"] = hw
        if hw > w + 1e-6:
            sp["warnings"].append("Head wider than the base: printing on its side needs support under the arm.")
        if reach < at + 2:
            sp["errors"].append("Reach too short for the arm thickness.")
        if typ == "hook" and sp["bend_r"] < 1:
            sp["errors"].append("Bend radius under 1 mm.")
        if turn == "across":
            rib = min(rib, max(0.0, w / 2 - at / 2 - 0.3))     # the rib has to stay on the base
    sp["rib"] = rib
    sp["rib_len"] = min(0.75 * reach, reach - 1.0) if rib > 0 else 0.0

    # --- layout along the base -----------------------------------------
    # bolts sit below the head (toward x = 0); the head takes the end of the
    # base. Hook / peg across: the arm spans hw along the base.
    hp = p["hole_pitch"]
    nh = max(1, p["holes"])
    if rack and turn == "across":
        off = p["hole_offset"] if p["hole_offset"] > 0 else RIB_T + dk / 2 + 1.5
        xs = [off + i * hp for i in range(nh)]
        base_len = max(hw, xs[-1] + dk / 2 + 1.5 + RIB_T, p["leg"])
        x_f0, x_f1 = 0.0, base_len
        need_w = 2 * (dk / 2 + 0.3 + at + 0.5)
        if w < need_w:
            w = math.ceil(need_w)
            sp["w"] = w
            sp["warnings"].append(f"Base widened to {w:.0f} mm so the bolt heads clear the shelf (it overhangs the face).")
        rib_y = min(rib, w - at - 0.5)
        sp["rib_y"] = rib_y
        sp["hw"] = base_len
    else:
        off = p["hole_offset"] if p["hole_offset"] > 0 else max(dk / 2 + 2.0, 6.0)
        xs = [off + i * hp for i in range(nh)]
        rib_x = rib if (rack or turn == "along") else 0.0
        foot = at if (rack or turn == "along") else hw
        x_f0 = xs[-1] + dk / 2 + 1.5 + rib_x
        x_f1 = x_f0 + foot
        if typ == "tray":
            tail = sp["rim"]                       # the base runs on as the tray's back wall
        elif rack or typ == "clip":
            tail = 0.0 if rack else 1.5
        else:
            tail = sp["root_r"] + 1.5
        base_len = x_f1 + tail
        if p["leg"] > base_len:
            base_len = p["leg"]
            if rack:                               # the shelf closes the top end
                x_f1, x_f0 = base_len - tail, base_len - tail - foot
        elif p["leg"] > 0:
            sp["warnings"].append(f"Base lengthened to {base_len:.0f} mm to fit the bolts and the head.")
    sp.update(xs=xs, base_len=base_len, x_f0=x_f0, x_f1=x_f1)
    if typ == "tray":
        sp["mags"] = tray_magnets(sp)
    return sp


def tray_magnets(sp):
    """Magnet pocket centres (u, v) on the floor: u across the floor's
    width, v from the base face outward."""
    md = sp["mag_d"]
    if md <= 0:
        return []
    t, reach, hw = sp["t"], sp["reach"], sp["hw"]
    pitch = max(sp["pitch"] if sp["pitch"] > 0 else 0.0, md + 3.0)
    u0, u1 = -hw / 2 + RIM_T + 1.5 + md / 2, hw / 2 - RIM_T - 1.5 - md / 2
    v0, v1 = t + 2.0 + md / 2, t + reach - RIM_T - 1.5 - md / 2
    if u1 < u0 or v1 < v0:
        return []
    cols = int((u1 - u0) / pitch) + 1
    rows = int((v1 - v0) / pitch) + 1
    us = [(u0 + u1) / 2 + (i - (cols - 1) / 2) * pitch for i in range(cols)]
    vs = [(v0 + v1) / 2 + (j - (rows - 1) / 2) * pitch for j in range(rows)]
    return [(u, v) for v in vs for u in us]


def acc_head_profile(sp):
    """J-hook or peg as an XZ polygon list, arm centred on x = 0 standing on z = t."""
    t, reach, at = sp["t"], sp["reach"], sp["at"]
    zr = t + reach
    if sp["type"] == "hook":
        ri = sp["bend_r"]
        ro = ri + at
        cx, cz = at / 2 + ri, zr
        tip = max(0.0, sp["tip"])
        c45 = math.cos(math.radians(45))
        wp = (cq.Workplane("XZ").moveTo(-at / 2, t - EPS).lineTo(at / 2, t - EPS).lineTo(at / 2, zr)
              .threePointArc((cx - ri * c45, cz + ri * c45), (cx, cz + ri)))
        if tip > 0.05:
            wp = wp.lineTo(cx + tip, cz + ri).lineTo(cx + tip, cz + ro)
        wp = (wp.lineTo(cx, cz + ro).threePointArc((cx - ro * c45, cz + ro * c45), (-at / 2, zr)).close())
        return wp
    lip = min(max(0.0, sp["tip"]), 6.0)
    lt = min(3.0, reach * 0.3)
    pts = [(-at / 2, t - EPS), (at / 2, t - EPS), (at / 2, zr - lt), (at / 2 + lip, zr - lt),
           (at / 2 + lip, zr), (-at / 2, zr)]
    return cq.Workplane("XZ").polyline(pts).close()


def acc_build_head(sp):
    """Hook / peg head in the along frame (tip toward +X), arm centred on x = 0."""
    t, at, hw, rib, rr = sp["t"], sp["at"], sp["hw"], sp["rib"], sp["root_r"]
    head = acc_head_profile(sp).extrude(-hw).translate((0, -hw / 2, 0))
    if sp["type"] == "hook":
        try:
            head = head.edges("|Y").edges(">X").fillet(min(at / 2 - 0.1, 1.5))
        except Exception:
            pass
    if rib > 0.1 and sp["rib_len"] > 1:
        head = head.union(xz_poly([(-at / 2 + EPS, t - EPS), (-at / 2 + EPS, t + sp["rib_len"]),
                                   (-at / 2 - rib, t - EPS)], -hw / 2, hw / 2))
    if rr > 0.2:
        c45 = math.cos(math.radians(45))
        cove = (cq.Workplane("XZ").moveTo(at / 2 - EPS, t - EPS).lineTo(at / 2 + rr, t - EPS).lineTo(at / 2 + rr, t)
                .threePointArc((at / 2 + rr - rr * c45, t + rr - rr * c45), (at / 2, t + rr))
                .lineTo(at / 2 - EPS, t + rr).close().extrude(-hw).translate((0, -hw / 2, 0)))
        head = head.union(cove)
    return head


def acc_build_clip(sp):
    """Wire clip block in the along frame: wires run along X through a
    block x in [-at/2, at/2], channels side by side along Y."""
    t, at, hw = sp["t"], sp["at"], sp["hw"]
    wall, snap, kind = sp["wall"], sp["snap"], sp["clip"]
    d, cw = sp["wire_d"], sp["wire_w"]
    H = wall + d + wall
    blk = box(-at / 2, at / 2, -hw / 2, hw / 2, t - EPS, t + H)
    try:
        blk = blk.edges("|X").edges(">Z").fillet(min(1.0, wall * 0.4))
    except Exception:
        pass
    cutters = []
    zc = t + wall + d / 2
    for yc in sp["ys"]:
        if sp["wire"] == "round":
            ch = cq.Workplane("YZ").circle(d / 2).extrude(at + 2).translate((-at / 2 - 1, yc, zc))
        else:
            ch = box(-at / 2 - 1, at / 2 + 1, yc - cw / 2, yc + cw / 2, zc - d / 2, zc + d / 2)
            try:
                ch = ch.edges("|X").fillet(min(d / 2 - 0.1, 1.0))
            except Exception:
                pass
        if kind != "loop":
            o = max(cw - 2 * snap, cw * 0.4) if kind == "snap" else cw
            mouth = box(-at / 2 - 1, at / 2 + 1, yc - o / 2, yc + o / 2, zc, t + H + 1)
            flare = yz_poly([(yc - o / 2, t + H - 1.0), (yc + o / 2, t + H - 1.0),
                             (yc + o / 2 + 1.0, t + H + EPS), (yc - o / 2 - 1.0, t + H + EPS)],
                            -at / 2 - 1, at / 2 + 1)
            ch = ch.union(mouth).union(flare)
        cutters.append(ch)
    return cut_all(blk, cutters)


def build_acc(p, sp, export=False):
    g = sp["g"]
    w, t, bl = sp["w"], sp["t"], sp["base_len"]
    reach, at, hw = sp["reach"], sp["at"], sp["hw"]
    typ, turn = sp["type"], sp["turn"]
    Wt, Ht, Ln = sp["tongue_w"], sp["tongue_h"], sp["tn_ref_len"]

    body = box(0, bl, -w / 2, w / 2, 0, t)
    try:
        body = body.edges("|Z").fillet(min(2.0, w / 4, bl / 4))
    except Exception:
        pass

    if not sp["rack"]:
        head = acc_build_clip(sp) if typ == "clip" else acc_build_head(sp)
        if turn == "along":
            head = head.translate((sp["x_f0"] + at / 2, 0, 0))
        else:
            head = rotz(head, 90).translate((sp["x_f0"] + hw / 2, 0, 0))
        body = body.union(head)
    elif turn == "along":
        x0, x1 = sp["x_f0"], sp["x_f1"]
        shelf = box(x0, x1, -hw / 2, hw / 2, t - EPS, t + reach)
        if typ != "tray":
            try:
                shelf = shelf.edges("|X").edges(">Z").fillet(min(1.5, at / 3))
            except Exception:
                pass
        body = body.union(shelf)
        if sp["rib"] > 0.1:
            yr = min(hw, w) / 2 - RIB_T / 2
            ribs_y = [-yr, yr] + ([0.0] if hw > 2.2 * w else [])
            for yc in ribs_y:
                body = body.union(xz_poly([(x0 + EPS, t - EPS), (x0 + EPS, t + sp["rib_len"]),
                                           (x0 - sp["rib"], t - EPS)], yc - RIB_T / 2, yc + RIB_T / 2))
        cutters = []
        if typ == "tray":
            rim = sp["rim"]
            parts = [box(x1 - EPS, x1 + rim, -hw / 2, hw / 2, t + reach - RIM_T, t + reach),
                     box(x1 - EPS, x1 + rim, -hw / 2, -hw / 2 + RIM_T, t - EPS, t + reach),
                     box(x1 - EPS, x1 + rim, hw / 2 - RIM_T, hw / 2, t - EPS, t + reach)]
            if hw > w + 0.5:                      # back rim beside the base, which is the back wall
                parts += [box(x1 - EPS, x1 + rim, w / 2 - EPS, hw / 2, t - EPS, t + RIM_T),
                          box(x1 - EPS, x1 + rim, -hw / 2, -w / 2 + EPS, t - EPS, t + RIM_T)]
            gh = min(rim, 8.0)
            yr = min(hw / 2 - RIM_T, w / 2) - RIB_T / 2
            for yc in (-yr, yr):
                parts.append(xz_poly([(x1 - EPS, t - EPS), (x1 + gh, t - EPS), (x1 - EPS, t + gh)],
                                     yc - RIB_T / 2, yc + RIB_T / 2))
            for q in parts:
                body = body.union(q)
            rm, dm = sp["mag_d"] / 2 + 0.15, sp["mag_t"] + 0.2
            for u, v in sp["mags"]:
                cutters.append(cq.Workplane("YZ").circle(rm).extrude(dm + 1).translate((x1 - dm, u, v)))
        elif typ == "pliers":
            d, wl = sp["ds"][0], sp["win_len"]
            zb = t + reach - 5.0 - d
            win = box(x0 - 1, x1 + 1, -wl / 2, wl / 2, zb, zb + d)
            try:
                win = win.edges("|X").fillet(min(d / 2 - 0.1, 3.0))
            except Exception:
                pass
            cutters.append(win)
        else:
            for yc, d in zip(sp["ys"], sp["ds"]):
                if typ == "wrenches":
                    zb = t + reach - sp["slot_depth"] + d / 2
                    cutters.append(box(x0 - 1, x1 + 1, yc - d / 2, yc + d / 2, zb, t + reach + 1)
                                   .union(cq.Workplane("YZ").circle(d / 2).extrude(at + 2).translate((x0 - 1, yc, zb))))
                else:
                    zc = t + reach - d / 2 - 3.0
                    hole = cq.Workplane("YZ").circle(d / 2).extrude(at + 2).translate((x0 - 1, yc, zc))
                    lead = (cq.Workplane("YZ").workplane(offset=x1 - 0.6).circle(d / 2)
                            .workplane(offset=0.6 + EPS).circle(d / 2 + 0.6).loft().translate((0, yc, zc)))
                    cutters.append(hole.union(lead))
        body = cut_all(body, cutters)
    else:
        # across rack: shelf along the top edge of the base, ribs at its ends
        y0 = w / 2 - at
        shelf = box(0, bl, y0, w / 2, t - EPS, t + reach)
        if typ != "tray":
            try:
                shelf = shelf.edges("|Y").edges(">Z").fillet(min(1.5, at / 3))
            except Exception:
                pass
        body = body.union(shelf)
        if sp["rib"] > 0.1 and sp["rib_y"] > 0.5:
            for xr in (0.0, bl - RIB_T):
                body = body.union(yz_poly([(y0 + EPS, t - EPS), (y0 + EPS, t + sp["rib_len"]),
                                           (y0 - sp["rib_y"], t - EPS)], xr, xr + RIB_T))
        cutters = []
        if typ == "tray":
            rim = sp["rim"]
            parts = [box(0, bl, w / 2 - EPS, w / 2 + rim, t + reach - RIM_T, t + reach),
                     box(0, RIM_T, w / 2 - EPS, w / 2 + rim, t - EPS, t + reach),
                     box(bl - RIM_T, bl, w / 2 - EPS, w / 2 + rim, t - EPS, t + reach),
                     box(0, bl, w / 2 - EPS, w / 2 + rim, t - EPS, t + RIM_T)]
            for q in parts:
                body = body.union(q)
            rm, dm = sp["mag_d"] / 2 + 0.15, sp["mag_t"] + 0.2
            for u, v in sp["mags"]:
                cutters.append(cq.Workplane("XZ").circle(rm).extrude(-(dm + 1)).translate((bl / 2 + u, w / 2 - dm, v)))
        elif typ == "pliers":
            d, wl = sp["ds"][0], sp["win_len"]
            zb = t + reach - 5.0 - d
            win = box(bl / 2 - wl / 2, bl / 2 + wl / 2, y0 - 1, w / 2 + 1, zb, zb + d)
            try:
                win = win.edges("|Y").fillet(min(d / 2 - 0.1, 3.0))
            except Exception:
                pass
            cutters.append(win)
        else:
            for yc, d in zip(sp["ys"], sp["ds"]):
                xc = bl / 2 + yc
                if typ == "wrenches":
                    zb = t + reach - sp["slot_depth"] + d / 2
                    cutters.append(box(xc - d / 2, xc + d / 2, y0 - 1, w / 2 + 1, zb, t + reach + 1)
                                   .union(cq.Workplane("XZ").circle(d / 2).extrude(-(at + 2)).translate((xc, y0 - 1, zb))))
                else:
                    zc = t + reach - d / 2 - 3.0
                    hole = cq.Workplane("XZ").circle(d / 2).extrude(-(at + 2)).translate((xc, y0 - 1, zc))
                    lead = (cq.Workplane("XZ").workplane(offset=-(w / 2 - 0.6)).circle(d / 2)
                            .workplane(offset=-(0.6 + EPS)).circle(d / 2 + 0.6).loft().translate((xc, 0, zc)))
                    cutters.append(hole.union(lead))
        body = cut_all(body, cutters)

    # tongue and bolts, shared by every head
    if p["tongue"] and Ht > 0.05 and bl - 2.5 > 3:
        tg = box(1.0, bl - 1.5, -Wt / 2, Wt / 2, -Ht, EPS)
        for x in sp["xs"]:
            tg = tg.cut(box(x - Ln / 2 - 0.5, x + Ln / 2 + 0.5, -Wt, Wt, -Ht - 1, 1))
        body = body.union(tg)
    cutters = []
    for x in sp["xs"]:
        cutters.append(cyl(sp["d_clear"] / 2, -Ht - 2, t + 1, x=x))
        if sp["cb"] > 0:
            cutters.append(cyl(sp["dk"] / 2 + 0.3, t - sp["cb"], t + 1, x=x))
    body = cut_all(body, cutters)
    return body.translate((-bl / 2, 0, 0))        # base centred on the member stub


def acc_context(p, sp):
    g = sp["g"]
    s = g["size"]
    L = max(p["member_len"], 120.0)
    return member_prism(g, -L / 2, L / 2).translate((0, 0, -s / 2))


# ---------------------------------------------------------------------
# SPLICE (inline extension of two members). Members along X on the
# origin axis, joint plane x = 0. Sleeve: wraps 1-4 faces of both
# members, keys in the slot openings, bolts into slide-in T-nuts each
# side. Bar: a long slide-in T-nut body spanning the joint; grub screws
# through the opening press the cavity floor and jam it under the lips.
# ---------------------------------------------------------------------

def splice_spec(p):
    sp = joint_common(p)
    g = sp["g"]
    s = g["size"]
    kind = p["sp_kind"] if p["sp_kind"] in ("sleeve", "bar") else "sleeve"
    sp["kind"] = kind
    n = max(1, p["holes"])
    pitch = p["hole_pitch"]
    dk = sp["dk"]
    Ln = sp["tn_ref_len"]
    lim = P.SLOT_LIMITS.get(sp["slot"], {})
    if kind == "sleeve":
        T, fit = p["sp_t"], max(0.0, p["sp_fit"])
        faces = min(4, max(1, p["sp_faces"]))
        off = p["hole_offset"] if p["hole_offset"] > 0 else Ln / 2 + 3.0
        xs = [off + i * pitch for i in range(n)]
        half = xs[-1] + dk / 2 + 4.0
        L = p["sp_len"] if p["sp_len"] > 0 else 2 * half
        if L < 2 * half:
            sp["warnings"].append(f"Sleeve lengthened to {2 * half:.0f} mm for the bolts.")
            L = 2 * half
        sp.update(T=T, fit=fit, faces=faces, xs=xs, L=L, cb=cbore_depth(p, sp, T))
        if T < 3:
            sp["warnings"].append("Sleeve wall under 3 mm; 4 mm recommended.")
        sp["limit_note"] = (f"Sleeve on {faces} face(s): {2 * n * faces} × M{sp['size']} into slide-in T-nuts (slide them in "
                            f"from the ends before closing the joint). Torque ≤ {lim.get('torque_nm', '?')} Nm.")
    else:
        size = sp["size"]
        Hh = g["cavity_d"] - p["clear_depth"]
        Wh = g["cavity_w"] - p["clear_wide"]
        Wn = g["opening"] - p["clear_neck"]
        Hn = max(0.0, min(g["lip"] - 0.2, 1.8))
        fix = p["sp_fix"] if p["sp_fix"] in ("hex", "thread") else "hex"
        off = p["hole_offset"] if p["hole_offset"] > 0 else 8.0
        xs = [off + i * pitch for i in range(n)]
        half = xs[-1] + 8.0
        L = p["sp_len"] if p["sp_len"] > 0 else max(2 * half, 60.0)
        if L < 2 * half:
            sp["warnings"].append(f"Bar lengthened to {2 * half:.0f} mm for the screws.")
            L = 2 * half
        sp.update(Hh=Hh, Wh=Wh, Wn=Wn, Hn=Hn, xs=xs, L=L, fix=fix)
        if Hh < 1.6:
            sp["errors"].append("Cavity too shallow for a bar.")
        if fix == "hex":
            nut = p["tn_nut"]
            af, m = F.NUTS[nut]["t"][size]
            if Hh - (m + p["clear_depth"]) - 0.3 < 0.6 and nut != "thin":
                af, m = F.NUTS["thin"]["t"][size]
                if Hh - (m + p["clear_depth"]) - 0.3 >= 0.6:
                    nut = "thin"
                    sp["warnings"].append(f"Thin nut (DIN 439) used: the {F.NUTS[p['tn_nut']]['label']} does not fit under the lips.")
            sp["nut"] = nut
            af_p = af + p["clear_hex"]
            h_p = m + p["clear_depth"]
            sp.update(af=af, af_p=af_p, ac_p=F.across_corners(af_p), h_p=h_p)
            wall_side = (Wh - af_p) / 2
            ceiling = Hh - h_p - 0.3
            sp.update(wall_side=wall_side, ceiling=ceiling)
            if ceiling < 0.6:
                sp["errors"].append(f"Only {ceiling:.2f} mm above the nut; use a thin nut or a smaller screw.")
            if wall_side < 0.8:
                sp["errors"].append(f"Side wall beside the nut is {wall_side:.2f} mm (min 0.8).")
            if size > Wn - 1.0:
                sp["warnings"].append(f"M{size} is wide for the {g['opening']:.1f} slot opening the screw passes through.")
        else:
            st = F.thread_status(size)
            if st == "no":
                sp["errors"].append(f"A printed M{size} thread falls under the extrusion width; use a captive nut.")
            elif st == "warn":
                sp["warnings"].append("Printed M5: print at 0.10-0.12 mm layers and tap-chase it.")
            sp["wall_side"] = (Wh - (size + 2 * p["clear_thread"])) / 2
            if sp["wall_side"] < 1.0:
                sp["errors"].append(f"Wall beside the thread is {sp['wall_side']:.2f} mm (min 1.0).")
        sp["limit_note"] = (f"Bar in one slot, {2 * n} × M{size} grub screws through the opening press the cavity "
                            f"floor and jam it under the lips: friction only, torque ≤ {min(lim.get('torque_nm', 3), 3):.0f} Nm. "
                            "Use one bar per slot, or add a sleeve for a load-bearing splice.")
    return sp


FACE_ROT = {1: [0], 2: [0, -90], 3: [0, -90, 90], 4: [0, -90, 90, 180]}   # rotations about X: top, +Y, -Y, bottom


def build_splice(p, sp, export=False):
    g = sp["g"]
    s = g["size"]
    L = sp["L"]
    if sp["kind"] == "sleeve":
        T, fit, faces = sp["T"], sp["fit"], sp["faces"]
        a = s / 2 + fit                         # bore half-size
        ro, ri = g["corner_r"] + fit + T, g["corner_r"] + fit
        outer = box(-L / 2, L / 2, -a - T, a + T, -a - T, a + T)
        if ro > 0.05:
            outer = outer.edges("|X").fillet(ro)
        inner = box(-L / 2 - 1, L / 2 + 1, -a, a, -a, a)
        if ri > 0.05:
            inner = inner.edges("|X").fillet(ri)
        body = outer.cut(inner)
        big = 3 * s
        if faces == 1:
            body = body.cut(box(-L, L, -big, big, -big, a))
        elif faces == 2:
            body = body.cut(box(-L, L, -big, a, -big, a))
        elif faces == 3:
            body = body.cut(box(-L, L, -a, a, -big, a))
        Wt, Ht, Ln = sp["tongue_w"], sp["tongue_h"], sp["tn_ref_len"]
        kw, kh = Wt, max(0.6, g["lip"] - 0.3)
        feats, keys = [], []
        for x in sp["xs"]:
            for sx in (-1, 1):
                feats.append(cyl(sp["d_clear"] / 2, a - 1, a + T + 1, x=sx * x))
                if sp["cb"] > 0:
                    feats.append(cyl(sp["dk"] / 2 + 0.3, a + T - sp["cb"], a + T + 1, x=sx * x))
        if p["tongue"] and g["lip"] >= 0.9:
            key = box(-L / 2 + 1.0, L / 2 - 1.0, -kw / 2, kw / 2, s / 2 - kh, a + EPS)
            for x in sp["xs"]:
                for sx in (-1, 1):
                    key = key.cut(box(sx * x - Ln / 2 - 0.5, sx * x + Ln / 2 + 0.5, -kw, kw, s / 2 - kh - 1, a + 1))
            key = key.cut(box(-1.0, 1.0, -kw, kw, s / 2 - kh - 1, a + 1))      # clear of the joint line
            keys.append(key)
        cutters = []
        for rot in FACE_ROT[faces]:
            cutters += [rotx(f, rot) for f in feats]
            for k in keys:
                body = body.union(rotx(k, rot))
        body = cut_all(body, cutters)
        return body
    # bar
    Hh, Wh, Wn, Hn = sp["Hh"], sp["Wh"], sp["Wn"], sp["Hn"]
    head = box(-L / 2, L / 2, -Wh / 2, Wh / 2, 0, Hh)
    fc = min(g["floor_ch"] + 0.2, Hh * 0.4, Wh * 0.2)
    if fc > 0.05:
        head = head.edges("|X and <Z").chamfer(fc)
    lead = min(1.0, Hh * 0.3, Wh * 0.2)
    try:
        head = head.edges("|Z").chamfer(lead)
    except Exception:
        pass
    body = head
    if Hn > 0:
        body = body.union(box(-L / 2 + lead, L / 2 - lead, -Wn / 2, Wn / 2, Hh - EPS, Hh + Hn))
    Htot = Hh + Hn + 1
    cutters = []
    for x0 in sp["xs"]:
        for sx in (-1, 1):
            x = sx * x0
            if sp["fix"] == "hex":
                rt = 0.3
                h_p = sp["h_p"]
                pocket = hex_prism(sp["af_p"], rt, rt + h_p, p["tn_corner_r"]) \
                    .union(hex_prism(sp["af_p"] - 2 * rt, -1, rt + EPS, p["tn_corner_r"]))
                cutters.append(pocket.translate((x, 0, 0)))
                cutters.append(cyl(sp["d_clear"] / 2, -1, Htot, x=x))
            else:
                if export or p["tn_thread_preview"]:
                    groove, r_minor = thread_groove(sp["size"], Htot, p["clear_thread"])
                    v0 = body.val().Volume()
                    body = body.cut(groove.translate((x, 0, 0)))
                    if body.val().Volume() > v0 - 1.0:
                        raise RuntimeError("thread groove boolean failed; try a different clearance")
                    cutters.append(cyl(r_minor + 0.03, -1, Htot, x=x))
                else:
                    cutters.append(cyl(F.minor_d(sp["size"]) / 2 + p["clear_thread"], -1, Htot, x=x))
    return cut_all(body, cutters)


def splice_context(p, sp):
    g = sp["g"]
    s = g["size"]
    L = max(p["member_len"], sp["L"] / 2 + 20.0)
    ctx = member_prism(g, -L, -0.3).union(member_prism(g, 0.3, L))
    if sp["kind"] == "bar":
        ctx = ctx.translate((0, 0, -(s / 2 - g["lip"]) + sp["Hh"]))
    return ctx


# ---------------------------------------------------------------------
# PIVOT (movable joint). Plate-family frame: members in the XY plane,
# top faces at z = 0, pivot axis Z through the origin, both members
# square-cut `setback` from it. Leaf A bolts to member 1 (+X) and
# carries the lower lug with the nut captive underneath; leaf B bolts to
# member 2 (at `angle`), its arm steps up over lug A to the upper lug.
# Bolt from the top: a knob there is a friction lock; `arc` adds a second
# bolt in lug A riding in an arc slot in lug B for a positive lock.
# ---------------------------------------------------------------------

def pivot_min_angle(s, d, D, x_rise, wa):
    """Smallest interior angle before member 2 or arm B runs into member 1
    or arm A (degrees, 1° steps)."""
    def rect_hit(pts, x0, x1, y0, y1):
        return any(x0 < x < x1 and y0 < y < y1 for x, y in pts)
    m2 = [(d, (i / 8 - 0.5) * s) for i in range(9)] + [(d + 2 * s * i / 16, -s / 2) for i in range(17)]
    b2 = [(x_rise + (d + 1 - x_rise) * i / 8, -wa / 2) for i in range(9)] + [(x_rise, (i / 8 - 0.5) * wa) for i in range(9)]
    last = 180
    for th in range(180, 4, -1):
        c, s_ = math.cos(math.radians(th)), math.sin(math.radians(th))
        r = lambda q: (q[0] * c - q[1] * s_, q[0] * s_ + q[1] * c)
        if rect_hit([r(q) for q in m2], d, d + 3 * s, -s / 2, s / 2):
            break
        if rect_hit([r(q) for q in b2], 0, d + 1, -wa / 2, wa / 2):
            break
        last = th
    return float(last)


def pivot_spec(p):
    sp = joint_common(p)
    g = sp["g"]
    s = g["size"]
    th = sp["angle"]
    size = sp["size"]
    w = min(p["width"] if p["width"] > 0 else s, s)
    t = p["thick"]
    d_clear, dk = sp["d_clear"], sp["dk"]
    lock = p["pv_lock"] if p["pv_lock"] in ("none", "arc") else "none"
    af, m = F.NUTS[p["tn_nut"]]["t"][size]
    af_p = af + p["clear_hex"]
    ac_p = F.across_corners(af_p)
    h_p = m + p["clear_depth"]
    bore = d_clear + max(0.0, p["pv_clear"])
    if lock == "arc":
        R_min = bore / 2 + ac_p / 2 + 1.5
        D_min = 2 * (R_min + bore / 2 + 2.5)
    else:
        D_min = max(3.0 * size, dk + 6.0, ac_p + 4.0)
    D = p["pv_lug_d"] if p["pv_lug_d"] > 0 else D_min
    if D < D_min - 1e-6:
        sp["warnings"].append(f"Lug widened to Ø{D_min:.0f} for the nut pocket{' and the arc slot' if lock == 'arc' else ''}.")
        D = D_min
    if p["pv_knob"] > D + 1e-6:
        sp["warnings"].append(f"A Ø{p['pv_knob']:.0f} knob overhangs the Ø{D:.0f} lug; widen the lug for a flat seat.")
    R = D / 2 - bore / 2 - 2.5 if lock == "arc" else 0.0
    hA = max(t, h_p + 1.8)
    hB = t
    gap = max(0.0, p["pv_gap"])
    wa = min(D, w)
    setback = p["pv_setback"] if p["pv_setback"] > 0 else max(D / 2 + 2.0, s / 2 + 2.0)
    if setback < D / 2 + 1.0:
        sp["warnings"].append(f"Setback raised to {D / 2 + 1.0:.0f} mm so the lugs clear the member ends.")
        setback = D / 2 + 1.0
    Ln = sp["tn_ref_len"]
    off = p["hole_offset"] if p["hole_offset"] > 0 else Ln / 2 + 1.0
    n = max(1, p["holes"])
    pitch = p["hole_pitch"]
    xs = [setback + off + i * pitch for i in range(n)]
    leg = p["leg"] if p["leg"] > 0 else xs[-1] - setback + max(Ln / 2 + 2.0, dk / 2 + 3.0)
    if xs[-1] - setback + dk / 2 + 1.5 > leg:
        leg = xs[-1] - setback + dk / 2 + 1.5
        sp["warnings"].append("Leg lengthened to fit the last hole.")
    x_rise = D / 2 + 1.5
    amin = pivot_min_angle(s, setback, D, x_rise, wa)
    if th < amin - 1e-6:
        sp["warnings"].append(f"At {th:.0f}° the members or arms collide: free swing is {amin:.0f}°–180°.")
    if lock == "arc":
        rng = max(10.0, min(p["pv_range"], 180.0 - amin))
        lo, hi = th - rng / 2, th + rng / 2
        if hi > 180:
            lo, hi = 180 - rng, 180.0
        if lo < amin:
            lo, hi = amin, min(180.0, amin + rng)
        sp.update(lock_lo=lo, lock_hi=hi, lock_R=R, phi0=-90.0)
    part = p["pv_part"] if p["pv_part"] in ("both", "a", "b") else "both"
    sp.update(w=w, t=t, D=D, hA=hA, hB=hB, gap=gap, bore=bore, af_p=af_p, h_p=h_p, setback=setback,
              xs=xs, leg=leg, x_rise=x_rise, amin=amin, lock=lock, part=part, wa=wa, cb=cbore_depth(p, sp, t))
    if t < 4:
        sp["warnings"].append("Leaves under 4 mm; 5 mm recommended.")
    sp["limit_note"] = (f"Pivot M{size}: nut captive under lug A, bolt or knob on top (friction lock). "
                        f"Free swing {amin:.0f}°–180°. Bore Ø{bore:.1f}, lug gap {gap:.1f}."
                        + (f" Arc lock: second M{size} in lug A, slot {sp['lock_lo']:.0f}–{sp['lock_hi']:.0f}°." if lock == "arc" else ""))
    return sp


def arc_slot(R, a0, a1, wd, z0, z1):
    """Slot of width wd along the arc of radius R from a0 to a1 (degrees)."""
    ring = cq.Workplane("XY").circle(R + wd / 2).circle(R - wd / 2).extrude(z1 - z0).translate((0, 0, z0))
    k = max(3, int((a1 - a0) / 10) + 2)
    pts = [(0.0, 0.0)] + [(3 * R * math.cos(math.radians(a0 + (a1 - a0) * i / (k - 1))),
                           3 * R * math.sin(math.radians(a0 + (a1 - a0) * i / (k - 1)))) for i in range(k)]
    wedge = cq.Workplane("XY").polyline(pts).close().extrude(z1 - z0).translate((0, 0, z0))
    slot = ring.intersect(wedge)
    for a in (a0, a1):
        slot = slot.union(cyl(wd / 2, z0, z1, x=R * math.cos(math.radians(a)), y=R * math.sin(math.radians(a))))
    return slot


def pivot_leaf(p, sp, which):
    """One leaf in its own frame: its member along +X from x = setback."""
    g = sp["g"]
    w, t, D, d, leg, wa = sp["w"], sp["t"], sp["D"], sp["setback"], sp["leg"], sp["wa"]
    hA, hB, gap, bore = sp["hA"], sp["hB"], sp["gap"], sp["bore"]
    plate = box(d, d + leg, -w / 2, w / 2, 0, t)
    try:
        plate = plate.edges("|Z").edges(">X").fillet(min(3.0, w / 4))
    except Exception:
        pass
    cutters = []
    if which == "a":
        body = plate.union(box(0, d + EPS, -wa / 2, wa / 2, 0, t)).union(cyl(D / 2, t - hA, t))
        zb = t - hA
        rt = 0.3
        cutters.append(cyl(bore / 2, zb - 1, t + 1))
        cutters.append(hex_prism(sp["af_p"], zb + rt, zb + rt + sp["h_p"], p["tn_corner_r"])
                       .union(hex_prism(sp["af_p"] - 2 * rt, zb - 1, zb + rt + EPS, p["tn_corner_r"])))
        if sp["lock"] == "arc":
            R, phi = sp["lock_R"], sp["phi0"]
            lx, ly = R * math.cos(math.radians(phi)), R * math.sin(math.radians(phi))
            cutters.append(cyl(sp["d_clear"] / 2, zb - 1, t + 1, x=lx, y=ly))
            cutters.append(hex_prism(sp["af_p"], zb + rt, zb + rt + sp["h_p"], p["tn_corner_r"])
                           .union(hex_prism(sp["af_p"] - 2 * rt, zb - 1, zb + rt + EPS, p["tn_corner_r"]))
                           .translate((lx, ly, 0)))
    else:
        xr = sp["x_rise"]
        rl = max(t, 5.0)
        z0, z1 = t + gap, t + gap + hB
        body = (plate.union(box(xr, d + EPS, -wa / 2, wa / 2, 0, t))
                .union(box(xr, xr + rl, -wa / 2, wa / 2, 0, z1))
                .union(box(0, xr + rl, -wa / 2, wa / 2, z0, z1))
                .union(cyl(D / 2, z0, z1)))
        cutters.append(cyl(bore / 2, z0 - 1, z1 + 1))
        if sp["lock"] == "arc":
            R, phi = sp["lock_R"], sp["phi0"]
            a0, a1 = phi - sp["lock_hi"], phi - sp["lock_lo"]
            cutters.append(arc_slot(R, a0, a1, bore, z0 - 1, z1 + 1))
    # T-nut bolts and tongue on the plate
    Wt, Ht, Ln = sp["tongue_w"], sp["tongue_h"], sp["tn_ref_len"]
    for x in sp["xs"]:
        cutters.append(cyl(sp["d_clear"] / 2, -Ht - 2, t + 1, x=x))
        if sp["cb"] > 0:
            cutters.append(cyl(sp["dk"] / 2 + 0.3, t - sp["cb"], t + 1, x=x))
    if p["tongue"] and Ht > 0.05 and leg - 2.5 > 3:
        tg = box(d + 1.0, d + leg - 1.5, -Wt / 2, Wt / 2, -Ht, EPS)
        for x in sp["xs"]:
            tg = tg.cut(box(x - Ln / 2 - 0.5, x + Ln / 2 + 0.5, -Wt, Wt, -Ht - 1, 1))
        body = body.union(tg)
    return cut_all(body, cutters)


def build_pivot(p, sp, export=False):
    part, th = sp["part"], sp["angle"]
    if part == "a":
        return pivot_leaf(p, sp, "a")
    if part == "b":
        return pivot_leaf(p, sp, "b")
    a = pivot_leaf(p, sp, "a").val()
    b = rotz(pivot_leaf(p, sp, "b"), th).val()
    return cq.Workplane("XY").newObject([cq.Compound.makeCompound([a, b])])


def pivot_context(p, sp):
    g = sp["g"]
    s = g["size"]
    d, th = sp["setback"], sp["angle"]
    L = p["member_len"]
    m1 = member_prism(g, d, d + L)
    m2 = rotz(member_prism(g, d, d + L), th)
    if sp["part"] == "a":
        m2 = None
    if sp["part"] == "b":
        m1, m2 = m2, None
        m1 = member_prism(g, d, d + L)
    ctx = m1 if m2 is None else m1.union(m2)
    return ctx.translate((0, 0, -s / 2))


# ---------------------------------------------------------------------
# dispatch
# ---------------------------------------------------------------------

def spec(p):
    f = p["family"]
    if f == "tnut":
        return tnut_spec(p)
    if f == "plate":
        return plate_spec(p)
    if f == "elbow":
        return elbow_spec(p)
    if f == "cap":
        return cap_spec(p)
    if f == "acc":
        return acc_spec(p)
    if f == "sign":
        return sign_spec(p)
    if f == "splice":
        return splice_spec(p)
    if f == "pivot":
        return pivot_spec(p)
    return bracket_spec(p)


def validate(p):
    if p["family"] not in FAMILIES:
        return ["Unknown family."]
    if p["thread"] not in F.SIZES:
        return ["Unknown thread size."]
    if p["opening"] >= p["cavity_w"]:
        return ["Opening must be narrower than the cavity."]
    if p["lip"] + p["cavity_d"] >= p["size"] / 2:
        return ["Slot deeper than half the profile."]
    try:
        sp = spec(p)
    except Exception as e:
        return [f"Spec failed: {e}"]
    return sp["errors"]


def build(p, export=False):
    """Returns (part Workplane, spec, warnings)."""
    sp = spec(p)
    if sp["errors"]:
        raise ValueError("; ".join(sp["errors"]))
    f = p["family"]
    if f == "tnut":
        part = build_tnut(p, sp, export)
    elif f == "plate":
        part = build_plate(p, sp, export)
    elif f == "elbow":
        part = build_elbow(p, sp, export)
    elif f == "cap":
        part = build_cap(p, sp, export)
    elif f == "acc":
        part = build_acc(p, sp, export)
    elif f == "sign":
        part = build_sign(p, sp, export)
    elif f == "splice":
        part = build_splice(p, sp, export)
    elif f == "pivot":
        part = build_pivot(p, sp, export)
    else:
        part = build_bracket(p, sp, export)
    return part, sp, sp["warnings"]


def context(p, sp):
    """Extrusion stubs for the viewport; None for the T-nut."""
    f = p["family"]
    if f == "tnut":
        g = sp["g"]
        L = max(sp["L"] * 2.2, 30)
        m = member_prism(g, -L / 2, L / 2)
        # in use the head is pulled up against the lips: put the cavity
        # ceiling at the head top, the depth clearance stays under it
        return m.translate((0, 0, -(g["size"] / 2 - g["lip"]) + sp["Hh"]))
    if f == "plate":
        return plate_context(p, sp)
    if f == "elbow":
        return elbow_context(p, sp)
    if f == "cap":
        return cap_context(p, sp)
    if f == "acc":
        return acc_context(p, sp)
    if f == "sign":
        return sign_context(p, sp)
    if f == "splice":
        return splice_context(p, sp)
    if f == "pivot":
        return pivot_context(p, sp)
    return bracket_context(p, sp)


def context_key(p, sp):
    """Everything the extrusion context depends on, from the resolved spec,
    so the server's context cache can never serve stale stubs."""
    f = p["family"]
    k = [f, P.geometry(p), float(p["member_len"])]
    if f == "tnut":
        k += [sp["L"], sp["Hh"]]
    elif f == "plate":
        k += [sp["angle"], p["ends"]]
    elif f == "elbow":
        k += [sp["angle"], sp["arm"], p["z_arm"]]
    elif f == "bracket":
        k += [sp["angle"], sp["rot"]]
    elif f == "cap":
        k += [sp["t"]]
    elif f == "sign":
        k += [sp["mount"], sp["w"], sp["h"], sp["t"], sp.get("rails")]
    elif f == "splice":
        k += [sp["kind"], sp["L"], sp.get("Hh")]
    elif f == "pivot":
        k += [sp["setback"], sp["angle"], sp["part"]]
    import json
    return json.dumps(k, sort_keys=True, default=float)


def print_note(p):
    f = p["family"]
    if f == "acc":
        typ = p["acc_type"]
        if typ == "tray":
            return ("Print floor down, base standing at the back, no supports (magnets drop in from the top). "
                    "Across trays need support under the base.")
        if typ == "clip":
            return ("Print on its side (the block spans the base), channels horizontal, no supports. "
                    "Snap lips flex best in PETG.")
        if typ in RACKS:
            return ("Print standing on the shelf's top face (holes vertical, base upright), no supports. "
                    "Layers lie in the shelf's bending plane.")
        if p["acc_turn"] == "across":
            return ("Print on its side with support under the arm, or inner face down with the tongue off. "
                    "Across heads twist the base: keep loads light.")
        return ("Print on its side with the J flat on the bed, no supports at full width. "
                "The arm then bends inside the layers.")
    if f == "sign":
        if p["sg_mount"] == "slot":
            return "Print standing on the slot key, show face vertical, no supports."
        return "Print flat, show face up. Recesses and embossing print clean; a through cut is a stencil."
    if f == "splice":
        if p["sp_kind"] == "bar":
            return "Print head down like a T-nut, pockets and bores vertical, no supports."
        if p["sp_faces"] == 4:
            return "Print standing on an end face (a ring), no supports; keys run vertical."
        return "Print on the outer face of the top plate, sides standing, no supports."
    if f == "pivot":
        return ("Leaf A: print top face down (nut pocket up). Leaf B: plate down; the upper arm bridges "
                "over the lug gap (≤ 15 mm, or add support). Export each leaf on its own.")
    return {
        "tnut": "Print head down, neck up, no supports. Threads and pockets are vertical.",
        "plate": "Print flat, extrusion side (tongues) up, no supports. Layers lie in the load plane.",
        "elbow": "Print on a flat side face, no supports. Bores are horizontal: a 0.5 mm chamfer or "
                 "sacrificial layer inside them helps; sand the bore ceiling if the head binds.",
        "bracket": "Print on its side with the L profile flat on the bed, no supports. Bending at the corner "
                   "then runs inside the layers.",
        "cap": "Print as exported, outer face down, plugs up, no supports. A smooth plate gives the show face.",
    }[f]


def derived(p, sp):
    """
    Readout for the UI: up to five [label, value, warn] cells (the
    envelope and volume are added by the server), a print note and a
    structural note.
    """
    f = p["family"]
    g = sp["g"]
    cells = []
    if f == "tnut":
        cells.append(["Head L×W×H", f"{sp['L']:.1f}×{sp['Wh']:.1f}×{sp['Hh']:.1f}", False])
        cells.append(["Neck", f"{sp['Wn']:.1f}×{sp['Hn']:.1f}" if sp["Hn"] > 0 else "none", False])
        ws = sp["wall_side"]
        if sp["fix"] == "hex":
            ce = sp["ceiling"]
            cells.append(["Wall / ceiling", f"{ws:.2f} / {ce:.2f}", ws < 1.2 or ce < 1.0])
            cells.append(["Fastening", f"M{sp['size']} hex {sp['af']:.0f} AF, {p['tn_load']}", False])
        elif sp["fix"] == "thread":
            cells.append(["Wall / engage", f"{ws:.2f} / {sp['engagement']:.1f}", ws < 1.2])
            cells.append(["Fastening", f"M{sp['size']} printed thread, +{p['clear_thread']:.2f} r", F.thread_status(sp["size"]) != "ok"])
        elif sp["fix"] == "insert":
            cells.append(["Wall", f"{ws:.2f}", ws < 1.2])
            cells.append(["Fastening", f"M{sp['size']} insert Ø{sp['ins_hole']:.1f}×{sp['ins_len']:.1f}", False])
        else:
            cells.append(["Wall", f"{ws:.2f}", ws < 1.2])
            cells.append(["Fastening", f"Ø{sp['d_clear']:.1f} bore", False])
        n = len(sp["xs"])
        cells.append(["Holes", f"{n} @ {sp['pitch']:.1f}" if n > 1 else "1", False])
    elif f in ("plate", "bracket"):
        xs = ", ".join(f"{x:.0f}" for x in sp["xs"])
        cells.append(["Leg × width × t", f"{sp['leg']:.0f}×{sp['w']:.0f}×{sp['t']:.0f}", False])
        cells.append(["Holes from vertex", xs, False])
        cells.append(["Bolt", f"M{sp['size']} SHCS, cbore {sp['cb']:.1f}", False])
        cells.append(["T-nut", f"slide-in L{sp['tn_ref_len']:.0f}, tongue {sp['tongue_h']:.1f}" if p["tongue"]
                      else f"slide-in L{sp['tn_ref_len']:.0f}, no tongue", False])
        if f == "plate":
            cells.append(["Member cut", f"{sp['mitre']:.1f}° mitre" if p["ends"] == "mitre" and sp["angle"] < 179.5
                          else "square", False])
        else:
            cells.append(["Web / rotation", f"{sp['web']}, {sp['rot']}°", False])
    elif f == "cap":
        cells.append(["Plan × t", f"{sp['plan']:.1f}×{sp['plan']:.1f}×{sp['t']:.1f}", False])
        cells.append(["Edge / corner", (f"{p['cap_edge']} {sp['e']:.1f}" if sp["e"] > 0 else "square") + f" / R{sp['cr']:.1f}", False])
        plugs = []
        if sp["plug"] != "none":
            plugs.append(f"4 {sp['plug']} {sp['key_w']:.1f}×{sp['key_h']:.1f}")
        if sp["core"]:
            plugs.append(f"core Ø{sp['core_d']:.1f}")
        cells.append(["Plugs", (", ".join(plugs) + f" L{sp['plug_len']:.0f}") if plugs else "none", not plugs and sp["hole"] == "none"])
        if sp["hole"] == "none":
            cells.append(["Centre hole", "none", False])
        elif sp["hole"] == "cbore":
            cells.append(["Centre hole", f"M{sp['size']} cbore {sp['cb']:.1f}", sp["protrude"] > 0.05])
        elif sp["hole"] == "csk":
            cells.append(["Centre hole", f"M{sp['size']} csk Ø{sp['csk_d']:.1f}", False])
        else:
            cells.append(["Centre hole", f"M{sp['size']} Ø{sp['d_clear']:.1f}", False])
        if sp.get("brand"):
            bi = sp.get("brand_info", {})
            cells.append(["Branding", f"{bi.get('src', '')} {bi.get('w', '?')}×{bi.get('h', '?')} {sp['brand']['mode']} {sp['brand']['depth']:.1f}", False])
        else:
            cells.append(["Member end", sp.get("tap_note", "square cut, untapped").split(";")[0], False])
    elif f == "acc":
        xs = ", ".join(f"{x:.0f}" for x in sp["xs"])
        cells.append(["Base L×W×t", f"{sp['base_len']:.0f}×{sp['w']:.0f}×{sp['t']:.0f}", False])
        cells.append(["Holes from base end", xs, False])
        if sp["type"] == "hook":
            cells.append(["Hook", f"reach {sp['reach']:.0f}, tip {sp['tip']:.0f}, R{sp['bend_r']:.0f}, {sp['hw']:.0f}×{sp['at']:.0f}", False])
        elif sp["type"] == "peg":
            cells.append(["Peg", f"reach {sp['reach']:.0f}, {sp['hw']:.0f}×{sp['at']:.0f}, lip {min(sp['tip'], 6):.0f}", False])
        elif sp["type"] == "hexkeys":
            cells.append(["Hex keys", " ".join(f"{k:g}" for k in sp["hex_keys"]) + f" @ {sp['pitch']:.0f}", False])
        elif sp["type"] == "pliers":
            cells.append(["Pliers", f"gap {sp['ds'][0]:.0f}, window {sp['win_len']:.0f}, {sp['hw']:.0f}×{sp['reach']:.0f}", sp["ds"][0] < 10])
        elif sp["type"] == "tray":
            cells.append(["Tray", f"{sp['hw']:.0f}×{sp['reach']:.0f}, rim {sp['rim']:.0f}, {len(sp['mags'])} × Ø{sp['mag_d']:.0f}×{sp['mag_t']:.0f}", False])
        elif sp["type"] == "clip":
            cells.append(["Clip", f"{sp['n']} × {sp['wire']} {sp['wire_d']:.1f}{'×' + format(sp['wire_w'], '.0f') if sp['wire'] == 'flat' else ''}, {sp['clip']}, wall {sp['wall']:.1f}", False])
        else:
            cells.append([sp["type"].capitalize(), f"{sp['n']} × {'slot' if sp['type'] == 'wrenches' else 'Ø'} {sp['ds'][0]:.1f} @ {sp['pitch']:.0f}", False])
        cells.append(["Bolt", f"M{sp['size']} SHCS, cbore {sp['cb']:.1f}", False])
        cells.append(["Rib / facing", f"{sp['rib']:.0f} / {sp['turn']}", False])
    elif f == "sign":
        cells.append(["Plate w×h×t", f"{sp['w']:.0f}×{sp['h']:.0f}×{sp['t']:.1f}", False])
        cells.append(["Edge / corner / lip", (f"{p['sg_edge']} {sp['e']:.1f}" if sp["e"] > 0 else "square") + f" / R{sp['cr']:.1f}"
                      + (f" / {sp['lip']} {sp['lip_h']:.1f}×{sp['lip_w']:.1f}" if sp["lip"] != "none" else " / no lip"), False])
        if sp["mount"] == "bolts":
            kind = "ears" if sp["ears"] else "in plate"
            pos = {"bottom": "bottom", "sides": "sides", "both": "top + bottom"}[sp["where"]]
            cells.append(["Mount", f"{len(sp['bolts'])} × M{sp['size']} {kind}, {pos}", False])
        elif sp["mount"] == "slot":
            cells.append(["Mount", f"slot key {sp['kl']:.0f} long, neck {sp['Wn']:.1f}", False])
        else:
            cells.append(["Mount", "none", False])
        bi = sp.get("brand_info", {})
        cells.append(["Branding", (f"{bi.get('src')} {bi.get('w', '?')}×{bi.get('h', '?')} {sp['brand']['mode']} {sp['brand']['depth']:.1f}"
                                   if sp.get("brand") else "none"), not sp.get("brand")])
        y0, y1 = sp["band"]
        cells.append(["Free band", f"{sp['avail_w']:.0f} × {y1 - y0:.0f}", y1 - y0 < 6])
    elif f == "splice":
        if sp["kind"] == "sleeve":
            cells.append(["Sleeve L × wall", f"{sp['L']:.0f} × {sp['T']:.1f}, fit {sp['fit']:.2f}", False])
            cells.append(["Faces", {1: "top plate", 2: "L: top + side", 3: "U: top + sides", 4: "box, all four"}[sp["faces"]], False])
            cells.append(["Bolts", f"{2 * len(sp['xs']) * sp['faces']} × M{sp['size']}, cbore {sp['cb']:.1f}", False])
            cells.append(["Keys", f"{sp['tongue_w']:.1f} wide, {sp['tongue_h']:.1f} deep" if p["tongue"] else "none", False])
            cells.append(["Bolts from joint", ", ".join(f"±{x:.0f}" for x in sp["xs"]), False])
        else:
            cells.append(["Bar L×W×H", f"{sp['L']:.0f}×{sp['Wh']:.1f}×{sp['Hh']:.1f}", False])
            cells.append(["Neck", f"{sp['Wn']:.1f}×{sp['Hn']:.1f}", False])
            cells.append(["Grub screws", f"{2 * len(sp['xs'])} × M{sp['size']} {sp['fix']}", False])
            if sp["fix"] == "hex":
                cells.append(["Wall / ceiling", f"{sp['wall_side']:.2f} / {sp['ceiling']:.2f}", sp["wall_side"] < 1.2 or sp["ceiling"] < 1.0])
            else:
                cells.append(["Wall", f"{sp['wall_side']:.2f}", sp["wall_side"] < 1.2])
            cells.append(["Screws from joint", ", ".join(f"±{x:.0f}" for x in sp["xs"]), False])
    elif f == "pivot":
        cells.append(["Lugs Ø / A / B", f"{sp['D']:.0f} / {sp['hA']:.1f} / {sp['hB']:.1f}", False])
        cells.append(["Pivot bolt", f"M{sp['size']}, bore Ø{sp['bore']:.1f}, gap {sp['gap']:.1f}", False])
        cells.append(["Free swing", f"{sp['amin']:.0f}°–180°", sp["angle"] < sp["amin"]])
        cells.append(["Lock", f"arc {sp['lock_lo']:.0f}–{sp['lock_hi']:.0f}°, R{sp['lock_R']:.1f}" if sp["lock"] == "arc" else "friction (knob)", False])
        cells.append(["Leaves", f"leg {sp['leg']:.0f}, holes " + ", ".join(f"{x:.0f}" for x in sp["xs"]), False])
    else:
        cells.append(["Arm", f"{sp['arm']:.0f} from vertex", False])
        cells.append(["Members", "square cut, end-tapped", False])
        cells.append(["Bolt", f"M{sp['size']} SHCS, key {sp['hexkey']}", False])
        cells.append(["Access bore", f"Ø{sp['head_d']:.1f}, {sp['access_len']:.0f} long", False])
        cells.append(["Keys", f"4 × {sp['key_w']:.1f}×{sp['key_h']:.1f}" if p["keys"] else "none", False])
    return {"cells": cells, "print": print_note(p), "limit": sp.get("limit_note", ""),
            "slot": sp["slot"], "size": sp["size"], "mitre": sp.get("mitre")}


def polygon_info(n, side_centre, size):
    """Regular n-gon from centreline side length: interior angle, mitre,
    outer and inner edge lengths of each member."""
    th = (n - 2) * 180.0 / n
    turn = 360.0 / n
    tan = math.tan(math.radians(turn / 2))
    return {"n": n, "interior": th, "mitre": turn / 2,
            "outer": side_centre + size * tan, "inner": side_centre - size * tan}

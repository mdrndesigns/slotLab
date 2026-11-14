"""
SLOTLAB batch verification. Builds every profile x family x a spread of
fasteners and angles, meshes the part and the extrusion context, and
checks them independently of the builder with trimesh:

    watertight, one body, positive volume
    no interference between the part and the extrusion (vertex containment
    both ways, 0.05 mm tolerance)
    voids where bolts and nuts go, material where walls should be
    bolt holes sit over a slot cavity

    python3.12 tests/batch.py            all cases
    python3.12 tests/batch.py tnut       one family
"""
import os, sys, time, math, itertools, json, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np
import cadquery as cq
import trimesh
import model as M
import profiles as P
import fasteners as F

OUT = os.environ.get("SLOTLAB_OUT", os.path.join(tempfile.gettempdir(), "slotlab_batch"))
os.makedirs(OUT, exist_ok=True)


def mesh_of(wp, tol=0.01):
    path = os.path.join(OUT, "_tmp.stl")
    cq.exporters.export(wp, path, tolerance=tol, angularTolerance=0.1)
    return trimesh.load(path)


def interference(a, b, tol=0.05, ignore_line_z=False):
    """Vertices of a strictly inside b, and of b inside a (after shrinking by tol via contains on offset?)."""
    # contains() is exact; vertices lying ON the surface can flip, so test a
    # point pulled inward along the vertex normal by tol instead.
    # face centroids pulled inward along the FACE normal (vertex normals
    # average across edges and give false hits at touching corners)
    rng = np.random.default_rng(1)
    ia_idx = rng.choice(len(a.faces), min(len(a.faces), 20000), replace=False)
    ib_idx = rng.choice(len(b.faces), min(len(b.faces), 20000), replace=False)
    pa = a.triangles_center[ia_idx] - a.face_normals[ia_idx] * tol
    pb = b.triangles_center[ib_idx] - b.face_normals[ib_idx] * tol
    ha = b.contains(pa)
    hb = a.contains(pb)
    if ignore_line_z:
        # faces whose centroid lies on the shared corner line (z axis) are
        # contact, not penetration
        ha &= np.hypot(a.triangles_center[ia_idx, 0], a.triangles_center[ia_idx, 1]) > 0.1
        hb &= np.hypot(b.triangles_center[ib_idx, 0], b.triangles_center[ib_idx, 1]) > 0.1
    return int(ha.sum()), int(hb.sum())


def rotz(x, y, deg):
    a = math.radians(deg)
    return (x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a))


def check_case(name, over):  # noqa
    p = M.merge_params({})
    if "profile" in over:
        M.apply_profile(p, over["profile"])
    p.update(over)
    t = time.time()
    errs = M.validate(p)
    if errs:
        return ("invalid", errs, time.time() - t)
    part, sp, warns = M.build(p, export=True)
    ctx = M.context(p, sp)
    m = mesh_of(part, tol=0.03 if over.get("tn_fix") == "thread" else 0.01)
    c = mesh_of(ctx, tol=0.03) if ctx is not None else None
    problems = []
    brand = sp.get("brand_solid")
    if p.get("brand_dual") and brand is None and sp.get("brand"):
        problems.append("dual branding body missing")
    if brand is not None:
        import io as _io
        mb = trimesh.load(_io.BytesIO(M.stl_bytes(brand, 0.01, 0.1)[0]), file_type="stl")
        if not mb.is_watertight:
            problems.append("brand body not watertight")
        if int(m.contains(mb.triangles_center - mb.face_normals * 0.05).sum()):
            problems.append("brand body overlaps the base")
        # the inlay / insert must touch the base: its face centres pushed outward land in the base
        if sp["brand"]["mode"] != "emboss" and not m.contains(mb.triangles_center + mb.face_normals * 0.05).any():
            problems.append("brand body not seated in the base")
    if not m.is_watertight:
        problems.append("not watertight")
    want_bodies = 2 if (p["family"] == "pivot" and sp["part"] == "both") else 1
    if len(m.split(only_watertight=False)) != want_bodies:
        problems.append("bodies=%d" % len(m.split(only_watertight=False)))
    if m.volume <= 0:
        problems.append("volume<=0")
    if p["family"] == "tnut":
        c.apply_translation((0, 0, 0.05))     # head top touches the lip exactly; give the test a hair
    if p["family"] == "bracket" and sp.get("rot"):
        # probes below are written in the unrotated frame: turn both meshes back
        R = trimesh.transformations.rotation_matrix(math.radians(-sp["rot"]), [0, 0, 1])
        m.apply_transform(R)
        c.apply_transform(R)
    if c is not None:
        ia, ib = interference(m, c, ignore_line_z=(p["family"] == "bracket"))
        if ia or ib:
            problems.append(f"interference part-in-ext={ia} ext-in-part={ib}")

    f = p["family"]
    g = sp["g"]
    inside = lambda pts: m.contains(np.array(pts, dtype=float))
    in_ext = lambda pts: c.contains(np.array(pts, dtype=float)) if c is not None else np.zeros(len(pts), bool)

    if f == "tnut":
        x0 = sp["xs"][0]
        Hh, Hn, Wh, Wn = sp["Hh"], sp["Hn"], sp["Wh"], sp["Wn"]
        # bolt path void through everything
        if inside([(x0, 0, Hh / 2), (x0, 0, Hh + Hn - 0.1 if Hn > 0 else Hh - 0.1)]).any():
            problems.append("bolt path blocked")
        # head material at the side wall
        if not inside([(x0, Wh / 2 - 0.3, Hh / 2 if Hh > 2 else 0.5)]).all():
            problems.append("no material at head side wall")
        if Hn > 0:
            if not inside([(0, Wn / 2 - 0.3, Hh + Hn - 0.2)]).all():
                problems.append("no neck material")
            if inside([(0, Wn / 2 + 0.3, Hh + Hn - 0.2)]).any():
                problems.append("neck too wide")
        if sp["fix"] == "hex":
            z0, z1 = sp["pocket_z"]
            zm = (z0 + z1) / 2
            r_in = sp["af_p"] / 2
            # pocket void just inside the flats, material just outside
            if inside([(x0, r_in - 0.25, zm), (x0, -r_in + 0.25, zm)]).any():
                problems.append("hex pocket not cut")
            if not inside([(x0, r_in + 0.25, zm)]).all():
                problems.append("missing wall outside hex pocket")
            # ceiling: material above the pocket beside the bolt hole
            zc = z1 + sp["ceiling"] / 2
            yc = sp["d_clear"] / 2 + 0.2
            if not inside([(x0, yc, zc)]).all():
                problems.append("no ceiling above nut")
            if p["tn_load"] == "end":
                # lane open to the end face
                sgn = 1 if x0 >= 0 else -1
                if inside([(sgn * (sp["L"] / 2 - 0.3), 0, zm)]).any():
                    problems.append("end lane not open")
                if not inside([(x0, sp["d_clear"] / 2 + 0.3, z0 / 2)]).all():
                    problems.append("no floor under end-loaded nut")
        elif sp["fix"] == "insert":
            d = sp["ins_hole"]
            if inside([(x0, d / 2 - 0.2, sp["ins_len"] / 2)]).any():
                problems.append("insert hole not cut")
            if not inside([(x0, d / 2 + 0.3, sp["ins_len"] / 2)]).all():
                problems.append("no wall beside insert")
            if not inside([(x0, sp["d_clear"] / 2 + 0.3, sp["ins_len"] + 0.4 + 0.5)]).all() and (Hh + Hn) > sp["ins_len"] + 1.2:
                problems.append("insert hole runs through")
        elif sp["fix"] == "thread":
            r_minor = F.minor_d(sp["size"]) / 2 + p["clear_thread"]
            r_major = sp["size"] / 2 + p["clear_thread"]
            pch = F.PITCH[sp["size"]]
            # sample the groove: along a radial line at r between minor and major,
            # over one pitch in z, some samples must be void and some material
            rr = (r_minor + r_major) / 2
            zs = np.linspace(0.5, 0.5 + pch, 24)
            pts = [(x0 + rr, 0, z) for z in zs]
            ins = inside(pts)
            if ins.all() or (~ins).all():
                problems.append("thread groove not present at mid-flank radius")
            if inside([(x0, r_minor - 0.1, Hh / 2)]).any():
                problems.append("minor bore blocked")
        else:
            if not inside([(x0, sp["d_clear"] / 2 + 0.3, Hh / 2)]).all():
                problems.append("no wall beside plain bore")
    elif f in ("plate", "bracket"):
        tk = sp["t"]
        for ang_i, (ang, mirror) in enumerate([(0.0, False), (sp["angle"], True)]):
            for x in sp["xs"]:
                if f == "plate":
                    hx, hy = rotz(x, 0, ang)
                    # void at mid-thickness, material beside the hole
                    if inside([(hx, hy, tk / 2)]).any():
                        problems.append(f"hole {x} leg {ang_i} blocked")
                    ox, oy = rotz(x, sp["d_clear"] / 2 + 0.6 if not p["cbore"] else sp["dk"] / 2 + 1.0, ang)
                    if not inside([(ox, oy, tk / 2)]).all():
                        problems.append(f"no material beside hole {x} leg {ang_i}")
                    # under the hole: inside the slot cavity, not aluminium
                    cz = -g["lip"] - g["cavity_d"] / 2
                    if in_ext([(hx, hy, cz)]).any():
                        problems.append(f"hole {x} leg {ang_i} not over a slot")
                    if p["cbore"] and sp["cb"] > 0:
                        cx, cy = rotz(x, sp["dk"] / 2 - 0.3, ang)
                        if inside([(cx, cy, tk - sp["cb"] / 2)]).any():
                            problems.append(f"counterbore {x} leg {ang_i} not cut")
                else:
                    # bracket: hole axis along local y, through leg at (x, y in [0,tk])
                    ly = -1 if mirror else 1
                    hx, hy = rotz(x, ly * tk / 2, ang)
                    if inside([(hx, hy, 0)]).any():
                        problems.append(f"hole {x} leg {ang_i} blocked")
                    if not inside([(hx, hy, sp["dk"] / 2 + 1.0)]).all():
                        problems.append(f"no material beside hole {x} leg {ang_i}")
                    # under the hole: slot cavity of the member behind this face
                    cx, cy = rotz(x, -ly * (g["lip"] + g["cavity_d"] / 2), ang)
                    if in_ext([(cx, cy, 0)]).any():
                        problems.append(f"hole {x} leg {ang_i} not over a slot")
                    if p["cbore"] and sp["cb"] > 0:
                        bx, by = rotz(x, ly * (tk - sp["cb"] / 2), ang)
                        if inside([(bx, by, sp["dk"] / 2 - 0.3)]).any():
                            problems.append(f"counterbore {x} leg {ang_i} not cut")
            # tongue sits in the slot opening: a point in the tongue must be inside the part
            if p["tongue"] and len(sp["xs"]) >= 1:
                xt = sp["xs"][0] + sp["tn_ref_len"] / 2 + 0.5 + 1.0   # just past the window
                if f == "plate":
                    tx, ty = rotz(xt, 0, ang)
                    pt = (tx, ty, -sp["tongue_h"] / 2)
                else:
                    tx, ty = rotz(xt, (-1 if mirror else 1) * -sp["tongue_h"] / 2, ang)
                    pt = (tx, ty, 0)
                if xt < sp["leg"] - 2 and not inside([pt]).all():
                    problems.append(f"tongue missing leg {ang_i}")
    elif f == "elbow":
        arm = sp["arm"]
        arms = [(0.0, "z")]
        arms.append((sp["angle"], "z"))
        for ang, _ in arms:
            # bolt void along the axis at the end face and inside; material at bolt_wall ring
            ex, ey = rotz(arm - 0.5, 0, ang)
            if inside([(ex, ey, 0)]).any():
                problems.append(f"bolt bore blocked at end face {ang}")
            rx, ry = rotz(arm - p["bolt_wall"] / 2, sp["d_clear"] / 2 + 0.5, ang)
            if not inside([(rx, ry, 0)]).all():
                problems.append(f"no bolt wall at {ang}")
            hx, hy = rotz(arm - p["bolt_wall"] - 2, sp["head_d"] / 2 - 0.3, ang)
            if inside([(hx, hy, 0)]).any():
                problems.append(f"head bore not cut at {ang}")
            if p["keys"]:
                kx, ky = rotz(arm + p["key_len"] / 2, 0, ang)
                if not inside([(kx, ky, g["size"] / 2 - sp["key_h"] / 2 - 0.2)]).all():
                    problems.append(f"key missing at {ang}")
    elif f == "cap":
        s_ = g["size"]
        t_, L = sp["t"], sp["plug_len"]
        if sp["plug"] != "none":
            # key material in the slot opening, on all four sides
            for q in range(4):
                kx, ky = rotz(s_ / 2 - sp["key_h"] / 2, 0, 90 * q)
                if not inside([(kx, ky, t_ + L / 2)]).all():
                    problems.append(f"key {q} missing")
            if sp["plug"] == "tee":
                tx, ty = s_ / 2 - g["lip"] - sp["tee_h"] / 2, 0
                if not inside([(tx, ty, t_ + L / 2)]).all():
                    problems.append("tee head missing")
        if sp["core"] and not inside([(0, 0, t_ + L / 2)]).all():
            problems.append("core plug missing")
        if sp["hole"] == "none":
            if not inside([(0, 0, t_ / 2)]).all():
                problems.append("centre not solid")
        else:
            if inside([(0, 0, t_ / 2), (0, 0, t_ + L / 2)]).any():
                problems.append("centre hole blocked")
            if sp["cb"] > 0 and inside([(sp["dk"] / 2 - 0.3, 0, sp["cb"] / 2)]).any():
                problems.append("counterbore not cut")
            if sp["csk_d"] > 0 and inside([(sp["csk_d"] / 2 - 0.4, 0, 0.1)]).any():
                problems.append("countersink not cut")
        # plate material near the edge, outside the plug footprint
        if not inside([(sp["plan"] / 2 - 1.5, 0, t_ / 2)]).all():
            problems.append("plate edge missing")
    elif f == "sign":
        w_, h_, t_ = sp["w"], sp["h"], sp["t"]
        # a point just inside the plate edge, away from any bolt head
        cands = [(w_ / 2 - 2.0, 0.0), (0.0, h_ / 2 - 2.0), (0.0, -h_ / 2 + 2.0), (-w_ / 2 + 2.0, 0.0)]
        bolts = sp.get("bolts", [])
        far = [q for q in cands if all(math.hypot(q[0] - bx, q[1] - by) > sp.get("head_r", 0) + 1.5 for bx, by in bolts)]
        q = (far or cands)[0]
        if not inside([(q[0], q[1], t_ / 2)]).all():
            problems.append("plate edge missing")
        if sp.get("brand") and sp.get("brand_info", {}).get("w") and sp.get("brand_solid") is None:
            # (with two filaments the branding is its own body, checked above)
            y0, y1 = sp["band"]
            yc = (y0 + y1) / 2
            mode = sp["brand"]["mode"]
            # somewhere in the artwork band the face differs from a plain plate
            zs = t_ - sp["brand"]["depth"] / 2 if mode == "recess" else (t_ + sp["brand"]["depth"] / 2 if mode == "emboss" else t_ / 2)
            bw, bh = sp["brand_info"]["w"], sp["brand_info"].get("h", 1.0)
            pts = [(x, yc + fy * bh, zs) for fy in (-0.35, -0.2, 0.0, 0.2, 0.35)
                   for x in np.linspace(-bw / 2, bw / 2, 41)]
            ins = inside(pts)
            if mode == "emboss" and not ins.any():
                problems.append("no raised branding found")
            if mode in ("recess", "through") and ins.all():
                problems.append("no branding cut found")
        if sp["lip"] != "none":
            yl = h_ / 2 - sp["lip_in"] - sp["lip_w"] / 2
            if sp["lip"] == "raised" and not inside([(0, yl, t_ + sp["lip_h"] / 2)]).all():
                problems.append("raised lip missing")
            if sp["lip"] == "groove" and inside([(0, yl, t_ - sp["lip_h"] / 2)]).any():
                problems.append("groove not cut")
            # the face just inside the lip, clear of the branding margin
            if not inside([(w_ / 2 - sp["lip_in"] - sp["lip_w"] - 0.5, 0, t_ - 0.3)]).all():
                problems.append("face inside the lip missing")
        if sp["mount"] == "bolts":
            for x, ys in sp["bolts"]:
                if inside([(x, ys, t_ / 2)]).any():
                    problems.append(f"bolt hole {x:.0f},{ys:.0f} blocked")
                if in_ext([(x, ys, -g["lip"] - g["cavity_d"] / 2)]).any():
                    problems.append(f"bolt hole {x:.0f},{ys:.0f} not over the slot")
                # material around the head: ear rim or plate (toward the plate centre)
                dx = -sp["head_r"] - 0.6 if x > 0 else sp["head_r"] + 0.6
                if not inside([(x + dx, ys, t_ / 2)]).all():
                    problems.append(f"no material beside bolt {x:.0f},{ys:.0f}")
                if p["cbore"] and sp["cb"] > 0 and inside([(x + sp["head_r"] - 0.3, ys, t_ - sp["cb"] / 2)]).any():
                    problems.append(f"counterbore {x:.0f},{ys:.0f} not cut")
            if sp["ears"] and sp["where"] != "sides":
                # the plate edge between the ears is still the plain edge (no tab there)
                if abs(sp["bolts"][0][0]) > sp["er"] + 2 and inside([(0.0, sp["rails"][0], t_ / 2)]).any():
                    problems.append("ear material where no ear should be")
            if sp["where"] == "sides" and sp.get("brand_info", {}).get("w"):
                # branding must stay between the end bolts
                if sp["brand_info"]["w"] / 2 > abs(sp["bolts"][1][0]) - sp["head_r"] - 1.0 and not sp["ears"]:
                    problems.append("branding runs into the end bolts")
        elif sp["mount"] == "slot":
            if not inside([(0, -h_ / 2 - g["lip"] - sp["Hh"] / 2, t_ / 2)]).all():
                problems.append("slot key head missing")
            if not inside([(0, -h_ / 2 - g["lip"] / 2, t_ / 2)]).all():
                problems.append("slot key neck missing")
    elif f == "splice":
        L = sp["L"]
        if sp["kind"] == "sleeve":
            a = g["size"] / 2 + sp["fit"]
            for rot in M.FACE_ROT[sp["faces"]]:
                for x0 in sp["xs"]:
                    for sx in (-1, 1):
                        hx, hy, hz = x0 * sx, 0.0, a + sp["T"] / 2
                        y, z = rotz(hy, hz, rot)           # rotation about X: (y, z) plane
                        if inside([(hx, y, z)]).any():
                            problems.append(f"sleeve bolt {hx:.0f} face {rot} blocked")
                        y2, z2 = rotz(sp["dk"] / 2 + 1.5, hz, rot)
                        if not inside([(hx, y2, z2)]).all():
                            problems.append(f"no plate beside bolt {hx:.0f} face {rot}")
                # key in the opening, in the first gap between T-nut windows (or past the last one)
                if p["tongue"]:
                    Ln = sp["tn_ref_len"]
                    edges = [1.0] + [v for x0 in sp["xs"] for v in (x0 - Ln / 2 - 0.5, x0 + Ln / 2 + 0.5)] + [L / 2 - 1.0]
                    gaps = [(edges[i], edges[i + 1]) for i in range(0, len(edges), 2)]
                    gaps = [gp for gp in gaps if gp[1] - gp[0] >= 2.0]
                    if gaps:
                        xk = sum(gaps[0]) / 2
                        y, z = rotz(0.0, g["size"] / 2 - max(0.6, g["lip"] - 0.3) / 2, rot)
                        if not inside([(xk, y, z)]).all():
                            problems.append(f"sleeve key missing face {rot}")
        else:
            Hh = sp["Hh"]
            for x0 in sp["xs"]:
                for sx in (-1, 1):
                    x = x0 * sx
                    if inside([(x, 0, Hh / 2)]).any():
                        problems.append(f"bar bore {x:.0f} blocked")
                    if sp["fix"] == "hex":
                        r_in = sp["af_p"] / 2
                        zm = 0.3 + sp["h_p"] / 2
                        if inside([(x, r_in - 0.25, zm)]).any():
                            problems.append(f"bar pocket {x:.0f} not cut")
                        if not inside([(x, r_in + 0.25, zm)]).all():
                            problems.append(f"bar wall missing at {x:.0f}")
            if not inside([(0, sp["Wh"] / 2 - 0.3, Hh / 2)]).all():
                problems.append("bar side wall missing")
    elif f == "pivot":
        t_, D = sp["t"], sp["D"]
        hA = sp["hA"]
        if sp["part"] in ("both", "a"):
            if inside([(0, 0, t_ - hA / 2)]).any():
                problems.append("pivot bore blocked in lug A")
            if not inside([(D / 2 - 1.0, 0, t_ - 0.5)]).all():
                problems.append("lug A rim missing")
            zm = t_ - hA + 0.3 + sp["h_p"] / 2
            if inside([(0, sp["af_p"] / 2 - 0.3, zm)]).any():
                problems.append("nut pocket not cut")
        if sp["part"] in ("both", "b"):
            th = sp["angle"] if sp["part"] == "both" else 0.0
            z0 = t_ + sp["gap"] + sp["hB"] / 2
            if inside([(0, 0, z0)]).any():
                problems.append("pivot bore blocked in lug B")
            rx, ry = rotz(D / 2 - 1.0, 0, th)
            if not inside([(rx, ry, z0)]).all():
                problems.append("lug B rim missing")
            if sp["lock"] == "arc":
                R = sp["lock_R"]
                a_mid = sp["phi0"] - (sp["lock_lo"] + sp["lock_hi"]) / 2 + th
                sx, sy = R * math.cos(math.radians(a_mid)), R * math.sin(math.radians(a_mid))
                if inside([(sx, sy, z0)]).any():
                    problems.append("arc slot not cut")
        for x in sp["xs"]:
            if inside([(x, 0, t_ / 2)]).any():
                problems.append(f"leaf A hole {x:.0f} blocked")
            if in_ext([(x, 0, -g["lip"] - g["cavity_d"] / 2)]).any():
                problems.append(f"leaf A hole {x:.0f} not over the slot")
    else:  # acc
        t_, bl, w_ = sp["t"], sp["base_len"], sp["w"]
        for x in sp["xs"]:
            if inside([(x - bl / 2, 0, t_ / 2)]).any():
                problems.append(f"bolt hole {x:.0f} blocked")
            if in_ext([(x - bl / 2, 0, -g["lip"] - g["cavity_d"] / 2)]).any():
                problems.append(f"bolt hole {x:.0f} not over the slot")
            if p["cbore"] and sp["cb"] > 0 and inside([(x - bl / 2, sp["dk"] / 2 - 0.3, t_ - sp["cb"] / 2)]).any():
                problems.append(f"counterbore {x:.0f} not cut")
        if sp["type"] == "clip":
            xc = (sp["x_f0"] + (sp["at"] / 2 if sp["turn"] == "along" else sp["hw"] / 2)) - bl / 2
            zc = t_ + sp["wall"] + sp["wire_d"] / 2
            for yc in sp["ys"]:
                pt = (xc, yc, zc) if sp["turn"] == "along" else (xc + yc, 0, zc)
                if inside([pt]).any():
                    problems.append(f"wire channel {yc:.0f} blocked")
            edge = (xc, sp["hw"] / 2 - 0.5, t_ + sp["wall"] / 2) if sp["turn"] == "along" else (xc + sp["hw"] / 2 - 0.5, 0, t_ + sp["wall"] / 2)
            if not inside([edge]).all():
                problems.append("clip block missing")
        elif sp["type"] == "tray":
            if sp["turn"] == "along":
                xf = sp["x_f1"] - sp["at"] / 2 - bl / 2
                if not inside([(xf, 0, t_ + 3.0)]).all():
                    problems.append("tray floor missing")
                if not inside([(sp["x_f1"] + sp["rim"] / 2 - bl / 2, 0, t_ + sp["reach"] - 1.0)]).all():
                    problems.append("front rim missing")
                for u, v in sp["mags"]:
                    if inside([(sp["x_f1"] - sp["mag_t"] / 2 - bl / 2, u, v)]).any():
                        problems.append("magnet pocket not cut")
                        break
                    if not inside([(sp["x_f1"] - sp["mag_t"] - 0.5 - bl / 2, u, v)]).all():
                        problems.append("no floor under a magnet")
                        break
        elif sp["type"] == "pliers":
            xs_ = (sp["x_f1"] - sp["at"] / 2 - bl / 2) if sp["turn"] == "along" else 0.0
            ys_ = 0.0 if sp["turn"] == "along" else w_ / 2 - sp["at"] / 2
            zw = t_ + sp["reach"] - 5.0 - sp["ds"][0] / 2
            if inside([(xs_, ys_, zw)]).any():
                problems.append("plier window blocked")
            if not inside([(xs_, ys_, t_ + sp["reach"] - 2.5)]).all():
                problems.append("front rail missing")
        elif not sp["rack"]:
            xc = (sp["x_f0"] + (sp["at"] / 2 if sp["turn"] == "along" else sp["hw"] / 2)) - bl / 2
            if not inside([(xc, 0, t_ + sp["reach"] / 2)]).all():
                problems.append("arm missing")
            if sp["type"] == "hook" and sp["tip"] > 2 and sp["turn"] == "along":
                ri = sp["bend_r"]
                tipx = sp["x_f0"] + sp["at"] + ri + sp["tip"] / 2 - bl / 2
                tz = t_ + sp["reach"] + ri + sp["at"] / 2
                if not inside([(tipx, 0, tz)]).all():
                    problems.append("hook tip missing")
        elif sp["turn"] == "along":
            xs_ = sp["x_f1"] - sp["at"] / 2 - bl / 2
            if not inside([(xs_, 0, t_ + 1.5)]).all():
                problems.append("shelf missing")
            for yc, d in zip(sp["ys"], sp["ds"]):
                zc = t_ + sp["reach"] - d / 2 - 3.0 if sp["type"] != "wrenches" else t_ + sp["reach"] - 1.0
                if inside([(xs_, yc, zc)]).any():
                    problems.append(f"feature at {yc:.0f} blocked")
                if sp["type"] != "wrenches" and not inside([(xs_, yc + d / 2 + 1.0, zc)]).all():
                    problems.append(f"no material beside feature {yc:.0f}")
        else:
            ys_ = w_ / 2 - sp["at"] / 2
            if not inside([(0, ys_, t_ + 1.5)]).all():
                problems.append("shelf missing")
            for yc, d in zip(sp["ys"], sp["ds"]):
                zc = t_ + sp["reach"] - d / 2 - 3.0 if sp["type"] != "wrenches" else t_ + sp["reach"] - 1.0
                if inside([(yc, ys_, zc)]).any():
                    problems.append(f"feature at {yc:.0f} blocked")
                if sp["type"] != "wrenches" and not inside([(yc + d / 2 + 1.0, ys_, zc)]).all():
                    problems.append(f"no material beside feature {yc:.0f}")
        if p["tongue"]:
            xt = sp["xs"][0] + sp["tn_ref_len"] / 2 + 0.5 + 1.0 - bl / 2
            if xt < sp["x_f0"] - bl / 2 - 1 and not inside([(xt, 0, -sp["tongue_h"] / 2)]).all():
                problems.append("tongue missing")
    dt = time.time() - t
    return ("ok" if not problems else "FAIL", problems + [f"warn: {w}" for w in warns], dt)


def cases():
    out = {}
    profs = list(P.PROFILES)
    # T-nuts: every profile x fastening x sensible sizes x type
    for pr in profs:
        slot = P.nominal_slot(P.PROFILES[pr]["opening"])
        for size in P.SLOT_THREADS[slot]:
            for fix in ("hex", "thread", "insert", "plain"):
                for tt in ("slide", "drop"):
                    over = dict(family="tnut", profile=pr, thread=size, tn_fix=fix, tn_type=tt)
                    if fix == "hex":
                        over["tn_nut"] = "thin" if slot == 6 else "iso4032"
                    out[f"tnut_{pr}_M{size}_{fix}_{tt}"] = over
        out[f"tnut_{pr}_end_M{P.SLOT_DEFAULT_THREAD[slot]}"] = dict(family="tnut", profile=pr, thread=P.SLOT_DEFAULT_THREAD[slot],
                                                                   tn_fix="hex", tn_load="end", tn_len=24, tn_nut="thin" if slot == 6 else "iso4032")
        out[f"tnut_{pr}_2holes"] = dict(family="tnut", profile=pr, thread=P.SLOT_DEFAULT_THREAD[slot], tn_fix="hex", tn_holes=2,
                                        tn_len=36, tn_nut="thin" if slot == 6 else "iso4032", tn_retain=0.3)
    # joints: three profiles x angles
    for pr in ("hfs5_2020", "hfs6_3030", "i_4040", "hfs8_4040"):
        slot = P.nominal_slot(P.PROFILES[pr]["opening"])
        size = P.SLOT_DEFAULT_THREAD[slot]
        for ang in (60, 90, 108, 120, 135, 150, 180):
            out[f"plate_{pr}_{ang}"] = dict(family="plate", profile=pr, thread=size, angle=ang)
            if ang in (90, 120):
                out[f"plate_{pr}_{ang}_sq"] = dict(family="plate", profile=pr, thread=size, angle=ang, ends="square", holes=3)
            if ang <= 170:
                out[f"elbow_{pr}_{ang}"] = dict(family="elbow", profile=pr, thread=P.PROFILES[pr]["tap"], angle=ang)
            out[f"bracket_{pr}_{ang}"] = dict(family="bracket", profile=pr, thread=size, angle=ang, web="sides")
        out[f"elbow_{pr}_90z"] = dict(family="elbow", profile=pr, thread=P.PROFILES[pr]["tap"], angle=90, z_arm="up")
        out[f"bracket_{pr}_90full"] = dict(family="bracket", profile=pr, thread=size, angle=90, web="full", holes=1)
        out[f"bracket_{pr}_90none"] = dict(family="bracket", profile=pr, thread=size, angle=90, web="none", cbore=False, tongue=False)
        for rot in (90, 180, 270):
            out[f"bracket_{pr}_rot{rot}"] = dict(family="bracket", profile=pr, thread=size, angle=90, br_rot=rot, tongue=False)
    # end caps: every profile x plugs x centre hole
    for pr in profs:
        tap = P.PROFILES[pr]["tap"]
        for plug in ("none", "keys", "tee"):
            for hole in ("none", "plain", "cbore", "csk"):
                out[f"cap_{pr}_{plug}_{hole}"] = dict(family="cap", profile=pr, thread=tap, cap_plug=plug, cap_hole=hole)
        out[f"cap_{pr}_fillet_over"] = dict(family="cap", profile=pr, thread=tap, cap_edge="fillet", cap_edge_s=1.5,
                                            cap_oversize=1.0, cap_t=5)
        out[f"cap_{pr}_bare"] = dict(family="cap", profile=pr, thread=tap, cap_plug="none", cap_core=False, cap_edge="none")
    # accessories: profiles x head x facing
    for pr in ("hfs5_2020", "hfs6_3030", "i_4040", "hfs8_4040"):
        slot = P.nominal_slot(P.PROFILES[pr]["opening"])
        size = P.SLOT_DEFAULT_THREAD[slot]
        for typ in ("hook", "peg", "drivers", "hexkeys", "wrenches"):
            for turn in ("along", "across"):
                out[f"acc_{pr}_{typ}_{turn}"] = dict(family="acc", profile=pr, thread=size, acc_type=typ, acc_turn=turn)
        out[f"acc_{pr}_hook_narrow"] = dict(family="acc", profile=pr, thread=size, acc_type="hook", acc_w=12, holes=1, acc_rib=0)
        out[f"acc_{pr}_hex9"] = dict(family="acc", profile=pr, thread=size, acc_type="hexkeys", acc_n=9, acc_pitch=9)
        out[f"acc_{pr}_wr_flat"] = dict(family="acc", profile=pr, thread=size, acc_type="wrenches", tongue=False, cbore=False, acc_n=6)
        out[f"acc_{pr}_clip_flat"] = dict(family="acc", profile=pr, thread=size, acc_type="clip", acc_wire="flat", acc_wire_d=2, acc_wire_w=12, acc_n=2)
        out[f"acc_{pr}_clip_loop"] = dict(family="acc", profile=pr, thread=size, acc_type="clip", acc_clip="loop", acc_n=4, acc_wire_d=3, holes=1)
        out[f"acc_{pr}_tray_big"] = dict(family="acc", profile=pr, thread=size, acc_type="tray", acc_w=100, acc_reach=50, acc_mag_d=10, acc_rim=8)
    # branding: caps and signs, text and svg, three finishes
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 60 40"><rect x="2" y="2" width="26" height="36" rx="5"/>'
           '<circle cx="15" cy="20" r="8" fill="#fff"/><circle cx="15" cy="20" r="3"/>'
           '<path d="M32 2 L58 2 L45 38 Z M40 8 h10 l-5 16 z"/></svg>')
    import branding as B
    key, _ = B.store_svg(svg)
    for pr in ("hfs5_2020", "hfs6_3030", "hfs8_4040"):
        tap = P.PROFILES[pr]["tap"]
        slot = P.nominal_slot(P.PROFILES[pr]["opening"])
        size = P.SLOT_DEFAULT_THREAD[slot]
        for mode in ("recess", "emboss", "through"):
            out[f"cap_{pr}_text_{mode}"] = dict(family="cap", profile=pr, thread=tap, brand_src="text", brand_text="AB", brand_mode=mode, brand_font="mono")
            out[f"sign_{pr}_slot_text_{mode}"] = dict(family="sign", profile=pr, thread=size, sg_mount="slot", brand_src="text", brand_text="LAB", brand_mode=mode, brand_font="serif")
        out[f"cap_{pr}_svg"] = dict(family="cap", profile=pr, thread=tap, brand_src="svg", brand_svg=key, brand_mode="recess", cap_plug="tee")
        out[f"sign_{pr}_bolts_svg"] = dict(family="sign", profile=pr, thread=size, sg_mount="bolts", brand_src="svg", brand_svg=key, sg_h=50)
        out[f"sign_{pr}_free"] = dict(family="sign", profile=pr, thread=size, sg_mount="none", brand_src="text", brand_text="A\nB", brand_font="sans", brand_bold=True)
        out[f"sign_{pr}_ears"] = dict(family="sign", profile=pr, thread=size, sg_mount="bolts", sg_holes="ears", brand_src="text", brand_text="EARS", brand_align="centre")
        out[f"sign_{pr}_ears2"] = dict(family="sign", profile=pr, thread=size, sg_mount="bolts", sg_holes="ears", sg_where="both", holes=3, brand_src="text", brand_text="TWO", brand_align="centre", sg_edge="fillet")
        out[f"sign_{pr}_rows2"] = dict(family="sign", profile=pr, thread=size, sg_mount="bolts", sg_where="both", sg_h=60, sg_inset=10, brand_src="text", brand_text="MID")
        out[f"sign_{pr}_edge_inset"] = dict(family="sign", profile=pr, thread=size, sg_mount="bolts", sg_inset=8, holes=2, sg_h=45, brand_src="text", brand_text="EDGE", cbore=False)
        out[f"sign_{pr}_lip_raised"] = dict(family="sign", profile=pr, thread=size, sg_mount="bolts", sg_holes="ears", sg_lip="raised", brand_src="text", brand_text="RIM", brand_align="centre")
        out[f"sign_{pr}_lip_groove"] = dict(family="sign", profile=pr, thread=size, sg_mount="slot", sg_lip="groove", sg_lip_h=1.0, sg_edge="fillet", brand_src="text", brand_text="GROOVE")
        out[f"sign_{pr}_sides"] = dict(family="sign", profile=pr, thread=size, sg_mount="bolts", sg_where="sides", brand_src="text", brand_text="SIDES", brand_align="centre", sg_w=110)
        out[f"sign_{pr}_sides_ears"] = dict(family="sign", profile=pr, thread=size, sg_mount="bolts", sg_where="sides", sg_holes="ears", brand_src="text", brand_text="EARS", brand_align="centre", sg_edge="fillet")
        out[f"sign_{pr}_sides_offset"] = dict(family="sign", profile=pr, thread=size, sg_mount="bolts", sg_where="sides", sg_offset=-6, sg_inset=9, brand_src="text", brand_text="OFF")
        for mode in ("recess", "emboss", "through"):
            out[f"sign_{pr}_dual_{mode}"] = dict(family="sign", profile=pr, thread=size, sg_mount="bolts", sg_where="sides", sg_holes="ears", brand_src="text", brand_text="DUO", brand_mode=mode, brand_dual=True, brand_align="centre")
            out[f"cap_{pr}_dual_{mode}"] = dict(family="cap", profile=pr, thread=tap, brand_src="text", brand_text="AB", brand_mode=mode, brand_dual=True, brand_font="mono")
        out[f"sign_{pr}_dual_svg"] = dict(family="sign", profile=pr, thread=size, sg_mount="slot", brand_src="svg", brand_svg=key, brand_dual=True)
        out[f"sign_{pr}_emoji"] = dict(family="sign", profile=pr, thread=size, sg_mount="none", brand_src="text", brand_text="OK \U0001F527", brand_align="centre")
    # splice
    for pr in profs:
        slot = P.nominal_slot(P.PROFILES[pr]["opening"])
        size = P.SLOT_DEFAULT_THREAD[slot]
        for faces in (1, 2, 3, 4):
            out[f"splice_{pr}_sleeve{faces}"] = dict(family="splice", profile=pr, thread=size, sp_kind="sleeve", sp_faces=faces)
        out[f"splice_{pr}_bar"] = dict(family="splice", profile=pr, thread=4 if slot == 6 else size, sp_kind="bar", sp_fix="hex")
        if slot >= 8:
            out[f"splice_{pr}_bar_thread"] = dict(family="splice", profile=pr, thread=6, sp_kind="bar", sp_fix="thread")
    # pivot
    for pr in ("hfs5_2020", "hfs6_3030", "i_4040", "hfs8_4040"):
        slot = P.nominal_slot(P.PROFILES[pr]["opening"])
        size = P.SLOT_DEFAULT_THREAD[slot]
        for lock in ("none", "arc"):
            for ang in (90, 120, 180):
                out[f"pivot_{pr}_{lock}_{ang}"] = dict(family="pivot", profile=pr, thread=size, pv_lock=lock, angle=ang)
            out[f"pivot_{pr}_{lock}_a"] = dict(family="pivot", profile=pr, thread=size, pv_lock=lock, pv_part="a")
            out[f"pivot_{pr}_{lock}_b"] = dict(family="pivot", profile=pr, thread=size, pv_lock=lock, pv_part="b")
    return out


if __name__ == "__main__":
    only = sys.argv[1:]
    C = cases()
    res = {}
    t0 = time.time()
    for name, over in C.items():
        if only and not any(name.startswith(o) for o in only):
            continue
        try:
            status, notes, dt = check_case(name, over)
        except Exception as e:
            status, notes, dt = "EXC", [repr(e)[:200]], 0
        res[name] = (status, notes, dt)
        flag = "" if status == "ok" else "  <<<"
        print(f"{status:7s} {dt:5.1f}s {name}{flag}  {'; '.join(n for n in notes if not n.startswith('warn')) if status != 'ok' else ''}")
        sys.stdout.flush()
    n = len(res)
    ok = sum(1 for v in res.values() if v[0] == "ok")
    inv = sum(1 for v in res.values() if v[0] == "invalid")
    print(f"\n{ok} ok, {inv} invalid (refused by validation), {n - ok - inv} failed, of {n} in {time.time() - t0:.0f}s")
    json.dump(res, open(os.path.join(OUT, "results.json"), "w"), indent=1)

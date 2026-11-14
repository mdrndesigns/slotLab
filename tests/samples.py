"""Export representative sample parts (STEP + STL + preview) into ../samples."""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import cadquery as cq
import model as M
from render import render

OUT = os.path.join(os.path.dirname(__file__), "..", "samples")
os.makedirs(OUT, exist_ok=True)

SAMPLES = {
    "tnut_3030_m6_hex":      dict(profile="hfs6_3030", family="tnut", thread=6, tn_fix="hex", tn_retain=0.3),
    "tnut_3030_m6_thread":   dict(profile="hfs6_3030", family="tnut", thread=6, tn_fix="thread"),
    "tnut_2020_m4_thin_hex": dict(profile="hfs5_2020", family="tnut", thread=4, tn_fix="hex", tn_nut="thin", tn_len=12),
    "tnut_2020_m3_drop":     dict(profile="hfs5_2020", family="tnut", thread=3, tn_type="drop", tn_fix="plain"),
    "plate_3030_hexagon":    dict(profile="hfs6_3030", family="plate", thread=6, angle=120),
    "plate_2020_square":     dict(profile="hfs5_2020", family="plate", thread=5, angle=90, ends="square"),
    "elbow_3030_cube":       dict(profile="hfs6_3030", family="elbow", thread=8, angle=90, z_arm="up"),
    "elbow_4040_octagon":    dict(profile="i_4040", family="elbow", thread=8, angle=135),
    "bracket_2020_tee":      dict(profile="hfs5_2020", family="bracket", thread=5, angle=90),
    "bracket_3030_60":       dict(profile="hfs6_3030", family="bracket", thread=6, angle=60),
    "bracket_2020_flat_rot90": dict(profile="hfs5_2020", family="bracket", thread=5, angle=90, tongue=False, br_rot=90),
    "cap_3030_keys":         dict(profile="hfs6_3030", family="cap", thread=8),
    "cap_2020_tee_csk":      dict(profile="hfs5_2020", family="cap", thread=5, cap_plug="tee", cap_hole="csk", cap_edge="fillet"),
    "cap_4040_bolt_cbore":   dict(profile="i_4040", family="cap", thread=8, cap_hole="cbore", cap_t=9, cap_oversize=1.0),
    "acc_3030_hook":         dict(profile="hfs6_3030", family="acc", thread=6, acc_type="hook"),
    "acc_3030_drivers":      dict(profile="hfs6_3030", family="acc", thread=6, acc_type="drivers"),
    "acc_2020_hexkeys":      dict(profile="hfs5_2020", family="acc", thread=5, acc_type="hexkeys", acc_n=7, acc_pitch=11),
    "acc_4040_wrenches_across": dict(profile="i_4040", family="acc", thread=8, acc_type="wrenches", acc_turn="across", acc_n=5, acc_d=6),
    "acc_3030_pliers":       dict(profile="hfs6_3030", family="acc", thread=6, acc_type="pliers", acc_n=3, acc_d=14),
    "acc_3030_magtray":      dict(profile="hfs6_3030", family="acc", thread=6, acc_type="tray", acc_mag_d=8, acc_mag_t=3),
    "acc_2020_wireclip":     dict(profile="hfs5_2020", family="acc", thread=5, acc_type="clip", acc_n=3, acc_wire_d=4, holes=1),
    "cap_3030_text":         dict(profile="hfs6_3030", family="cap", thread=8, brand_src="text", brand_text="SLOT", brand_font="mono", brand_bold=True),
    "sign_3030_slot":        dict(profile="hfs6_3030", family="sign", thread=6, sg_mount="slot", brand_src="text", brand_text="SLOTLAB", brand_font="sans", brand_bold=True, sg_w=110, sg_h=40),
    "sign_2020_bolts_serif": dict(profile="hfs5_2020", family="sign", thread=5, sg_mount="bolts", brand_src="text", brand_text="Bay 3", brand_font="serif", brand_mode="emboss", sg_h=45),
    "sign_3030_ears":        dict(profile="hfs6_3030", family="sign", thread=6, sg_mount="bolts", sg_holes="ears", brand_src="text", brand_text="@mdrndesigns", brand_align="centre", sg_w=100),
    "sign_3030_sides":       dict(profile="hfs6_3030", family="sign", thread=6, sg_mount="bolts", sg_where="sides", brand_src="text", brand_text="we are\nan island", brand_align="centre", sg_w=100, sg_h=40),
    "sign_3030_dual_inlay":  dict(profile="hfs6_3030", family="sign", thread=6, sg_mount="bolts", sg_where="sides", sg_holes="ears", brand_src="text", brand_text="TWO TONE", brand_bold=True, brand_align="centre", brand_dual=True, sg_w=100),
    "sign_3030_sides_ears":  dict(profile="hfs6_3030", family="sign", thread=6, sg_mount="bolts", sg_where="sides", sg_holes="ears", brand_src="text", brand_text="FULL FACE", brand_bold=True, brand_align="centre", sg_w=100),
    "sign_3030_two_rails":   dict(profile="hfs6_3030", family="sign", thread=6, sg_mount="bolts", sg_holes="ears", sg_where="both", brand_src="text", brand_text="PANEL", brand_bold=True, brand_align="centre", sg_w=100, sg_h=50),
    "splice_3030_sleeve":    dict(profile="hfs6_3030", family="splice", thread=6, sp_kind="sleeve", sp_faces=4),
    "splice_3030_bar":       dict(profile="hfs6_3030", family="splice", thread=6, sp_kind="bar"),
    "pivot_3030_arc":        dict(profile="hfs6_3030", family="pivot", thread=6, pv_lock="arc", angle=120),
    "pivot_3030_leafB":      dict(profile="hfs6_3030", family="pivot", thread=6, pv_lock="arc", pv_part="b"),
}

for name, over in SAMPLES.items():
    p = M.merge_params({})
    M.apply_profile(p, over["profile"])
    p.update(over)
    errs = M.validate(p)
    if errs:
        print(name, "INVALID", errs)
        continue
    part, sp, warns = M.build(p, export=True)
    ctx = M.context(p, sp)
    brand = sp.get("brand_solid")
    if brand is not None:
        open(f"{OUT}/{name}.3mf", "wb").write(M.write_3mf([("base", part.val()), ("brand", brand)], name))
        part = M.assembly(part, sp)
    cq.exporters.export(part, f"{OUT}/{name}.stl", tolerance=0.005, angularTolerance=0.05)
    cq.exporters.export(part, f"{OUT}/{name}.step")
    if ctx is not None:
        cq.exporters.export(ctx, f"{OUT}/_ctx.stl", tolerance=0.05, angularTolerance=0.3)
    render(f"{OUT}/{name}.stl", f"{OUT}/{name}_preview.png", f"{OUT}/_ctx.stl" if ctx is not None else None)
    json.dump(p, open(f"{OUT}/{name}_parameters.json", "w"), indent=2)
    print(name, "ok", warns)
os.remove(f"{OUT}/_ctx.stl")

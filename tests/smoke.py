"""Build one of each family with defaults, export STL + context, render."""
import os, sys, time, json, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import cadquery as cq
import trimesh
import model as M
from render import render

OUT = os.environ.get("SLOTLAB_OUT", os.path.join(tempfile.gettempdir(), "slotlab_smoke"))
os.makedirs(OUT, exist_ok=True)

CASES = {
    "tnut_hex":      dict(family="tnut", tn_fix="hex", thread=6),
    "tnut_thread":   dict(family="tnut", tn_fix="thread", thread=6, tn_thread_preview=True),
    "tnut_insert":   dict(family="tnut", tn_fix="insert", thread=5),
    "tnut_drop":     dict(family="tnut", tn_type="drop", tn_fix="thread", thread=6, tn_thread_preview=True),
    "tnut_end":      dict(family="tnut", tn_fix="hex", tn_load="end", thread=5, tn_len=18),
    "plate_90":      dict(family="plate", angle=90),
    "plate_120":     dict(family="plate", angle=120),
    "plate_180":     dict(family="plate", angle=180),
    "plate_sq":      dict(family="plate", angle=90, ends="square"),
    "elbow_90":      dict(family="elbow", angle=90),
    "elbow_120":     dict(family="elbow", angle=120),
    "elbow_90z":     dict(family="elbow", angle=90, z_arm="up"),
    "bracket_90":    dict(family="bracket", angle=90),
    "bracket_60":    dict(family="bracket", angle=60),
    "bracket_135":   dict(family="bracket", angle=135, web="full"),
    "bracket_rot90": dict(family="bracket", angle=90, br_rot=90, tongue=False),
    "cap":           dict(family="cap", thread=8),
    "cap_cbore":     dict(family="cap", thread=8, cap_hole="cbore", cap_plug="tee", cap_t=6),
    "acc_hook":      dict(family="acc", acc_type="hook"),
    "acc_drivers":   dict(family="acc", acc_type="drivers"),
    "acc_wr_across": dict(family="acc", acc_type="wrenches", acc_turn="across"),
    "acc_tray":      dict(family="acc", acc_type="tray"),
    "acc_clip":      dict(family="acc", acc_type="clip", acc_n=3),
    "acc_pliers":    dict(family="acc", acc_type="pliers", acc_d=14),
    "cap_text":      dict(family="cap", thread=8, brand_src="text", brand_text="SLOT", brand_font="mono"),
    "sign_slot":     dict(family="sign", brand_src="text", brand_text="SLOTLAB", brand_bold=True),
    "sign_bolts":    dict(family="sign", sg_mount="bolts", brand_src="text", brand_text="EXIT", brand_mode="through"),
    "splice_sleeve": dict(family="splice", sp_kind="sleeve", sp_faces=4),
    "splice_bar":    dict(family="splice", sp_kind="bar"),
    "pivot_arc":     dict(family="pivot", pv_lock="arc", angle=120),
}

only = sys.argv[1:]
for name, over in CASES.items():
    if only and name not in only:
        continue
    p = M.merge_params({})
    p.update(over)
    t = time.time()
    errs = M.validate(p)
    if errs:
        print(f"{name:14s} INVALID {errs}")
        continue
    try:
        part, sp, warns = M.build(p, export=True)
        ctx = M.context(p, sp)
    except Exception as e:
        print(f"{name:14s} BUILD FAIL {e}")
        continue
    stl = os.path.join(OUT, name + ".stl")
    cstl = os.path.join(OUT, name + "_ctx.stl")
    cq.exporters.export(part, stl, tolerance=0.01, angularTolerance=0.1)
    if ctx is not None:
        cq.exporters.export(ctx, cstl, tolerance=0.05, angularTolerance=0.3)
    else:
        cstl = None
    m = trimesh.load(stl)
    secs = []
    if p["family"] == "tnut":
        secs = [((0, 0, 0), (0, 1, 0), "section XZ"), ((sp["xs"][0], 0, 0), (1, 0, 0), "section YZ at hole")]
    elif p["family"] == "plate":
        secs = [((sp["xs"][0], 0, 0), (1, 0, 0), "section YZ at hole 1")]
    elif p["family"] == "elbow":
        secs = [((0, 0, 0), (0, 0, 1), "section XY"), ((0, 0, 0), (0, 1, 0), "section XZ")]
    elif p["family"] in ("cap", "acc", "sign", "splice", "pivot"):
        secs = [((0, 0, 0), (0, 1, 0), "section XZ"), ((0, 0, 0), (1, 0, 0), "section YZ")]
    else:
        secs = [((0, 0, 0), (0, 0, 1), "section XY")]
    render(stl, os.path.join(OUT, name + ".png"), cstl, secs)
    print(f"{name:14s} {time.time()-t:5.1f}s valid={part.val().isValid()} wt={m.is_watertight} "
          f"bodies={len(m.split(only_watertight=False))} vol={m.volume:8.1f} bbox={[round(x,1) for x in m.extents]} "
          f"warn={warns}")

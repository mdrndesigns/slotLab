"""Quick orthographic renders of an STL (no GPU): iso + 3 views + a section."""
import sys
import numpy as np
import trimesh
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection


def view(ax, mesh, R, light=(0.3, 0.5, 0.8), ctx=None, title=""):
    def draw(m, base, alpha=1.0, edge=0.15):
        v = m.vertices @ R.T
        f = m.faces
        tri = v[f]
        n = m.face_normals @ R.T
        depth = tri[:, :, 2].mean(axis=1)
        order = np.argsort(depth)
        shade = np.clip(0.35 + 0.65 * np.abs(n @ np.array(light) / np.linalg.norm(light)), 0, 1)
        cols = np.outer(shade, base)
        cols = np.clip(cols, 0, 1)
        rgba = np.concatenate([cols, np.full((len(cols), 1), alpha)], axis=1)
        pc = PolyCollection(tri[order][:, :, :2], facecolors=rgba[order], edgecolors=(0, 0, 0, edge), linewidths=0.2)
        ax.add_collection(pc)
    if ctx is not None:
        draw(ctx, np.array([0.75, 0.75, 0.75]), alpha=0.5, edge=0.1)
    draw(mesh, np.array([0.25, 0.25, 1.0]))
    allv = mesh.vertices @ R.T
    if ctx is not None:
        allv = np.vstack([allv, ctx.vertices @ R.T])
    lo, hi = allv.min(axis=0), allv.max(axis=0)
    pad = 0.05 * (hi - lo).max()
    ax.set_xlim(lo[0] - pad, hi[0] + pad)
    ax.set_ylim(lo[1] - pad, hi[1] + pad)
    ax.set_aspect("equal")
    ax.set_title(title, fontsize=8)
    ax.axis("off")


def rot(ax_, deg):
    a = np.radians(deg)
    c, s = np.cos(a), np.sin(a)
    if ax_ == "x":
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    if ax_ == "y":
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def section(ax, mesh, origin, normal, title=""):
    s = mesh.section(plane_origin=origin, plane_normal=normal)
    if s is None:
        ax.set_title(title + " (no section)", fontsize=8)
        ax.axis("off")
        return
    p, _ = s.to_2D()
    for e in p.entities:
        pts = p.vertices[e.points]
        ax.plot(pts[:, 0], pts[:, 1], "k-", lw=0.7)
    ax.set_aspect("equal")
    ax.set_title(title, fontsize=8)
    ax.grid(True, lw=0.2)


def render(stl, out, ctx_stl=None, sections=()):
    m = trimesh.load(stl)
    ctx = trimesh.load(ctx_stl) if ctx_stl else None
    n = 4 + len(sections)
    cols = 4
    rows = int(np.ceil(n / cols))
    fig, axs = plt.subplots(rows, cols, figsize=(4 * cols, 4 * rows))
    axs = np.array(axs).reshape(-1)
    iso = rot("x", -60) @ rot("z", 30)
    view(axs[0], m, iso, ctx=ctx, title="iso")
    view(axs[1], m, np.eye(3), ctx=ctx, title="top (XY)")
    view(axs[2], m, rot("x", -90), ctx=ctx, title="front (XZ)")
    view(axs[3], m, rot("x", -90) @ rot("z", -90), ctx=ctx, title="side (YZ)")
    for i, (o, nrm, t) in enumerate(sections):
        section(axs[4 + i], m, o, nrm, t)
    for a in axs[n:]:
        a.axis("off")
    fig.tight_layout()
    fig.savefig(out, dpi=110)
    plt.close(fig)
    return m


if __name__ == "__main__":
    render(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)

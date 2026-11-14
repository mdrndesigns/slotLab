#!/usr/bin/env python3
"""
SLOTLAB - local parametric front end for T-slot extrusion hardware.

    python3 app.py

Serves http://localhost:8767. Sliders in the browser, CadQuery on the
server. The browser never computes geometry: it displays the mesh the
server built, so what you see is what exports. Sister of BOXLAB and
KNOBLAB.
"""

import argparse
import io
import json
import os
import tempfile
import threading
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import cadquery as cq

import branding as B
import fasteners as F
import model as M
import profiles as P

HERE = os.path.dirname(os.path.abspath(__file__))
KERNEL_LOCK = threading.Lock()   # OpenCascade is not reentrant
CONTEXT_CACHE = {}               # extrusion stubs change rarely; cache by key
EMPTY_STL = bytes(84)            # binary STL with zero triangles: "no context"


def export_bytes(obj, ext, **kw):
    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as fh:
        path = fh.name
    try:
        cq.exporters.export(obj, path, **kw)
        with open(path, "rb") as fh:
            return fh.read()
    finally:
        os.unlink(path)


def stats_for(result):
    shape = result.val()
    bb = shape.BoundingBox()
    return {"bbox": [round(bb.xlen, 2), round(bb.ylen, 2), round(bb.zlen, 2)],
            "volume": round(shape.Volume() / 1000.0, 2),
            "valid": bool(shape.isValid())}


def catalog():
    return {
        "profiles": {k: {**v} for k, v in P.PROFILES.items()},
        "profile_order": P.ORDER,
        "geom_keys": list(P.GEOM_KEYS),
        "materials": F.MATERIALS,
        "families": list(M.FAMILIES),
        "sizes": F.SIZES,
        "slot_threads": {str(k): v for k, v in P.SLOT_THREADS.items()},
        "slot_default": {str(k): v for k, v in P.SLOT_DEFAULT_THREAD.items()},
        "nuts": {k: v["label"] for k, v in F.NUTS.items()},
        "steel_nuts": {str(k): v for k, v in P.STEEL_NUTS.items()},
        "fonts": B.available_fonts(),
        "acc_types": list(M.ACC_TYPES),
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype, extra=None):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _params(self, qs):
        return M.merge_params({k: v[0] for k, v in qs.items()})

    def do_GET(self):
        u = urlparse(self.path)
        qs = parse_qs(u.query)

        if u.path in ("/", "/index.html"):
            with open(os.path.join(HERE, "index.html"), "rb") as fh:
                return self._send(200, fh.read(), "text/html; charset=utf-8")

        if u.path == "/defaults":
            return self._send(200, json.dumps({"defaults": M.DEFAULTS, "catalog": catalog()}),
                              "application/json")

        if u.path == "/preview.stl":
            p = self._params(qs)
            errs = M.validate(p)
            if errs:
                return self._send(400, json.dumps({"errors": errs}), "application/json")
            try:
                with KERNEL_LOCK:
                    result, spec, warnings = M.build(p)
                    data = export_bytes(result, "stl", tolerance=0.03, angularTolerance=0.2)
                    brand_tris = 0
                    if spec.get("brand_solid") is not None:
                        # second-filament body appended after the base triangles; the viewer colours it
                        bdata, brand_tris = M.stl_bytes(spec["brand_solid"], 0.03, 0.2)
                        data = M.stl_merge(data, bdata)
                    stats = {"part": stats_for(M.assembly(result, spec)), "derived": M.derived(p, spec),
                             "warnings": warnings, "context_key": M.context_key(p, spec),
                             "brand_tris": brand_tris}
            except Exception as e:
                return self._send(400, json.dumps({"errors": [f"Build failed: {e}"]}), "application/json")
            return self._send(200, data, "model/stl", {"X-Stats": json.dumps(stats)})

        if u.path == "/context.stl":
            p = self._params(qs)
            errs = M.validate(p)
            if errs:
                return self._send(400, json.dumps({"errors": errs}), "application/json")
            try:
                spec = M.spec(p)
                key = M.context_key(p, spec)
                if key in CONTEXT_CACHE:
                    return self._send(200, CONTEXT_CACHE[key], "model/stl")
                with KERNEL_LOCK:
                    ctx = M.context(p, spec)
                    data = EMPTY_STL if ctx is None else export_bytes(ctx, "stl", tolerance=0.08, angularTolerance=0.4)
            except Exception as e:
                return self._send(400, json.dumps({"errors": [f"Context failed: {e}"]}), "application/json")
            if len(CONTEXT_CACHE) > 40:
                CONTEXT_CACHE.clear()
            CONTEXT_CACHE[key] = data
            return self._send(200, data, "model/stl")

        if u.path == "/export":
            p = self._params(qs)
            errs = M.validate(p)
            if errs:
                return self._send(400, json.dumps({"errors": errs}), "application/json")
            name = qs.get("name", ["part"])[0].strip() or "part"
            name = "".join(c for c in name if c.isalnum() or c in "-_")
            with KERNEL_LOCK:
                result, spec, warnings = M.build(p, export=True)
                brand = spec.get("brand_solid")
                whole = M.assembly(result, spec)
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                    z.writestr(f"{name}.step", export_bytes(whole, "step"))
                    if brand is None:
                        z.writestr(f"{name}.stl", export_bytes(result, "stl", tolerance=0.005, angularTolerance=0.05))
                        z.writestr(f"{name}.3mf", export_bytes(result, "3mf"))
                    else:
                        # two filaments: one 3MF object with two parts, plus each part as STL
                        base_stl, _ = M.stl_bytes(result.val(), 0.005, 0.05)
                        brand_stl, _ = M.stl_bytes(brand, 0.005, 0.05)
                        z.writestr(f"{name}.3mf", M.write_3mf([(f"{name}_base", result.val()), (f"{name}_brand", brand)], name))
                        z.writestr(f"{name}_base.stl", base_stl)
                        z.writestr(f"{name}_brand.stl", brand_stl)
                        z.writestr(f"{name}.stl", M.stl_merge(base_stl, brand_stl))
                        z.writestr(f"{name}_TWO_FILAMENTS.txt", DUAL_NOTE.format(name=name))
                    svg_name = None
                    if p["brand_src"] == "svg" and p["brand_svg"] in B.SVG_STORE:
                        svg_name = f"{name}_brand.svg"
                        z.writestr(svg_name, B.SVG_STORE[p["brand_svg"]])
                    z.writestr(f"{name}_parameters.json", json.dumps(p, indent=2))
                    z.writestr(f"{name}_spec.json", json.dumps(
                        {"derived": M.derived(p, spec), "warnings": warnings,
                         "part": stats_for(whole)}, indent=2))
                    z.writestr(f"{name}_model.py", script_for(p, svg_name))
            return self._send(200, buf.getvalue(), "application/zip",
                              {"Content-Disposition": f'attachment; filename="{name}.zip"'})

        return self._send(404, "not found", "text/plain")

    def do_POST(self):
        u = urlparse(self.path)
        if u.path != "/svg":
            return self._send(404, "not found", "text/plain")
        n = int(self.headers.get("Content-Length", "0") or 0)
        if n <= 0 or n > B.SVG_MAX:
            return self._send(400, json.dumps({"errors": ["SVG missing or over 2 MB."]}), "application/json")
        text = self.rfile.read(n).decode("utf-8", "replace")
        try:
            key, info = B.store_svg(text)
        except Exception as e:
            return self._send(400, json.dumps({"errors": [f"SVG rejected: {e}"]}), "application/json")
        return self._send(200, json.dumps({"key": key, **info}), "application/json")


DUAL_NOTE = """{name}: two-filament branding
=================================

{name}.3mf is one object with two parts: "{name}_base" and "{name}_brand".

Bambu Studio
  1. File > Import > Import 3MF/STL/STEP/SVG/OBJ/AMF..., pick {name}.3mf.
     (If a dialog asks whether to load as a single object with multiple
     parts, answer Yes.)
  2. In the object list on the right, expand the object: two parts.
  3. Right-click "{name}_brand" > Change filament > pick the second
     filament. The base keeps filament 1. Or select the part and use the
     filament dropdown in the toolbar.
  4. Slice. For a flush inlay (Recessed) the brand part fills the pocket
     exactly; Raised stands on the face; Cut through runs through the
     whole plate and shows on both sides.

Fallback: import {name}_base.stl and {name}_brand.stl together (multi-select)
and answer Yes to "load as a single object with multiple parts"; they share
the same origin, so they land in place.

Tips: use the same material family for both filaments (PETG + PETG) so the
parts bond; a prime tower is on by default; a 0.2 mm first layer with a
0.6 mm inlay gives three clean colour layers.
"""


def script_for(p, svg_name=None):
    lines = [
        "# Generated by SLOTLAB. Standalone - edit and re-run with:",
        "#   python3 this_file.py     (needs model.py, branding.py, fasteners.py,",
        "#                             profiles.py and the fonts folder beside it)",
        "import sys, os",
        "HERE = os.path.dirname(os.path.abspath(__file__))",
        "sys.path.insert(0, HERE)",
        "import cadquery as cq",
        "import model as M",
        "",
        "PARAMS = {",
    ]
    for k, v in p.items():
        lines.append(f"    {k!r}: {v!r},")
    lines += ["}", ""]
    if svg_name:
        lines += [
            "import branding as B",
            f"with open(os.path.join(HERE, {svg_name!r}), encoding='utf-8') as fh:",
            "    B.SVG_STORE[PARAMS['brand_svg']] = fh.read()",
            "",
        ]
    lines += [
        "errs = M.validate(PARAMS)",
        "if errs:",
        "    raise SystemExit('\\n'.join(errs))",
        "result, spec, warnings = M.build(PARAMS, export=True)",
        "brand = spec.get('brand_solid')",
        "cq.exporters.export(M.assembly(result, spec), 'part.step')",
        "if brand is None:",
        "    cq.exporters.export(result, 'part.stl', tolerance=0.005, angularTolerance=0.05)",
        "    cq.exporters.export(result, 'part.3mf')",
        "else:   # two filaments: one 3MF object with two parts",
        "    open('part.3mf', 'wb').write(M.write_3mf([('base', result.val()), ('brand', brand)], 'part'))",
        "    open('part_base.stl', 'wb').write(M.stl_bytes(result.val(), 0.005, 0.05)[0])",
        "    open('part_brand.stl', 'wb').write(M.stl_bytes(brand, 0.005, 0.05)[0])",
        "print('exported', M.derived(PARAMS, spec), warnings)",
    ]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8767)
    ap.add_argument("--no-open", action="store_true")
    a = ap.parse_args()
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    except OSError as e:
        print(f"Cannot bind port {a.port}: {e}")
        print(f"Something is already using it. Try:  python3 app.py --port {a.port + 1}")
        raise SystemExit(1)
    url = f"http://localhost:{a.port}"
    print(f"SLOTLAB running at {url}   (ctrl-C to stop)")
    if not a.no_open:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()

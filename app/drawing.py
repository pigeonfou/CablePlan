import csv
import io
from html import escape

from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.pagesizes import A3, A4, landscape
from reportlab.pdfgen import canvas

from .models import awg_mm2, length_mm


def layout(assembly):
    positions, endpoints = {}, {}
    sides = {"left": 0, "right": 0, "free": 0}
    for c in assembly.connectors:
        n = sides[c.side]
        sides[c.side] += 1
        x = c.x if c.side == "free" else (70 if c.side == "left" else 760)
        y = c.y if c.side == "free" else 95 + n * (max(len(c.pins), 6) * 30 + 100)
        positions[c.id] = (x, y)
        for i, p in enumerate(c.pins):
            endpoints[c.id, p.id] = (x + (150 if c.side != "right" else 0), y + 50 + i * 30)
        endpoints[c.id, None] = (x + (150 if c.side != "right" else 0), y + 50 + len(c.pins) * 30)
    height = max([v[1] for v in endpoints.values()] + [400]) + 190
    width = max([v[0] for v in endpoints.values()] + [980]) + 50
    return positions, endpoints, width, height


def wire_rows(assembly):
    cs = {c.id: c for c in assembly.connectors}
    rows = []
    for edge in assembly.connections:
        a, b = cs[edge.start.connector_id], cs[edge.end.connector_id]
        pa = next(p.name for p in a.pins if p.id == edge.start.pin_id)
        pb = next(p.name for p in b.pins if p.id == edge.end.pin_id)
        w = edge.conductor
        rows.append(
            [
                a.reference,
                pa,
                b.reference,
                pb,
                w.color_name,
                "" if w.awg is None else w.awg,
                round(w.section_mm2 or awg_mm2(w.awg), 3),
                w.length,
                w.unit,
                w.reference,
                w.comment,
            ]
        )
    return rows


def svg(assembly, project):
    pos, endpoints, width, height = layout(assembly)
    el = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        'role="img" aria-label="Plan de câblage">',
        f'<rect width="{width}" height="{height}" fill="#fff"/>',
    ]

    def text(x, y, value, size=12):
        el.append(
            f'<text x="{x}" y="{y}" font-family="sans-serif" font-size="{size}" '
            f'fill="#172b43">{escape(str(value))}</text>'
        )

    d = assembly.drawing
    text(70, 28, f"{d.designation or project['name']} • {d.cable_reference}", 18)
    text(300, 65, f"Longueur {d.length_mm:g} mm (+{d.tolerance_plus_mm:g}/−{d.tolerance_minus_mm:g})")
    el.append('<path d="M 220 72 H 760 M 220 66 V 78 M 760 66 V 78" stroke="#52667c" fill="none"/>')
    for edge in assembly.connections:
        x1, y1 = endpoints[edge.start.connector_id, edge.start.pin_id]
        x2, y2 = endpoints[edge.end.connector_id, edge.end.pin_id]
        mid = (x1 + x2) / 2
        path = f"M {x1} {y1} C {mid} {y1}, {mid} {y2}, {x2} {y2}"
        el.append(
            f'<g data-wire="{escape(edge.id, quote=True)}" cursor="pointer">'
            f'<path d="{path}" fill="none" stroke="#334155" stroke-width="6"/>'
            f'<path d="{path}" fill="none" stroke="{edge.conductor.color}" stroke-width="4"/></g>'
        )
        w = edge.conductor
        section = f"AWG {w.awg}" if w.awg is not None else f"{w.section_mm2:g} mm²"
        text(
            mid - 80, (y1 + y2) / 2 - 9, f"{w.marker} {w.color_name} · {section} · {w.length:g} {w.unit}", 10
        )
    for i, shield in enumerate(assembly.shields):
        a = endpoints[shield.start.connector_id, shield.start.pin_id] if shield.start else (260, height - 210)
        b = endpoints[shield.end.connector_id, shield.end.pin_id] if shield.end else (710, height - 210)
        y = max(a[1], b[1]) + 25 + i * 32
        el.append(
            f'<path d="M {a[0]} {a[1]} V {y} H {b[0]} V {b[1]}" '
            'fill="none" stroke="#52667c" stroke-width="2" stroke-dasharray="5 4"/>'
        )
        text((a[0] + b[0]) / 2 - 60, y - 6, f"{shield.designation} · {shield.length_mm:g} mm")
    for i, sheath in enumerate(assembly.sheaths):
        y = height - 170 - i * 22
        el.append(f'<rect x="270" y="{y - 10}" width="440" height="20" fill="#e2e8f0" stroke="#64748b"/>')
        text(290, y + 4, f"{sheath.designation} · {sheath.length_mm:g} mm · début {sheath.start_mm:g} mm", 10)
    for c in assembly.connectors:
        x, y = pos[c.id]
        el.append(
            f'<rect x="{x}" y="{y}" width="150" height="{80 + len(c.pins) * 30}" '
            'rx="8" fill="#f1f5f9" stroke="#52667c"/>'
        )
        text(x + 12, y + 24, c.reference, 16)
        for p in c.pins:
            px, py = endpoints[c.id, p.id]
            el.append(
                f'<circle cx="{px}" cy="{py}" r="6" fill="#fff" stroke="#172b43" '
                f'data-connector="{escape(c.id, quote=True)}" data-pin="{escape(p.id, quote=True)}" '
                'cursor="crosshair"/>'
            )
            text(x + 15 if c.side == "right" else x + 120, py + 4, p.name)
        text(x + 12, y + 67 + len(c.pins) * 30, "Boîtier", 10)
        text(x, y + 105 + len(c.pins) * 30, "Vue soudure" if c.view == "solder" else "Vue accouplement", 10)
    y = height - 115
    el.append(f'<rect x="60" y="{y}" width="{width - 120}" height="95" fill="none" stroke="#52667c"/>')
    text(75, y + 22, f"Projet : {project['name']} | Client : {project['client']}")
    text(75, y + 44, f"Plan : {d.drawing_number} | Révision : {d.revision} | Créateur : {d.creator}")
    text(75, y + 66, f"Validation : {d.validated_by} {d.validation_date} | {d.comment}")
    text(75, y + 85, "CablePlan • Document technique confidentiel • 1/1", 10)
    el.append("</svg>")
    return "".join(el)


def csv_export(assembly):
    stream = io.StringIO()
    writer = csv.writer(stream, delimiter=";")
    writer.writerow(
        [
            "Départ",
            "Pin départ",
            "Arrivée",
            "Pin arrivée",
            "Couleur",
            "AWG",
            "Section mm²",
            "Longueur",
            "Unité",
            "Référence",
            "Commentaire",
        ]
    )
    for row in wire_rows(assembly):
        # Prevent spreadsheet formula injection while retaining values in the model.
        writer.writerow(
            ["'" + v if isinstance(v, str) and v.startswith(("=", "+", "-", "@")) else v for v in row]
        )
    return "\ufeff" + stream.getvalue()


def pdf(assembly, project, page_format="A4"):
    stream = io.BytesIO()
    page_w, page_h = landscape(A3 if page_format == "A3" else A4)
    out = canvas.Canvas(stream, pagesize=(page_w, page_h), pageCompression=1)
    out.setTitle(assembly.drawing.designation or project["name"])
    pos, endpoints, width, height = layout(assembly)
    scale = min((page_w - 40) / width, (page_h - 70) / height)
    out.saveState()
    out.translate(20, page_h - 30)
    out.scale(scale, -scale)

    def line(a, b, color=black, thickness=1):
        out.setStrokeColor(color)
        out.setLineWidth(thickness)
        out.line(*a, *b)

    def label(x, y, s, size=12):
        out.saveState()
        out.translate(x, y)
        out.scale(1, -1)
        out.setFillColor(black)
        out.setFont("Helvetica", size)
        out.drawString(0, 0, str(s))
        out.restoreState()

    d = assembly.drawing
    label(60, 25, d.designation or project["name"], 20)
    label(300, 65, f"Longueur {d.length_mm:g} mm (+{d.tolerance_plus_mm:g}/-{d.tolerance_minus_mm:g})")
    line((220, 72), (760, 72))
    for edge in assembly.connections:
        a = endpoints[edge.start.connector_id, edge.start.pin_id]
        b = endpoints[edge.end.connector_id, edge.end.pin_id]
        path = out.beginPath()
        path.moveTo(*a)
        mid = (a[0] + b[0]) / 2
        path.curveTo(mid, a[1], mid, b[1], *b)
        for color, thickness in [(HexColor("#334155"), 6), (HexColor(edge.conductor.color), 4)]:
            out.setStrokeColor(color)
            out.setLineWidth(thickness)
            out.drawPath(path)
        w = edge.conductor
        section = f"AWG {w.awg}" if w.awg is not None else f"{w.section_mm2:g} mm2"
        label(mid - 90, (a[1] + b[1]) / 2 - 10, f"{w.color_name} / {section} / {w.length:g} {w.unit}", 10)
    for i, shield in enumerate(assembly.shields):
        a = endpoints[shield.start.connector_id, shield.start.pin_id] if shield.start else (260, height - 210)
        b = endpoints[shield.end.connector_id, shield.end.pin_id] if shield.end else (710, height - 210)
        y = max(a[1], b[1]) + 25 + i * 32
        out.setDash(5, 4)
        line(a, (a[0], y))
        line((a[0], y), (b[0], y))
        line((b[0], y), b)
        out.setDash()
        label((a[0] + b[0]) / 2 - 60, y - 6, f"{shield.designation} / {shield.length_mm:g} mm")
    for i, sheath in enumerate(assembly.sheaths):
        y = height - 170 - i * 22
        out.setFillColor(HexColor("#e2e8f0"))
        out.setStrokeColor(HexColor("#64748b"))
        out.rect(270, y - 10, 440, 20, fill=1)
        label(
            290, y + 4, f"{sheath.designation} / {sheath.length_mm:g} mm / début {sheath.start_mm:g} mm", 10
        )
    for c in assembly.connectors:
        x, y = pos[c.id]
        out.setStrokeColor(black)
        out.setFillColor(HexColor("#f1f5f9"))
        out.setLineWidth(1)
        out.roundRect(x, y, 150, 80 + len(c.pins) * 30, 8, fill=1)
        label(x + 12, y + 24, c.reference, 16)
        for p in c.pins:
            px, py = endpoints[c.id, p.id]
            out.setFillColor(white)
            out.circle(px, py, 5, fill=1)
            label(x + 15 if c.side == "right" else x + 120, py + 4, p.name)
        label(x + 12, y + 67 + len(c.pins) * 30, "Boîtier", 10)
        label(x, y + 105 + len(c.pins) * 30, "Vue soudure" if c.view == "solder" else "Vue accouplement", 10)
    table_rows = wire_rows(assembly)
    per_page = int((page_h - 110) / 18)
    total_pages = 1 + max(1, (len(table_rows) + per_page - 1) // per_page)
    y = height - 115
    out.setStrokeColor(black)
    out.rect(60, y, width - 120, 95)
    label(75, y + 22, f"Projet : {project['name']} / Client : {project['client']}")
    label(75, y + 44, f"Plan : {d.drawing_number} / Révision : {d.revision} / Créateur : {d.creator}")
    label(75, y + 66, f"Validation : {d.validated_by} {d.validation_date} / {d.comment}")
    label(75, y + 85, f"CablePlan / Document technique confidentiel / 1/{total_pages}", 10)
    out.restoreState()
    for page_idx in range(max(1, (len(table_rows) + per_page - 1) // per_page)):
        out.showPage()
        out.setFont("Helvetica-Bold", 14)
        out.drawString(30, page_h - 35, "Tableau de câblage")
        out.setFont("Helvetica", 9)
        y = page_h - 65
        for row in table_rows[page_idx * per_page : (page_idx + 1) * per_page]:
            value = f"{row[0]}-{row[1]} > {row[2]}-{row[3]} | {row[4]} | AWG {row[5]} | {row[6]} mm2 | {row[7]} {row[8]}"
            out.drawString(30, y, value)
            y -= 18
        out.drawRightString(page_w - 30, 25, f"CablePlan / {page_idx + 2}/{total_pages}")
    out.save()
    return stream.getvalue()


def bom(assembly):
    rows = []
    for c in assembly.connectors:
        rows.append(
            {
                "kind": "Connecteur",
                "reference": c.part_number or c.reference,
                "designation": c.designation,
                "quantity": 1,
                "unit": "pièce",
            }
        )
    for edge in assembly.connections:
        w = edge.conductor
        rows.append(
            {
                "kind": "Conducteur",
                "reference": w.reference or w.part_number,
                "designation": w.color_name,
                "quantity": length_mm(w.length, w.unit),
                "unit": "mm",
            }
        )
    for s in assembly.shields + assembly.sheaths:
        rows.append(
            {
                "kind": "Blindage" if hasattr(s, "coverage") else "Gaine",
                "reference": s.reference,
                "designation": s.designation,
                "quantity": s.length_mm,
                "unit": "mm",
            }
        )
    for a in assembly.accessories:
        rows.append(
            {
                "kind": a.kind,
                "reference": a.reference,
                "designation": a.designation,
                "quantity": a.quantity,
                "unit": "pièce",
            }
        )
    return rows

"""
PDF Report Generator — AML IntelliGent Platform
================================================
Generates a professional A4 PDF report from agent analysis results.
Requires: reportlab
"""

import io
import json
from datetime import date

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    HRFlowable, PageBreak, SimpleDocTemplate, Spacer, Table, TableStyle
)
from reportlab.platypus import Paragraph as P

# ── Palette ───────────────────────────────────────────────────────
C_BLACK  = colors.HexColor("#1E2328")
C_DARK   = colors.HexColor("#1E293B")
C_MED    = colors.HexColor("#475569")
C_LIGHT  = colors.HexColor("#94A3B8")
C_BORDER = colors.HexColor("#E2E8F0")
C_BG     = colors.HexColor("#F8FAFC")

_RISK_PALETTE = {
    "CRITICO":      (colors.HexColor("#F3E8FF"), colors.HexColor("#6B21A8")),
    "ALTO":         (colors.HexColor("#FEE2E2"), colors.HexColor("#B91C1C")),
    "HIGH":         (colors.HexColor("#FEE2E2"), colors.HexColor("#B91C1C")),
    "MEDIO-ALTO":   (colors.HexColor("#FFEDD5"), colors.HexColor("#C2410C")),
    "MEDIO":        (colors.HexColor("#FEF9C3"), colors.HexColor("#92400E")),
    "MEDIUM":       (colors.HexColor("#FEF9C3"), colors.HexColor("#92400E")),
    "BASSO":        (colors.HexColor("#DCFCE7"), colors.HexColor("#15803D")),
    "LOW":          (colors.HexColor("#DCFCE7"), colors.HexColor("#15803D")),
    "NON_VALUTABILE":(colors.HexColor("#F3F4F6"), colors.HexColor("#6B7280")),
}
_EV_PALETTE = {
    "CRITICO":    (colors.HexColor("#FDECEA"), colors.HexColor("#B71C1C"), colors.HexColor("#C62828")),
    "ANOMALIA":   (colors.HexColor("#FDECEA"), colors.HexColor("#B71C1C"), colors.HexColor("#C62828")),
    "ATTENZIONE": (colors.HexColor("#FFFDE7"), colors.HexColor("#F57F17"), colors.HexColor("#F9A825")),
}
_EV_DEFAULT   = (colors.HexColor("#F5F5F5"), colors.HexColor("#424242"), colors.HexColor("#BDBDBD"))


def _ev_style(livello: str):
    return _EV_PALETTE.get((livello or "").upper(), _EV_DEFAULT)


# ── Styles ────────────────────────────────────────────────────────
def _styles():
    def s(name, **kw):
        return ParagraphStyle(name, **kw)
    return {
        "page_title": s("page_title", fontName="Helvetica-Bold",
                        fontSize=20, textColor=C_BLACK, spaceAfter=3, leading=24),
        "page_sub":   s("page_sub",   fontName="Helvetica",
                        fontSize=10,  textColor=C_MED,   spaceAfter=2, leading=13),
        "sec_head":   s("sec_head",   fontName="Helvetica-Bold",
                        fontSize=12,  textColor=C_BLACK, spaceBefore=8, spaceAfter=3, leading=15),
        "label":      s("label",      fontName="Helvetica-Bold",
                        fontSize=6.5, textColor=C_LIGHT, spaceAfter=1, leading=9,
                        letterSpacing=0.6),
        "field":      s("field",      fontName="Helvetica",
                        fontSize=8.5, textColor=C_DARK,  spaceAfter=0, leading=11),
        "body":       s("body",       fontName="Helvetica",
                        fontSize=8.5, textColor=C_DARK,  spaceAfter=4, leading=12),
        "narrative":  s("narrative",  fontName="Helvetica",
                        fontSize=8.5, textColor=C_DARK,  spaceAfter=6, leading=13,
                        alignment=TA_JUSTIFY),
        "ev_text":    s("ev_text",    fontName="Helvetica",
                        fontSize=8.5, textColor=C_DARK,  spaceAfter=2, leading=12),
        "ev_norm":    s("ev_norm",    fontName="Helvetica-Oblique",
                        fontSize=7,   textColor=C_MED,   spaceAfter=0, leading=10),
        "small":      s("small",      fontName="Helvetica",
                        fontSize=7,   textColor=C_LIGHT, spaceAfter=2, leading=9),
        "risk_big":   s("risk_big",   fontName="Helvetica-Bold",
                        fontSize=16,  textColor=C_BLACK, leading=20),
    }


# ── Helpers ───────────────────────────────────────────────────────
def _parse(text: str):
    if not text:
        return None
    s = text.find("{"); e = text.rfind("}") + 1
    if s >= 0 and e > s:
        try:
            return json.loads(text[s:e])
        except Exception:
            pass
    return None


def _tbl(rows, col_widths, row_bgs=True, box=True):
    t = Table(rows, colWidths=col_widths)
    style = [
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW",    (0, 0), (-1, -2), 0.3, C_BORDER),
    ]
    if row_bgs:
        style.append(("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, C_BG]))
    if box:
        style.append(("BOX", (0, 0), (-1, -1), 0.5, C_BORDER))
    t.setStyle(TableStyle(style))
    return t


def _ev_block(ev: dict, W: float, st: dict) -> Table:
    """Build a single evidence row table."""
    l = (ev.get("livello") or "").upper()
    bg, fg, bd = _ev_style(l)
    lbl = {"CRITICO": "CRITICO", "ANOMALIA": "ANOMALIA",
           "ATTENZIONE": "ATTENZIONE"}.get(l, "INFO")
    norm = ev.get("normativa", "")
    lbl_style = ParagraphStyle("_ev_l", fontName="Helvetica-Bold",
                                fontSize=7.5, textColor=fg, leading=10)
    rows = [[P(f"<b>{lbl}</b>", lbl_style), P(ev.get("evidenza", ""), st["ev_text"])]]
    if norm:
        rows.append([P("", st["small"]), P(norm, st["ev_norm"])])
    t = Table(rows, colWidths=[2.2*cm, W - 2.2*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), bg),
        ("BOX",           (0, 0), (-1, -1), 0.5, bd),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))
    return t


# ── Main builder ──────────────────────────────────────────────────
def build_pdf(
    company_name: str,
    counterparty_info: dict,
    section_results: dict,   # {key: raw_json_string}
    sections_meta: list,     # MAIN_SECTIONS list of dicts
    final_result: str = None,
    case_id: str = "",
) -> bytes:
    """Build the full AML report PDF and return raw bytes."""
    buf = io.BytesIO()
    W = A4[0] - 4 * cm  # usable width

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm,  bottomMargin=2*cm,
        title=f"Rapporto AML — {company_name}",
    )
    st = _styles()
    story = []

    # ── HEADER ────────────────────────────────────────────────────
    story.append(Spacer(1, 4*mm))
    story.append(P("RAPPORTO DI ADEGUATA VERIFICA AML", st["page_sub"]))
    story.append(P(company_name, st["page_title"]))
    story.append(P(
        f"Data analisi: {date.today().strftime('%d/%m/%Y')}" +
        (f"&nbsp;&nbsp;·&nbsp;&nbsp;Pratica: {case_id}" if case_id else ""),
        st["small"]))
    story.append(HRFlowable(width=W, thickness=1, color=C_BORDER, spaceBefore=4, spaceAfter=8))

    # ── COUNTERPARTY CARD ─────────────────────────────────────────
    if counterparty_info:
        ci = counterparty_info
        ateco_val = (f'{ci["ateco"]} — {ci["descrizioneAttivita"]}'
                     if ci.get("ateco") and ci.get("descrizioneAttivita")
                     else ci.get("ateco") or ci.get("descrizioneAttivita"))
        cfpiva = " / ".join(filter(None, [ci.get("codiceFiscale"), ci.get("partitaIva")])) or None

        info_fields = [
            ("Forma giuridica",  ci.get("formaGiuridica")),
            ("Sede legale",      ci.get("sedeLegale")),
            ("ATECO",            ateco_val),
            ("CF / P.IVA",       cfpiva),
            ("Capitale sociale", ci.get("capitaleSociale")),
            ("Costituzione",     ci.get("dataCostituzione")),
        ]
        rows = [[P(lbl.upper(), st["label"]), P(val or "—", st["field"])]
                for lbl, val in info_fields if val]
        if rows:
            story.append(_tbl(rows, [3.5*cm, W - 3.5*cm]))
            story.append(Spacer(1, 6*mm))

    # ── SECTION RESULTS ───────────────────────────────────────────
    for sec in sections_meta:
        key  = sec["key"]
        raw  = section_results.get(key, "")
        parsed = _parse(raw)
        if not parsed:
            continue

        risk = (parsed.get("rischioComplessivo") or
                parsed.get("customerRiskRating") or "").upper()
        risk_bg, risk_fg = _RISK_PALETTE.get(risk, (C_BG, C_MED))

        story.append(HRFlowable(width=W, thickness=0.5, color=C_BORDER,
                                spaceBefore=6, spaceAfter=2))

        # Section header: name left, risk badge right
        risk_lbl_style = ParagraphStyle("_rl", fontName="Helvetica-Bold",
                                         fontSize=8, textColor=risk_fg,
                                         alignment=TA_RIGHT, leading=10)
        hdr_t = Table(
            [[P(f'{sec["number"]} — {sec["full_label"]}', st["sec_head"]),
              P(f" {risk} ", risk_lbl_style)]],
            colWidths=[W * 0.75, W * 0.25])
        hdr_t.setStyle(TableStyle([
            ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",   (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
            ("BACKGROUND",   (1, 0), (1, 0),   risk_bg),
        ]))
        story.append(hdr_t)

        # Evidences
        evidenze = parsed.get("principaliEvidenze", [])
        if evidenze:
            story.append(P("PRINCIPALI EVIDENZE AML", st["label"]))
            story.append(Spacer(1, 1.5*mm))
            for ev in evidenze:
                story.append(_ev_block(ev, W, st))
                story.append(Spacer(1, 1.5*mm))

        # Narrative
        narr = (parsed.get("narrativa") or parsed.get("narrativaCompleta")
                or parsed.get("sintesiEsecutiva") or "")
        if narr:
            story.append(Spacer(1, 2*mm))
            story.append(P("NARRATIVA", st["label"]))
            story.append(Spacer(1, 1*mm))
            story.append(P(narr.replace("\n", "<br/>"), st["narrative"]))

    # ── FINAL VALUATION ───────────────────────────────────────────
    fp = _parse(final_result) if final_result else None
    if fp:
        story.append(PageBreak())
        story.append(P("VALUTAZIONE FINALE", st["page_sub"]))
        crr = (fp.get("customerRiskRating") or "").upper()
        crr_bg, crr_fg = _RISK_PALETTE.get(crr, (C_BG, C_MED))
        crr_style = ParagraphStyle("_crr", fontName="Helvetica-Bold",
                                    fontSize=18, textColor=crr_fg, leading=22)
        story.append(P(crr or "—", crr_style))
        story.append(Spacer(1, 2*mm))

        sintesi = fp.get("sintesiEsecutiva", "")
        if sintesi:
            story.append(P(sintesi.replace("\n", "<br/>"), st["body"]))

        story.append(HRFlowable(width=W, thickness=1, color=C_BORDER,
                                spaceBefore=4, spaceAfter=6))

        # Risk matrix
        matrice = fp.get("matriceRischio", {})
        dim_labels = [
            ("identitaStruttura", "Identità / Struttura"),
            ("reputazionale",     "Reputazionale"),
            ("economico",         "Economico"),
            ("transazionale",     "Transazionale"),
            ("geografico",        "Geografico"),
        ]
        if matrice:
            story.append(P("MATRICE DI RISCHIO", st["label"]))
            story.append(Spacer(1, 1.5*mm))
            mat_rows = []
            for dk, dl in dim_labels:
                d = matrice.get(dk, {})
                score = int(d.get("score", 0))
                bar   = "■" * score + "□" * (5 - score)
                mot   = d.get("motivazione", "")[:130]
                sc_style = ParagraphStyle("_sc", fontName="Helvetica-Bold",
                                          fontSize=9, textColor=C_BLACK, leading=12)
                mat_rows.append([
                    P(dl, st["body"]),
                    P(f"{score}/5  {bar}", sc_style),
                    P(mot + ("…" if len(d.get("motivazione","")) > 130 else ""), st["small"]),
                ])
            story.append(_tbl(mat_rows, [3.8*cm, 2.8*cm, W - 6.6*cm]))
            story.append(Spacer(1, 4*mm))

        # Final evidences
        f_ev = fp.get("principaliEvidenze", [])
        if f_ev:
            story.append(P("PRINCIPALI EVIDENZE AML CONSOLIDATE", st["label"]))
            story.append(Spacer(1, 1.5*mm))
            for ev in f_ev:
                story.append(_ev_block(ev, W, st))
                story.append(Spacer(1, 1.5*mm))

        # Recommendation
        rec = fp.get("raccomandazione", {})
        if rec:
            story.append(Spacer(1, 4*mm))
            story.append(P("RACCOMANDAZIONE OPERATIVA", st["label"]))
            story.append(Spacer(1, 1.5*mm))
            rec_fields = [
                ("Accettazione",           rec.get("accettazione")),
                ("Adeguata verifica",       rec.get("livelloAdeguataVerifica")),
                ("Frequenza monitoraggio",  rec.get("frequenzaMonitoraggio")),
                ("Senior Management",       rec.get("autorizzazioneSeniorManagement")),
                ("Valutazione SOS",         rec.get("valutazioneSOS")),
                ("Condizioni",              rec.get("condizioniAccettazione")),
            ]
            rec_rows = [[P(lbl.upper(), st["label"]), P(str(v), st["field"])]
                        for lbl, v in rec_fields if v]
            if rec_rows:
                story.append(_tbl(rec_rows, [4.5*cm, W - 4.5*cm]))

        # Full narrative
        narr_f = fp.get("narrativaCompleta") or fp.get("narrativa") or ""
        if narr_f:
            story.append(Spacer(1, 4*mm))
            story.append(P("NARRATIVA COMPLETA", st["label"]))
            story.append(Spacer(1, 1*mm))
            story.append(P(narr_f.replace("\n", "<br/>"), st["narrative"]))

    # ── FOOTER ────────────────────────────────────────────────────
    story.append(Spacer(1, 8*mm))
    story.append(HRFlowable(width=W, thickness=0.5, color=C_BORDER))
    story.append(Spacer(1, 2*mm))
    story.append(P(
        f"Documento generato da AML IntelliGent Platform · "
        f"{date.today().strftime('%d/%m/%Y')} · "
        f"Uso riservato — Adeguata verifica D.Lgs. 231/2007",
        st["small"]))

    doc.build(story)
    buf.seek(0)
    return buf.read()

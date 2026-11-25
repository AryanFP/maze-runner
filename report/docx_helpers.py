"""Small layer over python-docx used by build_report.py."""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

_TOKEN = re.compile(r"(\*\*.+?\*\*|\*.+?\*|`.+?`|\[\[.+?\]\])")
HEADER_FILL = "1F3A5F"
BODY_FONT = "Calibri"


class Report:
    def __init__(self, figures: list[str], tables: list[str]):
        self.doc = Document()
        self.fig_no = {key: i + 1 for i, key in enumerate(figures)}
        self.tab_no = {key: i + 1 for i, key in enumerate(tables)}
        self._used_figs: list[str] = []
        self._used_tabs: list[str] = []
        section = self.doc.sections[0]
        section.left_margin = section.right_margin = Cm(2.3)
        section.top_margin = section.bottom_margin = Cm(2.2)
        normal = self.doc.styles["Normal"]
        normal.font.name = BODY_FONT
        normal.font.size = Pt(11)
        normal.paragraph_format.space_after = Pt(6)
        normal.paragraph_format.line_spacing = 1.08
        for level, size in ((1, 15), (2, 12.5), (3, 11)):
            style = self.doc.styles[f"Heading {level}"]
            style.font.name = BODY_FONT
            style.font.size = Pt(size)
            style.font.bold = True
            style.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)
            style.paragraph_format.space_before = Pt(14 if level == 1 else 10)
            style.paragraph_format.space_after = Pt(4)
            style.paragraph_format.keep_with_next = True
        self._page_numbers(section)

    # ---- references to numbered items -------------------------------------
    def F(self, key: str) -> str:
        return f"Figure {self.fig_no[key]}"

    def T(self, key: str) -> str:
        return f"Table {self.tab_no[key]}"

    # ---- text ---------------------------------------------------------------
    def _runs(self, paragraph, text: str, size=None, color=None):
        for part in _TOKEN.split(text):
            if not part:
                continue
            bold = italic = code = highlight = False
            if part.startswith("**") and part.endswith("**"):
                part, bold = part[2:-2], True
            elif part.startswith("[[") and part.endswith("]]"):
                part, highlight = part[2:-2], True
            elif part.startswith("`") and part.endswith("`"):
                part, code = part[1:-1], True
            elif part.startswith("*") and part.endswith("*") and len(part) > 2:
                part, italic = part[1:-1], True
            run = paragraph.add_run(part)
            run.bold, run.italic = bold or None, italic or None
            if code:
                run.font.name = "Consolas"
                run.font.size = Pt(9.5)
            if highlight:
                run.font.highlight_color = 7  # yellow: something a team member must fill in
            if size:
                run.font.size = Pt(size)
            if color:
                run.font.color.rgb = color
        return paragraph

    def h(self, text: str, level: int = 1):
        return self.doc.add_heading(text, level=level)

    def p(self, text: str, align=None, size=None, space_after=None, italic=False):
        paragraph = self.doc.add_paragraph()
        self._runs(paragraph, text, size=size)
        if italic:
            for run in paragraph.runs:
                run.italic = True
        if align == "center":
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif align != "left":
            paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        if space_after is not None:
            paragraph.paragraph_format.space_after = Pt(space_after)
        return paragraph

    def bullets(self, items: list[str], numbered: bool = False):
        style = "List Number" if numbered else "List Bullet"
        for item in items:
            paragraph = self.doc.add_paragraph(style=style)
            self._runs(paragraph, item)
            paragraph.paragraph_format.space_after = Pt(2)

    def code(self, text: str):
        for i, line in enumerate(text.strip("\n").splitlines()):
            paragraph = self.doc.add_paragraph()
            paragraph.paragraph_format.left_indent = Cm(0.8)
            paragraph.paragraph_format.space_after = Pt(0)
            paragraph.paragraph_format.line_spacing = 1.0
            paragraph.paragraph_format.keep_with_next = True
            run = paragraph.add_run(line or " ")
            run.font.name = "Consolas"
            run.font.size = Pt(9)
        self.doc.add_paragraph().paragraph_format.space_after = Pt(2)

    def page_break(self):
        self.doc.add_page_break()

    # ---- figures and tables ---------------------------------------------------
    def figure(self, key: str, path: Path, caption: str, width_cm: float = 15.5):
        self._used_figs.append(key)
        paragraph = self.doc.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.keep_with_next = True
        paragraph.paragraph_format.space_after = Pt(3)
        paragraph.add_run().add_picture(str(path), width=Cm(width_cm))
        cap = self.doc.add_paragraph()
        self._runs(cap, f"**{self.F(key)}.** {caption}", size=9.5)
        cap.alignment = WD_ALIGN_PARAGRAPH.LEFT
        cap.paragraph_format.space_after = Pt(10)

    def table(self, key: str | None, header: list[str], rows: list[list], caption: str = "",
              widths_cm: list[float] | None = None, font_size: float = 9, align_right_from: int = 1):
        if key:
            self._used_tabs.append(key)
            cap = self.doc.add_paragraph()
            self._runs(cap, f"**{self.T(key)}.** {caption}", size=9.5)
            cap.alignment = WD_ALIGN_PARAGRAPH.LEFT
            cap.paragraph_format.keep_with_next = True
            cap.paragraph_format.space_after = Pt(3)
        table = self.doc.add_table(rows=1, cols=len(header))
        table.style = "Table Grid"
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        for i, text in enumerate(header):
            cell = table.rows[0].cells[i]
            self._cell(cell, str(text), font_size, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF),
                       right=i >= align_right_from)
            shade = OxmlElement("w:shd")
            shade.set(qn("w:val"), "clear")
            shade.set(qn("w:color"), "auto")
            shade.set(qn("w:fill"), HEADER_FILL)
            cell._tc.get_or_add_tcPr().append(shade)
        for row in rows:
            cells = table.add_row().cells
            for i, text in enumerate(row):
                self._cell(cells[i], str(text), font_size, right=i >= align_right_from)
        if widths_cm:
            for row in table.rows:
                for cell, width in zip(row.cells, widths_cm):
                    cell.width = Cm(width)
        spacer = self.doc.add_paragraph()
        spacer.paragraph_format.space_after = Pt(4)
        return table

    def _cell(self, cell, text: str, size: float, bold: bool = False, color=None, right: bool = False):
        paragraph = cell.paragraphs[0]
        paragraph.paragraph_format.space_after = Pt(0)
        paragraph.paragraph_format.line_spacing = 1.0
        self._runs(paragraph, text, size=size, color=color)
        if bold:
            for run in paragraph.runs:
                run.bold = True
        if right:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    # ---- housekeeping -------------------------------------------------------
    def _page_numbers(self, section):
        paragraph = section.footer.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = paragraph.add_run()
        for tag, text in (("begin", None), (None, "PAGE"), ("end", None)):
            if tag:
                el = OxmlElement("w:fldChar")
                el.set(qn("w:fldCharType"), tag)
            else:
                el = OxmlElement("w:instrText")
                el.set(qn("xml:space"), "preserve")
                el.text = text
            run._r.append(el)
        run.font.size = Pt(9)

    def save(self, path: Path):
        missing_f = [k for k in self.fig_no if k not in self._used_figs]
        missing_t = [k for k in self.tab_no if k not in self._used_tabs]
        order_ok = self._used_figs == list(self.fig_no) and self._used_tabs == list(self.tab_no)
        if missing_f or missing_t or not order_ok:
            raise RuntimeError(f"figure/table numbering problem: unused {missing_f + missing_t}, "
                               f"order ok: {order_ok}")
        self.doc.save(str(path))

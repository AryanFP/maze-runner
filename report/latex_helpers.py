"""LaTeX (IEEE conference template) backend for build_report.py.

Same interface as docx_helpers.Report, so one script produces both the Word
report and the IEEEtran paper from the same text and the same results files.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

_TOKEN = re.compile(r"(\*\*.+?\*\*|//.+?//|`.+?`|\[\[.+?\]\])", re.S)
_CITE = re.compile(r"\[(\d+(?:,\s*\d+)*)\]")
_SECREF = re.compile(r"\b(Sections?) (\d(?:\.\d)?(?!\d)(?:(?:, | and )\d(?:\.\d)?(?![\d.%]))*)")
_ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX"]
_LETTER = " ABCDEFGHI"

_SPECIAL = {
    "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
    "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
    "<": r"\textless{}", ">": r"\textgreater{}", "|": r"\textbar{}",
    "±": r"$\pm$", "²": r"\textsuperscript{2}", "µ": r"\textmu{}", "·": r"$\cdot$", "×": r"$\times$",
    "ö": r"\"o", "Δ": r"$\Delta$", "ε": r"$\varepsilon$", "–": "--", "“": "``", "”": "''",
    "−": r"$-$", "≤": r"$\leq$", "≥": r"$\geq$", "’": "'", "…": r"\ldots{}",
}


def _section_ref(match: re.Match) -> str:
    def one(m: re.Match) -> str:
        major, _, minor = m.group(0).partition(".")
        return _ROMAN[int(major)] + (f"-{_LETTER[int(minor)]}" if minor else "")
    return f"{match.group(1)} " + re.sub(r"\d(?:\.\d)?", one, match.group(2))


class Report:
    """Collects the report and writes an IEEEtran .tex file plus its figures."""

    title = ""
    subtitle = ""
    authors: list[tuple[str, str]] = []
    affiliation: list[str] = []
    keywords = ""

    def __init__(self, figures: list[str], tables: list[str]):
        self.fig_keys, self.tab_keys = list(figures), list(tables)
        self.body: list[str] = []
        self.refs: list[str] = []
        self.abstract: list[str] = []
        self.figure_files: dict[str, Path] = {}
        self._mode = "front"  # front (title lines, ignored) -> abstract -> body / refs
        self._appendix = False
        self._cite_order: list[int] = []

    # ---- references to numbered items -------------------------------------
    def F(self, key: str) -> str:
        return f"Fig. @@fig:{key}@@"

    def T(self, key: str) -> str:
        return f"Table @@tab:{key}@@"

    # ---- inline text ----------------------------------------------------------
    def _plain(self, text: str, code: bool = False) -> str:
        if not code:
            text = _SECREF.sub(_section_ref, text)
        out = "".join(_SPECIAL.get(ch, ch) for ch in text)
        bad = sorted({ch for ch in out if ord(ch) > 127})
        if bad:
            raise ValueError(f"characters with no LaTeX mapping: {bad}")
        if code:
            return out
        out = re.sub(r"@@(fig|tab):(\w+)@@", r"\\ref{\1:\2}", out)
        out = out.replace("Fig. \\ref", "Fig.~\\ref").replace("Table \\ref", "Table~\\ref")

        def cite(m: re.Match) -> str:
            numbers = [int(x) for x in m.group(1).split(",")]
            for n in numbers:
                if n not in self._cite_order:
                    self._cite_order.append(n)
            return "\\cite{" + ",".join(f"ref{n}" for n in numbers) + "}"
        out = _CITE.sub(cite, out)
        return out.replace(" \\cite", "~\\cite")

    def _tex(self, text: str) -> str:
        parts = []
        for part in _TOKEN.split(text):
            if not part:
                continue
            if part.startswith("**") and part.endswith("**"):
                parts.append(r"\textbf{" + self._plain(part[2:-2]) + "}")
            elif part.startswith("[[") and part.endswith("]]"):
                parts.append(r"\textbf{[" + self._plain(part[2:-2]) + "]}")
            elif part.startswith("`") and part.endswith("`"):
                parts.append(r"\texttt{" + self._plain(part[1:-1], code=True).replace("/", r"/\allowbreak{}")
                             .replace(r"\_", r"\_\allowbreak{}") + "}")
            elif part.startswith("//") and part.endswith("//") and len(part) > 4:
                parts.append(r"\emph{" + self._plain(part[2:-2]) + "}")
            else:
                parts.append(self._plain(part))
        return "".join(parts)

    def _emit(self, line: str):
        (self.abstract if self._mode == "abstract" else self.body).append(line)

    # ---- structure --------------------------------------------------------------
    def h(self, text: str, level: int = 1):
        if text == "Abstract":
            self._mode = "abstract"
            return
        if text == "References":
            self._mode = "refs"
            return
        self._mode = "body"
        if text.startswith("Appendix"):
            if not self._appendix:
                self.body.append("\\appendices")
                self._appendix = True
                self._appendix_at = len(self.body)  # wide floats of the appendices are placed here
            text = text.split(": ", 1)[1]
        else:
            text = re.sub(r"^\d+(\.\d+)?\.?\s+", "", text)
        command = {1: "section", 2: "subsection", 3: "subsubsection"}[level]
        self.body.append(f"\n\\{command}{{{self._tex(text)}}}")

    def p(self, text: str, align=None, size=None, space_after=None, italic=False):
        if self._mode == "front":
            return  # the title block is written from the class attributes
        if self._mode == "refs":
            number, entry = re.match(r"\[(\d+)\] (.*)", text, re.S).groups()
            self.refs.append((int(number), self._tex(entry)))
            return
        self._emit("\n" + self._tex(text) + "\n")

    def bullets(self, items: list[str], numbered: bool = False):
        env = "enumerate" if numbered else "itemize"
        self._emit(f"\\begin{{{env}}}")
        for item in items:
            self._emit("  \\item " + self._tex(item))
        self._emit(f"\\end{{{env}}}")

    def code(self, text: str):
        self._emit("{\\scriptsize\\begin{verbatim}\n" + text.strip("\n") + "\n\\end{verbatim}}")

    def page_break(self):
        pass

    # ---- figures and tables ---------------------------------------------------
    def figure(self, key: str, path: Path, caption: str, width_cm: float = 15.5):
        self.figure_files[key] = Path(path)
        wide = width_cm >= 13.0
        env = "figure*" if wide else "figure"
        width = f"{min(1.0, width_cm / 16.0):.2f}\\textwidth" if wide else "\\columnwidth"
        self._emit(
            f"\\begin{{{env}}}[!t]\n\\centering\n"
            f"\\includegraphics[width={width}]{{figures/{Path(path).name}}}\n"
            f"\\caption{{{self._tex(caption)}}}\n\\label{{fig:{key}}}\n\\end{{{env}}}"
        )

    def table(self, key: str | None, header: list[str], rows: list[list], caption: str = "",
              widths_cm: list[float] | None = None, font_size: float = 9, align_right_from: int = 1):
        n = len(header)
        widths = widths_cm or [1.0] * n
        wide = n >= 3
        env, line = ("table*", "\\textwidth") if wide else ("table", "\\columnwidth")
        total = sum(widths)
        spec = "".join(
            f">{{\\ragged{'left' if i >= align_right_from else 'right'}\\arraybackslash}}"
            f"p{{\\dimexpr {w / total:.4f}\\tabw\\relax}}"
            for i, w in enumerate(widths)
        )
        out = [f"\\begin{{{env}}}[!t]", "\\centering", "\\footnotesize",
               f"\\setlength{{\\tabw}}{{\\dimexpr {line}-{2 * n}\\tabcolsep\\relax}}"]
        if key:
            out += [f"\\caption{{{self._tex(caption)}}}", f"\\label{{tab:{key}}}"]
        out += [f"\\begin{{tabular}}{{{spec}}}", "\\toprule",
                " & ".join(r"\textbf{" + self._tex(str(c)) + "}" for c in header) + r" \\", "\\midrule"]
        out += [" & ".join(self._tex(str(c)) for c in row) + r" \\" for row in rows]
        out += ["\\bottomrule", "\\end{tabular}", f"\\end{{{env}}}"]
        if wide and self._appendix:
            # a two-column float can only appear on a later page; start it early so it is not left
            # alone on a last page after the references
            self.body.insert(self._appendix_at, "\n".join(out))
            self._appendix_at += 1
        else:
            self._emit("\n".join(out))

    # ---- output -----------------------------------------------------------------
    def _author_block(self) -> str:
        blocks = []
        for name, detail in self.authors:
            lines = [f"\\IEEEauthorblockN{{{self._plain(name)}}}", "\\IEEEauthorblockA{"
                     + " \\\\ ".join(self._plain(x) for x in [detail, *self.affiliation]) + "}"]
            blocks.append("\n".join(lines))
        rows = [blocks[:3], blocks[3:]]
        return "\n\\and\n".join(rows[0]) + ("\n\\linebreakand\n" + "\n\\and\n".join(rows[1]) if rows[1] else "")

    def save(self, path: Path):
        path = Path(path)
        fig_dir = path.parent / "figures"
        fig_dir.mkdir(parents=True, exist_ok=True)
        for src in self.figure_files.values():
            shutil.copyfile(src, fig_dir / src.name)
        cited = self._cite_order
        missing = [n for n, _ in self.refs if n not in cited]
        if missing:
            raise RuntimeError(f"references never cited: {missing}")
        by_number = dict(self.refs)
        bib = "\n".join(f"\\bibitem{{ref{n}}} {by_number[n]}" for n in cited)  # order of first citation
        title = self._plain(self.title)
        if self.subtitle:
            title += r"\\[2pt]{\Large\itshape " + self._plain(self.subtitle) + "}"
        doc = "\n".join([
            "% Generated by report/build_report.py --ieee. Do not edit by hand: change the script and rebuild.",
            "\\documentclass[conference]{IEEEtran}",
            "\\usepackage{amsmath,amssymb,graphicx,textcomp,booktabs,array}",
            "\\renewcommand{\\ttdefault}{cmtt}",
            "\\newlength{\\tabw}",
            "\\makeatletter",
            "\\newcommand{\\linebreakand}{\\end{@IEEEauthorhalign}\\hfill\\mbox{}\\par\\mbox{}\\hfill"
            "\\begin{@IEEEauthorhalign}}",
            "\\makeatother",
            "\\setlength{\\emergencystretch}{2em}",
            "\\begin{document}",
            f"\\title{{{title}}}",
            "\\author{" + self._author_block() + "}",
            "\\maketitle",
            "\\begin{abstract}", *[a.strip() for a in self.abstract], "\\end{abstract}",
            "\\begin{IEEEkeywords}", self._plain(self.keywords), "\\end{IEEEkeywords}",
            *self.body,
            "\n\\begin{thebibliography}{00}", bib, "\\end{thebibliography}",
            "\\end{document}", "",
        ])
        path.write_text(doc, encoding="utf-8", newline="\n")

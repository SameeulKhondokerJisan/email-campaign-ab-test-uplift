"""Build the campaign P&L workbook (excel/campaign_pnl_model.xlsx).

Every calculated cell is an Excel formula that points at the Inputs sheet, so the
model recalculates when the margin, e-mail cost or campaign size change.
Colour code: blue = typed input or pasted analysis result, black = formula,
green = link to another sheet, yellow fill = assumption to review.
"""
from __future__ import annotations

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.comments import Comment
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from src import config

ARIAL = "Arial"
BLUE, BLACK, GREEN, WHITE = "0000FF", "000000", "008000", "FFFFFF"
HEADER_FILL = PatternFill("solid", fgColor="1F3864")
INPUT_FILL = PatternFill("solid", fgColor="FFFF00")
THIN = Side(style="thin", color="BFBFBF")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
USD = '$#,##0.00;($#,##0.00);"-"'
USD0 = '$#,##0;($#,##0);"-"'
PCT = '0.0%;(0.0%);"-"'
PCT2 = '0.00%;(0.00%);"-"'
SOURCE = "Source: reports/results.json, written by src/run_pipeline.py from the Hillstrom data."


def _font(color=BLACK, bold=False, size=10, italic=False):
    return Font(name=ARIAL, color=color, bold=bold, size=size, italic=italic)


def _cell(ws, ref, value, color=BLACK, fmt=None, bold=False, fill=None, comment=None, italic=False):
    cell = ws[ref]
    cell.value = value
    cell.font = _font(color, bold, italic=italic)
    if fmt:
        cell.number_format = fmt
    if fill:
        cell.fill = fill
    if comment:
        cell.comment = Comment(comment, "pipeline")
    return cell


def _header(ws, row, labels, start_col=1):
    for i, label in enumerate(labels):
        cell = ws.cell(row=row, column=start_col + i, value=label)
        cell.font = _font(WHITE, bold=True)
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BOX


def _title(ws, text, subtitle=None):
    _cell(ws, "A1", text, bold=True).font = _font(bold=True, size=14)
    if subtitle:
        _cell(ws, "A2", subtitle, italic=True)


def _widths(ws, widths):
    for col, width in widths.items():
        ws.column_dimensions[col].width = width


def build(results: dict, deciles: pd.DataFrame) -> str:
    wb = Workbook()

    # README -------------------------------------------------------------------
    ws = wb.active
    ws.title = "README"
    _title(ws, "E-mail campaign P&L model", "Hillstrom MineThatData e-mail test, 64,000 customers")
    notes = [
        "Purpose: turn the measured lift of each e-mail into profit, and size the targeting decision.",
        "How to use: change the yellow cells on the Inputs sheet; every other number recalculates.",
        "Colour code: blue = input or pasted analysis result; black = formula; green = link to another sheet.",
        "Results sheet: experiment results pasted from the Python pipeline (see the source note there).",
        "P&L sheet: profit per customer and for the next campaign, with 95% CI low and high cases.",
        "Targeting sheet: profit by targeting depth using the uplift model's deciles (held-out test set).",
        "Sensitivity sheet: net profit per 1,000 customers across margin and e-mail cost assumptions.",
        "Margin and e-mail cost are assumptions, not data. The defaults are deliberately conservative.",
    ]
    for i, text in enumerate(notes, start=4):
        _cell(ws, f"A{i}", text)
    _widths(ws, {"A": 110})

    # Inputs -------------------------------------------------------------------
    inp = wb.create_sheet("Inputs")
    _title(inp, "Inputs", "Edit the yellow cells. Everything else is calculated.")
    _header(inp, 4, ["Assumption", "Value", "Note"])
    rows = [("Gross margin", config.GROSS_MARGIN, PCT, "Share of each sales dollar kept after cost of goods. Assumption."),
            ("Cost per e-mail ($)", config.COST_PER_EMAIL, USD, "Send, creative and list cost per e-mail. Conservative assumption."),
            ("Customers in next campaign", config.NEXT_CAMPAIGN_SIZE, "#,##0", "Size of the list the decision applies to.")]
    for i, (label, value, fmt, note) in enumerate(rows, start=5):
        _cell(inp, f"A{i}", label)
        _cell(inp, f"B{i}", value, BLUE, fmt, fill=INPUT_FILL)
        _cell(inp, f"C{i}", note, italic=True)
    _widths(inp, {"A": 30, "B": 14, "C": 70})
    margin, cost, size = "Inputs!$B$5", "Inputs!$B$6", "Inputs!$B$7"

    # Results ------------------------------------------------------------------
    res = wb.create_sheet("Results")
    _title(res, "Experiment results (pasted from the analysis)", SOURCE)
    _header(res, 4, ["Arm", "Customers", "Visit rate", "Conversion rate", "Spend per customer ($)",
                     "Spend lift vs control ($)", "Lift 95% CI low ($)", "Lift 95% CI high ($)", "Holm p-value"])
    summary = {r["arm"]: r for r in results["arm_summary"]}
    ate = pd.DataFrame(results["ate"])
    for i, arm in enumerate([config.CONTROL, *config.ARMS], start=5):
        s = summary[arm]
        _cell(res, f"A{i}", arm if arm == config.CONTROL else f"{arm} e-mail")
        _cell(res, f"B{i}", int(s["customers"]), BLUE, "#,##0")
        _cell(res, f"C{i}", s["visit_rate"], BLUE, PCT2)
        _cell(res, f"D{i}", s["conversion_rate"], BLUE, PCT2)
        _cell(res, f"E{i}", s["spend_per_customer"], BLUE, '$#,##0.000')
        if arm == config.CONTROL:
            for col in "FGHI":
                _cell(res, f"{col}{i}", None)
        else:
            row = ate[(ate.arm == arm) & (ate.outcome == "spend")].iloc[0]
            _cell(res, f"F{i}", f"=E{i}-$E$5", BLACK, '$#,##0.000')
            _cell(res, f"G{i}", float(row.ci_low), BLUE, '$#,##0.000', comment="Welch 95% CI from the pipeline")
            _cell(res, f"H{i}", float(row.ci_high), BLUE, '$#,##0.000', comment="Welch 95% CI from the pipeline")
            _cell(res, f"I{i}", float(row.p_holm), BLUE, "0.0000")
    _widths(res, {get_column_letter(c): 17 for c in range(1, 10)})

    # P&L ----------------------------------------------------------------------
    pnl = wb.create_sheet("P&L")
    _title(pnl, "Campaign P&L per e-mail", "Formulas only: change Inputs to update.")
    _header(pnl, 4, ["Line item", "Mens e-mail", "Womens e-mail", "How it is calculated"])
    lines = [
        ("Incremental spend per customer ($)", "=Results!F6", "=Results!F7", USD, GREEN, "Treated minus control spend per customer"),
        ("Gross margin", f"={margin}", f"={margin}", PCT, GREEN, "Inputs"),
        ("Gross profit per customer ($)", "=B5*B6", "=C5*C6", USD, BLACK, "Incremental spend x margin"),
        ("Cost per e-mail ($)", f"={cost}", f"={cost}", USD, GREEN, "Inputs"),
        ("Net profit per customer mailed ($)", "=B7-B8", "=C7-C8", USD, BLACK, "Gross profit minus e-mail cost"),
        ("Customers mailed", f"={size}", f"={size}", "#,##0", GREEN, "Inputs"),
        ("Net profit for the campaign ($)", "=B9*B10", "=C9*C10", USD0, BLACK, "Per customer x customers mailed"),
        ("Return on e-mail spend", '=IF(B8=0,"-",B9/B8)', '=IF(C8=0,"-",C9/C8)', PCT, BLACK, "Net profit / e-mail cost"),
        ("Break-even cost per e-mail ($)", "=B7", "=C7", USD, BLACK, "Highest e-mail cost that still breaks even"),
        ("Break-even spend lift per customer ($)", '=IF(B6=0,"-",B8/B6)', '=IF(C6=0,"-",C8/C6)', USD, BLACK, "Lift needed to cover the e-mail cost"),
        ("Low case: net profit at CI low ($)", f"=(Results!G6*B6-B8)*B10", f"=(Results!G7*C6-C8)*C10", USD0, BLACK, "Uses the 95% CI lower bound of the lift"),
        ("High case: net profit at CI high ($)", f"=(Results!H6*B6-B8)*B10", f"=(Results!H7*C6-C8)*C10", USD0, BLACK, "Uses the 95% CI upper bound of the lift"),
    ]
    for i, (label, f_m, f_w, fmt, color, note) in enumerate(lines, start=5):
        _cell(pnl, f"A{i}", label)
        _cell(pnl, f"B{i}", f_m, color, fmt)
        _cell(pnl, f"C{i}", f_w, color, fmt)
        _cell(pnl, f"D{i}", note, italic=True)
    for r in (11, 15, 16):
        for col in "BC":
            pnl[f"{col}{r}"].font = _font(BLACK if r != 11 else BLACK, bold=True)
    _widths(pnl, {"A": 40, "B": 16, "C": 16, "D": 48})

    # Targeting ----------------------------------------------------------------
    tgt = wb.create_sheet("Targeting")
    _title(tgt, "Profit by targeting depth (uplift model deciles)",
           "Deciles ranked by predicted visit uplift; spend lift observed on the held-out test set. "
           "Decile estimates are noisy (see SE column).")
    start = 4
    for block, arm in enumerate(config.ARMS):
        col0 = 1 + block * 9
        c = lambda k: get_column_letter(col0 + k)  # noqa: E731
        _cell(tgt, f"{c(0)}{start}", f"{arm} e-mail", bold=True)
        _header(tgt, start + 1, ["Decile", "Share of list", "Incremental spend per customer ($)", "SE ($)",
                                 "Net profit per 1,000 in decile ($)", "Cumulative share mailed",
                                 "Cumulative net profit per 1,000 on list ($)"], start_col=col0)
        sub = deciles[deciles.arm == arm].sort_values("decile")
        first = start + 2
        for j, row in enumerate(sub.itertuples()):
            r = first + j
            _cell(tgt, f"{c(0)}{r}", int(row.decile), BLACK, "0")
            _cell(tgt, f"{c(1)}{r}", row.customers / sub.customers.sum(), BLUE, PCT)
            _cell(tgt, f"{c(2)}{r}", float(row.incremental_spend_per_customer), BLUE, USD)
            _cell(tgt, f"{c(3)}{r}", float(row.incremental_spend_se), BLUE, USD)
            _cell(tgt, f"{c(4)}{r}", f"=1000*({c(2)}{r}*{margin}-{cost})", BLACK, USD0)
            _cell(tgt, f"{c(5)}{r}", f"=SUM({c(1)}${first}:{c(1)}{r})", BLACK, PCT)
            _cell(tgt, f"{c(6)}{r}", f"=SUMPRODUCT({c(1)}${first}:{c(1)}{r},{c(4)}${first}:{c(4)}{r})", BLACK, USD0)
        last = first + len(sub) - 1
        _cell(tgt, f"{c(0)}{last + 2}", "Best depth (share mailed)", bold=True)
        _cell(tgt, f"{c(5)}{last + 2}",
              f"=INDEX({c(5)}{first}:{c(5)}{last},MATCH(MAX({c(6)}{first}:{c(6)}{last}),{c(6)}{first}:{c(6)}{last},0))",
              BLACK, PCT)
        _cell(tgt, f"{c(0)}{last + 3}", "Profit at best depth per 1,000 on list ($)", bold=True)
        _cell(tgt, f"{c(6)}{last + 3}", f"=MAX({c(6)}{first}:{c(6)}{last})", BLACK, USD0)
        _cell(tgt, f"{c(0)}{last + 4}", "Profit if everyone is mailed per 1,000 ($)", bold=True)
        _cell(tgt, f"{c(6)}{last + 4}", f"={c(6)}{last}", BLACK, USD0)
        chart = BarChart()
        chart.type = "col"
        chart.title = f"{arm} e-mail: cumulative net profit per 1,000 customers"
        chart.y_axis.title = "Net profit ($)"
        chart.x_axis.title = "Deciles mailed (best first)"
        chart.add_data(Reference(tgt, min_col=col0 + 6, min_row=start + 1, max_row=last), titles_from_data=True)
        chart.set_categories(Reference(tgt, min_col=col0, min_row=first, max_row=last))
        chart.roundedCorners = False
        chart.legend = None
        chart.title.overlay = False
        chart.x_axis.delete = False
        chart.y_axis.delete = False
        chart.height, chart.width = 7, 14
        tgt.add_chart(chart, f"{c(0)}{last + 7}")
        for k in range(7):
            tgt.column_dimensions[c(k)].width = 15
    # Sensitivity --------------------------------------------------------------
    sen = wb.create_sheet("Sensitivity")
    _title(sen, "Net profit per 1,000 customers mailed ($)",
           "Rows: cost per e-mail. Columns: gross margin. Uses the measured spend lift from the Results sheet.")
    margins = [0.20, 0.30, 0.40, 0.50, 0.60]
    costs = [0.01, 0.05, 0.10, 0.20, 0.30, 0.50]
    for block, (arm, lift_ref) in enumerate((("Mens", "Results!$F$6"), ("Womens", "Results!$F$7"))):
        top = 4 + block * (len(costs) + 4)
        _cell(sen, f"A{top}", f"{arm} e-mail", bold=True)
        _cell(sen, f"A{top + 1}", "Cost per e-mail \\ Margin", bold=True)
        for j, m in enumerate(margins):
            _cell(sen, f"{get_column_letter(2 + j)}{top + 1}", m, BLUE, PCT, bold=True)
        for i, cst in enumerate(costs):
            r = top + 2 + i
            _cell(sen, f"A{r}", cst, BLUE, USD)
            for j in range(len(margins)):
                col = get_column_letter(2 + j)
                _cell(sen, f"{col}{r}", f"=1000*({lift_ref}*{col}${top + 1}-$A{r})", BLACK, USD0)
        rng = f"B{top + 2}:{get_column_letter(1 + len(margins))}{top + 1 + len(costs)}"
        sen.conditional_formatting.add(rng, CellIsRule(operator="lessThan", formula=["0"],
                                                         fill=PatternFill("solid", fgColor="F8CBAD")))
        sen.conditional_formatting.add(rng, CellIsRule(operator="greaterThanOrEqual", formula=["0"],
                                                         fill=PatternFill("solid", fgColor="C6EFCE")))
    _widths(sen, {"A": 26, **{get_column_letter(c): 13 for c in range(2, 8)}})

    for sheet in wb.worksheets:
        sheet.sheet_view.showGridLines = False
    config.EXCEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    wb.save(config.EXCEL_PATH)
    return str(config.EXCEL_PATH.relative_to(config.ROOT))

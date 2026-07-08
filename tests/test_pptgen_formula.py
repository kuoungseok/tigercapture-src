from __future__ import annotations


def test_formula_evaluates_literals_functions_and_cell_refs():
    from app.pptgen.formula import evaluate_numeric_formula, format_formula_value

    cells = [
        ["Name", "Value"],
        ["A", "12"],
        ["B", "=B2*2"],
    ]

    assert evaluate_numeric_formula("=1+2*3") == 7
    assert evaluate_numeric_formula("=SUM(1,2,3)") == 6
    assert evaluate_numeric_formula("=AVG(10,20)") == 15
    assert evaluate_numeric_formula("=B2+B3", cells=cells) == 36
    assert format_formula_value("=B2+B3", cells=cells) == "36"


def test_formula_errors_render_as_err_for_display():
    from app.pptgen.formula import format_formula_value

    assert format_formula_value("=UNKNOWN(1)") == "#ERR"

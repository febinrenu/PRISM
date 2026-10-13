"""Domain guess for the workspace header."""
from types import SimpleNamespace as N

from routers.intelligence import _detect_domain


def _doc(*texts):
    return [N(text=t) for t in texts]


def test_hyphenated_income_tax_is_income_tax():
    doc = _doc("The income-tax payable by an assessee for the tax year shall be computed on the total income.",
               "A rebate under this section shall not exceed the income-tax on the total income of the assessee.",
               "The employer shall deduct tax from the salary of an employee.")
    assert _detect_domain(doc) == "Income Tax"


def test_labour_law():
    doc = _doc("The employer shall pay wages to every employee before the seventh day.",
               "No employer shall order the termination of an employee without notice; wages are payable.")
    assert _detect_domain(doc) == "Labour Law"


def test_no_clear_signal():
    assert _detect_domain(_doc("This Act may be called the Short Title Act.")) == "General Legislation"

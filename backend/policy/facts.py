"""
The closed vocabulary of facts a rule condition may test.

Keeping the vocabulary closed is deliberate: a rule whose condition needs a
fact outside it is marked non-executable instead of being approximated, and
the share of executable rules is reported as a metric.
"""
from typing import Literal

FactType = Literal["number", "bool", "category"]

FACTS: dict[str, tuple[FactType, str]] = {
    # who
    "is_individual": ("bool", "the person is an individual"),
    "is_company": ("bool", "the person is a company"),
    "is_firm": ("bool", "the person is a firm or LLP"),
    "is_resident": ("bool", "resident in India"),
    "age": ("number", "age in years"),
    "is_employer": ("bool", "the person employs one or more employees"),
    "is_registered_person": ("bool", "registered under the GST law"),
    "is_data_fiduciary": ("bool", "determines purpose and means of processing personal data"),
    "is_significant_data_fiduciary": ("bool", "notified as a Significant Data Fiduciary"),
    "is_data_processor": ("bool", "processes personal data on behalf of a fiduciary"),
    # how much
    "total_income": ("number", "total income, rupees"),
    "aggregate_turnover": ("number", "aggregate turnover in the financial year, rupees"),
    "tax_due": ("number", "tax payable, rupees"),
    "tax_unpaid": ("number", "tax payable but not paid, rupees"),
    "employees": ("number", "number of employees"),
    "wage_monthly": ("number", "monthly wage of the employee, rupees"),
    "wage_shortfall": ("number", "wages paid below the statutory minimum, rupees"),
    "bonus_due": ("number", "bonus payable, rupees"),
    "data_principals": ("number", "number of data principals affected"),
    # when
    "days_late": ("number", "days after the due date"),
    "months_late": ("number", "months (or part) after the due date"),
    "return_filed": ("bool", "the return was furnished"),
    "is_first_offence": ("bool", "no earlier contravention of the same provision"),
    # what happened
    "failed_to_register": ("bool", "liable to register but did not"),
    "failed_to_file_return": ("bool", "required to furnish a return but did not"),
    "failed_to_pay_wages": ("bool", "wages not paid by the due date"),
    "paid_below_minimum_wage": ("bool", "wage below the notified minimum"),
    "gender_discrimination_in_wages": ("bool", "wage discrimination on ground of gender"),
    "failed_to_maintain_records": ("bool", "required registers or records not maintained"),
    "personal_data_breach": ("bool", "a personal data breach occurred"),
    "failed_to_notify_breach": ("bool", "breach not intimated to the Board and principals"),
    "failed_security_safeguards": ("bool", "reasonable security safeguards not taken"),
    "child_data_violation": ("bool", "obligations for children's data not fulfilled"),
    "processed_without_consent": ("bool", "processing without consent or a legitimate use"),
    "obstructed_officer": ("bool", "obstructed an inspector or officer"),
    "evaded_tax": ("bool", "tax evaded, or input credit wrongly availed"),
    "amount_involved": ("number", "amount of tax evaded / credit wrongly availed, rupees"),
}


def fact_type(name: str) -> FactType:
    return FACTS[name][0]


def is_known(name: str) -> bool:
    return name in FACTS

"""Accounts Receivable and Accounts Payable: what each party owes on a date, by the age of its invoices."""

import frappe
from frappe import _
from frappe.utils import date_diff, getdate

from frappe_books.accounting import settlement
from frappe_books.accounting.money import as_decimal, rounded, sum_decimal

# The days since the invoice date that each range ends on; the last range has no end.
RANGES = (30, 60, 90)
RANGE_KEYS = ("range_0_30", "range_31_60", "range_61_90", "range_91_above")
AMOUNT_KEYS = ("invoice_amount", "outstanding", *RANGE_KEYS)
# The party doctype and field of each report's invoices
PARTIES = {
	"Books Sales Invoice": ("Books Customer", "customer"),
	"Books Purchase Invoice": ("Books Supplier", "supplier"),
}


def get_default_filters() -> dict:
	"""Show what is owed today."""
	return {"to_date": getdate()}


def get_columns(doctype) -> list[dict]:
	return [
		{"fieldname": "index", "label": "#", "fieldtype": "Int", "width": 60},
		{"fieldname": "party", "label": _("Party"), "fieldtype": "Link", "options": PARTIES[doctype][0]},
		{"fieldname": "date", "label": _("Date"), "fieldtype": "Date"},
		{"fieldname": "voucher_no", "label": _("Invoice"), "fieldtype": "Data", "width": 150},
		{"fieldname": "age", "label": _("Age (Days)"), "fieldtype": "Int", "width": 90},
		{"fieldname": "invoice_amount", "label": _("Invoice Amount"), "fieldtype": "Currency", "width": 150},
		{"fieldname": "outstanding", "label": _("Outstanding"), "fieldtype": "Currency", "width": 150},
		{"fieldname": "range_0_30", "label": _("0-30"), "fieldtype": "Currency"},
		{"fieldname": "range_31_60", "label": _("31-60"), "fieldtype": "Currency"},
		{"fieldname": "range_61_90", "label": _("61-90"), "fieldtype": "Currency"},
		{"fieldname": "range_91_above", "label": _("91+"), "fieldtype": "Currency"},
		{"fieldname": "voucher_type", "label": _("Ref Type"), "fieldtype": "Data"},
	]


def get_data(doctype, filters) -> list[dict]:
	"""Return each invoice with an amount outstanding on the date, oldest first within its party.

	Grouped by party, each party's invoices end with its total and a blank row. The last row is
	the total of every invoice.
	"""
	to_date = getdate(filters.get("to_date") or getdate())
	rows = [
		_invoice_row(doctype, invoice, outstanding, to_date)
		for invoice, outstanding in _outstanding_invoices(doctype, filters, to_date)
	]
	for index, row in enumerate(rows, 1):
		row["index"] = index
	if filters.get("group_by") == "party":
		rows = _grouped_by_party(rows)
	elif rows:
		rows.append({})
	return [*rows, _total_row(row for row in rows if row.get("type") == "invoice")]


def _outstanding_invoices(doctype, filters, to_date):
	"""Yield the submitted invoices up to the date with what each still owed at the end of it."""
	party_field = PARTIES[doctype][1]
	conditions = [["docstatus", "=", 1], ["posting_date", "<=", to_date]]
	if filters.get("party"):
		conditions.append([party_field, "=", filters["party"]])
	fields = ["name", party_field, "posting_date", "base_grand_total", "outstanding_amount", "return_against"]
	invoices = frappe.get_list(
		doctype, filters=conditions, fields=fields, order_by=f"{party_field} asc, posting_date asc, name asc"
	)
	settled_later = _settled_after(doctype, [invoice.name for invoice in invoices], to_date)
	for invoice in invoices:
		invoice.party = invoice[party_field]
		# A payment after the date had not settled its part yet, so it still counts as owed.
		outstanding = as_decimal(invoice.outstanding_amount) + settlement.signed(
			invoice, settled_later.get(invoice.name, 0)
		)
		if rounded(outstanding):
			yield invoice, rounded(outstanding)


def _settled_after(doctype, invoice_names, to_date) -> dict:
	"""Return what submitted payments dated after the date settled on each invoice."""
	if not invoice_names:
		return {}
	references = frappe.get_all(
		"Books Payment Entry Reference",
		filters={
			"parenttype": "Books Payment Entry",
			"reference_doctype": doctype,
			"reference_name": ["in", invoice_names],
		},
		fields=["parent", "reference_name", "allocated_amount"],
	)
	later = set(
		frappe.get_all(
			"Books Payment Entry",
			filters=[
				["name", "in", list({row.parent for row in references})],
				["docstatus", "=", 1],
				["posting_date", ">", to_date],
			],
			pluck="name",
		)
		if references
		else []
	)
	settled = {}
	for row in references:
		if row.parent in later:
			settled[row.reference_name] = settled.get(row.reference_name, 0) + as_decimal(
				row.allocated_amount
			)
	return settled


def _invoice_row(doctype, invoice, outstanding, to_date) -> dict:
	age = max(date_diff(to_date, getdate(invoice.posting_date)), 0)
	row = {
		"type": "invoice",
		"party": invoice.party,
		"date": getdate(invoice.posting_date),
		"voucher_no": invoice.name,
		"voucher_type": doctype,
		"age": age,
		"invoice_amount": settlement.signed(invoice, abs(as_decimal(invoice.base_grand_total))),
		"outstanding": outstanding,
		**{key: as_decimal(0) for key in RANGE_KEYS},
	}
	row[_range_key(age)] = outstanding
	return row


def _range_key(age) -> str:
	for end, key in zip(RANGES, RANGE_KEYS, strict=False):
		if age <= end:
			return key
	return RANGE_KEYS[-1]


def _grouped_by_party(rows) -> list[dict]:
	groups = {}
	for row in rows:
		groups.setdefault(row["party"], []).append(row)
	grouped = []
	for party, invoices in groups.items():
		grouped += [*invoices, {**_total_row(invoices), "party": party, "voucher_no": _("Total")}, {}]
	return grouped


def _total_row(rows) -> dict:
	rows = list(rows)
	return {
		"type": "total",
		"party": _("Total"),
		**{key: sum_decimal(row[key] for row in rows) for key in AMOUNT_KEYS},
	}

from decimal import Decimal

import frappe
from frappe.desk.query_report import run
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, nowdate

from frappe_books.accounting.returns import map_return
from frappe_books.reports.filters import get_default_filters
from frappe_books.tests.accounting import (
	enable_features,
	make_account,
	make_customer,
	make_invoice,
	make_item,
	make_supplier,
)

RECEIVABLE = "Books Accounts Receivable"
PAYABLE = "Books Accounts Payable"
RANGES = ("range_0_30", "range_31_60", "range_61_90", "range_91_above")


class IntegrationTestAgeingReports(IntegrationTestCase):
	def setUp(self):
		enable_features()
		frappe.db.set_single_value("Books Accounting Settings", "enable_partial_payment", 1)
		self.receivable = make_account("Ageing Receivable", account_type="Receivable")
		self.payable = make_account("Ageing Payable", root_type="Liability", account_type="Payable")
		self.cash = make_account("Ageing Cash", account_type="Cash")
		self.income = make_account("Ageing Income", root_type="Income", account_type="Income Account")
		self.expense = make_account("Ageing Expense", root_type="Expense", account_type="Expense Account")
		self.item = make_item(self.income.name, self.expense.name)
		self.customer = make_customer(self.receivable.name).name

	def test_opens_on_today(self):
		self.assertEqual(get_default_filters(RECEIVABLE), {"to_date": getdate()})

	def test_each_invoice_falls_in_the_range_of_its_age(self):
		for days in (0, 31, 75, 200):
			self._invoice(days_ago=days)

		rows = self._entries(_run(RECEIVABLE, party=self.customer))

		self.assertEqual([row["age"] for row in rows], [200, 75, 31, 0])
		self.assertEqual(
			[[row[key] for key in RANGES] for row in rows],
			[
				[0, 0, 0, Decimal(200)],
				[0, 0, Decimal(200), 0],
				[0, Decimal(200), 0, 0],
				[Decimal(200), 0, 0, 0],
			],
		)

	def test_the_total_adds_up_every_invoice(self):
		for days in (0, 45):
			self._invoice(days_ago=days)

		rows = _run(RECEIVABLE, party=self.customer)

		self.assertEqual(rows[-2], {})
		self.assertEqual(
			{key: rows[-1][key] for key in ("outstanding", *RANGES)},
			{
				"outstanding": Decimal(400),
				"range_0_30": Decimal(200),
				"range_31_60": Decimal(200),
				"range_61_90": Decimal(0),
				"range_91_above": Decimal(0),
			},
		)

	def test_a_paid_invoice_is_left_out_and_a_part_payment_lowers_what_is_owed(self):
		paid = self._invoice()
		part = self._invoice()
		self._pay(paid, 200)
		self._pay(part, 50)

		rows = self._entries(_run(RECEIVABLE, party=self.customer))

		self.assertEqual(
			[(row["voucher_no"], row["outstanding"]) for row in rows], [(part.name, Decimal(150))]
		)

	def test_a_payment_after_the_date_still_counts_as_owed_on_it(self):
		invoice = self._invoice(days_ago=10)
		self._pay(invoice, 200)
		as_on = add_days(nowdate(), -5)

		rows = self._entries(_run(RECEIVABLE, party=self.customer, to_date=as_on))

		self.assertEqual([(row["outstanding"], row["age"]) for row in rows], [(Decimal(200), 5)])

	def test_an_invoice_after_the_date_is_left_out(self):
		self._invoice(days_ago=1)

		rows = _run(RECEIVABLE, party=self.customer, to_date=add_days(nowdate(), -2))

		self.assertEqual(self._entries(rows), [])
		self.assertEqual(rows[-1]["outstanding"], 0)

	def test_drafts_and_cancelled_invoices_owe_nothing(self):
		make_invoice(
			"Books Sales Invoice", self.customer, self.receivable.name, self.item.name, self.income.name
		)
		self._invoice().cancel()

		self.assertEqual(self._entries(_run(RECEIVABLE, party=self.customer)), [])

	def test_a_credit_note_lowers_what_the_customer_owes(self):
		invoice = self._invoice()
		credit_note = map_return(invoice.doctype, invoice.name)
		credit_note.insert()
		credit_note.submit()

		rows = _run(RECEIVABLE, party=self.customer)

		self.assertEqual(
			sorted(row["outstanding"] for row in self._entries(rows)), [Decimal(-200), Decimal(200)]
		)
		self.assertEqual(rows[-1]["outstanding"], 0)

	def test_grouped_by_party_each_party_ends_with_its_total(self):
		other = make_customer(self.receivable.name).name
		self._invoice()
		self._invoice(party=other)

		rows = _run(RECEIVABLE, group_by="party", to_date=nowdate())
		totals = {row["party"]: row["outstanding"] for row in rows if row.get("type") == "total"}

		self.assertEqual(totals[self.customer], Decimal(200))
		self.assertEqual(totals[other], Decimal(200))
		start = [row.get("party") for row in rows].index(self.customer)
		self.assertEqual([row.get("type") for row in rows[start : start + 3]], ["invoice", "total", None])

	def test_payables_age_purchase_invoices(self):
		supplier = make_supplier(self.payable.name).name
		invoice = make_invoice(
			"Books Purchase Invoice",
			supplier,
			self.payable.name,
			self.item.name,
			self.expense.name,
			posting_date=add_days(nowdate(), -40),
		)
		invoice.items[0].discount_percentage = 0
		invoice.items[0].discount_amount = 0
		invoice.save()
		invoice.submit()

		rows = self._entries(_run(PAYABLE, party=supplier))

		self.assertEqual(
			[(row["voucher_no"], row["voucher_type"], row["range_31_60"]) for row in rows],
			[(invoice.name, "Books Purchase Invoice", Decimal(200))],
		)

	def _invoice(self, days_ago=0, party=None):
		invoice = make_invoice(
			"Books Sales Invoice",
			party or self.customer,
			self.receivable.name,
			self.item.name,
			self.income.name,
			posting_date=add_days(nowdate(), -days_ago),
		)
		invoice.items[0].discount_percentage = 0
		invoice.items[0].discount_amount = 0
		invoice.save()
		invoice.submit()
		return invoice

	def _pay(self, invoice, amount):
		payment = frappe.get_doc(
			{
				"doctype": "Books Payment Entry",
				"party_type": "Books Customer",
				"party": invoice.customer,
				"posting_date": nowdate(),
				"payment_type": "Receive",
				"paid_from": self.receivable.name,
				"paid_to": self.cash.name,
				"mode_of_payment": "Cash",
				"paid_amount": amount,
				"references": [
					{
						"reference_doctype": invoice.doctype,
						"reference_name": invoice.name,
						"allocated_amount": amount,
					}
				],
			}
		).insert()
		payment.submit()
		return payment

	def _entries(self, rows):
		return [row for row in rows if row.get("type") == "invoice"]


def _run(report_name, **filters):
	return run(report_name, filters)["result"]

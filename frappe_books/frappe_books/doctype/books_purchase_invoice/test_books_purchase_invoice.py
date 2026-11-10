# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from frappe_books.tests.accounting import (
	make_account,
	make_customer,
	make_invoice,
	make_item,
	make_supplier,
)


class IntegrationTestBooksPurchaseInvoice(IntegrationTestCase):
	def test_purchase_needs_a_supplier_and_a_payable_account(self):
		payable = make_account("Payable", root_type="Liability", account_type="Payable")
		receivable = make_account("Receivable", account_type="Receivable")
		income = make_account("Income", root_type="Income", account_type="Income Account")
		expense = make_account("Purchase", root_type="Expense", account_type="Expense Account")
		supplier = make_supplier(payable.name)
		customer = make_customer(receivable.name)
		item = make_item(income.name, expense.name)
		for party, account, message in (
			(customer, payable, "Could not find Supplier"),
			(supplier, receivable, "must be of type Payable"),
		):
			with self.subTest(message=message), self.assertRaisesRegex(frappe.ValidationError, message):
				make_invoice("Books Purchase Invoice", party.name, account.name, item.name, expense.name)

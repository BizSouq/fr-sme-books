import json

import frappe
from frappe.tests import IntegrationTestCase

from frappe_books.inventory.labels import (
	create_barcodes,
	get_label_items,
	get_label_rows,
	gs1_check_digit,
	seed_label_templates,
)
from frappe_books.inventory.variants import create_variants, seed_attributes
from frappe_books.tests.accounting import make_account, make_item, make_supplier, unique_name


class TestLabels(IntegrationTestCase):
	def setUp(self):
		seed_attributes()
		self.income = make_account("Label Sales", root_type="Income", account_type="Income Account").name
		self.expense = make_account("Label Cost", root_type="Expense", account_type="Expense Account").name

	def item(self, **values):
		return make_item(self.income, self.expense, **values)

	def test_check_digit_matches_gs1(self):
		# 4006381333931 is GS1's own example.
		self.assertEqual(gs1_check_digit("400638133393"), 1)
		self.assertEqual(gs1_check_digit("200000000001"), 5)

	def test_a_new_site_has_a_default_price_tag(self):
		seed_label_templates()
		template = frappe.get_doc("Books Label Template", "Price Tag 38x25 mm")
		fields = [element["field"] for element in template.get_elements()]
		self.assertEqual(fields, ["item_name", "variant", "barcode", "price"])
		self.assertTrue(frappe.db.exists("Books Label Template", {"is_default": 1}))

	def test_one_template_is_the_default(self):
		names = []
		for _index in range(2):
			doc = frappe.get_doc(
				{
					"doctype": "Books Label Template",
					"template_name": unique_name("Shelf"),
					"label_width": 50,
					"label_height": 30,
					"is_default": 1,
					"layout": json.dumps([{"field": "item_name"}]),
				}
			).insert()
			names.append(doc.name)
		defaults = frappe.get_all("Books Label Template", filters={"is_default": 1}, pluck="name")
		self.assertEqual(defaults, [names[1]])

	def test_a_template_needs_a_size_and_a_valid_layout(self):
		values = {"doctype": "Books Label Template", "label_width": 38, "label_height": 25}
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc({**values, "template_name": unique_name("Bad"), "label_width": 0}).insert()
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc({**values, "template_name": unique_name("Bad"), "layout": "{oops"}).insert()
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{**values, "template_name": unique_name("Bad"), "paper": "A4 Sheet", "columns": 6}
			).insert()

	def test_items_without_a_barcode_get_in_store_ones(self):
		bought = self.item(barcodes=[{"barcode": unique_name("8941")}])
		first, second = self.item(), self.item()
		barcodes = create_barcodes([bought.name, first.name, second.name])

		self.assertEqual(barcodes[bought.name], bought.barcodes[0].barcode)
		new = [barcodes[first.name], barcodes[second.name]]
		for code in new:
			self.assertRegex(code, r"^2\d{12}$")
			self.assertEqual(gs1_check_digit(code[:12]), int(code[12]))
		self.assertEqual(int(new[1][1:12]), int(new[0][1:12]) + 1)
		self.assertEqual(frappe.get_doc("Books Item", first.name).barcodes[0].barcode_type, "EAN-13")
		self.assertTrue(frappe.db.get_single_value("Books Inventory Settings", "show_barcode_field"))

		# Asking again keeps them.
		self.assertEqual(create_barcodes([first.name])[first.name], new[0])

	def test_an_article_labels_each_of_its_sizes(self):
		template = self.item(
			item_name="Label Shoe",
			standard_rate=2450,
			has_variants=1,
			attributes=[{"attribute": "Shoe Size"}, {"attribute": "Color"}],
		)
		create_variants(template.name, {"Shoe Size": ["40", "41"], "Color": ["Black"]})

		result = get_label_rows("Item", [template.name])
		self.assertIn("Color", result["attributes"])
		rows = result["rows"]
		self.assertEqual(len(rows), 2)
		self.assertEqual({row["qty"] for row in rows}, {1})
		row = next(row for row in rows if row["attributes"]["Shoe Size"] == "41")
		self.assertEqual(row["attributes"], {"Shoe Size": "41", "Color": "Black"})
		self.assertEqual((row["item_name"], row["price"]), ("Label Shoe - 41 / Black", 2450))
		self.assertEqual(row["article_name"], "Label Shoe")

		# An article gets no barcode itself; its sizes do.
		barcodes = create_barcodes([template.name, *(row["item_code"] for row in rows)])
		self.assertNotIn(template.name, barcodes)
		self.assertEqual(len(barcodes), 2)

	def test_a_receipt_labels_each_piece_received(self):
		received = make_account("Label Received", root_type="Liability").name
		stock = dict(expense_account=received, is_stock_item=1)
		shirt = make_item(self.income, **stock, standard_rate=900)
		rice = make_item(self.income, **stock, standard_rate=80, stock_uom="Kg")
		payable = make_account("Label Payable", root_type="Liability", account_type="Payable").name
		receipt = frappe.get_doc(
			{
				"doctype": "Books Purchase Receipt",
				"supplier": make_supplier(payable).name,
				"items": [
					{"item_code": shirt.name, "warehouse": "Stores", "qty": 3, "rate": 500},
					{"item_code": rice.name, "warehouse": "Stores", "qty": 2.5, "rate": 60},
				],
			}
		).insert()

		rows = get_label_rows("Purchase Receipt", [receipt.name])["rows"]
		self.assertEqual([(row["item_code"], row["qty"]) for row in rows], [(shirt.name, 3), (rice.name, 3)])
		self.assertEqual(rows[0]["price"], 900)

	def test_items_added_by_hand_get_one_label_each(self):
		item = self.item(item_name="Hand Item")
		self.assertEqual(
			[(row["item_name"], row["qty"]) for row in get_label_items([item.name])], [("Hand Item", 1)]
		)

import frappe
from frappe.tests import IntegrationTestCase

from frappe_books.inventory.variants import SHIPPED_ATTRIBUTES, create_variants, get_variants, seed_attributes
from frappe_books.tests.accounting import (
	make_account,
	make_customer,
	make_invoice,
	make_item,
	unique_name,
)


class TestItemVariants(IntegrationTestCase):
	def setUp(self):
		seed_attributes()
		self.income = make_account("Shoe Sales", root_type="Income", account_type="Income Account").name
		self.expense = make_account("Shoe Cost", root_type="Expense", account_type="Expense Account").name

	def make_template(self, *attributes, **values):
		return make_item(
			self.income,
			self.expense,
			item_name="Runner Shoe",
			standard_rate=2500,
			has_variants=1,
			attributes=[{"attribute": attribute} for attribute in attributes],
			**values,
		)

	def test_a_new_site_has_size_shoe_size_and_color(self):
		for attribute in SHIPPED_ATTRIBUTES:
			self.assertTrue(frappe.db.exists("Books Item Attribute", attribute))
		color = frappe.get_doc("Books Item Attribute", "Color")
		black = color.values[0]
		self.assertEqual((black.attribute_value, black.abbreviation), ("Black", "BLK"))

	def test_a_value_without_a_code_is_coded_by_itself(self):
		attribute = frappe.get_doc(
			{
				"doctype": "Books Item Attribute",
				"attribute_name": unique_name("Fit"),
				"values": [{"attribute_value": "Slim fit"}, {"attribute_value": "Regular"}],
			}
		).insert()
		self.assertEqual([row.abbreviation for row in attribute.values], ["SLIMFIT", "REGULAR"])

		attribute.append("values", {"attribute_value": "regular"})
		with self.assertRaises(frappe.ValidationError):
			attribute.save()

	def test_a_template_needs_an_attribute(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_template()

	def test_creates_an_item_for_each_size_and_color(self):
		template = self.make_template("Shoe Size", "Color")
		result = create_variants(template.name, {"Shoe Size": ["41", "40"], "Color": ["Black", "White"]})

		self.assertEqual(len(result["created"]), 4)
		self.assertIn(f"{template.name}-40-BLK", result["created"])
		variant = frappe.get_doc("Books Item", f"{template.name}-41-WHT")
		self.assertEqual(variant.variant_of, template.name)
		self.assertEqual(variant.item_name, "Runner Shoe - 41 / White")
		self.assertEqual(variant.standard_rate, 2500)
		self.assertFalse(variant.has_variants)
		self.assertEqual(
			[(row.attribute, row.attribute_value) for row in variant.attributes],
			[("Shoe Size", "41"), ("Color", "White")],
		)

		# Asking again creates only the sizes it lacks, at the given price.
		again = create_variants(template.name, {"Shoe Size": ["40", "42"], "Color": ["Black"]}, rate=2800)
		self.assertEqual(again["created"], [f"{template.name}-42-BLK"])
		self.assertEqual(frappe.db.get_value("Books Item", again["created"][0], "standard_rate"), 2800)

		grid = get_variants(template.name)
		self.assertEqual([row["attribute"] for row in grid["attributes"]], ["Shoe Size", "Color"])
		self.assertEqual(len(grid["variants"]), 5)
		self.assertEqual(grid["variants"][0]["stock_qty"], 0)

	def test_a_variant_has_one_value_of_each_attribute_once(self):
		template = self.make_template("Size")
		(name,) = create_variants(template.name, {"Size": ["M"]})["created"]

		twin = frappe.copy_doc(frappe.get_doc("Books Item", name))
		twin.item_code = unique_name("Twin")
		with self.assertRaises(frappe.ValidationError):
			twin.insert()

		twin.attributes[0].attribute_value = "Huge"
		with self.assertRaises(frappe.ValidationError):
			twin.insert()

	def test_a_template_with_sizes_keeps_its_attributes(self):
		template = self.make_template("Size")
		create_variants(template.name, {"Size": ["S"]})

		template.reload()
		template.append("attributes", {"attribute": "Color"})
		with self.assertRaises(frappe.ValidationError):
			template.save()

		template.reload()
		template.has_variants = 0
		with self.assertRaises(frappe.ValidationError):
			template.save()

	def test_variants_follow_the_template(self):
		template = self.make_template("Size", description="Cotton tee")
		(name,) = create_variants(template.name, {"Size": ["L"]})["created"]

		template.reload()
		template.gst_hsn_code = "640299"
		template.save()
		self.assertEqual(frappe.db.get_value("Books Item", name, "gst_hsn_code"), "640299")

	def test_a_sale_names_a_size_not_the_article(self):
		template = self.make_template("Size")
		(variant,) = create_variants(template.name, {"Size": ["XL"]})["created"]
		receivable = make_account("Shoe Receivable", account_type="Receivable").name
		customer = make_customer(receivable).name

		with self.assertRaises(frappe.ValidationError):
			make_invoice("Books Sales Invoice", customer, receivable, template.name, self.income)
		invoice = make_invoice("Books Sales Invoice", customer, receivable, variant, self.income)
		self.assertEqual(invoice.items[0].item_code, variant)

	def test_a_used_value_stays_on_its_attribute(self):
		attribute = frappe.get_doc(
			{
				"doctype": "Books Item Attribute",
				"attribute_name": unique_name("Width"),
				"values": [{"attribute_value": "Wide"}, {"attribute_value": "Narrow"}],
			}
		).insert()
		template = self.make_template(attribute.name)
		create_variants(template.name, {attribute.name: ["Wide"]})

		attribute.values = [row for row in attribute.values if row.attribute_value != "Wide"]
		with self.assertRaises(frappe.ValidationError):
			attribute.save()

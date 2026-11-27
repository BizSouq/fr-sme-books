"""Sizes and colors: one article, many items.

A template item (`has_variants`) names the attributes it varies by, like Size and
Color. Each of its variants is an ordinary item with its own stock, price and
barcode, which `variant_of` ties to the template and whose attribute rows name
its values, as ERPNext's item variants do. The template itself is never sold or
stocked: a sale or a receipt picks one of its variants.
"""

import itertools
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt

from frappe_books.inventory.availability import get_stock_quantities

ITEM = "Books Item"
ATTRIBUTE = "Books Item Attribute"

# What a shop starts with; the shop adds its own values or attributes.
SHIPPED_ATTRIBUTES = {
	"Size": ["XS", "S", "M", "L", "XL", "XXL", "3XL"],
	"Shoe Size": [str(size) for size in range(35, 47)],
	"Color": [
		("Black", "BLK", "#111827"),
		("White", "WHT", "#F9FAFB"),
		("Red", "RED", "#DC2626"),
		("Maroon", "MRN", "#7F1D1D"),
		("Pink", "PNK", "#EC4899"),
		("Orange", "ORG", "#F97316"),
		("Yellow", "YLW", "#FACC15"),
		("Green", "GRN", "#16A34A"),
		("Blue", "BLU", "#2563EB"),
		("Navy", "NVY", "#1E3A8A"),
		("Brown", "BRN", "#92400E"),
		("Beige", "BGE", "#E7D7B8"),
		("Grey", "GRY", "#6B7280"),
	],
}

# Template fields that its variants keep in step with. Price, picture, name and
# barcodes are each variant's own.
SHARED_FIELDS = (
	"item_group",
	"item_type",
	"stock_uom",
	"is_stock_item",
	"has_batch_no",
	"batch_number_series",
	"has_serial_no",
	"serial_no_series",
	"gst_hsn_code",
)


def seed_attributes():
	"""Give a site the shipped Size, Shoe Size and Color attributes it lacks."""
	for name, values in SHIPPED_ATTRIBUTES.items():
		if frappe.db.exists(ATTRIBUTE, name):
			continue
		rows = []
		for value in values:
			value, abbreviation, color = value if isinstance(value, tuple) else (value, value, None)
			rows.append({"attribute_value": value, "abbreviation": abbreviation, "color": color})
		frappe.get_doc({"doctype": ATTRIBUTE, "attribute_name": name, "values": rows}).insert(
			ignore_permissions=True
		)


def validate_item(item):
	"""The rules of a template and of a variant; run as the item validates."""
	attributes = [row.attribute for row in item.attributes]
	if len(attributes) != len(set(attributes)):
		frappe.throw(_("Each attribute can be listed only once."))
	if not item.is_new() and item.has_value_changed("variant_of"):
		frappe.throw(_("A size or color stays an item of the article it was made for."))
	if item.variant_of:
		_validate_variant(item)
	elif item.has_variants:
		_validate_template(item)
	elif item.attributes:
		# Rows left from unticking Has Sizes or Colors mean nothing.
		item.attributes = []
	if not item.has_variants and not item.is_new() and item.has_value_changed("has_variants"):
		if frappe.db.exists(ITEM, {"variant_of": item.name}):
			frappe.throw(_("{0} has sizes or colors. Delete them first.").format(item.name))


def _validate_template(item):
	if not item.attributes:
		frappe.throw(_("Add an attribute, like Size or Color, that the sizes or colors differ by."))
	for row in item.attributes:
		row.attribute_value = None
	if item.is_new():
		return
	if item.has_value_changed("has_variants") and frappe.db.exists(
		"Books Stock Ledger Entry", {"item_code": item.name}
	):
		frappe.throw(_("{0} already has stock. Create a new item for its sizes or colors.").format(item.name))
	if _attribute_changes(item):
		frappe.throw(_("Delete the sizes or colors before you change the attributes."))


def _attribute_changes(item):
	"""Whether a saved template with variants now varies by other attributes."""
	if item.is_new() or not frappe.db.exists(ITEM, {"variant_of": item.name}):
		return False
	before = set(
		frappe.get_all(
			"Books Item Variant Attribute",
			filters={"parenttype": ITEM, "parent": item.name},
			pluck="attribute",
		)
	)
	return before != {row.attribute for row in item.attributes}


def _validate_variant(item):
	template = frappe.db.get_value(ITEM, item.variant_of, ["name", "has_variants"], as_dict=True)
	if not template or not template.has_variants:
		frappe.throw(_("{0} has no sizes or colors.").format(item.variant_of))
	item.has_variants = 0
	expected = template_attributes(item.variant_of)
	given = {row.attribute: row.attribute_value for row in item.attributes}
	if set(given) != set(expected):
		frappe.throw(_("Give a value for each of: {0}.").format(", ".join(expected)))
	allowed = attribute_values(expected)
	for attribute, value in given.items():
		if value not in {row.attribute_value for row in allowed[attribute]}:
			frappe.throw(_("{0} is not a value of {1}.").format(value or _("Empty"), attribute))
	twin = _find_variant(item.variant_of, given, exclude=item.name)
	if twin:
		frappe.throw(_("{0} already has these values.").format(twin))


def on_template_update(item):
	"""Keep the variants' shared fields and taxes as the template has them."""
	if not item.has_variants:
		return
	changed = [field for field in SHARED_FIELDS if item.has_value_changed(field)]
	taxes = [(row.item_tax_template, row.valid_from) for row in item.taxes]
	before = item.get_doc_before_save()
	taxes_changed = before is None or taxes != [
		(row.item_tax_template, row.valid_from) for row in before.taxes
	]
	if not changed and not taxes_changed:
		return
	for name in frappe.get_all(ITEM, filters={"variant_of": item.name}, pluck="name"):
		variant = frappe.get_doc(ITEM, name)
		variant.update({field: item.get(field) for field in changed})
		if taxes_changed:
			variant.set("taxes", [{"item_tax_template": t, "valid_from": v} for t, v in taxes])
		variant.save()


def template_attributes(template):
	"""The attributes a template varies by, in its order."""
	return frappe.get_all(
		"Books Item Variant Attribute",
		filters={"parenttype": ITEM, "parent": template},
		pluck="attribute",
		order_by="idx asc",
	)


def attribute_values(attributes):
	"""Map each attribute to its value rows, in their order."""
	values = defaultdict(list)
	for row in frappe.get_all(
		"Books Item Attribute Value",
		filters={"parenttype": ATTRIBUTE, "parent": ["in", list(attributes) or [""]]},
		fields=["parent", "attribute_value", "abbreviation", "color"],
		order_by="idx asc",
	):
		values[row.parent].append(row)
	return values


def _variant_values(template):
	"""Map each variant of the template to its {attribute: value}."""
	values = defaultdict(dict)
	variants = frappe.get_all(ITEM, filters={"variant_of": template}, pluck="name")
	for row in frappe.get_all(
		"Books Item Variant Attribute",
		filters={"parenttype": ITEM, "parent": ["in", variants or [""]]},
		fields=["parent", "attribute", "attribute_value"],
	):
		values[row.parent][row.attribute] = row.attribute_value
	return {name: values[name] for name in variants}


def _find_variant(template, values, exclude=None):
	for name, given in _variant_values(template).items():
		if name != exclude and given == values:
			return name
	return None


@frappe.whitelist()
def get_variants(item: str) -> dict:
	"""The template's attributes with their values, and each variant with its values, price and stock."""
	frappe.has_permission(ITEM, "read", item, throw=True)
	attributes = template_attributes(item)
	values = attribute_values(attributes)
	variant_values = _variant_values(item)
	details = {
		row.name: row
		for row in frappe.get_all(
			ITEM,
			filters={"name": ["in", list(variant_values) or [""]]},
			fields=["name", "item_name", "standard_rate", "image", "is_stock_item"],
		)
	}
	stock = defaultdict(float)
	if variant_values and frappe.has_permission("Books Stock Ledger Entry", "read"):
		for row in get_stock_quantities(items=list(variant_values)):
			stock[row.item_code] += flt(row.actual_qty)
	return {
		"attributes": [
			{
				"attribute": attribute,
				"values": [
					{"value": row.attribute_value, "abbreviation": row.abbreviation, "color": row.color}
					for row in values[attribute]
				],
			}
			for attribute in attributes
		],
		"variants": [
			{
				"name": name,
				"item_name": details[name].item_name,
				"standard_rate": details[name].standard_rate,
				"image": details[name].image,
				"is_stock_item": details[name].is_stock_item,
				"stock_qty": stock[name],
				"values": given,
			}
			for name, given in variant_values.items()
		],
	}


@frappe.whitelist()
def create_variants(item: str, values: dict, rate: float | None = None) -> dict:
	"""Create an item for each combination of the chosen values that the template lacks.

	`values` maps each of the template's attributes to the values chosen, like
	{"Shoe Size": ["40", "41"], "Color": ["Black"]}. Each new item is priced at
	`rate`, else at the template's price.
	"""
	frappe.has_permission(ITEM, "create", throw=True)
	template = frappe.get_doc(ITEM, item)
	template.check_permission("read")
	if not template.has_variants:
		frappe.throw(_("Tick Has Sizes or Colors on {0} first.").format(item))
	attributes = template_attributes(item)
	allowed = attribute_values(attributes)
	chosen = []
	for attribute in attributes:
		rows = {row.attribute_value: row for row in allowed[attribute]}
		picked = [rows[value] for value in rows if value in set(values.get(attribute) or [])]
		if not picked:
			frappe.throw(_("Pick at least one {0}.").format(attribute))
		chosen.append(picked)
	existing = list(_variant_values(item).values())
	created = []
	for combination in itertools.product(*chosen):
		given = {
			attribute: row.attribute_value for attribute, row in zip(attributes, combination, strict=True)
		}
		if given in existing:
			continue
		variant = _new_variant(template, attributes, combination, rate)
		variant.insert()
		created.append(variant.name)
	return {"created": created, "existing": len(existing)}


def _new_variant(template, attributes, combination, rate):
	variant = frappe.copy_doc(template)
	codes = [row.abbreviation or row.attribute_value for row in combination]
	labels = [row.attribute_value for row in combination]
	variant.update(
		{
			"item_code": _unique_code("-".join([template.name, *codes])),
			"item_name": "{0} - {1}".format(template.item_name or template.name, " / ".join(labels)),
			"has_variants": 0,
			"variant_of": template.name,
			"standard_rate": flt(rate) if rate else template.standard_rate,
			"barcodes": [],
		}
	)
	variant.set(
		"attributes",
		[
			{"attribute": attribute, "attribute_value": row.attribute_value}
			for attribute, row in zip(attributes, combination, strict=True)
		],
	)
	return variant


def _unique_code(code):
	"""The code, or the code with a number when an item has it already."""
	candidate, number = code, 1
	while frappe.db.exists(ITEM, candidate):
		number += 1
		candidate = f"{code}-{number}"
	return candidate


def validate_transaction_items(doc, method=None):
	"""A sale, purchase or stock move names a size or color of an article, never the article."""
	names = sorted({row.item_code for row in doc.get("items") or [] if row.get("item_code")})
	if not names:
		return
	templates = frappe.get_all(ITEM, filters={"name": ["in", names], "has_variants": 1}, pluck="name")
	if templates:
		frappe.throw(_("{0} has sizes or colors. Pick one of them instead.").format(templates[0]))

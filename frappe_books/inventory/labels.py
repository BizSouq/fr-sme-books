"""Barcode labels: the items to label, with what a label shows, and barcodes for items that lack one.

A Books Label Template lays the label out; the browser draws the barcodes and
prints. An item's label shows its first barcode. An item with none gets an
EAN-13 in GS1's in-store range, 200 to 299, which no maker's product uses, so
any scanner reads it and it never clashes with a bought-in product's code.
"""

import json
import math
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt

from frappe_books.company import default_company

ITEM = "Books Item"
BARCODE = "Books Item Barcode"
TEMPLATE = "Books Label Template"
# The prefix of the barcodes Books makes; the rest is a running number and a check digit.
IN_STORE_PREFIX = "2"
SOURCES = {"Item": ITEM, "Purchase Receipt": "Books Purchase Receipt"}


def gs1_check_digit(digits: str) -> int:
	"""The check digit EAN-13 and UPC put after `digits`."""
	total = sum(int(digit) * (3 if index % 2 == 0 else 1) for index, digit in enumerate(reversed(digits)))
	return (10 - total % 10) % 10


@frappe.whitelist()
def get_label_rows(source: str = "", names: list | str | None = None) -> dict:
	"""The items to label, with how many labels of each.

	From an item, one label each of its sizes and colors, or of the item itself.
	From a purchase receipt, one label for each piece received, by stock unit.
	"""
	names = _as_list(names)
	rows = []
	if source == "Item":
		rows = _rows_from_items(names)
	elif source == "Purchase Receipt":
		rows = _rows_from_receipts(names)
	elif source:
		frappe.throw(_("Labels print from an Item or a Purchase Receipt."))
	return {
		"rows": _with_item_details(rows),
		"attributes": frappe.get_all("Books Item Attribute", pluck="name", order_by="creation asc"),
		"company": default_company() or "",
	}


@frappe.whitelist()
def get_label_items(items: list | str) -> list[dict]:
	"""What labels show for each item, one label each; for items added on the print page."""
	return _with_item_details([{"item_code": item, "qty": 1} for item in _as_list(items)])


def _rows_from_items(names):
	rows = []
	for name in names:
		frappe.has_permission(ITEM, "read", name, throw=True)
		if frappe.db.get_value(ITEM, name, "has_variants"):
			variants = frappe.get_all(
				ITEM, filters={"variant_of": name}, pluck="name", order_by="creation asc"
			)
			rows.extend({"item_code": variant, "qty": 1} for variant in variants)
		else:
			rows.append({"item_code": name, "qty": 1})
	return rows


def _rows_from_receipts(names):
	rows = []
	for name in names:
		receipt = frappe.get_doc(SOURCES["Purchase Receipt"], name)
		receipt.check_permission("read")
		for row in receipt.items:
			if not row.item_code:
				continue
			qty = flt(row.stock_qty) or flt(row.qty)
			rows.append(
				{
					"item_code": row.item_code,
					# A label a piece: 2.5 kg of rice gets 3 labels; the shop can change it.
					"qty": max(0, math.ceil(qty - 1e-9)),
					"batch_no": row.batch_no or "",
				}
			)
	return rows


def _with_item_details(rows):
	"""Each row with the item's name, price, unit, group, first barcode and attribute values."""
	codes = list({row["item_code"] for row in rows})
	if not codes:
		return []
	items = {
		item.name: item
		for item in frappe.get_all(
			ITEM,
			filters={"name": ["in", codes]},
			fields=["name", "item_name", "standard_rate", "stock_uom", "item_group", "variant_of"],
		)
	}
	# A size or color's label names its article, as its size and color show on their own.
	articles = dict(
		frappe.get_all(
			ITEM,
			filters={
				"name": ["in", list({item.variant_of for item in items.values() if item.variant_of}) or [""]]
			},
			fields=["name", "item_name"],
			as_list=True,
		)
	)
	barcodes = {}
	for row in frappe.get_all(
		BARCODE,
		filters={"parenttype": ITEM, "parent": ["in", codes]},
		fields=["parent", "barcode"],
		order_by="idx asc",
	):
		barcodes.setdefault(row.parent, row.barcode)
	attributes = defaultdict(dict)
	for row in frappe.get_all(
		"Books Item Variant Attribute",
		filters={"parenttype": ITEM, "parent": ["in", codes]},
		fields=["parent", "attribute", "attribute_value"],
		order_by="idx asc",
	):
		attributes[row.parent][row.attribute] = row.attribute_value
	result = []
	for row in rows:
		item = items.get(row["item_code"])
		if not item:
			continue
		result.append(
			{
				"item_code": item.name,
				"item_name": item.item_name or item.name,
				"article_name": articles.get(item.variant_of) or item.item_name or item.name,
				"barcode": barcodes.get(item.name, ""),
				"price": flt(item.standard_rate),
				"uom": item.stock_uom or "",
				"item_group": item.item_group or "",
				"batch_no": row.get("batch_no", ""),
				"attributes": attributes.get(item.name, {}),
				"qty": row["qty"],
			}
		)
	return result


@frappe.whitelist()
def create_barcodes(items: list | str) -> dict:
	"""Give each item without a barcode a new in-store EAN-13; the barcode of every item, by item."""
	codes = list(dict.fromkeys(_as_list(items)))
	existing = {}
	for row in frappe.get_all(
		BARCODE,
		filters={"parenttype": ITEM, "parent": ["in", codes or [""]]},
		fields=["parent", "barcode"],
		order_by="idx asc",
	):
		existing.setdefault(row.parent, row.barcode)
	missing = [code for code in codes if code not in existing]
	if missing:
		_enable_barcodes()
	next_number = _next_in_store_number()
	for code in missing:
		item = frappe.get_doc(ITEM, code)
		item.check_permission("write")
		if item.has_variants:
			# An article is never sold itself; its sizes get the barcodes.
			continue
		barcode = _in_store_barcode(next_number)
		next_number += 1
		item.append("barcodes", {"barcode": barcode, "barcode_type": "EAN-13"})
		item.save()
		existing[code] = barcode
	return existing


def _enable_barcodes():
	"""Show items' barcodes, and the scan field on sales, once Books makes barcodes."""
	settings = "Books Inventory Settings"
	if not frappe.db.get_single_value(settings, "show_barcode_field"):
		doc = frappe.get_single(settings)
		doc.show_barcode_field = 1
		doc.save(ignore_permissions=True)


def _in_store_barcode(number: int) -> str:
	body = f"{IN_STORE_PREFIX}{number:011d}"
	return f"{body}{gs1_check_digit(body)}"


def _next_in_store_number() -> int:
	"""One more than the largest running number of the in-store barcodes the site has."""
	largest = 0
	for barcode in frappe.get_all(
		BARCODE, filters={"barcode": ["like", f"{IN_STORE_PREFIX}%"]}, pluck="barcode"
	):
		if len(barcode) == 13 and barcode.isdigit():
			largest = max(largest, int(barcode[1:12]))
	return largest + 1


def seed_label_templates():
	"""Give a site a ready label: name, size and color, barcode and price on a 38x25 mm roll label."""
	name = "Price Tag 38x25 mm"
	if frappe.db.exists(TEMPLATE, name):
		return
	layout = [
		{
			"id": "name",
			"field": "item_name",
			"x": 1.5,
			"y": 1,
			"width": 35,
			"height": 4,
			"fontSize": 7,
			"bold": True,
			"align": "center",
		},
		{
			"id": "variant",
			"field": "variant",
			"x": 1.5,
			"y": 5,
			"width": 35,
			"height": 3.5,
			"fontSize": 6.5,
			"align": "center",
		},
		{
			"id": "barcode",
			"field": "barcode",
			"x": 2.6,
			"y": 8.5,
			"width": 32.9,
			"height": 10.5,
			"fontSize": 6,
			"showNumber": True,
			"align": "center",
		},
		{
			"id": "price",
			"field": "price",
			"x": 1.5,
			"y": 19.5,
			"width": 35,
			"height": 4.5,
			"fontSize": 9,
			"bold": True,
			"align": "center",
		},
	]
	frappe.get_doc(
		{
			"doctype": TEMPLATE,
			"template_name": name,
			"is_default": 0 if frappe.db.exists(TEMPLATE, {"is_default": 1}) else 1,
			"paper": "Label Printer",
			"label_width": 38,
			"label_height": 25,
			"columns": 1,
			"layout": json.dumps(layout),
		}
	).insert(ignore_permissions=True)


def _as_list(value) -> list[str]:
	if not value:
		return []
	if isinstance(value, str):
		try:
			value = json.loads(value)
		except ValueError:
			value = [value]
	if isinstance(value, str):
		value = [value]
	return [str(name) for name in value if name]

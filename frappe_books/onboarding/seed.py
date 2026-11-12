"""Make the records a business starts with: its items and groups, guest parties and local defaults."""

import frappe
from frappe import _
from frappe.utils import flt

from frappe_books.onboarding import images
from frappe_books.onboarding.catalog import clean_groups, clean_items, clean_uoms
from frappe_books.regional import (
	BANGLADESH_VAT_RATES,
	ensure_bangladesh_cash_denominations,
	ensure_bangladesh_mobile_wallets,
	ensure_bangladesh_vat,
	vat_template_name,
)
from frappe_books.settings import company_country

GUEST_CUSTOMER = "Guest Customer"
GUEST_SUPPLIER = "Guest Supplier"
# What a company in each country can take besides its items, each one a switch on the setup page.
LOCAL_DEFAULTS = {"Bangladesh": ("vat", "mobile_wallets", "cash_denominations")}


def local_defaults() -> tuple[str, ...]:
	return LOCAL_DEFAULTS.get(company_country(), ())


def apply_setup(options: dict) -> dict:
	"""Make what the user chose. Records that exist are left as they are, so this can run again."""
	local = set(local_defaults())
	result = {"items": 0, "item_groups": 0, "skipped_items": 0, "images_queued": 0}
	vat_rate = options.get("vat_rate")
	tax_template = None
	if "vat" in local and options.get("vat"):
		result["vat_templates"] = ensure_bangladesh_vat()
		if vat_rate is not None and flt(vat_rate) in BANGLADESH_VAT_RATES:
			tax_template = vat_template_name(flt(vat_rate))
	if "mobile_wallets" in local and options.get("mobile_wallets"):
		result["mobile_wallets"] = ensure_bangladesh_mobile_wallets()
	if "cash_denominations" in local and options.get("cash_denominations"):
		result["cash_denominations"] = ensure_bangladesh_cash_denominations()
	if options.get("guest_parties"):
		result["guest_parties"] = ensure_guest_parties()

	items = clean_items(options.get("items"))
	groups = clean_groups(options.get("groups"))
	ensure_uoms([*clean_uoms(options.get("uoms")), *({"name": item["uom"], "whole": 0} for item in items)])
	picture_rows = []
	if groups or any(item["group"] for item in items):
		frappe.db.set_single_value("Books Accounting Settings", "enable_item_group", 1)
		known = {group["name"] for group in groups}
		groups += [{"name": name, "image": ""} for name in {item["group"] for item in items} - known if name]
		for group in groups:
			if make_item_group(group["name"]):
				result["item_groups"] += 1
				picture_rows.append(
					{"doctype": "Books Item Group", "name": group["name"], "url": group["image"]}
				)
	for item in items:
		if make_item(item, tax_template):
			result["items"] += 1
			picture_rows.append({"doctype": "Books Item", "name": item["name"], "url": item["image"]})
		else:
			result["skipped_items"] += 1

	picture_rows = [row for row in picture_rows if images.is_allowed_image_url(row["url"])]
	if options.get("fetch_images") and picture_rows:
		result["images_queued"] = len(picture_rows)
		# Downloads take a while, so the page does not wait for them.
		frappe.enqueue(
			images.attach_images,
			queue="long",
			rows=picture_rows,
			enqueue_after_commit=True,
			now=bool(frappe.flags.in_test),
		)
	return result


def ensure_guest_parties() -> list[str]:
	"""A customer and a supplier for sales and purchases with no named party; POS sales default to the customer."""
	made = []
	for doctype, fieldname, name in (
		("Books Customer", "customer_name", GUEST_CUSTOMER),
		("Books Supplier", "supplier_name", GUEST_SUPPLIER),
	):
		if not frappe.db.exists(doctype, name):
			frappe.get_doc({"doctype": doctype, fieldname: name}).insert(ignore_permissions=True)
			made.append(name)
	if not frappe.db.get_single_value("Books Defaults", "pos_customer"):
		frappe.db.set_single_value("Books Defaults", "pos_customer", GUEST_CUSTOMER)
	return made


def ensure_uoms(uoms: list[dict]) -> None:
	for uom in uoms:
		name = uom["name"]
		if name and not frappe.db.exists("Books UOM", name):
			frappe.get_doc(
				{"doctype": "Books UOM", "uom_name": name, "must_be_whole_number": uom["whole"]}
			).insert(ignore_permissions=True)


def make_item_group(name: str) -> bool:
	if frappe.db.exists("Books Item Group", name):
		return False
	frappe.get_doc({"doctype": "Books Item Group", "item_group_name": name}).insert()
	return True


def make_item(item: dict, tax_template: str | None = None) -> bool:
	"""Make the item by the user's own rights; an item of that name is left alone."""
	if frappe.db.exists("Books Item", item["name"]):
		return False
	frappe.get_doc(
		{
			"doctype": "Books Item",
			"item_code": item["name"],
			"item_name": item["name"],
			"item_group": item["group"] or None,
			"item_type": item["type"],
			"stock_uom": item["uom"] or "Unit",
			"standard_rate": item["rate"],
			"description": item["description"],
			"taxes": [{"item_tax_template": tax_template}] if tax_template else [],
		}
	).insert()
	return True


def check_setup_rights() -> None:
	"""The business setup is for someone who may set up the company and make its items."""
	if not frappe.db.get_single_value("Books Accounting Settings", "setup_complete"):
		frappe.throw(_("Set up your organization first."))
	frappe.has_permission("Books Accounting Settings", "write", throw=True)
	frappe.has_permission("Books Item", "create", throw=True)

"""The business setup page's endpoints."""

import frappe
from frappe import _

from frappe_books.onboarding import catalog, images, seed, suggest
from frappe_books.regional import BANGLADESH_VAT_RATES
from frappe_books.settings import company_country


@frappe.whitelist()
def get_options() -> dict:
	"""What the page starts with: the business types, the local defaults on offer and whether the AI can help."""
	seed.check_setup_rights()
	local = seed.local_defaults()
	return {
		"country": company_country(),
		"currency": frappe.db.get_single_value("System Settings", "currency"),
		"business_types": [
			{
				**{key: business[key] for key in ("id", "label", "description", "icon", "questions")},
				"item_count": len(business["items"]),
			}
			for business in catalog.business_types()
		],
		"local_defaults": list(local),
		"vat_rates": list(BANGLADESH_VAT_RATES) if "vat" in local else [],
		"ai": {"available": suggest.is_available()},
	}


@frappe.whitelist(methods=["POST"])
def get_items(business_type: str, answers: dict | None = None) -> dict:
	"""The catalog's groups, units and items for a business type and the answers picked."""
	seed.check_setup_rights()
	business = catalog.get_business_type(business_type)
	if not business:
		frappe.throw(_("Unknown business type: {0}").format(business_type))
	items = catalog.select_items(business, answers)
	used_groups = {item["group"] for item in items}
	rates_apply = not business["currency"] or business["currency"] == frappe.db.get_single_value(
		"System Settings", "currency"
	)
	return {
		"groups": [group for group in business["groups"] if group["name"] in used_groups],
		"uoms": business["uoms"],
		# A price in another currency would mislead, so it is left for the user to fill.
		"items": [item if rates_apply else {**item, "rate": 0} for item in items],
		"existing": frappe.get_all(
			"Books Item", filters={"name": ["in", [item["name"] for item in items]]}, pluck="name"
		),
	}


@frappe.whitelist(methods=["POST"])
def find_images(queries: list) -> dict:
	"""Picture addresses for search phrases, for the page to show beside its items."""
	seed.check_setup_rights()
	return images.find_images([query for query in queries if isinstance(query, str)])


@frappe.whitelist(methods=["POST"])
def suggest_questions(business_label: str, answers: list | None = None, note: str | None = None) -> dict:
	seed.check_setup_rights()
	return {"questions": suggest.suggest_questions(business_label, answers or [], note or "")}


@frappe.whitelist(methods=["POST"])
def suggest_items(
	business_label: str,
	answers: list | None = None,
	note: str | None = None,
	existing: list | None = None,
) -> dict:
	seed.check_setup_rights()
	return suggest.suggest_items(business_label, answers or [], note or "", existing or [])


@frappe.whitelist(methods=["POST"])
def apply(options: dict) -> dict:
	"""Make the items and defaults the user chose."""
	seed.check_setup_rights()
	return seed.apply_setup(options)

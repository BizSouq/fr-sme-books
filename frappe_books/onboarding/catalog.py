"""The business types a new company picks from, and the master data each one starts with.

Books ships a starter catalog in `data/business_types`. A site can add to it, or replace a type, from
an online catalog: set `books_master_data_url` in the site config to a JSON document of the same
shape, `{"business_types": [...]}`. What an online catalog or the AI sends is cleaned here before use.
"""

import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

import frappe
import requests
from frappe.utils import cint, flt

CATALOG_DIRECTORY = Path(__file__).parent.parent / "data" / "business_types"
REMOTE_CATALOG_CONFIG = "books_master_data_url"
REMOTE_CACHE_KEY = "books_onboarding:remote_catalog"
REMOTE_CACHE_SECONDS = 6 * 60 * 60
REMOTE_TIMEOUT_SECONDS = 10
ITEM_TYPES = ("Product", "Service")
MAX_ITEMS = 500
MAX_GROUPS = 60
MAX_QUESTIONS = 8
MAX_OPTIONS = 12


def business_types() -> list[dict]:
	"""Every business type, the shipped ones first, an online one replacing a shipped one of its id."""
	types = {business["id"]: business for business in _shipped_types()}
	for business in _remote_types():
		types[business["id"]] = business
	return sorted(types.values(), key=lambda business: (business["order"], business["label"]))


def get_business_type(business_id: str) -> dict | None:
	return next((business for business in business_types() if business["id"] == business_id), None)


def select_items(business: dict, answers: dict | None) -> list[dict]:
	"""The items that match the answers: an item with no tags always does, a tagged one needs a picked tag.

	With nothing picked at all, every item is offered.
	"""
	picked = {str(tag) for tags in (answers or {}).values() for tag in _as_list(tags)}
	if not picked:
		return business["items"]
	return [item for item in business["items"] if not item["tags"] or picked & set(item["tags"])]


def clean_business_type(raw) -> dict | None:
	"""A business type in the shape the app uses, or None when it has no id or label."""
	if not isinstance(raw, dict):
		return None
	business_id, label = clean_text(raw.get("id"), 60), clean_text(raw.get("label"), 80)
	if not business_id or not label:
		return None
	return {
		"id": business_id,
		"label": label,
		"description": clean_text(raw.get("description"), 200),
		"icon": clean_text(raw.get("icon"), 40),
		"order": cint(raw.get("order")) or 100,
		"currency": clean_text(raw.get("currency"), 3).upper(),
		"uoms": clean_uoms(raw.get("uoms")),
		"questions": clean_questions(raw.get("questions")),
		"groups": clean_groups(raw.get("groups")),
		"items": clean_items(raw.get("items")),
	}


def clean_questions(raw) -> list[dict]:
	questions = []
	for index, question in enumerate(_as_list(raw)[:MAX_QUESTIONS]):
		if not isinstance(question, dict):
			continue
		options = []
		for option in _as_list(question.get("options"))[:MAX_OPTIONS]:
			option = option if isinstance(option, dict) else {"label": option}
			option_label = clean_text(option.get("label"), 80)
			if option_label:
				options.append(
					{"id": clean_text(option.get("id"), 60) or option_label, "label": option_label}
				)
		label = clean_text(question.get("label"), 200)
		if label and len(options) > 1:
			questions.append(
				{
					"id": clean_text(question.get("id"), 60) or f"question_{index + 1}",
					"label": label,
					"multiple": bool(question.get("multiple", True)),
					"options": options,
				}
			)
	return questions


def clean_uoms(raw) -> list[dict]:
	uoms = {}
	for uom in _as_list(raw)[:40]:
		uom = uom if isinstance(uom, dict) else {"name": uom}
		if name := clean_text(uom.get("name"), 40):
			uoms[name] = {"name": name, "whole": 1 if uom.get("whole", 1) else 0}
	return list(uoms.values())


def clean_groups(raw) -> list[dict]:
	groups = {}
	for group in _as_list(raw)[:MAX_GROUPS]:
		group = group if isinstance(group, dict) else {"name": group}
		if name := clean_text(group.get("name"), 140):
			groups[name] = {
				"name": name,
				"image": clean_image_url(group.get("image")),
				"image_query": clean_text(group.get("image_query"), 100),
			}
	return list(groups.values())


def clean_items(raw) -> list[dict]:
	"""Items by name, the first of a name kept; a name is an item's code, so it is one line of text."""
	items = {}
	for item in _as_list(raw)[:MAX_ITEMS]:
		if not isinstance(item, dict):
			continue
		name = clean_text(item.get("name"), 140)
		if not name or name in items:
			continue
		item_type = item.get("type")
		items[name] = {
			"name": name,
			"group": clean_text(item.get("group"), 140),
			"description": clean_text(item.get("description"), 500),
			"type": item_type if item_type in ITEM_TYPES else "Product",
			"uom": clean_text(item.get("uom"), 40),
			"rate": max(flt(item.get("rate")), 0),
			"tags": [tag for tag in (clean_text(tag, 60) for tag in _as_list(item.get("tags"))[:20]) if tag],
			"image": clean_image_url(item.get("image")),
			"image_query": clean_text(item.get("image_query"), 100),
		}
	return list(items.values())


def clean_text(value, length: int) -> str:
	"""One line of plain text, cut to `length`."""
	if not isinstance(value, str | int | float) or isinstance(value, bool):
		return ""
	return " ".join(str(value).split())[:length].strip()


def clean_image_url(value) -> str:
	"""An https address, or nothing: images are fetched by the server, which follows no other scheme."""
	if not isinstance(value, str) or len(value) > 1000:
		return ""
	url = urlparse(value.strip())
	return value.strip() if url.scheme == "https" and url.hostname else ""


def remote_catalog_host() -> str | None:
	url = frappe.conf.get(REMOTE_CATALOG_CONFIG)
	return urlparse(url).hostname if url else None


@lru_cache(maxsize=1)
def _shipped_types() -> list[dict]:
	types = (
		clean_business_type(json.loads(path.read_text())) for path in sorted(CATALOG_DIRECTORY.glob("*.json"))
	)
	return [business for business in types if business]


def _remote_types() -> list[dict]:
	"""The site's online catalog, kept for some hours. A catalog that cannot be read adds nothing."""
	url = frappe.conf.get(REMOTE_CATALOG_CONFIG)
	if not url or urlparse(url).scheme != "https":
		return []
	cached = frappe.cache.get_value(REMOTE_CACHE_KEY)
	if cached is not None:
		return cached
	try:
		response = requests.get(url, timeout=REMOTE_TIMEOUT_SECONDS, headers={"accept": "application/json"})
		response.raise_for_status()
		raw = response.json()
	except (requests.RequestException, ValueError):
		frappe.log_error("Books business setup: the online catalog could not be read")
		raw = {}
	raw_types = raw.get("business_types") if isinstance(raw, dict) else raw
	types = [business for business in map(clean_business_type, _as_list(raw_types)[:100]) if business]
	frappe.cache.set_value(REMOTE_CACHE_KEY, types, expires_in_sec=REMOTE_CACHE_SECONDS)
	return types


def _as_list(value) -> list:
	if isinstance(value, list | tuple):
		return list(value)
	return [] if value is None else [value]

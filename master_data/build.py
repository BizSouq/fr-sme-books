#!/usr/bin/env python3
"""Build the online master data catalog for the business setup page.

Each business type lives in `sources/<id>/`: `type.json` holds its label, questions, groups and units,
and `items.csv` its items, one row each, so the list can be kept in a spreadsheet. This joins them
into `catalog.json`, the `{"business_types": [...]}` document a site reads from the address in
its `books_master_data_url` site config.

The catalog is checked with the app's own cleaning rules, so what is built is what a site will use:

    python3 master_data/build.py             # build master_data/catalog.json
    python3 master_data/build.py --check     # fail if master_data/catalog.json is out of date or invalid
    python3 master_data/build.py --images    # also look up a picture for each item on Wikipedia

Run it from anywhere; it needs only Python 3.10+, not a bench.
"""

import argparse
import csv
import json
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
SOURCES = HERE / "sources"
DIST = HERE / "catalog.json"
IMAGE_CACHE = HERE / "images.json"
SHIPPED = REPO / "frappe_books" / "data" / "business_types"
CSV_COLUMNS = ("group", "name", "type", "uom", "rate", "tags", "image_query", "description", "image")
# Units every site has from install (DEFAULT_UOMS in frappe_books/setup.py), usable without listing.
SITE_UOMS = frozenset(("Unit", "Kg", "Gram", "Meter", "Hour", "Day"))
CATALOG_VERSION = 1


def load_catalog_module():
	"""The app's catalog module, with just enough of Frappe for its cleaning functions."""

	def cint(value):
		try:
			return int(float(value or 0))
		except (TypeError, ValueError):
			return 0

	def flt(value):
		try:
			return float(value or 0)
		except (TypeError, ValueError):
			return 0.0

	frappe = types.ModuleType("frappe")
	frappe.conf = {}
	utils = types.ModuleType("frappe.utils")
	utils.cint, utils.flt = cint, flt
	frappe.utils = utils
	sys.modules.setdefault("frappe", frappe)
	sys.modules.setdefault("frappe.utils", utils)
	try:
		import requests  # noqa: F401
	except ImportError:
		# Only --images needs it.
		sys.modules["requests"] = types.ModuleType("requests")
	sys.path.insert(0, str(REPO))
	from frappe_books.onboarding import catalog

	return catalog


def read_type(directory: Path, images: dict[str, str]) -> dict:
	business = json.loads((directory / "type.json").read_text())
	with (directory / "items.csv").open(newline="", encoding="utf-8") as file:
		rows = list(csv.DictReader(file))
	business["items"] = []
	for row in rows:
		item = {
			"name": row["name"].strip(),
			"group": row["group"].strip(),
			"description": row["description"].strip(),
			"type": (row.get("type") or "").strip() or "Product",
			"uom": row["uom"].strip(),
			"rate": float(row["rate"] or 0),
			"tags": (row.get("tags") or "").split(),
			"image_query": (row.get("image_query") or "").strip(),
		}
		image = (row.get("image") or "").strip() or images.get(item["image_query"], "")
		if image:
			item["image"] = image
		if item["rate"].is_integer():
			item["rate"] = int(item["rate"])
		business["items"].append(item)
	for group in business.get("groups", []):
		if not group.get("image") and images.get(group.get("image_query", "")):
			group["image"] = images[group["image_query"]]
	return business


def problems_in(business: dict, catalog) -> list[str]:
	"""What would be lost or wrong once a site reads this type."""
	found = []
	cleaned = catalog.clean_business_type(business)
	if not cleaned:
		return ["it has no id or label"]
	groups = {group["name"] for group in business.get("groups", [])}
	tags = {option["id"] for question in business.get("questions", []) for option in question["options"]}
	uoms = {uom["name"] for uom in business.get("uoms", [])} | SITE_UOMS
	if len(business["items"]) > catalog.MAX_ITEMS:
		found.append(f"{len(business['items'])} items, more than the {catalog.MAX_ITEMS} a site reads")
	if len(groups) > catalog.MAX_GROUPS:
		found.append(f"{len(groups)} groups, more than the {catalog.MAX_GROUPS} a site reads")
	if len(cleaned["questions"]) != len(business.get("questions", [])):
		found.append("a question would be dropped: it needs a label and two to twelve options")
	for question in business.get("questions", []):
		if len(question["options"]) > catalog.MAX_OPTIONS:
			found.append(f"question {question['id']} has more than {catalog.MAX_OPTIONS} options")
	seen = set()
	for line, item in enumerate(business["items"], start=2):
		where = f"items.csv line {line} ({item['name'] or 'no name'})"
		key = item["name"].casefold()
		if key in seen:
			found.append(f"{where}: the name is used twice")
		seen.add(key)
		if item["name"] != catalog.clean_text(item["name"], 140):
			found.append(f"{where}: the name must be one line of at most 140 characters")
		if item["group"] not in groups:
			found.append(f"{where}: group {item['group']!r} is not in type.json")
		if not set(item["tags"]) <= tags:
			found.append(f"{where}: tags {sorted(set(item['tags']) - tags)} are no question's options")
		if item["uom"] not in uoms:
			found.append(f"{where}: unit {item['uom']!r} is not in type.json")
		if item["type"] not in catalog.ITEM_TYPES:
			found.append(f"{where}: type must be Product or Service")
		if item["rate"] <= 0:
			found.append(f"{where}: it needs a price")
		if not item["description"] or len(item["description"]) > 500:
			found.append(f"{where}: it needs a description of at most 500 characters")
		if not item["image_query"] and not item.get("image"):
			found.append(f"{where}: it needs a picture or a phrase to look one up")
		if item.get("image") and not catalog.clean_image_url(item["image"]):
			found.append(f"{where}: the picture must be an https address")
	return found


def check_shipped(business: dict) -> list[str]:
	"""A type online replaces the shipped type of its id, so it must keep every shipped item."""
	path = SHIPPED / f"{business['id']}.json"
	if not path.exists():
		return []
	names = {item["name"] for item in business["items"]}
	missing = [item["name"] for item in json.loads(path.read_text())["items"] if item["name"] not in names]
	return [f"shipped item {name!r} is missing, and a site would lose it" for name in missing]


def find_pictures(queries: set[str], images: dict[str, str]) -> None:
	"""Look up pictures the way the app does, keeping them in images.json so a build needs no network."""
	from frappe_books.onboarding.images import IMAGE_HOSTS, search_image

	for query in sorted(queries - images.keys()):
		url = search_image(query, IMAGE_HOSTS)
		if url is not None:
			images[query] = url
			print(f"  {query}: {url or 'no picture'}")


def build(resolve_images: bool) -> dict:
	catalog = load_catalog_module()
	images = json.loads(IMAGE_CACHE.read_text()) if IMAGE_CACHE.exists() else {}
	directories = sorted(path for path in SOURCES.iterdir() if (path / "type.json").exists())
	if resolve_images:
		queries = set()
		for directory in directories:
			business = read_type(directory, {})
			queries |= {item["image_query"] for item in business["items"] if item["image_query"]}
			queries |= {group["image_query"] for group in business["groups"] if group.get("image_query")}
		find_pictures(queries, images)
		IMAGE_CACHE.write_text(json.dumps(dict(sorted(images.items())), indent=1, ensure_ascii=False) + "\n")
	images = {query: url for query, url in images.items() if url}

	business_types, problems = [], []
	for directory in directories:
		business = read_type(directory, images)
		found = problems_in(business, catalog) + check_shipped(business)
		problems += [f"{directory.name}: {problem}" for problem in found]
		business_types.append(business)
	if problems:
		raise SystemExit("The catalog has problems:\n  " + "\n  ".join(problems))
	business_types.sort(key=lambda business: (business.get("order", 100), business["label"]))
	return {"version": CATALOG_VERSION, "business_types": business_types}


def main() -> None:
	parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
	parser.add_argument(
		"--check", action="store_true", help="fail if master_data/catalog.json is out of date"
	)
	parser.add_argument("--images", action="store_true", help="look up pictures on Wikipedia first")
	args = parser.parse_args()

	catalog = build(args.images)
	text = json.dumps(catalog, indent=1, ensure_ascii=False) + "\n"
	if args.check:
		if not DIST.exists() or DIST.read_text() != text:
			raise SystemExit("master_data/catalog.json is out of date: run python3 master_data/build.py")
	else:
		DIST.write_text(text)
	for business in catalog["business_types"]:
		lookups = {item["image_query"] for item in business["items"] if not item.get("image")}
		print(
			f"{business['id']:<12} {len(business['groups']):>3} groups {len(business['items']):>4} items"
			f" {len(lookups):>4} picture phrases to look up"
		)
	print(f"{'total':<12} {sum(len(b['items']) for b in catalog['business_types']):>15} items")


if __name__ == "__main__":
	main()

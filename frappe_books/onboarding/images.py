"""Pictures for the items a business starts with, found online.

A picture is looked up on Wikipedia by a search phrase, like "Chicken biryani". The server downloads
only from the hosts named here and the site's own online catalog, so an address a browser sends
cannot make it fetch anything else.
"""

import mimetypes
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from urllib.parse import urlparse

import frappe
import requests

from frappe_books.onboarding.catalog import clean_image_url, clean_text, remote_catalog_host

SEARCH_ENDPOINT = "https://en.wikipedia.org/w/api.php"
# Wikimedia asks automated clients to name themselves.
USER_AGENT = "FrappeBooksBusinessSetup/1.0"
IMAGE_HOSTS = frozenset(("upload.wikimedia.org",))
# More hosts a site trusts for item pictures, as a list in the site config.
IMAGE_HOSTS_CONFIG = "books_image_hosts"
THUMBNAIL_WIDTH = 480
TIMEOUT_SECONDS = 8
MAX_IMAGE_BYTES = 3 * 1024 * 1024
MAX_QUERIES = 120
WORKERS = 8
CACHE_KEY = "books_onboarding:image"
CACHE_SECONDS = 30 * 24 * 60 * 60
IMAGE_TYPES = ("image/jpeg", "image/png", "image/webp", "image/gif")


def find_images(queries: list[str]) -> dict[str, str]:
	"""The picture address for each search phrase that has one."""
	queries = list(
		dict.fromkeys(query for query in (clean_text(q, 100) for q in queries[:MAX_QUERIES]) if query)
	)
	found = {query: frappe.cache.hget(CACHE_KEY, query.lower()) for query in queries}
	missing = [query for query, url in found.items() if url is None]
	if missing:
		with ThreadPoolExecutor(max_workers=WORKERS) as pool:
			# Worker threads have no site, so they are handed what they need from it.
			searched = dict(
				zip(missing, pool.map(partial(search_image, hosts=allowed_hosts()), missing), strict=True)
			)
		for query, url in searched.items():
			if url is not None:
				# An empty address is kept too: the phrase has no picture, so it is not searched again.
				frappe.cache.hset(CACHE_KEY, query.lower(), url)
		frappe.cache.expire(frappe.cache.make_key(CACHE_KEY), CACHE_SECONDS)
		found.update(searched)
	return {query: url for query, url in found.items() if url}


def search_image(query: str, hosts: frozenset[str]) -> str | None:
	"""The lead picture of the best matching Wikipedia article: "" for none, None when the search failed."""
	params = {
		"action": "query",
		"format": "json",
		"generator": "search",
		"gsrsearch": query,
		"gsrlimit": 1,
		"prop": "pageimages",
		"piprop": "thumbnail",
		"pithumbsize": THUMBNAIL_WIDTH,
	}
	try:
		response = requests.get(
			SEARCH_ENDPOINT, params=params, timeout=TIMEOUT_SECONDS, headers={"user-agent": USER_AGENT}
		)
		response.raise_for_status()
		pages = (response.json().get("query") or {}).get("pages") or {}
	except (requests.RequestException, ValueError, AttributeError):
		return None
	for page in pages.values():
		url = clean_image_url((page.get("thumbnail") or {}).get("source"))
		if url and urlparse(url).hostname in hosts:
			return url
	return ""


def allowed_hosts() -> frozenset[str]:
	hosts = {*IMAGE_HOSTS, *(frappe.conf.get(IMAGE_HOSTS_CONFIG) or []), remote_catalog_host()}
	return frozenset(host for host in hosts if host)


def is_allowed_image_url(url: str, hosts: frozenset[str] | None = None) -> bool:
	hosts = allowed_hosts() if hosts is None else hosts
	return urlparse(clean_image_url(url)).hostname in hosts


def download_image(url: str, hosts: frozenset[str]) -> tuple[bytes, str] | None:
	"""The picture and its file extension, or None when it is not a picture of a size worth keeping."""
	if not is_allowed_image_url(url, hosts):
		return None
	try:
		response = requests.get(
			url,
			timeout=TIMEOUT_SECONDS,
			headers={"user-agent": USER_AGENT},
			stream=True,
			# A redirect could lead off the allowed hosts.
			allow_redirects=False,
		)
		response.raise_for_status()
		content_type = (response.headers.get("content-type") or "").split(";")[0].strip().lower()
		if response.status_code != 200 or content_type not in IMAGE_TYPES:
			return None
		content = response.raw.read(MAX_IMAGE_BYTES + 1, decode_content=True)
	except requests.RequestException:
		return None
	if not content or len(content) > MAX_IMAGE_BYTES:
		return None
	return content, mimetypes.guess_extension(content_type) or ".jpg"


def attach_images(rows: list[dict]) -> int:
	"""Download a picture for each `{doctype, name, url}` and set it as the record's image.

	A record that has a picture already keeps it. Returns how many pictures were attached.
	"""
	rows = [row for row in rows if not frappe.db.get_value(row["doctype"], row["name"], "image")]
	with ThreadPoolExecutor(max_workers=WORKERS) as pool:
		downloads = list(
			pool.map(partial(download_image, hosts=allowed_hosts()), [row["url"] for row in rows])
		)
	attached = 0
	for row, download in zip(rows, downloads, strict=True):
		if not download:
			continue
		content, extension = download
		file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"{frappe.scrub(row['name'])[:80]}{extension}",
				"content": content,
				"attached_to_doctype": row["doctype"],
				"attached_to_name": row["name"],
				"attached_to_field": "image",
				"is_private": 0,
			}
		).insert(ignore_permissions=True)
		frappe.db.set_value(row["doctype"], row["name"], "image", file.file_url)
		attached += 1
	return attached

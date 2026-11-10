from frappe.utils.jinja_globals import bundled_asset

from frappe_books.ai import guard as ai_guard
from frappe_books.coa import chart_options
from frappe_books.company import default_company
from frappe_books.regional import INDIAN_STATES
from frappe_books.settings import regional_code


def extend_bootinfo(bootinfo):
	"""Add what the Books app starts with to the session boot."""
	bootinfo.books = {
		"country_code": regional_code(),
		"company": default_company(),
		"charts_of_accounts": chart_options(),
		"indian_states": INDIAN_STATES,
		# The stylesheet Frappe prints with, for print previews in /books
		"print_style": bundled_asset("print.bundle.css"),
		# Whether the AI Guard lets this user use the assistant, and change its settings
		"ai": {"can_use": ai_guard.can_use(), "is_admin": ai_guard.is_admin()},
	}

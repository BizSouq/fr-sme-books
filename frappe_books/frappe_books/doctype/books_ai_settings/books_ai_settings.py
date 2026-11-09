# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class BooksAISettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from frappe_books.frappe_books.doctype.books_ai_blocked_doctype.books_ai_blocked_doctype import (
			BooksAIBlockedDocType,
		)
		from frappe_books.frappe_books.doctype.books_ai_role.books_ai_role import BooksAIRole

		allow_destructive: DF.Check
		allow_personal_keys: DF.Check
		allow_writes: DF.Check
		allowed_roles: DF.TableMultiSelect[BooksAIRole]
		api_key: DF.Password | None
		blocked_doctypes: DF.TableMultiSelect[BooksAIBlockedDocType]
		enabled: DF.Check
		max_rows: DF.Int
		max_tool_rounds: DF.Int
		model: DF.Data | None
		provider: DF.Literal["anthropic", "openai", "gemini"]
		requests_per_day: DF.Int
		requests_per_minute: DF.Int
	# end: auto-generated types

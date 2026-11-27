# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import re

import frappe
from frappe import _
from frappe.model.document import Document


class BooksItemAttribute(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from frappe_books.frappe_books.doctype.books_item_attribute_value.books_item_attribute_value import (
			BooksItemAttributeValue,
		)

		attribute_name: DF.Data
		values: DF.Table[BooksItemAttributeValue]
	# end: auto-generated types

	_DOCTYPE_NAME = "Books Item Attribute"

	def before_validate(self):
		# A value without a code goes into item codes as itself, without spaces.
		for row in self.values:
			row.attribute_value = (row.attribute_value or "").strip()
			row.abbreviation = (row.abbreviation or "").strip() or value_code(row.attribute_value)

	def validate(self):
		values = [row.attribute_value.casefold() for row in self.values]
		duplicates = sorted(
			{row.attribute_value for row in self.values if values.count(row.attribute_value.casefold()) > 1}
		)
		if duplicates:
			frappe.throw(_("{0} is listed more than once.").format(", ".join(duplicates)))
		self.validate_used_values()

	def validate_used_values(self):
		"""A size or color that items use stays, so that they keep naming it."""
		if self.is_new():
			return
		kept = {row.attribute_value for row in self.values}
		used = frappe.get_all(
			"Books Item Variant Attribute",
			filters={"parenttype": "Books Item", "attribute": self.name, "attribute_value": ["is", "set"]},
			pluck="attribute_value",
			distinct=True,
		)
		removed = sorted(set(used) - kept)
		if removed:
			frappe.throw(_("Items use {0}, so it can't be removed.").format(", ".join(removed)))


def value_code(value):
	"""The part of an item code that names a value: its letters and digits, in capitals."""
	return re.sub(r"[^\w]+", "", value or "", flags=re.UNICODE).upper()

# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document


class BooksLabelTemplate(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		column_gap: DF.Float
		columns: DF.Int
		is_default: DF.Check
		label_height: DF.Float
		label_width: DF.Float
		layout: DF.Code | None
		margin_left: DF.Float
		margin_top: DF.Float
		paper: DF.Literal["Label Printer", "A4 Sheet"]
		row_gap: DF.Float
		template_name: DF.Data
	# end: auto-generated types

	def validate(self):
		if self.label_width <= 0 or self.label_height <= 0:
			frappe.throw(_("Give the label a width and a height."))
		self.columns = max(1, self.columns or 1)
		self.layout = json.dumps(self.get_elements(), ensure_ascii=False)
		if self.paper == "A4 Sheet":
			used = self.margin_left + self.columns * self.label_width + (self.columns - 1) * self.column_gap
			if used > 210.5:
				frappe.throw(_("{0} labels across don't fit on an A4 sheet's 210 mm.").format(self.columns))

	def on_update(self):
		# One default: the template last made the default.
		if self.is_default:
			frappe.db.set_value(
				self.doctype,
				{"name": ["!=", self.name], "is_default": 1},
				"is_default",
				0,
				update_modified=False,
			)

	def get_elements(self) -> list[dict]:
		"""The layout's elements, as the label designer saves them."""
		try:
			elements = json.loads(self.layout or "[]")
		except ValueError:
			frappe.throw(_("The label layout is not valid."))
		if not isinstance(elements, list) or not all(isinstance(element, dict) for element in elements):
			frappe.throw(_("The label layout is not valid."))
		return elements

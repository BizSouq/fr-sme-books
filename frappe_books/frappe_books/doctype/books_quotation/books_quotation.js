// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Books Quotation", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1) return;
		frm.add_custom_button(__("Sales Invoice"), () => frappe.model.open_mapped_doc({
			method: "frappe_books.frappe_books.doctype.books_quotation.books_quotation.make_sales_invoice",
			frm,
		}), __("Create"));
	},
});

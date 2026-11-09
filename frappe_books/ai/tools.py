"""What the assistant may do, and how each step runs.

Every tool runs here on the server as the signed-in user, behind the AI Guard. Reads return at most
the guard's row limit. Writes never run when the model asks: they come back as a proposal with a
preview, and run only when the person approves that exact proposal.
"""

import json

import frappe
from frappe import _
from frappe.desk.query_report import run as run_query_report

from frappe_books.ai import guard
from frappe_books.permissions import BOOKS_MODULE
from frappe_books.reports import dashboard
from frappe_books.reports.filters import get_default_filters

DEFAULT_LIMIT = 50
PREVIEW_FIELD_LIMIT = 8
SORTABLE_FIELDS = ("name", "creation", "modified")
FILTER_OPERATORS = ("=", "!=", ">", ">=", "<", "<=", "like", "not like", "in", "not in", "between", "is")
PERIODS = ("This Month", "This Quarter", "This Year", "YTD")
METRICS = ("cashflow", "profit_and_loss", "top_expenses", "sales_invoices", "purchase_invoices")
LAYOUT_FIELDTYPES = ("Section Break", "Column Break", "Tab Break", "HTML", "Button", "Fold", "Heading")

FILTERS_SCHEMA = {
	"type": "array",
	"description": "Conditions combined with AND, each [fieldname, operator, value], e.g. "
	'[["posting_date", ">=", "2026-04-01"], ["outstanding_amount", ">", 0]]. Operators: '
	+ ", ".join(FILTER_OPERATORS)
	+ '. "in" and "not in" take a list; "between" takes [from, to]. Dates are ISO-8601. '
	'Prefer "=" and "in"; "like" with a bare value matches anywhere, so write "Acme%" for a prefix.',
	"items": {"type": "array", "items": {}},
}
DOCTYPE_PARAMETER = {
	"type": "string",
	"description": "Exact record type name from list_record_types, e.g. Books Sales Invoice.",
}

READ_TOOLS = [
	{
		"name": "list_record_types",
		"description": "List the record types of these books the user may read, with whether each is a "
		"submittable document. Call this first when you are not sure what a thing is called here; "
		"the set depends on the features the company has turned on.",
		"parameters": {"type": "object", "properties": {}},
	},
	{
		"name": "describe_record_type",
		"description": "Describe one record type: its fields, their types, which are required, what Link "
		"fields point at, and its child tables. Call this before filtering on or proposing a field you "
		"have not seen in a result, because a guessed fieldname is refused.",
		"parameters": {
			"type": "object",
			"properties": {"doctype": DOCTYPE_PARAMETER},
			"required": ["doctype"],
		},
	},
	{
		"name": "list_records",
		"description": "Fetch rows of one record type: unpaid invoices, recent payments, items below a "
		"reorder level. Results are capped and say when rows were left out; for a total, call "
		"count_records instead. Child table rows are not included; use get_record for those.",
		"parameters": {
			"type": "object",
			"properties": {
				"doctype": DOCTYPE_PARAMETER,
				"fields": {
					"type": "array",
					"items": {"type": "string"},
					"description": "Fields to return. Ask only for what you need; the default is name only.",
				},
				"filters": FILTERS_SCHEMA,
				"order_by": {"type": "string", "enum": list(SORTABLE_FIELDS)},
				"order": {"type": "string", "enum": ["asc", "desc"]},
				"limit": {"type": "number", "description": "Rows to return, default 50."},
			},
			"required": ["doctype"],
		},
	},
	{
		"name": "get_record",
		"description": "Fetch one complete record by name, with its child tables: the items of an "
		"invoice, the accounts of a journal entry.",
		"parameters": {
			"type": "object",
			"properties": {"doctype": DOCTYPE_PARAMETER, "name": {"type": "string"}},
			"required": ["doctype", "name"],
		},
	},
	{
		"name": "count_records",
		"description": "Count the records that match the filters, without fetching them.",
		"parameters": {
			"type": "object",
			"properties": {"doctype": DOCTYPE_PARAMETER, "filters": FILTERS_SCHEMA},
			"required": ["doctype"],
		},
	},
	{
		"name": "list_reports",
		"description": "List the reports the user may run, with the filters each accepts and their "
		"default values. Call this before run_report rather than guessing a report name.",
		"parameters": {"type": "object", "properties": {}},
	},
	{
		"name": "run_report",
		"description": "Run a built-in report (profit and loss, balance sheet, trial balance, general "
		"ledger, stock balance and so on) and return its columns and rows. Prefer this over adding up "
		"records yourself: the reports apply opening balances, periods and sign conventions.",
		"parameters": {
			"type": "object",
			"properties": {
				"report_name": {"type": "string", "description": "Exact name from list_reports."},
				"filters": {
					"type": "object",
					"description": 'Filter values by name from list_reports, e.g. {"from_date": "2026-04-01"}.',
				},
			},
			"required": ["report_name"],
		},
	},
	{
		"name": "get_dashboard_summary",
		"description": "The dashboard's headline figures for a period ending today: monthly cash in and "
		"out, monthly profit, the top expense accounts, or the paid and unpaid totals of sales or "
		"purchase invoices. Cheaper than a full report when the question is a headline number.",
		"parameters": {
			"type": "object",
			"properties": {
				"metric": {"type": "string", "enum": list(METRICS)},
				"period": {"type": "string", "enum": list(PERIODS)},
			},
			"required": ["metric", "period"],
		},
	},
	{
		"name": "open_screen",
		"description": "Open a screen of the app for the user: a record, a list, a report or the "
		"dashboard. Use it when they would rather see the real thing, not in the middle of an answer.",
		"parameters": {
			"type": "object",
			"properties": {
				"target": {"type": "string", "enum": ["record", "list", "report", "dashboard"]},
				"doctype": DOCTYPE_PARAMETER,
				"name": {"type": "string", "description": "For a record."},
				"report_name": {"type": "string", "description": "For a report."},
			},
			"required": ["target"],
		},
	},
]

RECORD_PARAMETERS = {
	"type": "object",
	"properties": {"doctype": DOCTYPE_PARAMETER, "name": {"type": "string"}},
	"required": ["doctype", "name"],
}

WRITE_TOOLS = [
	{
		"name": "create_record",
		"description": "Propose a new record: a customer, an item, an invoice. The user sees every value "
		"and approves before anything is written, so propose the whole record at once. Check "
		"describe_record_type first so required fields are filled and Link values name records "
		"that exist.",
		"parameters": {
			"type": "object",
			"properties": {
				"doctype": DOCTYPE_PARAMETER,
				"values": {
					"type": "object",
					"description": 'Fieldname to value. Child tables are lists of rows, e.g. {"items": '
					'[{"item": "Widget", "quantity": 2}]}.',
				},
			},
			"required": ["doctype", "values"],
		},
	},
	{
		"name": "update_record",
		"description": "Propose changing fields of an existing draft or master record. The user sees each "
		"field before and after and approves. Send only the fields that change; a child table you send "
		"replaces all its rows. Submitted documents cannot be edited.",
		"parameters": {
			"type": "object",
			"properties": {
				"doctype": DOCTYPE_PARAMETER,
				"name": {"type": "string"},
				"values": {"type": "object", "description": "Fieldname to new value."},
			},
			"required": ["doctype", "name", "values"],
		},
	},
	{
		"name": "submit_document",
		"description": "Propose submitting a draft document, which posts its ledger entries and locks it.",
		"parameters": RECORD_PARAMETERS,
	},
	{
		"name": "delete_record",
		"description": "Propose deleting a draft or a master record. A submitted document is cancelled, "
		"not deleted.",
		"parameters": RECORD_PARAMETERS,
	},
	{
		"name": "cancel_document",
		"description": "Propose cancelling a submitted document, which reverses its ledger entries. This "
		"is how a posted transaction is undone.",
		"parameters": RECORD_PARAMETERS,
	},
]


def get_tool_specs() -> list[dict]:
	"""The tools offered to the model. A tool the guard would refuse is not offered at all."""
	settings = guard.get_settings()
	if not settings.allow_writes:
		return READ_TOOLS
	allowed = [
		tool
		for tool in WRITE_TOOLS
		if tool["name"] not in guard.DESTRUCTIVE_TOOLS or settings.allow_destructive
	]
	return READ_TOOLS + allowed


def run_tool(name: str, args: dict) -> dict:
	"""Run a read, or hold a write as a proposal. A refusal or failure becomes an error result."""
	args = args if isinstance(args, dict) else {}
	if name not in READERS and name not in PREVIEWERS:
		return {"status": "failed", "content": {"error": f"no tool named {name}"}}
	if name in guard.WRITE_TOOLS and name not in {tool["name"] for tool in get_tool_specs()}:
		return _failed(name, guard.AIGuardError(_("The assistant may not propose that change here.")))

	frappe.db.savepoint("books_ai_tool")
	try:
		if name in READERS:
			return {"status": "done", "content": _json(READERS[name](args))}
		guard.check_write(name)
		doctype, docname, preview = PREVIEWERS[name](args)
		token = guard.hold_proposal(name, args, doctype, docname)
		return {"status": "proposed", "token": token, "preview": _json(preview)}
	except Exception as error:
		frappe.db.rollback(save_point="books_ai_tool")
		guard.relog(error)
		return _failed(name, error)


def confirm_action(token: str) -> dict:
	"""Run the change the person approved: the held proposal, never anything the client sends."""
	proposal = guard.take_proposal(token)
	name, args = proposal["tool"], proposal["args"]
	frappe.db.savepoint("books_ai_write")
	try:
		guard.check_write(name)
		content = WRITERS[name](args)
	except Exception as error:
		frappe.db.rollback(save_point="books_ai_write")
		guard.relog(error)
		guard.log("Failed", name, proposal["doctype"], proposal["name"], reason=_message(error), payload=args)
		return _failed(name, error)
	guard.log("Approved", name, proposal["doctype"], content.get("name") or proposal["name"], payload=args)
	return {"status": "done", "content": _json(content)}


def decline_action(token: str, reason: str | None = None) -> dict:
	proposal = guard.take_proposal(token)
	guard.log("Declined", proposal["tool"], proposal["doctype"], proposal["name"], reason=reason)
	return {"status": "cancelled"}


def _failed(name, error) -> dict:
	# The model reads the reason and corrects itself; the user sees it on the tool card, not as a toast.
	frappe.local.message_log = []
	return {"status": "failed", "content": {"error": _message(error)}}


def _message(error) -> str:
	from frappe.utils import strip_html

	return strip_html(str(error)) or error.__class__.__name__


def _json(value):
	"""Decimals, dates and documents as the JSON the model reads."""
	return json.loads(frappe.as_json(value))


# Reads


def list_record_types(_args) -> dict:
	hidden = guard.blocked_doctypes() | guard.AI_DOCTYPES
	doctypes = frappe.get_all(
		"DocType",
		filters={"module": BOOKS_MODULE, "istable": 0},
		fields=["name", "issingle", "is_submittable"],
		order_by="name",
	)
	return {
		"record_types": [
			{
				"doctype": row.name,
				**({"single": True} if row.issingle else {}),
				**({"submittable": True} if row.is_submittable else {}),
			}
			for row in doctypes
			if row.name not in hidden and frappe.has_permission(row.name, "read")
		]
	}


def describe_record_type(args) -> dict:
	doctype = args.get("doctype")
	guard.check_doctype(doctype, "read", "describe_record_type")
	meta = frappe.get_meta(doctype)
	fields = []
	for field in meta.fields:
		if field.fieldtype in LAYOUT_FIELDTYPES or guard.is_secret_field(field):
			continue
		entry = {"fieldname": field.fieldname, "label": field.label, "fieldtype": field.fieldtype}
		if field.reqd:
			entry["required"] = True
		if field.read_only:
			entry["read_only"] = True
		if field.fieldtype in ("Link", "Table", "Table MultiSelect") and field.options:
			entry["target" if field.fieldtype == "Link" else "row_type"] = field.options
		if field.fieldtype == "Select" and field.options:
			entry["options"] = [option for option in field.options.split("\n") if option]
		if field.fieldtype in ("Table", "Table MultiSelect"):
			entry["row_fields"] = [
				child.fieldname
				for child in frappe.get_meta(field.options).fields
				if child.fieldtype not in LAYOUT_FIELDTYPES and not guard.is_secret_field(child)
			]
		fields.append(entry)
	return {
		"doctype": doctype,
		"single": bool(meta.issingle),
		"submittable": bool(meta.is_submittable),
		"title_field": meta.title_field,
		"fields": fields,
	}


def _filters(doctype, filters, tool):
	if not filters:
		return []
	if isinstance(filters, dict):
		filters = [[field, "=", value] for field, value in filters.items()]
	if not isinstance(filters, list):
		frappe.throw(_("filters must be a list of [fieldname, operator, value]."))
	conditions = []
	for condition in filters:
		if not isinstance(condition, list | tuple) or len(condition) != 3:
			frappe.throw(_("Each filter is [fieldname, operator, value], got {0}.").format(condition))
		fieldname, operator, value = condition
		operator = str(operator).lower()
		if operator not in FILTER_OPERATORS:
			frappe.throw(_("Unknown filter operator {0}.").format(operator))
		conditions.append([fieldname, operator, value])
	guard.check_fieldnames(doctype, [condition[0] for condition in conditions], tool)
	return conditions


def _limit(value) -> int:
	cap = guard.get_settings().max_rows or 200
	try:
		limit = int(value)
	except (TypeError, ValueError):
		limit = DEFAULT_LIMIT
	return max(1, min(limit if limit > 0 else DEFAULT_LIMIT, cap))


def list_records(args) -> dict:
	doctype = args.get("doctype")
	guard.check_doctype(doctype, "read", "list_records")
	fields = args.get("fields") or ["name"]
	if not isinstance(fields, list) or not all(isinstance(field, str) for field in fields):
		frappe.throw(_("fields must be a list of fieldnames."))
	guard.check_fieldnames(doctype, fields, "list_records")
	limit = _limit(args.get("limit"))
	order_by = args.get("order_by") if args.get("order_by") in SORTABLE_FIELDS else "creation"
	order = "asc" if args.get("order") == "asc" else "desc"
	rows = frappe.get_list(
		doctype,
		fields=fields,
		filters=_filters(doctype, args.get("filters"), "list_records"),
		order_by=f"{order_by} {order}",
		limit=limit + 1,
	)
	result = {"rows": rows[:limit], "truncated": len(rows) > limit}
	if len(rows) > limit:
		result["note"] = f"more than {limit} rows match; narrow the filters or use count_records"
	return result


def get_record(args) -> dict:
	doctype, name = args.get("doctype"), str(args.get("name") or "")
	if guard.is_single(doctype):
		name = doctype
	guard.check_record(doctype, name, "read", "get_record")
	doc = frappe.get_doc(doctype, name)
	values = doc.as_dict(no_default_fields=False, no_child_table_fields=True)
	for key in ("doctype", "owner", "modified_by", "idx", "_user_tags", "_comments", "_assign", "_liked_by"):
		values.pop(key, None)
	return guard.redact(doctype, values)


def count_records(args) -> dict:
	doctype = args.get("doctype")
	guard.check_doctype(doctype, "read", "count_records")
	rows = frappe.get_list(
		doctype,
		filters=_filters(doctype, args.get("filters"), "count_records"),
		fields=[{"COUNT": "*", "as": "count"}],
	)
	return {"count": rows[0].count if rows else 0}


def _reports():
	"""The Books script reports the user may run, by name."""
	names = frappe.get_all(
		"Report",
		filters={"module": BOOKS_MODULE, "disabled": 0, "report_type": "Script Report"},
		pluck="name",
		order_by="name",
	)
	reports = {}
	for name in names:
		report = frappe.get_doc("Report", name)
		if report.is_permitted() and report.ref_doctype not in guard.blocked_doctypes():
			reports[name] = report
	return reports


def list_reports(_args) -> dict:
	items = []
	for name in _reports():
		try:
			defaults = get_default_filters(name)
		except Exception:
			defaults = {}
		items.append({"report_name": name, "filters": _json(defaults)})
	return {"reports": items}


def run_report(args) -> dict:
	report_name = args.get("report_name")
	report = _reports().get(report_name)
	if not report:
		guard.block(
			"run_report", _("No report named {0} that you may run. Call list_reports.").format(report_name)
		)
	filters = args.get("filters") or {}
	if not isinstance(filters, dict):
		frappe.throw(_("Report filters are an object of filter names and values."))
	result = run_query_report(report_name, filters=filters, ignore_prepared_report=True)
	columns = [_column(column) for column in result.get("columns") or []]
	columns = [column for column in columns if not column.get("hidden")]
	cap = guard.get_settings().max_rows or 200
	rows = [_report_row(row, columns) for row in (result.get("result") or [])]
	rows = [row for row in rows if row]
	return {
		"report": report_name,
		"filters": filters,
		"columns": [column["label"] for column in columns],
		"rows": rows[:cap],
		"truncated": len(rows) > cap,
	}


def _column(column) -> dict:
	if isinstance(column, str):
		# Frappe's short form, "Label:Fieldtype/Options:Width".
		label = column.split(":")[0]
		return {"label": label, "fieldname": frappe.scrub(label)}
	return {
		"label": column.get("label") or column.get("fieldname"),
		"fieldname": column.get("fieldname"),
		"hidden": column.get("hidden"),
	}


def _report_row(row, columns):
	if isinstance(row, dict):
		cells = [row.get(column["fieldname"]) for column in columns]
	elif isinstance(row, list | tuple):
		cells = list(row)[: len(columns)]
	else:
		return None
	return cells if any(cell not in (None, "") for cell in cells) else None


def get_dashboard_summary(args) -> dict:
	metric, period = args.get("metric"), args.get("period") or "This Month"
	if metric not in METRICS:
		frappe.throw(_("Unknown metric {0}.").format(metric))
	if period not in PERIODS:
		frappe.throw(_("Unknown period {0}.").format(period))
	if metric in ("sales_invoices", "purchase_invoices"):
		doctype = "Books Sales Invoice" if metric == "sales_invoices" else "Books Purchase Invoice"
		guard.check_doctype(doctype, "read", "get_dashboard_summary")
		return dashboard.get_invoice_summary(doctype, period)
	guard.check_doctype(dashboard.LEDGER, "read", "get_dashboard_summary")
	from_date, to_date = dashboard.get_period_dates(period)
	read = {
		"cashflow": dashboard.get_cashflow,
		"profit_and_loss": dashboard.get_profit_and_loss,
		"top_expenses": dashboard.get_top_expenses,
	}[metric]
	return {"metric": metric, "from_date": from_date, "to_date": to_date, "data": read(period)}


def open_screen(args) -> dict:
	"""Checked here and opened by the app, which owns the routes."""
	target = args.get("target")
	if target == "dashboard":
		return {"open": "dashboard"}
	if target == "report":
		report_name = args.get("report_name")
		if report_name not in _reports():
			frappe.throw(_("No report named {0} that you may open.").format(report_name))
		return {"open": "report", "report_name": report_name}
	doctype = args.get("doctype")
	if target == "list":
		guard.check_doctype(doctype, "read", "open_screen")
		return {"open": "list", "doctype": doctype}
	if target == "record":
		name = str(args.get("name") or "")
		guard.check_record(doctype, name, "read", "open_screen")
		return {"open": "record", "doctype": doctype, "name": name}
	frappe.throw(_("Unknown screen {0}.").format(target))


READERS = {
	"list_record_types": list_record_types,
	"describe_record_type": describe_record_type,
	"list_records": list_records,
	"get_record": get_record,
	"count_records": count_records,
	"list_reports": list_reports,
	"run_report": run_report,
	"get_dashboard_summary": get_dashboard_summary,
	"open_screen": open_screen,
}


# Write proposals: checked and previewed now, run on approval.


def _format(value, field) -> str:
	if value in (None, ""):
		return "—"
	if isinstance(value, list):
		return _("{0} row(s)").format(len(value))
	try:
		return str(frappe.format_value(value, field) if field else value)
	except Exception:
		return str(value)


def _value_rows(doctype, values, doc=None) -> list[dict]:
	meta = frappe.get_meta(doctype)
	rows = []
	for fieldname, value in values.items():
		field = meta.get_field(fieldname)
		after = _format(value, field)
		row = {"fieldname": fieldname, "label": _(field.label) if field else fieldname, "after": after}
		if doc is not None:
			row["before"] = _format(doc.get(fieldname), field)
			row["changed"] = row["before"] != after
		else:
			row["changed"] = True
		if isinstance(value, list):
			row["rows"] = [_child_summary(field.options, child) for child in value]
		rows.append(row)
	return rows


def _child_summary(doctype, values) -> str:
	meta = frappe.get_meta(doctype)
	return ", ".join(
		f"{_(meta.get_label(fieldname))}: {_format(value, meta.get_field(fieldname))}"
		for fieldname, value in values.items()
	)


def _record_rows(doc) -> list[dict]:
	"""Enough of a record to recognize it, for a delete, submit or cancel."""
	rows = []
	for field in doc.meta.fields:
		value = doc.get(field.fieldname)
		if (
			field.fieldtype in LAYOUT_FIELDTYPES
			or field.fieldtype in ("Table", "Table MultiSelect")
			or guard.is_secret_field(field)
			or value in (None, "", 0)
		):
			continue
		rows.append({"fieldname": field.fieldname, "label": _(field.label), "before": _format(value, field)})
		if len(rows) >= PREVIEW_FIELD_LIMIT:
			break
	return rows


def _preview(action, doctype, name, rows) -> dict:
	return {
		"action": action,
		"doctype": doctype,
		"doctype_label": _(doctype),
		"name": name,
		"destructive": action in ("delete", "cancel"),
		"rows": rows,
	}


def preview_create(args):
	doctype, values = args.get("doctype"), args.get("values") or {}
	guard.check_doctype(doctype, "create", "create_record")
	if frappe.get_meta(doctype).issingle:
		frappe.throw(_("{0} is a settings record; use update_record.").format(doctype))
	guard.check_values(doctype, values, "create_record")
	return doctype, None, _preview("create", doctype, None, _value_rows(doctype, values))


def preview_update(args):
	doctype, name, values = args.get("doctype"), str(args.get("name") or ""), args.get("values") or {}
	if guard.is_single(doctype):
		name = args["name"] = doctype
	guard.check_record(doctype, name, "write", "update_record")
	if not values:
		frappe.throw(_("No fields to change were given."))
	guard.check_values(doctype, values, "update_record")
	doc = frappe.get_doc(doctype, name)
	if doc.docstatus != 0:
		frappe.throw(_("{0} {1} is submitted or cancelled and cannot be edited.").format(doctype, name))
	return doctype, name, _preview("update", doctype, name, _value_rows(doctype, values, doc))


def _preview_record(tool, action, ptype, docstatus):
	def preview(args):
		doctype, name = args.get("doctype"), str(args.get("name") or "")
		guard.check_record(doctype, name, ptype, tool)
		doc = frappe.get_doc(doctype, name)
		if action in ("submit", "cancel") and not doc.meta.is_submittable:
			frappe.throw(_("{0} records cannot be submitted or cancelled.").format(doctype))
		if docstatus is not None and doc.docstatus != docstatus:
			state = {0: _("a draft"), 1: _("submitted"), 2: _("cancelled")}[doc.docstatus]
			frappe.throw(_("{0} {1} is {2}.").format(doctype, name, state))
		return doctype, name, _preview(action, doctype, name, _record_rows(doc))

	return preview


PREVIEWERS = {
	"create_record": preview_create,
	"update_record": preview_update,
	"submit_document": _preview_record("submit_document", "submit", "submit", 0),
	"delete_record": _preview_record("delete_record", "delete", "delete", None),
	"cancel_document": _preview_record("cancel_document", "cancel", "cancel", 1),
}


# Writes, on approval. Each checks the guard again: rights and rules may have changed meanwhile.


def create_record(args) -> dict:
	doctype, values = args["doctype"], args.get("values") or {}
	guard.check_doctype(doctype, "create", "create_record")
	guard.check_values(doctype, values, "create_record")
	doc = frappe.get_doc({**values, "doctype": doctype}).insert()
	return {"doctype": doctype, "name": doc.name}


def update_record(args) -> dict:
	doctype, name, values = args["doctype"], args["name"], args.get("values") or {}
	guard.check_record(doctype, name, "write", "update_record")
	guard.check_values(doctype, values, "update_record")
	doc = frappe.get_doc(doctype, name)
	for fieldname, value in values.items():
		if isinstance(value, list):
			# A table is replaced, so "set the items to these" means exactly these.
			doc.set(fieldname, [])
			for row in value:
				doc.append(fieldname, row)
		else:
			doc.set(fieldname, value)
	doc.save()
	return {"doctype": doctype, "name": doc.name, "updated": list(values)}


def submit_document(args) -> dict:
	guard.check_record(args["doctype"], args["name"], "submit", "submit_document")
	doc = frappe.get_doc(args["doctype"], args["name"])
	doc.submit()
	return {"doctype": doc.doctype, "name": doc.name, "submitted": True}


def cancel_document(args) -> dict:
	guard.check_record(args["doctype"], args["name"], "cancel", "cancel_document")
	doc = frappe.get_doc(args["doctype"], args["name"])
	doc.cancel()
	return {"doctype": doc.doctype, "name": doc.name, "cancelled": True}


def delete_record(args) -> dict:
	guard.check_record(args["doctype"], args["name"], "delete", "delete_record")
	frappe.delete_doc(args["doctype"], args["name"])
	return {"doctype": args["doctype"], "name": args["name"], "deleted": True}


WRITERS = {
	"create_record": create_record,
	"update_record": update_record,
	"submit_document": submit_document,
	"cancel_document": cancel_document,
	"delete_record": delete_record,
}

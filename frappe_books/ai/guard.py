"""The AI Guard: every step the assistant takes passes through here first.

The model's requests are treated as untrusted input. The guard decides whether a user may use the
assistant at all, which record types and fields it may touch, how often it may be called, and it
holds every proposed change until the person approves that exact change. Reads and writes run as
the signed-in user, so the assistant can never do more than the user could do by hand, and the
guard narrows that further with the rules in Books AI Settings.
"""

import json
import secrets

import frappe
from frappe import _

from frappe_books.permissions import BOOKS_MODULE, has_app_permission

SETTINGS = "Books AI Settings"
USER_KEYS = "Books AI User Key"
ACTION_LOG = "Books AI Action Log"
# The assistant's own records: its keys, its rules and its log stay out of its reach.
AI_DOCTYPES = frozenset((SETTINGS, USER_KEYS, ACTION_LOG, "Books AI Role", "Books AI Blocked DocType"))
# Fields the model may never set, whatever the record type.
PROTECTED_FIELDS = frozenset(
	(
		"name",
		"owner",
		"creation",
		"modified",
		"modified_by",
		"docstatus",
		"idx",
		"parent",
		"parentfield",
		"parenttype",
		"amended_from",
		"company",
	)
)
# Fields the model may read and filter on besides the DocType's own.
STANDARD_FIELDS = frozenset(("name", "creation", "modified", "owner", "docstatus"))
SECRET_FIELDTYPES = frozenset(("Password",))
# Values the form works out or shows, never ones a person types.
UNSETTABLE_FIELDTYPES = frozenset(
	("Read Only", "Section Break", "Column Break", "Tab Break", "HTML", "Button", "Heading", "Fold")
)
SECRET_WORDS = ("password", "secret", "api_key", "token")
WRITE_TOOLS = frozenset(
	("create_record", "update_record", "delete_record", "submit_document", "cancel_document")
)
DESTRUCTIVE_TOOLS = frozenset(("delete_record", "cancel_document"))
PROPOSAL_TTL_SECONDS = 15 * 60
# A transcript larger than this is refused rather than sent on to the provider.
MAX_MESSAGES = 200
MAX_TRANSCRIPT_CHARS = 400_000
MAX_QUESTION_CHARS = 4_000


class AIGuardError(frappe.PermissionError):
	"""A step the AI Guard refused. Its message is shown to the user and the model."""


def get_settings():
	return frappe.get_cached_doc(SETTINGS)


def is_admin(user: str | None = None) -> bool:
	"""Whether the user may change the company key and the guard's rules."""
	return frappe.has_permission(SETTINGS, "write", user=user)


def can_use(user: str | None = None) -> bool:
	"""Whether the assistant is on and the AI Guard lets this user in."""
	user = user or frappe.session.user
	if user == "Guest":
		return False
	settings = get_settings()
	if not settings.enabled or not has_app_permission():
		return False
	allowed = {row.role for row in settings.allowed_roles}
	return not allowed or bool(allowed & set(frappe.get_roles(user)))


def check_access() -> None:
	if not can_use():
		block("access", _("The AI assistant is not available to you."), record=False)


def check_rate_limit() -> None:
	"""Count one model request against the user's per-minute and per-day allowance."""
	settings = get_settings()
	user = frappe.session.user
	now = frappe.utils.now_datetime()
	for limit, window, seconds in (
		(settings.requests_per_minute, now.strftime("%Y%m%d%H%M"), 60),
		(settings.requests_per_day, now.strftime("%Y%m%d"), 24 * 60 * 60),
	):
		if not limit:
			continue
		key = frappe.cache.make_key(f"books_ai:requests:{user}:{window}")
		count = frappe.cache.incrby(key, 1)
		if count == 1:
			frappe.cache.expire(key, seconds)
		if count > limit:
			block("rate_limit", _("You have reached the assistant's request limit. Try again later."))


def check_transcript(messages) -> None:
	"""Refuse a malformed or oversized transcript before it reaches the provider."""
	if not isinstance(messages, list) or not messages:
		block("transcript", _("The conversation is empty."), record=False)
	if len(messages) > MAX_MESSAGES or len(json.dumps(messages, default=str)) > MAX_TRANSCRIPT_CHARS:
		block("transcript", _("This conversation is too long. Start a new one."), record=False)
	for message in messages:
		role = message.get("role") if isinstance(message, dict) else None
		if role not in ("user", "assistant", "tool"):
			block("transcript", _("The conversation has a message the assistant cannot read."), record=False)
		if role == "user" and len(str(message.get("text") or "")) > MAX_QUESTION_CHARS:
			block("transcript", _("That question is too long."), record=False)


def check_doctype(doctype: str, ptype: str = "read", tool: str | None = None) -> None:
	"""Allow a Books record type the user holds `ptype` on and the guard does not hide."""
	if not isinstance(doctype, str) or not doctype or not frappe.db.exists("DocType", doctype):
		frappe.throw(_("No record type named {0}. Call list_record_types.").format(doctype))
	meta = frappe.get_meta(doctype)
	if meta.module != BOOKS_MODULE or doctype in AI_DOCTYPES or meta.istable:
		block(tool, _("The assistant cannot use {0} records.").format(doctype), doctype)
	if doctype in blocked_doctypes():
		block(tool, _("{0} records are hidden from the assistant.").format(doctype), doctype)
	if not frappe.has_permission(doctype, ptype):
		block(tool, _("You do not have the right to {0} {1} records.").format(_(ptype), doctype), doctype)


def is_single(doctype) -> bool:
	return isinstance(doctype, str) and bool(frappe.db.get_value("DocType", doctype, "issingle"))


def check_record(doctype: str, name: str, ptype: str, tool: str | None = None) -> None:
	check_doctype(doctype, ptype, tool)
	if is_single(doctype):
		return
	if not name or not frappe.db.exists(doctype, name):
		frappe.throw(_("{0} {1} does not exist.").format(doctype, name))
	if not frappe.has_permission(doctype, ptype, doc=name):
		block(
			tool,
			_("You do not have the right to {0} {1} {2}.").format(_(ptype), doctype, name),
			doctype,
			name,
		)


def check_write(tool: str) -> None:
	settings = get_settings()
	if not settings.allow_writes:
		block(tool, _("The assistant may only read the books here; it cannot propose changes."))
	if tool in DESTRUCTIVE_TOOLS and not settings.allow_destructive:
		block(tool, _("The assistant may not propose deletes or cancellations here."))


def blocked_doctypes() -> set[str]:
	return {row.document_type for row in get_settings().blocked_doctypes}


def is_secret_field(field) -> bool:
	name = field.fieldname.lower()
	return field.fieldtype in SECRET_FIELDTYPES or any(word in name for word in SECRET_WORDS)


def readable_fields(doctype: str) -> set[str]:
	"""The fields of a record type the model may read and filter on."""
	meta = frappe.get_meta(doctype)
	own = {
		field.fieldname for field in meta.fields if not is_secret_field(field) and field.fieldtype != "Table"
	}
	return own | STANDARD_FIELDS


def check_fieldnames(doctype: str, fieldnames, tool: str | None = None) -> None:
	unknown = sorted(set(fieldnames) - readable_fields(doctype))
	if unknown:
		block(
			tool,
			_("{0} has no readable fields named {1}. Call describe_record_type.").format(
				doctype, ", ".join(unknown)
			),
			doctype,
			record=False,
		)


def is_settable(field) -> bool:
	"""Whether a person could type this field's value in on the form."""
	return not (
		field.fieldname in PROTECTED_FIELDS
		or is_secret_field(field)
		or field.read_only
		or field.fieldtype in UNSETTABLE_FIELDTYPES
		or (field.fetch_from and not field.fetch_if_empty)
	)


def check_values(doctype: str, values, tool: str) -> None:
	"""Allow only the fields a person could fill in on the form, and child rows of the same kind."""
	if not isinstance(values, dict):
		frappe.throw(_("values must be an object of fieldnames and values."))
	meta = frappe.get_meta(doctype)
	for fieldname, value in values.items():
		field = meta.get_field(fieldname)
		if not field or not is_settable(field):
			block(tool, _("The assistant may not set {0} on {1}.").format(fieldname, doctype), doctype)
		if field.fieldtype in ("Table", "Table MultiSelect"):
			if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
				frappe.throw(_("{0} takes a list of rows.").format(fieldname))
			for row in value:
				check_child_values(field.options, row, tool)


def check_child_values(doctype: str, values: dict, tool: str) -> None:
	meta = frappe.get_meta(doctype)
	for fieldname in values:
		field = meta.get_field(fieldname)
		if not field or not is_settable(field):
			block(tool, _("The assistant may not set {0} on {1} rows.").format(fieldname, doctype), doctype)


def redact(doctype: str, values: dict) -> dict:
	"""Leave out secrets, recursing into child rows."""
	meta = frappe.get_meta(doctype)
	out = {}
	for key, value in values.items():
		field = meta.get_field(key)
		if field and is_secret_field(field):
			continue
		if field and field.fieldtype in ("Table", "Table MultiSelect") and isinstance(value, list):
			value = [redact(field.options, dict(row)) for row in value]
		out[key] = value
	return out


def hold_proposal(tool: str, args: dict, doctype: str | None, name: str | None) -> str:
	"""Keep a proposed change until the person decides; only that exact change can then run."""
	token = secrets.token_urlsafe(24)
	proposal = {"user": frappe.session.user, "tool": tool, "args": args, "doctype": doctype, "name": name}
	frappe.cache.set_value(_proposal_key(token), proposal, expires_in_sec=PROPOSAL_TTL_SECONDS)
	log("Proposed", tool, doctype, name, payload=args)
	return token


def take_proposal(token: str) -> dict:
	"""The held change for this token, once: a second approval of the same change finds nothing."""
	key = _proposal_key(token)
	proposal = frappe.cache.get_value(key)
	frappe.cache.delete_value(key)
	if not proposal or proposal.get("user") != frappe.session.user:
		block("confirm_action", _("This change has expired or was already decided. Ask again."), record=False)
	return proposal


def _proposal_key(token) -> str:
	if not isinstance(token, str) or not token:
		block("confirm_action", _("This change has expired or was already decided. Ask again."), record=False)
	return f"books_ai:proposal:{token}"


def block(tool, reason, doctype=None, name=None, record=True):
	"""Refuse a step, and record the refusal unless it is a plain input mistake."""
	error = AIGuardError(reason)
	if record:
		error.log_entry = ("Blocked", tool, doctype, name, reason)
		log(*error.log_entry)
	raise error


def relog(error) -> None:
	"""Record a refusal again after a rollback took its log row with the step it refused."""
	if entry := getattr(error, "log_entry", None):
		log(*entry)


def log(event, tool, doctype=None, name=None, reason=None, payload=None) -> None:
	"""Record what the assistant did, best effort: a lost log row never fails the step it describes."""
	try:
		frappe.get_doc(
			{
				"doctype": ACTION_LOG,
				"user": frappe.session.user,
				"event": event,
				"tool": (tool or "")[:140],
				"reference_doctype": doctype if doctype and frappe.db.exists("DocType", doctype) else None,
				"reference_name": name,
				"reason": reason,
				"payload": json.dumps(payload, default=str, indent=1) if payload is not None else None,
			}
		).insert(ignore_permissions=True, ignore_links=True)
	except Exception:
		frappe.log_error("Books AI action log")

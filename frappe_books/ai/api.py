"""The assistant's endpoints. Each passes the AI Guard before it does anything else."""

import frappe
from frappe import _
from frappe.utils import nowdate

from frappe_books.ai import guard, tools
from frappe_books.ai.prompt import get_system_prompt
from frappe_books.ai.providers import ProviderError, get_provider, list_providers
from frappe_books.company import default_company
from frappe_books.settings import regional_code

MAX_TOKENS = 16000
# Settings an administrator may change from the Books app; the rest are in the Desk form.
ADMIN_SETTINGS = ("enabled", "allow_writes", "allow_destructive", "allow_personal_keys")


@frappe.whitelist()
def get_status() -> dict:
	"""What the app needs to show the assistant and its settings. Never carries a key."""
	settings = guard.get_settings()
	is_admin = guard.is_admin()
	user_key = _user_key_row()
	return {
		"enabled": bool(settings.enabled),
		"can_use": guard.can_use(),
		"is_admin": is_admin,
		"allow_writes": bool(settings.allow_writes),
		"allow_destructive": bool(settings.allow_destructive),
		"allow_personal_keys": bool(settings.allow_personal_keys),
		"providers": list_providers(),
		"company_key": _summary(settings.provider, settings.model, settings.get_password("api_key", False)),
		"user_key": user_key
		and _summary(user_key.provider, user_key.model, user_key.get_password("api_key", False)),
	}


@frappe.whitelist(methods=["POST"])
def save_key(scope: str, provider: str, api_key: str, model: str | None = None) -> dict:
	get_provider(provider)
	if not (api_key or "").strip():
		frappe.throw(_("An API key is required."))
	if scope == "company":
		_check_admin()
		settings = frappe.get_doc(guard.SETTINGS)
		settings.update({"provider": provider, "model": (model or "").strip(), "api_key": api_key.strip()})
		settings.save()
	elif scope == "user":
		if not guard.get_settings().allow_personal_keys:
			frappe.throw(_("Personal API keys are turned off for this company."))
		doc = _user_key_row() or frappe.new_doc(guard.USER_KEYS)
		doc.update({"user": frappe.session.user, "provider": provider, "model": (model or "").strip()})
		doc.api_key = api_key.strip()
		doc.save(ignore_permissions=True)
	else:
		frappe.throw(_("Unknown key scope {0}.").format(scope))
	return get_status()


@frappe.whitelist(methods=["POST"])
def remove_key(scope: str) -> dict:
	if scope == "company":
		_check_admin()
		settings = frappe.get_doc(guard.SETTINGS)
		settings.api_key = None
		settings.save()
	elif scope == "user" and (row := _user_key_row()):
		frappe.delete_doc(guard.USER_KEYS, row.name, ignore_permissions=True)
	return get_status()


@frappe.whitelist(methods=["POST"])
def save_settings(values: dict) -> dict:
	"""Turn the assistant and the guard's main switches on or off."""
	_check_admin()
	settings = frappe.get_doc(guard.SETTINGS)
	settings.update({key: 1 if values[key] else 0 for key in ADMIN_SETTINGS if key in values})
	settings.save()
	return get_status()


@frappe.whitelist(methods=["POST"])
def test_connection() -> dict:
	"""One cheap round trip, so a mistyped key fails here rather than in someone's first question."""
	guard.check_access()
	provider, model, api_key = _credential()
	try:
		provider.chat(
			api_key=api_key,
			model=model,
			system="Reply with the single word OK.",
			messages=[{"role": "user", "text": "Are you there?"}],
			tools=[],
			max_tokens=32,
		)
	except ProviderError as error:
		return {"ok": False, "provider": provider.name, "model": model, "message": str(error)}
	return {"ok": True, "provider": provider.name, "model": model}


@frappe.whitelist(methods=["POST"])
def chat(messages: list, context: dict | None = None) -> dict:
	"""Send the conversation to the provider and return its next turn.

	The browser keeps the transcript; the server keeps nothing between requests but the guard's
	counters and held proposals.
	"""
	guard.check_access()
	guard.check_transcript(messages)
	settings = guard.get_settings()
	if _rounds_since_question(messages) >= (settings.max_tool_rounds or 8):
		guard.log("Blocked", "chat", reason="lookup limit reached")
		return {
			"text": "",
			"tool_calls": [],
			"finish_reason": "limit",
			"usage": {},
		}
	try:
		guard.check_rate_limit()
	except guard.AIGuardError as error:
		# Answered, not raised, so the request commits and the refusal stays in the log.
		return {"text": "", "tool_calls": [], "finish_reason": "rate_limit", "error": str(error), "usage": {}}
	provider, model, api_key = _credential()
	specs = tools.get_tool_specs()
	writes = any(spec["name"] in guard.WRITE_TOOLS for spec in specs)
	destructive = any(spec["name"] in guard.DESTRUCTIVE_TOOLS for spec in specs)
	system = get_system_prompt(_prompt_context(context or {}), writes, destructive)
	try:
		return provider.chat(
			api_key=api_key,
			model=model,
			system=system,
			messages=messages,
			tools=specs,
			max_tokens=MAX_TOKENS,
		)
	except ProviderError as error:
		# The provider's own words: "invalid x-api-key" is the whole answer to why it will not start.
		frappe.throw(str(error), title=_("The AI provider refused the request"))


@frappe.whitelist(methods=["POST"])
def run_tool(name: str, args: dict | None = None) -> dict:
	"""Run a tool call the model made: a read runs now, a change comes back as a proposal."""
	guard.check_access()
	return tools.run_tool(name, args or {})


@frappe.whitelist(methods=["POST"])
def confirm_action(token: str) -> dict:
	guard.check_access()
	return tools.confirm_action(token)


@frappe.whitelist(methods=["POST"])
def decline_action(token: str, reason: str | None = None) -> dict:
	guard.check_access()
	return tools.decline_action(token, reason)


def _check_admin():
	if not guard.is_admin():
		raise frappe.PermissionError(_("Only a Books Manager can change the assistant's settings."))


def _user_key_row():
	name = frappe.db.get_value(guard.USER_KEYS, {"user": frappe.session.user})
	return name and frappe.get_doc(guard.USER_KEYS, name)


def _summary(provider, model, api_key) -> dict | None:
	if not api_key:
		return None
	return {"provider": provider, "model": model or None, "hint": api_key[-4:] if len(api_key) > 8 else ""}


def _credential():
	"""The user's own key when personal keys are on and they set one, else the company key."""
	settings = guard.get_settings()
	row = _user_key_row() if settings.allow_personal_keys else None
	for source in (row, settings):
		if source and (api_key := source.get_password("api_key", False)):
			provider = get_provider(source.provider)
			return provider, source.model or provider.default_model, api_key
	frappe.throw(_("No AI provider key is set. Add one in the assistant's settings."))


def _rounds_since_question(messages) -> int:
	rounds = 0
	for message in reversed(messages):
		if message.get("role") == "user":
			break
		rounds += message.get("role") == "tool"
	return rounds


def _prompt_context(context: dict) -> dict:
	user = frappe.session.user
	return {
		"company_name": default_company() or _("this company"),
		"country_code": regional_code() or "",
		"currency": frappe.db.get_single_value("Books System Settings", "currency") or "",
		# The user's own date, so "this month" means what it means where they sit.
		"today": str(context.get("today") or nowdate())[:10],
		"user_name": frappe.utils.get_fullname(user) or user,
	}

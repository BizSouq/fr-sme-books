from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from frappe_books.ai import api, guard, tools
from frappe_books.ai.providers import Anthropic, Gemini, OpenAI, ProviderError
from frappe_books.tests.accounting import ensure_user, make_account, make_customer, unique_name

MANAGER = "books-ai-manager@example.com"
USER = "books-ai-user@example.com"
CASHIER = "books-ai-cashier@example.com"
TOOL = {"name": "list_records", "description": "Rows.", "parameters": {"type": "object", "properties": {}}}


def ai_settings(**values):
	defaults = {
		"enabled": 1,
		"allow_writes": 1,
		"allow_destructive": 0,
		"allow_personal_keys": 1,
		"requests_per_minute": 0,
		"requests_per_day": 0,
		"max_tool_rounds": 8,
		"max_rows": 200,
		"allowed_roles": [],
		"blocked_doctypes": [],
	}
	settings = frappe.get_doc(guard.SETTINGS)
	settings.update({**defaults, **values})
	settings.save(ignore_permissions=True)


class IntegrationTestAIProviders(IntegrationTestCase):
	def test_anthropic_replays_its_own_turns_verbatim(self):
		raw = [{"type": "thinking", "thinking": "", "signature": "x"}, {"type": "tool_use", "id": "t1"}]
		messages = [
			{"role": "user", "text": "Unpaid invoices?"},
			{
				"role": "assistant",
				"text": "",
				"tool_calls": [],
				"raw": {"provider": "anthropic", "content": raw},
			},
			{"role": "tool", "results": [{"id": "t1", "name": "list_records", "content": {"rows": []}}]},
		]
		body = Anthropic.build_body("claude-opus-5-5", "system", messages, [TOOL], 100)
		self.assertEqual(body["messages"][1], {"role": "assistant", "content": raw})
		self.assertEqual(body["messages"][2]["content"][0]["content"], '{"rows": []}')
		self.assertEqual(body["tools"][0]["input_schema"], TOOL["parameters"])

		turn = Anthropic.parse_turn(
			{
				"content": [{"type": "tool_use", "id": "t2", "name": "count_records", "input": {}}],
				"stop_reason": "tool_use",
			}
		)
		self.assertEqual(turn["tool_calls"], [{"id": "t2", "name": "count_records", "args": {}}])
		self.assertEqual(turn["finish_reason"], "tool_calls")

	def test_openai_retries_with_the_older_token_field(self):
		calls = []

		def post(provider, url, headers, body):
			calls.append(body)
			if "max_completion_tokens" in body:
				raise ProviderError("openai", 400, "Unsupported parameter: max_completion_tokens")
			return {"choices": [{"message": {"content": "Hi"}, "finish_reason": "stop"}]}

		with patch("frappe_books.ai.providers.post_json", post):
			turn = OpenAI.chat("key", "gpt-4o", "system", [{"role": "user", "text": "Hi"}], [], 10)
		self.assertEqual(turn["text"], "Hi")
		self.assertIn("max_tokens", calls[1])

	def test_gemini_mints_call_ids_and_keeps_only_its_schema_keywords(self):
		schema = {
			"type": "object",
			"properties": {"x": {"type": "string", "pattern": "a+"}},
			"additionalProperties": False,
		}
		self.assertEqual(
			Gemini.to_schema(schema), {"type": "OBJECT", "properties": {"x": {"type": "STRING"}}}
		)
		turn = Gemini.parse_turn(
			{"candidates": [{"content": {"parts": [{"functionCall": {"name": "list_reports"}}]}}]}
		)
		self.assertEqual(turn["tool_calls"], [{"id": "list_reports-0", "name": "list_reports", "args": {}}])


class IntegrationTestAIGuard(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_user(MANAGER, "Books Manager")
		ensure_user(USER, "Books User")
		ensure_user(CASHIER, "Books Cashier")

	def setUp(self):
		ai_settings()
		self.account = make_account("AI Receivable", account_type="Receivable").name

	def test_the_assistant_is_off_until_enabled_and_for_roles_left_out(self):
		ai_settings(enabled=0)
		with self.set_user(USER):
			self.assertFalse(guard.can_use())
			self.assertRaises(guard.AIGuardError, api.run_tool, "list_record_types")

		ai_settings(allowed_roles=[{"role": "Books Manager"}])
		with self.set_user(USER):
			self.assertFalse(guard.can_use())
		with self.set_user(MANAGER):
			self.assertTrue(guard.can_use())

	def test_reads_are_limited_to_the_users_rights_and_books_records(self):
		with self.set_user(CASHIER):
			types = {row["doctype"] for row in api.run_tool("list_record_types")["content"]["record_types"]}
			self.assertIn("Books Sales Invoice", types)
			self.assertNotIn("Books Journal Entry", types)
			self.assertNotIn(guard.SETTINGS, types)
			refused = api.run_tool("list_records", {"doctype": "Books Journal Entry"})
		self.assertEqual(refused["status"], "failed")

		with self.set_user(MANAGER):
			for doctype in ("User", guard.USER_KEYS, guard.SETTINGS, "Books Sales Invoice Item"):
				self.assertEqual(api.run_tool("list_records", {"doctype": doctype})["status"], "failed")

	def test_hidden_record_types_and_secret_fields_stay_out_of_reach(self):
		ai_settings(blocked_doctypes=[{"document_type": "Books Customer"}])
		with self.set_user(MANAGER):
			result = api.run_tool("list_records", {"doctype": "Books Customer"})
		self.assertEqual(result["status"], "failed")
		self.assertTrue(
			frappe.db.exists(guard.ACTION_LOG, {"event": "Blocked", "reference_doctype": "Books Customer"})
		)

		with patch.object(guard, "is_secret_field", lambda field: field.fieldname == "email"):
			with self.set_user(MANAGER):
				result = api.run_tool("list_records", {"doctype": "Books Supplier", "fields": ["email"]})
		self.assertEqual(result["status"], "failed")

	def test_lists_respect_filters_fields_and_the_row_cap(self):
		ai_settings(max_rows=2)
		customers = [make_customer(self.account).name for _ in range(3)]
		with self.set_user(MANAGER):
			result = api.run_tool(
				"list_records",
				{
					"doctype": "Books Customer",
					"fields": ["name"],
					"filters": [["name", "in", customers]],
					"limit": 50,
				},
			)
			count = api.run_tool(
				"count_records", {"doctype": "Books Customer", "filters": [["name", "in", customers]]}
			)
			unknown = api.run_tool("list_records", {"doctype": "Books Customer", "fields": ["no_such_field"]})
		self.assertEqual(len(result["content"]["rows"]), 2)
		self.assertTrue(result["content"]["truncated"])
		self.assertEqual(count["content"], {"count": 3})
		self.assertEqual(unknown["status"], "failed")

	def test_a_change_waits_for_approval_and_runs_once(self):
		name = unique_name("AI Customer")
		args = {"doctype": "Books Customer", "values": {"customer_name": name}}
		with self.set_user(MANAGER):
			proposal = api.run_tool("create_record", args)
			self.assertEqual(proposal["status"], "proposed")
			self.assertEqual(proposal["preview"]["action"], "create")
			self.assertFalse(frappe.db.exists("Books Customer", {"customer_name": name}))

			done = api.confirm_action(proposal["token"])
			self.assertEqual(done["status"], "done")
			self.assertTrue(frappe.db.exists("Books Customer", {"customer_name": name}))
			self.assertRaises(guard.AIGuardError, api.confirm_action, proposal["token"])

	def test_only_the_proposing_user_can_approve_and_a_decline_is_logged(self):
		with self.set_user(MANAGER):
			proposal = api.run_tool(
				"create_record", {"doctype": "Books Customer", "values": {"customer_name": unique_name("AI")}}
			)
		with self.set_user(USER):
			self.assertRaises(guard.AIGuardError, api.confirm_action, proposal["token"])

		with self.set_user(MANAGER):
			second = api.run_tool(
				"create_record", {"doctype": "Books Customer", "values": {"customer_name": unique_name("AI")}}
			)
			self.assertEqual(api.decline_action(second["token"], "not now"), {"status": "cancelled"})
		self.assertTrue(frappe.db.exists(guard.ACTION_LOG, {"event": "Declined", "user": MANAGER}))

	def test_protected_fields_and_switched_off_changes_are_refused(self):
		customer = make_customer(self.account).name
		with self.set_user(MANAGER):
			owner = api.run_tool(
				"update_record", {"doctype": "Books Customer", "name": customer, "values": {"owner": USER}}
			)
			delete = api.run_tool("delete_record", {"doctype": "Books Customer", "name": customer})
		self.assertEqual(owner["status"], "failed")
		self.assertEqual(delete["status"], "failed")
		self.assertNotIn("delete_record", {spec["name"] for spec in tools.get_tool_specs()})

		ai_settings(allow_writes=0)
		self.assertEqual({spec["name"] for spec in tools.get_tool_specs()}, set(tools.READERS))

	def test_an_update_previews_before_and_after(self):
		customer = make_customer(self.account, tax_id="OLD-1").name
		with self.set_user(MANAGER):
			proposal = api.run_tool(
				"update_record",
				{"doctype": "Books Customer", "name": customer, "values": {"tax_id": "NEW-2"}},
			)
			[row] = proposal["preview"]["rows"]
			self.assertEqual((row["before"], row["after"], row["changed"]), ("OLD-1", "NEW-2", True))
			api.confirm_action(proposal["token"])
			# A field the form shows but works out itself is not the model's to set.
			shown = api.run_tool(
				"update_record",
				{"doctype": "Books Customer", "name": customer, "values": {"email_id": "a@b.c"}},
			)
		self.assertEqual(frappe.db.get_value("Books Customer", customer, "tax_id"), "NEW-2")
		self.assertEqual(shown["status"], "failed")

	def test_the_request_limit_and_lookup_limit_stop_the_model(self):
		ai_settings(requests_per_minute=1, max_tool_rounds=1)
		frappe.cache.delete_keys("books_ai:requests:*")
		turn = {"text": "Hi", "tool_calls": [], "finish_reason": "end"}
		with (
			self.set_user(MANAGER),
			patch.object(api, "_credential", lambda: (Anthropic, "claude-opus-5-5", "key")),
			patch.object(Anthropic, "chat", lambda **kwargs: turn),
		):
			question = [{"role": "user", "text": "Hi"}]
			self.assertEqual(api.chat(question), turn)
			self.assertEqual(api.chat(question)["finish_reason"], "rate_limit")
			looked_up = [*question, {"role": "assistant", "tool_calls": []}, {"role": "tool", "results": []}]
			self.assertEqual(api.chat(looked_up)["finish_reason"], "limit")
		self.assertTrue(frappe.db.exists(guard.ACTION_LOG, {"event": "Blocked", "tool": "rate_limit"}))

	def test_keys_never_reach_the_browser(self):
		with self.set_user(MANAGER):
			status = api.save_key("company", "anthropic", "sk-ant-secret-1234", "claude-opus-5-5")
			self.assertEqual(status["company_key"]["hint"], "1234")
			self.assertNotIn("sk-ant-secret", frappe.as_json(status))
		with self.set_user(USER):
			self.assertRaises(frappe.PermissionError, api.save_key, "company", "openai", "x" * 20)
			status = api.save_key("user", "openai", "sk-user-key-9876")
			self.assertEqual(status["user_key"], {"provider": "openai", "model": None, "hint": "9876"})
			self.assertEqual(api._credential()[2], "sk-user-key-9876")
			api.remove_key("user")
			self.assertEqual(api._credential()[2], "sk-ant-secret-1234")

	def test_reports_records_and_dashboard_figures_read_as_json(self):
		customer = make_customer(self.account).name
		with self.set_user(MANAGER):
			reports = api.run_tool("list_reports")["content"]["reports"]
			self.assertIn("Books Trial Balance", {report["report_name"] for report in reports})
			report = api.run_tool("run_report", {"report_name": "Books Trial Balance"})
			record = api.run_tool("get_record", {"doctype": "Books Customer", "name": customer})
			summary = api.run_tool("get_dashboard_summary", {"metric": "cashflow", "period": "This Month"})
			screen = api.run_tool(
				"open_screen", {"target": "record", "doctype": "Books Customer", "name": customer}
			)
		self.assertEqual(report["status"], "done", report)
		self.assertTrue(report["content"]["columns"])
		self.assertEqual(record["content"]["accounts"][0]["account"], self.account)
		self.assertEqual(summary["status"], "done", summary)
		self.assertEqual(screen["content"], {"open": "record", "doctype": "Books Customer", "name": customer})
		with self.set_user(CASHIER):
			self.assertEqual(
				api.run_tool("run_report", {"report_name": "Books Trial Balance"})["status"], "failed"
			)

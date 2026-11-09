"""The three model providers, behind one shape.

Messages and turns are plain dicts in a provider-neutral form:

- a user message is `{"role": "user", "text": ...}`;
- an assistant message is `{"role": "assistant", "text", "tool_calls", "raw"}`;
- a tool message is `{"role": "tool", "results": [{"id", "name", "content", "is_error"}]}`.

`raw` keeps the provider's own content of an assistant turn, so the turn is replayed byte for byte.
Anthropic's models put thinking blocks there and reject a follow-up that drops them.
"""

import json

import requests

TIMEOUT_SECONDS = 120


class ProviderError(Exception):
	"""A failure the person setting up the assistant can act on, in the provider's own words."""

	def __init__(self, provider: str, status: int, message: str):
		super().__init__(message)
		self.provider = provider
		self.status = status


def post_json(provider: str, url: str, headers: dict, body: dict) -> dict:
	try:
		response = requests.post(
			url,
			headers={"content-type": "application/json", **headers},
			data=json.dumps(body, default=str),
			timeout=TIMEOUT_SECONDS,
		)
	except requests.RequestException as error:
		raise ProviderError(provider, 502, f"could not reach {provider}: {error}") from error

	if not response.ok:
		message = _error_message(response.text) or f"{provider} rejected the request ({response.status_code})"
		raise ProviderError(provider, response.status_code, message)

	try:
		return response.json()
	except ValueError as error:
		raise ProviderError(provider, 502, f"{provider} returned a response that was not JSON") from error


def _error_message(body: str) -> str:
	"""The human-readable reason, which each provider wraps differently."""
	try:
		parsed = json.loads(body)
	except ValueError:
		return body[:300]
	if not isinstance(parsed, dict):
		return ""
	error = parsed.get("error")
	if isinstance(error, dict) and isinstance(error.get("message"), str):
		return error["message"]
	return parsed.get("message") if isinstance(parsed.get("message"), str) else ""


def _stringify(content) -> str:
	return content if isinstance(content, str) else json.dumps(content, default=str)


class Anthropic:
	name = "anthropic"
	label = "Claude (Anthropic)"
	default_model = "claude-opus-5-5"
	models = ("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5")
	endpoint = "https://api.anthropic.com/v1/messages"

	@classmethod
	def build_body(cls, model, system, messages, tools, max_tokens) -> dict:
		body = {
			"model": model,
			"max_tokens": max_tokens,
			"system": system,
			"messages": cls._messages(messages),
		}
		if tools:
			body["tools"] = [
				{"name": tool["name"], "description": tool["description"], "input_schema": tool["parameters"]}
				for tool in tools
			]
		return body

	@staticmethod
	def _messages(messages):
		out = []
		for message in messages:
			if message["role"] == "user":
				out.append({"role": "user", "content": message["text"]})
			elif message["role"] == "tool":
				out.append(
					{
						"role": "user",
						"content": [
							{
								"type": "tool_result",
								"tool_use_id": result["id"],
								"content": _stringify(result.get("content")),
								**({"is_error": True} if result.get("is_error") else {}),
							}
							for result in message["results"]
						],
					}
				)
			elif (message.get("raw") or {}).get("provider") == "anthropic":
				out.append({"role": "assistant", "content": message["raw"]["content"]})
			else:
				content = [{"type": "text", "text": message["text"]}] if message.get("text") else []
				content += [
					{
						"type": "tool_use",
						"id": call["id"],
						"name": call["name"],
						"input": call.get("args") or {},
					}
					for call in message.get("tool_calls") or []
				]
				if content:
					out.append({"role": "assistant", "content": content})
		return out

	@staticmethod
	def parse_turn(response: dict) -> dict:
		blocks = response.get("content") or []
		finish = {"tool_use": "tool_calls", "max_tokens": "length", "refusal": "refusal"}
		usage = response.get("usage") or {}
		return {
			"text": "".join(block.get("text", "") for block in blocks if block.get("type") == "text"),
			"tool_calls": [
				{"id": block["id"], "name": block["name"], "args": block.get("input") or {}}
				for block in blocks
				if block.get("type") == "tool_use"
			],
			"raw": {"provider": "anthropic", "content": blocks},
			"finish_reason": finish.get(response.get("stop_reason"), "end"),
			"usage": {"input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens")},
		}

	@classmethod
	def chat(cls, api_key, model, system, messages, tools, max_tokens) -> dict:
		response = post_json(
			cls.name,
			cls.endpoint,
			{"x-api-key": api_key, "anthropic-version": "2023-06-01"},
			cls.build_body(model, system, messages, tools, max_tokens),
		)
		return cls.parse_turn(response)


class OpenAI:
	name = "openai"
	label = "ChatGPT (OpenAI)"
	default_model = "gpt-4o"
	models = ("gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini")
	endpoint = "https://api.openai.com/v1/chat/completions"

	@classmethod
	def build_body(cls, model, system, messages, tools, max_tokens, token_field="max_completion_tokens"):
		body = {"model": model, token_field: max_tokens, "messages": cls._messages(system, messages)}
		if tools:
			body["tools"] = [
				{
					"type": "function",
					"function": {
						"name": tool["name"],
						"description": tool["description"],
						"parameters": tool["parameters"],
					},
				}
				for tool in tools
			]
		return body

	@staticmethod
	def _messages(system, messages):
		out = [{"role": "system", "content": system}]
		for message in messages:
			if message["role"] == "user":
				out.append({"role": "user", "content": message["text"]})
			elif message["role"] == "tool":
				out += [
					{
						"role": "tool",
						"tool_call_id": result["id"],
						"content": _stringify(result.get("content")),
					}
					for result in message["results"]
				]
			elif (message.get("raw") or {}).get("provider") == "openai":
				out.append({"role": "assistant", **message["raw"]["content"]})
			else:
				entry = {"role": "assistant", "content": message.get("text") or None}
				if message.get("tool_calls"):
					entry["tool_calls"] = [
						{
							"id": call["id"],
							"type": "function",
							"function": {
								"name": call["name"],
								"arguments": json.dumps(call.get("args") or {}),
							},
						}
						for call in message["tool_calls"]
					]
				out.append(entry)
		return out

	@staticmethod
	def _args(raw: str) -> dict:
		try:
			parsed = json.loads(raw or "{}")
		except ValueError:
			return {}
		return parsed if isinstance(parsed, dict) else {}

	@classmethod
	def parse_turn(cls, response: dict) -> dict:
		choice = (response.get("choices") or [{}])[0]
		message = choice.get("message") or {}
		finish = {"tool_calls": "tool_calls", "function_call": "tool_calls", "length": "length"}
		finish["content_filter"] = "refusal"
		usage = response.get("usage") or {}
		return {
			"text": message.get("content") or "",
			"tool_calls": [
				{
					"id": call["id"],
					"name": call["function"]["name"],
					"args": cls._args(call["function"].get("arguments")),
				}
				for call in message.get("tool_calls") or []
			],
			"raw": {"provider": "openai", "content": message},
			"finish_reason": finish.get(choice.get("finish_reason"), "end"),
			"usage": {
				"input_tokens": usage.get("prompt_tokens"),
				"output_tokens": usage.get("completion_tokens"),
			},
		}

	@classmethod
	def chat(cls, api_key, model, system, messages, tools, max_tokens) -> dict:
		def send(token_field):
			body = cls.build_body(model, system, messages, tools, max_tokens, token_field)
			return post_json(cls.name, cls.endpoint, {"authorization": f"Bearer {api_key}"}, body)

		# Newer models want `max_completion_tokens`; older ones only know `max_tokens`.
		try:
			response = send("max_completion_tokens")
		except ProviderError as error:
			if error.status != 400 or "max_completion_tokens" not in str(error):
				raise
			response = send("max_tokens")
		return cls.parse_turn(response)


# Gemini accepts an OpenAPI subset of JSON Schema and rejects other keywords.
GEMINI_SCHEMA_KEYS = (
	"type",
	"format",
	"description",
	"nullable",
	"enum",
	"items",
	"properties",
	"required",
	"minItems",
	"maxItems",
)


class Gemini:
	name = "gemini"
	label = "Gemini (Google)"
	default_model = "gemini-2.5-flash"
	models = ("gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash")
	base_url = "https://generativelanguage.googleapis.com/v1beta/models"

	@classmethod
	def to_schema(cls, schema: dict) -> dict:
		out = {}
		for key in GEMINI_SCHEMA_KEYS:
			if key not in schema:
				continue
			value = schema[key]
			if key == "type" and isinstance(value, str):
				out["type"] = value.upper()
			elif key == "items" and isinstance(value, dict):
				out["items"] = cls.to_schema(value)
			elif key == "properties" and isinstance(value, dict):
				out["properties"] = {name: cls.to_schema(child) for name, child in value.items()}
			else:
				out[key] = value
		return out

	@classmethod
	def build_body(cls, model, system, messages, tools, max_tokens) -> dict:
		body = {
			"systemInstruction": {"parts": [{"text": system}]},
			"contents": cls._contents(messages),
			"generationConfig": {"maxOutputTokens": max_tokens},
		}
		if tools:
			declarations = []
			for tool in tools:
				declaration = {"name": tool["name"], "description": tool["description"]}
				parameters = cls.to_schema(tool["parameters"])
				# A declaration with an empty property bag is rejected.
				if parameters.get("properties"):
					declaration["parameters"] = parameters
				declarations.append(declaration)
			body["tools"] = [{"functionDeclarations": declarations}]
		return body

	@staticmethod
	def _contents(messages):
		out = []
		for message in messages:
			if message["role"] == "user":
				out.append({"role": "user", "parts": [{"text": message["text"]}]})
			elif message["role"] == "tool":
				out.append(
					{
						"role": "user",
						"parts": [
							{
								"functionResponse": {
									"name": result["name"],
									"response": {
										"error" if result.get("is_error") else "result": result.get("content")
									},
								}
							}
							for result in message["results"]
						],
					}
				)
			elif (message.get("raw") or {}).get("provider") == "gemini":
				out.append({"role": "model", "parts": message["raw"]["content"]})
			else:
				parts = [{"text": message["text"]}] if message.get("text") else []
				parts += [
					{"functionCall": {"name": call["name"], "args": call.get("args") or {}}}
					for call in message.get("tool_calls") or []
				]
				if parts:
					out.append({"role": "model", "parts": parts})
		return out

	@staticmethod
	def parse_turn(response: dict) -> dict:
		candidate = (response.get("candidates") or [{}])[0]
		parts = (candidate.get("content") or {}).get("parts") or []
		# Gemini does not identify calls, so ids are minted to pair results with calls.
		calls = [
			{"id": f"{part['functionCall']['name']}-{index}", **_gemini_call(part["functionCall"])}
			for index, part in enumerate(parts)
			if part.get("functionCall")
		]
		refusals = ("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST")
		reason = candidate.get("finishReason")
		finish = "length" if reason == "MAX_TOKENS" else "refusal" if reason in refusals else "end"
		usage = response.get("usageMetadata") or {}
		return {
			"text": "".join(part.get("text", "") for part in parts).strip(),
			"tool_calls": calls,
			"raw": {"provider": "gemini", "content": parts},
			"finish_reason": "tool_calls" if calls else finish,
			"usage": {
				"input_tokens": usage.get("promptTokenCount"),
				"output_tokens": usage.get("candidatesTokenCount"),
			},
		}

	@classmethod
	def chat(cls, api_key, model, system, messages, tools, max_tokens) -> dict:
		model = model.removeprefix("models/")
		response = post_json(
			cls.name,
			f"{cls.base_url}/{requests.utils.quote(model, safe='')}:generateContent",
			{"x-goog-api-key": api_key},
			cls.build_body(model, system, messages, tools, max_tokens),
		)
		return cls.parse_turn(response)


def _gemini_call(call: dict) -> dict:
	return {"name": call["name"], "args": call.get("args") or {}}


PROVIDERS = {provider.name: provider for provider in (Anthropic, OpenAI, Gemini)}


def get_provider(name: str):
	if name not in PROVIDERS:
		raise ProviderError(name, 400, f"unknown AI provider: {name}")
	return PROVIDERS[name]


def list_providers() -> list[dict]:
	"""What the settings offer. The model lists are suggestions; any model the key allows works."""
	return [
		{
			"name": provider.name,
			"label": provider.label,
			"default_model": provider.default_model,
			"models": list(provider.models),
		}
		for provider in PROVIDERS.values()
	]

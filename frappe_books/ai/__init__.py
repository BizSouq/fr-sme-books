"""The Books assistant: a model that reads the books and proposes changes, behind the AI Guard.

`api` holds the endpoints the /books app calls, `providers` speaks to Anthropic, OpenAI and Gemini,
`tools` declares and runs what the model may do, and `guard` decides whether each step may happen.
"""

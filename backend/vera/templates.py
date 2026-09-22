"""Challenge-only template registry. These are NOT Meta-approved templates."""
REGISTRY = {
    "vera_context_message_v1": "Vera update: {{1}}",
    "merchant_context_message_v1": "Business message: {{1}}",
    "vera_context_message_hi_v1": "Vera अपडेट: {{1}}",
    "merchant_context_message_hi_v1": "व्यवसाय का संदेश: {{1}}",
}


def template_for(customer: bool, language: str, body: str) -> tuple[str, list[str], str]:
    base = "merchant_context_message" if customer else "vera_context_message"
    name = base + ("_hi_v1" if language == "hi" else "_v1")
    return name, [body], REGISTRY[name].replace("{{1}}", body)

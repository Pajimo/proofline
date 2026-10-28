"""Does Muse Wonder call our tools on /v1/responses? Flat tools, tool_choice "auto" only (docs, 28 Oct 2026).

Sends one customer message, expects a function_call, returns a tool result with previous_response_id
and expects a text reply.
"""
import json
import sys

from _common import run

from proofline.backends import MetaClient
from proofline.backends.meta import WONDER, output_text

TOOLS = [
    {"type": "function", "name": "safety_stop",
     "description": "Stop the conversation and send emergency advice. Use for gas smells, CO alarms or electrical danger.",
     "parameters": {"type": "object", "properties": {
         "kind": {"type": "string", "enum": ["gas", "carbon_monoxide", "electrical"]}},
         "required": ["kind"]}},
    {"type": "function", "name": "request_more_footage",
     "description": "Ask the customer to film something specific.",
     "parameters": {"type": "object", "properties": {"what": {"type": "string"}}, "required": ["what"]}},
]


def wonder_tool_call():
    client = MetaClient()
    first = client.responses({
        "model": WONDER,
        "instructions": "You are the assistant for Dave's Plumbing. Use the tools when they apply.",
        "input": "Hi, there's a strong smell of gas in my kitchen, can Dave come today?",
        "tools": TOOLS,
        "tool_choice": "auto",
        "max_output_tokens": 2000,
    })
    calls = [i for i in first.get("output", []) if i.get("type") == "function_call"]
    if not calls:
        raise AssertionError(f"no function_call; text was {output_text(first)!r}")
    call = calls[0]
    second = client.responses({
        "model": WONDER,
        "previous_response_id": first["id"],
        "input": [{"type": "function_call_output", "call_id": call["call_id"],
                   "output": json.dumps({"sent": True})}],
        "tools": TOOLS,
        "max_output_tokens": 2000,
    })
    return (f"call: {call['name']}({call['arguments']})\n"
            f"follow-up text: {output_text(second)[:400]!r}\n"
            f"usage: {first.get('usage')} / {second.get('usage')}")


if __name__ == "__main__":
    sys.exit(run("Muse Wonder: tool calling", wonder_tool_call))

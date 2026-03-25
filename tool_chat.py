#!/usr/bin/env python3
"""Simple CLI harness for testing OpenAI tool calling against local planning tools.

Examples:
    python tool_chat.py
    python tool_chat.py --model gpt-4.1-mini
    python tool_chat.py --base-url http://127.0.0.1:1234/v1 --api-key not-needed --model local-model
    python tool_chat.py --once "Plan a birthday dinner for 20 people in Lagos under $2,000."
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, List

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from openai import OpenAI
except ImportError:
    print(
        "The 'openai' package is not installed in this Python environment.\n"
        "Install project dependencies first, for example:\n"
        "  python3 -m pip install -r requirements.txt"
    )
    raise SystemExit(1)

from app.llm_tools import TOOL_DEFINITIONS, TOOL_REGISTRY

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-nano")
DEFAULT_BASE_URL = os.getenv("OPENAI_BASE_URL")
DEFAULT_SYSTEM_PROMPT = """You are testing a local event-planning agent.

Use the provided tools whenever real venue/vendor discovery, place detail lookup,
budget planning, or task planning is needed. Be explicit about what you are
doing, prefer tool calls over guessing, and summarize the tool outputs clearly.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Chat with an OpenAI-compatible model and execute local planning tools."
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model name to use.")
    parser.add_argument(
        "--api-key",
        default=os.getenv("OPENAI_API_KEY"),
        help="API key. If omitted and --base-url is set, 'not-needed' is used.",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="OpenAI-compatible base URL. Useful for LM Studio or other local servers.",
    )
    parser.add_argument(
        "--system-prompt",
        default=DEFAULT_SYSTEM_PROMPT,
        help="System prompt used for the chat session.",
    )
    parser.add_argument(
        "--tool-choice",
        default="auto",
        choices=["auto", "none", "required"],
        help="Tool-choice mode passed to the model.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.2,
        help="Sampling temperature for assistant responses.",
    )
    parser.add_argument(
        "--max-tool-rounds",
        type=int,
        default=8,
        help="Maximum consecutive tool-execution rounds per user turn.",
    )
    parser.add_argument(
        "--once",
        help="Send a single prompt, run the full tool loop, then exit.",
    )
    return parser.parse_args()


def build_client(args: argparse.Namespace) -> OpenAI:
    api_key = args.api_key or ("not-needed" if args.base_url else None)
    if not api_key:
        raise SystemExit(
            "No API key provided. Set OPENAI_API_KEY or pass --api-key.\n"
            "For LM Studio or another local OpenAI-compatible server, pass "
            "--base-url and optionally --api-key not-needed."
        )

    client_kwargs: Dict[str, Any] = {"api_key": api_key}
    if args.base_url:
        client_kwargs["base_url"] = args.base_url
    return OpenAI(**client_kwargs)


def build_tools_payload() -> List[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": definition["name"],
                "description": definition["description"],
                "parameters": definition["parameters"],
            },
        }
        for definition in TOOL_DEFINITIONS
    ]


def serialize_for_json(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return serialize_for_json(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {key: serialize_for_json(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [serialize_for_json(inner) for inner in value]
    if isinstance(value, tuple):
        return [serialize_for_json(inner) for inner in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def format_json(value: Any) -> str:
    return json.dumps(serialize_for_json(value), indent=2, ensure_ascii=True)


async def invoke_tool(name: str, arguments: Dict[str, Any]) -> Any:
    tool = TOOL_REGISTRY.get(name)
    if tool is None:
        raise ValueError(f"Unknown tool: {name}")

    if inspect.iscoroutinefunction(tool):
        return await tool(**arguments)

    result = tool(**arguments)
    if inspect.isawaitable(result):
        return await result
    return result


def append_assistant_message(messages: List[Dict[str, Any]], message: Any) -> None:
    payload: Dict[str, Any] = {"role": "assistant"}
    payload["content"] = message.content
    if message.tool_calls:
        payload["tool_calls"] = [
            {
                "id": tool_call.id,
                "type": tool_call.type,
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments,
                },
            }
            for tool_call in message.tool_calls
        ]
    messages.append(payload)


def print_banner(args: argparse.Namespace) -> None:
    provider = args.base_url or "https://api.openai.com/v1"
    print("Tool Chat")
    print(f"model: {args.model}")
    print(f"provider: {provider}")
    print("commands: /quit, /exit, /reset, /tools")
    print("")


def print_tools() -> None:
    print("available tools:")
    for definition in TOOL_DEFINITIONS:
        print(f"  - {definition['name']}: {definition['description']}")
    print("")


def initial_messages(system_prompt: str) -> List[Dict[str, Any]]:
    return [{"role": "system", "content": system_prompt}]


def request_completion(
    client: OpenAI,
    args: argparse.Namespace,
    messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]],
):
    return client.chat.completions.create(
        model=args.model,
        messages=messages,
        tools=tools,
        tool_choice=args.tool_choice,
        temperature=args.temperature,
    )


def handle_user_turn(
    client: OpenAI,
    args: argparse.Namespace,
    messages: List[Dict[str, Any]],
    user_prompt: str,
) -> None:
    tools = build_tools_payload()
    messages.append({"role": "user", "content": user_prompt})

    for _ in range(args.max_tool_rounds):
        completion = request_completion(client, args, messages, tools)
        message = completion.choices[0].message
        append_assistant_message(messages, message)

        if message.content:
            print(f"\nassistant>\n{message.content}\n")

        if not message.tool_calls:
            return

        for tool_call in message.tool_calls:
            tool_name = tool_call.function.name
            raw_arguments = tool_call.function.arguments or "{}"
            print(f"[tool] {tool_name}")
            print("[arguments]")
            print(raw_arguments)

            try:
                arguments = json.loads(raw_arguments)
            except json.JSONDecodeError as exc:
                tool_payload = {
                    "ok": False,
                    "error": f"Tool arguments were not valid JSON: {exc}",
                }
            else:
                try:
                    result = asyncio.run(invoke_tool(tool_name, arguments))
                    tool_payload = {
                        "ok": True,
                        "result": serialize_for_json(result),
                    }
                except Exception as exc:
                    tool_payload = {
                        "ok": False,
                        "error": str(exc),
                    }

            print("[result]")
            print(format_json(tool_payload))
            print("")

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_payload, ensure_ascii=True),
                }
            )

    print(
        "assistant>\nReached the maximum tool-execution rounds for this turn. "
        "Inspect the tool logs above and refine the prompt or tool behavior.\n"
    )


def run_repl(client: OpenAI, args: argparse.Namespace) -> None:
    messages = initial_messages(args.system_prompt)
    print_banner(args)
    print(client)

    if args.once:
        handle_user_turn(client, args, messages, args.once)
        return

    while True:
        try:
            user_prompt = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye")
            return

        if not user_prompt:
            continue
        if user_prompt in {"/quit", "/exit"}:
            print("bye")
            return
        if user_prompt == "/reset":
            messages = initial_messages(args.system_prompt)
            print("conversation reset\n")
            continue
        if user_prompt == "/tools":
            print_tools()
            continue

        handle_user_turn(client, args, messages, user_prompt)


def main() -> None:
    args = parse_args()
    client = build_client(args)
    run_repl(client, args)


if __name__ == "__main__":
    main()

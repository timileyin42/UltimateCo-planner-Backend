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
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, Optional

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from openai import AsyncOpenAI
except ImportError:
    print(
        "The 'openai' package is not installed in this Python environment.\n"
        "Install project dependencies first, for example:\n"
        "  python3 -m pip install -r requirements.txt"
    )
    raise SystemExit(1)

from app.llm_tools import TOOL_DEFINITIONS
from app.services.tool_chat_service import (
    DEFAULT_TOOL_CHAT_SYSTEM_PROMPT,
    ToolChatRunner,
)

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-nano")
DEFAULT_BASE_URL = os.getenv("OPENAI_BASE_URL")
DEFAULT_SYSTEM_PROMPT = DEFAULT_TOOL_CHAT_SYSTEM_PROMPT


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


def build_client(args: argparse.Namespace) -> AsyncOpenAI:
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
    return AsyncOpenAI(**client_kwargs)


def print_banner(args: argparse.Namespace) -> None:
    provider = args.base_url or "https://api.openai.com/v1"
    print("Tool Chat")
    print(f"model: {args.model}")
    print(f"provider: {provider}")
    print("commands: /quit, /exit, /reset, /tools, /more")
    print("")


def print_tools() -> None:
    print("available tools:")
    for definition in TOOL_DEFINITIONS:
        print(f"  - {definition['name']}: {definition['description']}")
    print("")


async def handle_user_turn(
    runner: ToolChatRunner,
    args: argparse.Namespace,
    session_state: Dict[str, Any],
    user_prompt: str,
) -> None:
    result = await runner.run_turn(
        user_prompt=user_prompt,
        messages=session_state["messages"],
        model=args.model,
        system_prompt=args.system_prompt,
        tool_choice=args.tool_choice,
        temperature=args.temperature,
        max_tool_rounds=min(args.max_tool_rounds, 20),
        preflight_answers=session_state.get("preflight_answers"),
    )
    preflight = result.get("preflight") or {}
    if preflight and not preflight.get("complete"):
        print("\nquick questions>\n")
        answers = prompt_for_missing_preflight(preflight)
        session_state["preflight_answers"] = merge_preflight_answers(
            session_state.get("preflight_answers"),
            answers,
        )
        result = await runner.run_turn(
            user_prompt=user_prompt,
            messages=session_state["messages"],
            model=args.model,
            system_prompt=args.system_prompt,
            tool_choice=args.tool_choice,
            temperature=args.temperature,
            max_tool_rounds=min(args.max_tool_rounds, 20),
            preflight_answers=session_state.get("preflight_answers"),
        )

    session_state["messages"] = result["messages"]
    if result.get("preflight"):
        session_state["preflight_answers"] = merge_preflight_answers(
            session_state.get("preflight_answers"),
            result["preflight"].get("collected"),
        )
    if result.get("venue_shortlist"):
        session_state["venue_shortlist"] = result["venue_shortlist"]

    for entry in result["tool_trace"]:
        print(f"[tool] {entry['tool_name']}")
        print("[arguments]")
        print(entry["raw_arguments"])
        print("[result]")
        print(json.dumps(entry["result"], indent=2, ensure_ascii=True))
        print("")

    for assistant_message in result.get("assistant_messages", []):
        content = assistant_message.get("content")
        if content:
            print(f"\nassistant>\n{content}\n")

    if result.get("venue_shortlist"):
        print_venue_shortlist(result["venue_shortlist"])

    if result.get("warning"):
        print(f"assistant>\n{result['warning']}\n")


async def handle_more_venues(runner: ToolChatRunner, session_state: Dict[str, Any]) -> None:
    shortlist = session_state.get("venue_shortlist")
    if not shortlist:
        print("assistant>\nNo venue shortlist is loaded yet.\n")
        return
    if not shortlist.get("has_more"):
        print("assistant>\nNo more venue pages are available for the current shortlist.\n")
        return

    next_shortlist = await runner.load_more_venues(
        search_context=shortlist["search_context"],
    )
    session_state["venue_shortlist"] = next_shortlist
    print_venue_shortlist(next_shortlist)


def print_venue_shortlist(shortlist: Dict[str, Any]) -> None:
    items = shortlist.get("items") or []
    if not items:
        return

    print("\nvenue shortlist>\n")
    for index, item in enumerate(items, start=1):
        address = item.get("formatted_address") or "No address provided"
        rating = item.get("rating")
        rating_count = item.get("user_rating_count")
        price_level = item.get("price_level") or "n/a"
        maps_uri = item.get("google_maps_uri") or "n/a"
        reasons = ", ".join(item.get("fit_reasons") or []) or "No fit reasons provided"
        rating_text = "n/a"
        if rating is not None:
            rating_text = f"{rating}"
            if rating_count is not None:
                rating_text = f"{rating_text} ({rating_count} ratings)"
        print(f"{index}. {item.get('name')}")
        print(f"   {address}")
        print(f"   rating: {rating_text} | price: {price_level}")
        print(f"   fit: {reasons}")
        print(f"   maps: {maps_uri}")
    print("")
    if shortlist.get("has_more"):
        print("assistant>\nUse /more to load 10 more venue options.\n")


def prompt_for_missing_preflight(preflight: Dict[str, Any]) -> Dict[str, Any]:
    answers = dict((preflight.get("collected") or {}))
    for question in preflight.get("questions", []):
        field_id = question["id"]
        prompt = question["prompt"]
        placeholder = question.get("placeholder")
        options = question.get("options") or []
        while True:
            if options:
                option_text = ", ".join(option["value"] for option in options)
                raw_value = input(f"{prompt} [{option_text}]: ").strip()
            elif placeholder:
                raw_value = input(f"{prompt} [{placeholder}]: ").strip()
            else:
                raw_value = input(f"{prompt}: ").strip()

            normalized = normalize_preflight_value(field_id, raw_value)
            if normalized:
                answers[field_id] = normalized
                break
            print("Please provide a valid answer.")
    return answers


def normalize_preflight_value(field_id: str, value: str) -> Optional[str]:
    cleaned = value.strip()
    if not cleaned:
        return None
    if field_id != "venue_setting":
        return cleaned

    normalized = cleaned.lower().replace("-", "_").replace(" ", "_")
    if normalized in {"home", "restaurant", "event_space"}:
        return normalized
    return None


def merge_preflight_answers(existing: Optional[Dict[str, Any]], incoming: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    merged = dict(existing or {})
    for key, value in (incoming or {}).items():
        if value:
            merged[key] = value
    return merged


def run_repl(runner: ToolChatRunner, args: argparse.Namespace) -> None:
    session_state: Dict[str, Any] = {
        "messages": runner.initial_messages(args.system_prompt),
        "preflight_answers": {},
        "venue_shortlist": None,
    }
    print_banner(args)

    if args.once:
        asyncio.run(handle_user_turn(runner, args, session_state, args.once))
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
            session_state = {
                "messages": runner.initial_messages(args.system_prompt),
                "preflight_answers": {},
                "venue_shortlist": None,
            }
            print("conversation reset\n")
            continue
        if user_prompt == "/tools":
            print_tools()
            continue
        if user_prompt == "/more":
            asyncio.run(handle_more_venues(runner, session_state))
            continue

        asyncio.run(handle_user_turn(runner, args, session_state, user_prompt))


def main() -> None:
    args = parse_args()
    runner = ToolChatRunner(
        client=build_client(args),
        default_model=args.model,
        default_system_prompt=args.system_prompt,
        is_configured=bool(args.api_key or args.base_url),
    )
    run_repl(runner, args)


if __name__ == "__main__":
    main()

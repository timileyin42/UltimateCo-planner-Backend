"""Async tool-chat runner shared by the CLI harness and dev web UI."""

from __future__ import annotations

import inspect
import json
import re
from typing import Any, Dict, List, Literal, Optional

from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings
from app.core.logger import get_logger
from app.llm_tools import TOOL_DEFINITIONS, TOOL_REGISTRY
from app.llm_tools.schemas import BudgetRange, GooglePlacesSearchResponse

logger = get_logger(__name__)

DEFAULT_TOOL_CHAT_SYSTEM_PROMPT = """You are testing a local event-planning agent.

Before the first tool-search round, rely on the backend-provided shortlist intake.
Do not repeat identical tool calls. For venue discovery, prefer one simplified
location-first search such as "restaurant in Lekki, Lagos, Nigeria" or
"event venue in Lekki, Lagos, Nigeria". Use venue pagination or user choice
instead of re-running the same search. If the venue setting is home, skip venue
discovery unless the user explicitly asks for alternatives.

Use the provided tools whenever real venue/vendor discovery, place detail lookup,
budget planning, or task planning is needed. Be explicit about what you are
doing, prefer tool calls over guessing, and summarize the tool outputs clearly.
"""

ALLOWED_MESSAGE_ROLES = {"system", "user", "assistant", "tool"}
INTAKE_SYSTEM_MARKER = "[tool_chat_intake]"
SHORTLIST_SYSTEM_MARKER = "[tool_chat_shortlist]"
SELECTION_SYSTEM_MARKER = "[tool_chat_selection]"
MAX_VISIBLE_MESSAGES = 12
DEFAULT_VENUE_PAGE_SIZE = 10
VENUE_SELECTION_PATTERN = re.compile(r"\b(?:use\s+)?(?:venue|option)\s*#?\s*(\d+)\b", re.IGNORECASE)

LOCATION_PATTERN = re.compile(
    r"\b(?:in|at|around|near)\s+([a-z0-9][a-z0-9\s,\-]{1,80})",
    re.IGNORECASE,
)
TEMPORAL_PATTERN = re.compile(
    r"\b("
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
    r"(?:[^,.!?]{0,24})?"
    r"|today|tomorrow|tonight|this\s+\w+|next\s+\w+|weekend"
    r"|(?:mon|tues|wednes|thurs|fri|satur|sun)day"
    r")(?:[^,.!?]{0,24}?\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b)?",
    re.IGNORECASE,
)
TIME_ONLY_PATTERN = re.compile(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b", re.IGNORECASE)
LOCATION_STOP_WORDS = (
    " for ",
    " with ",
    " under ",
    " next ",
    " this ",
    " tomorrow",
    " tonight",
    " on ",
    " by ",
)
CUISINE_HINTS = {
    "nigerian swallows": "Nigerian swallows",
    "swallows": "Nigerian swallows",
    "continental": "Continental",
    "barbecue": "Barbecue",
    "bbq": "Barbecue",
    "nigerian": "Nigerian",
    "chinese": "Chinese",
    "italian": "Italian",
    "indian": "Indian",
    "seafood": "Seafood",
    "grill": "Grill",
    "pizza": "Pizza",
}


class ToolChatIntakeAnswers(BaseModel):
    """Collected answers for the first-turn venue/vendor shortlist intake."""

    model_config = ConfigDict(from_attributes=True)

    city_area: Optional[str] = None
    venue_setting: Optional[Literal["home", "restaurant", "event_space"]] = None
    cuisine: Optional[str] = None
    date_time_or_month: Optional[str] = None


class ToolChatPreflightQuestion(BaseModel):
    """Question the backend can ask before the first model call."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    label: str
    prompt: str
    input_type: Literal["text", "select"] = "text"
    options: List[Dict[str, str]] = Field(default_factory=list)
    placeholder: Optional[str] = None


class ToolChatPreflightState(BaseModel):
    """Current state of the preflight intake."""

    model_config = ConfigDict(from_attributes=True)

    complete: bool
    collected: ToolChatIntakeAnswers
    missing_fields: List[str] = Field(default_factory=list)
    questions: List[ToolChatPreflightQuestion] = Field(default_factory=list)


class VenueShortlistSearchContext(BaseModel):
    """Search context needed to paginate venue results without another LLM turn."""

    model_config = ConfigDict(from_attributes=True)

    city_area: str
    venue_setting: Literal["restaurant", "event_space", "either"] = "either"
    cuisine: Optional[str] = None
    event_type: str
    guest_count: Optional[int] = None
    budget: Optional[BudgetRange] = None
    indoor_outdoor: str = "either"
    page_size: int = DEFAULT_VENUE_PAGE_SIZE
    next_page_token: Optional[str] = None
    query: Optional[str] = None


class VenueShortlistItem(BaseModel):
    """UI-friendly venue card payload."""

    model_config = ConfigDict(from_attributes=True)

    place_id: str
    name: str
    formatted_address: Optional[str] = None
    rating: Optional[float] = None
    user_rating_count: Optional[int] = None
    price_level: Optional[str] = None
    fit_score: float = 0.0
    fit_reasons: List[str] = Field(default_factory=list)
    google_maps_uri: Optional[str] = None


class VenueShortlistResponse(BaseModel):
    """Current shortlist of venues and the context needed to fetch more."""

    model_config = ConfigDict(from_attributes=True)

    items: List[VenueShortlistItem] = Field(default_factory=list)
    search_context: VenueShortlistSearchContext
    has_more: bool = False


class ToolChatRunner:
    """Run an OpenAI chat-completions tool loop against the local tool registry."""

    def __init__(
        self,
        *,
        client: AsyncOpenAI,
        default_model: str,
        default_system_prompt: str = DEFAULT_TOOL_CHAT_SYSTEM_PROMPT,
        is_configured: bool = True,
    ) -> None:
        self.client = client
        self.default_model = default_model
        self.default_system_prompt = default_system_prompt
        self.is_configured = is_configured

    @classmethod
    def from_settings(cls) -> "ToolChatRunner":
        api_key = settings.OPENAI_API_KEY or (
            "not-needed" if settings.OPENAI_BASE_URL else "missing-openai-api-key"
        )
        return cls(
            client=AsyncOpenAI(
                api_key=api_key,
                base_url=settings.OPENAI_BASE_URL,
            ),
            default_model=settings.OPENAI_MODEL,
            default_system_prompt=DEFAULT_TOOL_CHAT_SYSTEM_PROMPT,
            is_configured=bool(settings.OPENAI_API_KEY or settings.OPENAI_BASE_URL),
        )

    def build_tools_payload(self) -> List[Dict[str, Any]]:
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

    def serialize_for_json(self, value: Any) -> Any:
        if hasattr(value, "model_dump"):
            return self.serialize_for_json(value.model_dump(mode="json"))
        if isinstance(value, dict):
            return {key: self.serialize_for_json(inner) for key, inner in value.items()}
        if isinstance(value, list):
            return [self.serialize_for_json(inner) for inner in value]
        if isinstance(value, tuple):
            return [self.serialize_for_json(inner) for inner in value]
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return str(value)

    async def invoke_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        tool = TOOL_REGISTRY.get(name)
        if tool is None:
            raise ValueError(f"Unknown tool: {name}")

        if inspect.iscoroutinefunction(tool):
            return await tool(**arguments)

        result = tool(**arguments)
        if inspect.isawaitable(result):
            return await result
        return result

    async def load_more_venues(
        self,
        *,
        search_context: VenueShortlistSearchContext | Dict[str, Any],
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        if isinstance(search_context, dict):
            search_context = VenueShortlistSearchContext.model_validate(search_context)
        resolved_page_token = page_token or search_context.next_page_token
        if not resolved_page_token:
            raise ValueError("No next page token is available for this venue shortlist.")

        logger.info(
            "venue_shortlist_pages_loaded city=%s venue_setting=%s page_size=%s",
            search_context.city_area,
            search_context.venue_setting,
            search_context.page_size,
        )
        response = await self.invoke_tool(
            "search_venues",
            {
                "city": search_context.city_area,
                "event_type": search_context.event_type,
                "indoor_outdoor": search_context.indoor_outdoor,
                "guest_count": search_context.guest_count,
                "venue_setting": search_context.venue_setting,
                "cuisine": search_context.cuisine,
                "budget": self.serialize_for_json(search_context.budget),
                "page_size": search_context.page_size,
                "page_token": resolved_page_token,
            },
        )
        shortlist = self._venue_shortlist_from_response(response)
        if shortlist is None:
            raise ValueError("No venue results were returned for the next page.")
        return self.serialize_for_json(shortlist)

    def initial_messages(self, system_prompt: Optional[str] = None) -> List[Dict[str, Any]]:
        return [
            {
                "role": "system",
                "content": system_prompt or self.default_system_prompt,
            }
        ]

    def _normalize_content(self, content: Any) -> Any:
        if content is None or isinstance(content, str):
            return content
        return json.dumps(self.serialize_for_json(content), ensure_ascii=True)

    def _normalize_tool_calls(self, tool_calls: Any) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        if not isinstance(tool_calls, list):
            return normalized

        for tool_call in tool_calls:
            if not isinstance(tool_call, dict):
                continue
            function_payload = tool_call.get("function")
            if not isinstance(function_payload, dict):
                continue

            normalized.append(
                {
                    "id": str(tool_call.get("id") or ""),
                    "type": str(tool_call.get("type") or "function"),
                    "function": {
                        "name": str(function_payload.get("name") or ""),
                        "arguments": str(function_payload.get("arguments") or "{}"),
                    },
                }
            )

        return normalized

    def normalize_messages(
        self,
        messages: Optional[List[Dict[str, Any]]],
        *,
        system_prompt: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return self.build_model_messages(messages, system_prompt=system_prompt)

    def build_model_messages(
        self,
        raw_messages: Optional[List[Dict[str, Any]]],
        *,
        system_prompt: Optional[str] = None,
        intake_state: Optional[ToolChatPreflightState] = None,
        venue_shortlist: Optional[VenueShortlistResponse] = None,
    ) -> List[Dict[str, Any]]:
        """Trim stored chat state down to the messages worth sending back to the model."""

        base_prompt = system_prompt or self._extract_base_system_prompt(raw_messages)
        messages: List[Dict[str, Any]] = [{"role": "system", "content": base_prompt}]

        intake_message = None
        if intake_state and intake_state.complete:
            intake_message = self._build_intake_system_message(intake_state.collected)
        else:
            intake_message = self._extract_tagged_system_message(raw_messages, INTAKE_SYSTEM_MARKER)
        if intake_message:
            messages.append({"role": "system", "content": intake_message})

        shortlist_message = None
        if venue_shortlist is not None:
            shortlist_message = self._build_shortlist_system_message(venue_shortlist)
        else:
            shortlist_message = self._extract_tagged_system_message(raw_messages, SHORTLIST_SYSTEM_MARKER)
        if shortlist_message:
            messages.append({"role": "system", "content": shortlist_message})

        visible_messages = self._visible_messages(raw_messages)
        messages.extend(visible_messages[-MAX_VISIBLE_MESSAGES:])
        return messages

    def assistant_message_to_payload(self, message: Any) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "role": "assistant",
            "content": self._normalize_content(getattr(message, "content", None)),
        }

        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls:
            payload["tool_calls"] = [
                {
                    "id": tool_call.id,
                    "type": tool_call.type,
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments,
                    },
                }
                for tool_call in tool_calls
            ]

        return payload

    async def run_turn(
        self,
        *,
        user_prompt: str,
        messages: Optional[List[Dict[str, Any]]] = None,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        tool_choice: str = "auto",
        temperature: float = 0.2,
        max_tool_rounds: int = 8,
        preflight_answers: Optional[Dict[str, Any] | ToolChatIntakeAnswers] = None,
    ) -> Dict[str, Any]:
        if not self.is_configured:
            raise ValueError(
                "OPENAI_API_KEY is not configured. Set OPENAI_API_KEY or OPENAI_BASE_URL before using the dev tool chat."
            )

        raw_messages = messages or []
        logger.info(
            "tool_chat_turn_start tool_choice=%s max_tool_rounds=%s carried_messages=%s",
            tool_choice,
            max_tool_rounds,
            len(raw_messages),
        )
        if tool_choice == "required":
            logger.warning(
                "tool_chat_required_tool_choice active=true max_tool_rounds=%s",
                max_tool_rounds,
            )
        explicit_preflight = ToolChatIntakeAnswers.model_validate(preflight_answers or {})
        preflight_state: Optional[ToolChatPreflightState] = None
        resolved_preflight = self._preflight_state_from_messages(raw_messages)
        existing_shortlist = self._extract_shortlist_from_messages(raw_messages)

        if self._should_run_preflight(raw_messages):
            preflight_state = self._build_preflight_state(
                user_prompt=user_prompt,
                explicit_answers=explicit_preflight,
            )
            resolved_preflight = preflight_state
            if not preflight_state.complete:
                logger.info(
                    "preflight_missing_fields fields=%s",
                    ",".join(preflight_state.missing_fields),
                )
                return {
                    "assistant_message": None,
                    "assistant_messages": [],
                    "messages": self.build_model_messages(
                        raw_messages,
                        system_prompt=system_prompt,
                    ),
                    "tool_trace": [],
                    "max_tool_rounds_reached": False,
                    "warning": "Complete the quick questions before the first venue/vendor shortlist.",
                    "preflight": self.serialize_for_json(resolved_preflight),
                    "venue_shortlist": None,
                }

        working_messages = self.build_model_messages(
            raw_messages,
            system_prompt=system_prompt,
            intake_state=preflight_state,
        )
        selection_message = self._build_selection_system_message(
            user_prompt=user_prompt,
            shortlist=existing_shortlist,
        )
        if selection_message:
            working_messages.append({"role": "system", "content": selection_message})
        working_messages.append({"role": "user", "content": user_prompt})

        tool_trace: List[Dict[str, Any]] = []
        assistant_messages: List[Dict[str, Any]] = []
        final_assistant_message: Optional[Dict[str, Any]] = None
        latest_shortlist: Optional[VenueShortlistResponse] = None
        current_intake_answers = (
            preflight_state.collected if preflight_state else self._extract_intake_answers_from_messages(raw_messages)
        )
        tools = self.build_tools_payload()
        executed_calls: Dict[tuple[str, str], Dict[str, Any]] = {}

        for _ in range(max_tool_rounds):
            completion = await self.client.chat.completions.create(
                model=model or self.default_model,
                messages=working_messages,
                tools=tools,
                tool_choice=tool_choice,
                temperature=temperature,
            )
            message = completion.choices[0].message
            assistant_payload = self.assistant_message_to_payload(message)
            working_messages.append(assistant_payload)
            assistant_messages.append(assistant_payload)
            final_assistant_message = assistant_payload

            if not getattr(message, "tool_calls", None):
                compact_messages = self.build_model_messages(
                    working_messages,
                    system_prompt=system_prompt,
                    intake_state=preflight_state,
                    venue_shortlist=latest_shortlist,
                )
                return {
                    "assistant_message": final_assistant_message,
                    "assistant_messages": assistant_messages,
                    "messages": compact_messages,
                    "tool_trace": tool_trace,
                    "max_tool_rounds_reached": False,
                    "warning": None,
                    "preflight": self.serialize_for_json(resolved_preflight) if resolved_preflight else None,
                    "venue_shortlist": self.serialize_for_json(latest_shortlist),
                }

            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                raw_arguments = tool_call.function.arguments or "{}"
                canonical_arguments = self._canonicalize_arguments(raw_arguments)
                cache_key = (tool_name, canonical_arguments)
                cache_hit = cache_key in executed_calls

                if cache_hit:
                    logger.info("tool_calls_deduped tool=%s", tool_name)
                    tool_payload = executed_calls[cache_key]
                    arguments = tool_payload.get("_arguments")
                else:
                    try:
                        arguments = json.loads(raw_arguments)
                    except json.JSONDecodeError as exc:
                        arguments = None
                        tool_payload = {
                            "ok": False,
                            "error": f"Tool arguments were not valid JSON: {exc}",
                        }
                    else:
                        try:
                            if self._should_skip_venue_search(
                                tool_name=tool_name,
                                arguments=arguments,
                                intake_answers=current_intake_answers,
                            ):
                                tool_payload = {
                                    "ok": False,
                                    "error": (
                                        "Venue search skipped because the shortlist intake says the event is at home. "
                                        "Only search venues if the user explicitly asks for venue alternatives."
                                    ),
                                }
                            else:
                                logger.info("tool_calls_executed tool=%s", tool_name)
                                result = await self.invoke_tool(tool_name, arguments)
                                tool_payload = {
                                    "ok": True,
                                    "result": self.serialize_for_json(result),
                                }
                        except Exception as exc:
                            logger.exception("Tool execution failed for %s", tool_name)
                            tool_payload = {
                                "ok": False,
                                "error": str(exc),
                            }
                    tool_payload["_arguments"] = arguments
                    executed_calls[cache_key] = tool_payload

                public_tool_payload = {
                    key: value
                    for key, value in tool_payload.items()
                    if not key.startswith("_")
                }
                tool_trace.append(
                    {
                        "tool_call_id": tool_call.id,
                        "tool_name": tool_name,
                        "arguments": arguments,
                        "raw_arguments": raw_arguments,
                        "result": public_tool_payload,
                        "cache_hit": cache_hit,
                    }
                )
                working_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(public_tool_payload, ensure_ascii=True),
                    }
                )

                if tool_name == "search_venues" and public_tool_payload.get("ok") is True:
                    latest_shortlist = self._venue_shortlist_from_response(
                        public_tool_payload.get("result"),
                        arguments=arguments,
                    )

        logger.warning("max_tool_rounds_reached rounds=%s", max_tool_rounds)
        warning = (
            "Reached the maximum tool-execution rounds for this turn. "
            "Inspect the tool trace and refine the prompt or tool behavior."
        )
        if not final_assistant_message or not final_assistant_message.get("content"):
            working_messages.append({"role": "assistant", "content": warning})
            final_assistant_message = {"role": "assistant", "content": warning}

        compact_messages = self.build_model_messages(
            working_messages,
            system_prompt=system_prompt,
            intake_state=preflight_state,
            venue_shortlist=latest_shortlist,
        )
        return {
            "assistant_message": final_assistant_message,
            "assistant_messages": assistant_messages,
            "messages": compact_messages,
            "tool_trace": tool_trace,
            "max_tool_rounds_reached": True,
            "warning": warning,
            "preflight": self.serialize_for_json(resolved_preflight) if resolved_preflight else None,
            "venue_shortlist": self.serialize_for_json(latest_shortlist),
        }

    def _should_run_preflight(self, raw_messages: List[Dict[str, Any]]) -> bool:
        return not any(message.get("role") in {"user", "assistant"} for message in raw_messages)

    def _build_preflight_state(
        self,
        *,
        user_prompt: str,
        explicit_answers: ToolChatIntakeAnswers,
    ) -> ToolChatPreflightState:
        extracted_answers = self._extract_preflight_answers(user_prompt)
        collected = ToolChatIntakeAnswers(
            city_area=explicit_answers.city_area or extracted_answers.city_area,
            venue_setting=explicit_answers.venue_setting or extracted_answers.venue_setting,
            cuisine=explicit_answers.cuisine or extracted_answers.cuisine,
            date_time_or_month=(
                explicit_answers.date_time_or_month or extracted_answers.date_time_or_month
            ),
        )

        missing_fields = [
            field_name
            for field_name in ("city_area", "venue_setting", "cuisine", "date_time_or_month")
            if not getattr(collected, field_name)
        ]
        questions = [self._question_for_field(field_name) for field_name in missing_fields]
        return ToolChatPreflightState(
            complete=not missing_fields,
            collected=collected,
            missing_fields=missing_fields,
            questions=questions,
        )

    def _preflight_state_from_messages(
        self,
        raw_messages: Optional[List[Dict[str, Any]]],
    ) -> Optional[ToolChatPreflightState]:
        answers = self._extract_intake_answers_from_messages(raw_messages)
        if answers is None:
            return None
        missing_fields = [
            field_name
            for field_name in ("city_area", "venue_setting", "cuisine", "date_time_or_month")
            if not getattr(answers, field_name)
        ]
        return ToolChatPreflightState(
            complete=not missing_fields,
            collected=answers,
            missing_fields=missing_fields,
            questions=[self._question_for_field(field_name) for field_name in missing_fields],
        )

    def _extract_preflight_answers(self, user_prompt: str) -> ToolChatIntakeAnswers:
        lower_prompt = user_prompt.lower()
        return ToolChatIntakeAnswers(
            city_area=self._extract_city_area(user_prompt),
            venue_setting=self._extract_venue_setting(lower_prompt),
            cuisine=self._extract_cuisine(lower_prompt),
            date_time_or_month=self._extract_date_hint(user_prompt),
        )

    def _extract_city_area(self, user_prompt: str) -> Optional[str]:
        match = LOCATION_PATTERN.search(user_prompt)
        if not match:
            return None

        value = match.group(1).strip()
        lower_value = value.lower()
        for stop_word in LOCATION_STOP_WORDS:
            if stop_word in lower_value:
                cutoff = lower_value.index(stop_word)
                value = value[:cutoff]
                break

        cleaned = re.sub(r"\s+", " ", value).strip(" ,.-")
        if not cleaned:
            return None
        if cleaned == cleaned.lower():
            return ", ".join(part.strip().title() for part in cleaned.split(","))
        return cleaned

    def _extract_venue_setting(
        self,
        lower_prompt: str,
    ) -> Optional[Literal["home", "restaurant", "event_space"]]:
        if any(keyword in lower_prompt for keyword in (" at home", " home ", " house ")):
            return "home"
        if any(
            keyword in lower_prompt
            for keyword in (" restaurant", " dinner at ", " lunch at ", " brunch at ", " book a table")
        ):
            return "restaurant"
        if any(
            keyword in lower_prompt
            for keyword in ("event space", "hall", "banquet", "venue", "event centre", "event center")
        ):
            return "event_space"
        return None

    def _extract_cuisine(self, lower_prompt: str) -> Optional[str]:
        for keyword, normalized in CUISINE_HINTS.items():
            if keyword in lower_prompt:
                return normalized
        return None

    def _extract_date_hint(self, user_prompt: str) -> Optional[str]:
        match = TEMPORAL_PATTERN.search(user_prompt)
        if match:
            return re.sub(r"\s+", " ", match.group(0)).strip(" ,.")
        match = TIME_ONLY_PATTERN.search(user_prompt)
        if match:
            return match.group(0)
        return None

    def _question_for_field(self, field_name: str) -> ToolChatPreflightQuestion:
        if field_name == "city_area":
            return ToolChatPreflightQuestion(
                id="city_area",
                label="City / Area",
                prompt="What city or area is the event in?",
                input_type="text",
                placeholder="Lekki, Lagos, Nigeria",
            )
        if field_name == "venue_setting":
            return ToolChatPreflightQuestion(
                id="venue_setting",
                label="Venue Type",
                prompt="Is it at home, a restaurant, or an event space?",
                input_type="select",
                options=[
                    {"label": "Home", "value": "home"},
                    {"label": "Restaurant", "value": "restaurant"},
                    {"label": "Event Space", "value": "event_space"},
                ],
            )
        if field_name == "cuisine":
            return ToolChatPreflightQuestion(
                id="cuisine",
                label="Cuisine",
                prompt="Any cuisine preference?",
                input_type="text",
                placeholder="Nigerian swallows, continental, barbecue",
            )
        return ToolChatPreflightQuestion(
            id="date_time_or_month",
            label="Date / Time",
            prompt="What date, time, or month is it?",
            input_type="text",
            placeholder="Next Friday at 7pm",
        )

    def _extract_base_system_prompt(self, raw_messages: Optional[List[Dict[str, Any]]]) -> str:
        for message in raw_messages or []:
            if message.get("role") != "system":
                continue
            content = self._normalize_content(message.get("content"))
            if not isinstance(content, str):
                continue
            if content.startswith(INTAKE_SYSTEM_MARKER) or content.startswith(SHORTLIST_SYSTEM_MARKER):
                continue
            return content
        return self.default_system_prompt

    def _extract_tagged_system_message(
        self,
        raw_messages: Optional[List[Dict[str, Any]]],
        marker: str,
    ) -> Optional[str]:
        for message in reversed(raw_messages or []):
            if message.get("role") != "system":
                continue
            content = self._normalize_content(message.get("content"))
            if isinstance(content, str) and content.startswith(marker):
                return content
        return None

    def _visible_messages(
        self,
        raw_messages: Optional[List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        visible: List[Dict[str, Any]] = []
        for message in raw_messages or []:
            if not isinstance(message, dict):
                continue
            role = message.get("role")
            if role not in {"user", "assistant"}:
                continue
            content = self._normalize_content(message.get("content"))
            if role == "assistant" and not content:
                continue
            visible.append({"role": role, "content": content})
        return visible

    def _build_intake_system_message(self, answers: ToolChatIntakeAnswers) -> str:
        venue_guidance = (
            "If venue setting is home, skip search_venues unless the user explicitly asks for venue alternatives."
        )
        return "\n".join(
            [
                INTAKE_SYSTEM_MARKER,
                "Quick shortlist intake collected by the backend:",
                f"- city/area: {answers.city_area or 'unknown'}",
                f"- venue setting: {answers.venue_setting or 'unknown'}",
                f"- cuisine: {answers.cuisine or 'unknown'}",
                f"- date/time or month: {answers.date_time_or_month or 'unknown'}",
                venue_guidance,
            ]
        )

    def _build_shortlist_system_message(
        self,
        shortlist: VenueShortlistResponse,
    ) -> str:
        shortlist_payload = self.serialize_for_json(
            {
                "selection_guidance": (
                    "If the user selects a numbered venue, use the exact place_id for get_place_details. "
                    "Use the google_maps_uri when a link is needed."
                ),
                "shortlist": {
                    "search_context": shortlist.search_context,
                    "has_more": shortlist.has_more,
                    "items": [
                        {
                            "place_id": item.place_id,
                            "name": item.name,
                            "formatted_address": item.formatted_address,
                            "google_maps_uri": item.google_maps_uri,
                        }
                        for item in shortlist.items
                    ],
                },
            }
        )
        return f"{SHORTLIST_SYSTEM_MARKER}\n{json.dumps(shortlist_payload, ensure_ascii=True, separators=(',', ':'))}"

    def _extract_shortlist_from_messages(
        self,
        raw_messages: Optional[List[Dict[str, Any]]],
    ) -> Optional[VenueShortlistResponse]:
        shortlist_message = self._extract_tagged_system_message(raw_messages, SHORTLIST_SYSTEM_MARKER)
        if not shortlist_message:
            return None
        try:
            _, raw_payload = shortlist_message.split("\n", 1)
        except ValueError:
            return None
        try:
            parsed = json.loads(raw_payload)
        except json.JSONDecodeError:
            return None
        shortlist_payload = parsed.get("shortlist") if isinstance(parsed, dict) else None
        if not shortlist_payload:
            return None
        try:
            return VenueShortlistResponse.model_validate(shortlist_payload)
        except Exception:
            logger.exception("Failed to parse venue shortlist from hidden system message.")
            return None

    def _build_selection_system_message(
        self,
        *,
        user_prompt: str,
        shortlist: Optional[VenueShortlistResponse],
    ) -> Optional[str]:
        if not shortlist or not shortlist.items:
            return None
        match = VENUE_SELECTION_PATTERN.search(user_prompt)
        if not match:
            return None
        selection_index = int(match.group(1)) - 1
        if selection_index < 0 or selection_index >= len(shortlist.items):
            return None
        selected_item = shortlist.items[selection_index]
        selection_payload = self.serialize_for_json(
            {
                "selection_guidance": (
                    "The user selected this venue from the shortlist. "
                    "Use this exact place_id for get_place_details instead of searching by name."
                ),
                "selected_index": selection_index + 1,
                "selected_venue": selected_item,
            }
        )
        return f"{SELECTION_SYSTEM_MARKER}\n{json.dumps(selection_payload, ensure_ascii=True, separators=(',', ':'))}"

    def _extract_intake_answers_from_messages(
        self,
        raw_messages: Optional[List[Dict[str, Any]]],
    ) -> Optional[ToolChatIntakeAnswers]:
        intake_message = self._extract_tagged_system_message(raw_messages, INTAKE_SYSTEM_MARKER)
        if not intake_message:
            return None

        values: Dict[str, Optional[str]] = {
            "city_area": None,
            "venue_setting": None,
            "cuisine": None,
            "date_time_or_month": None,
        }
        field_prefixes = {
            "city_area": "- city/area:",
            "venue_setting": "- venue setting:",
            "cuisine": "- cuisine:",
            "date_time_or_month": "- date/time or month:",
        }

        for raw_line in intake_message.splitlines():
            line = raw_line.strip()
            for field_name, prefix in field_prefixes.items():
                if not line.lower().startswith(prefix):
                    continue
                value = line[len(prefix):].strip()
                values[field_name] = None if value == "unknown" else value
                break

        try:
            return ToolChatIntakeAnswers.model_validate(values)
        except Exception:
            logger.exception("Failed to parse intake answers from hidden system message.")
            return None

    def _canonicalize_arguments(self, raw_arguments: str) -> str:
        try:
            parsed = json.loads(raw_arguments)
        except json.JSONDecodeError:
            return raw_arguments
        return json.dumps(parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    def _should_skip_venue_search(
        self,
        *,
        tool_name: str,
        arguments: Optional[Dict[str, Any]],
        intake_answers: Optional[ToolChatIntakeAnswers],
    ) -> bool:
        if tool_name != "search_venues" or not arguments or not intake_answers:
            return False
        if intake_answers.venue_setting != "home":
            return False
        city = str(arguments.get("city") or "").strip().lower()
        if city and intake_answers.city_area and city != intake_answers.city_area.strip().lower():
            return False
        return True

    def _venue_shortlist_from_response(
        self,
        payload: Any,
        *,
        arguments: Optional[Dict[str, Any]] = None,
    ) -> Optional[VenueShortlistResponse]:
        if not payload:
            return None
        response = GooglePlacesSearchResponse.model_validate(payload)
        if response.tool_name != "search_venues":
            return None

        arguments = arguments or {}
        venue_setting = str(arguments.get("venue_setting") or "either")
        cuisine = arguments.get("cuisine")
        guest_count = arguments.get("guest_count")
        indoor_outdoor = str(arguments.get("indoor_outdoor") or "either")
        event_type = str(arguments.get("event_type") or "event")
        budget = arguments.get("budget")

        items = [
            VenueShortlistItem(
                place_id=candidate.place_id,
                name=candidate.name,
                formatted_address=candidate.formatted_address,
                rating=candidate.rating,
                user_rating_count=candidate.user_rating_count,
                price_level=candidate.price_level,
                fit_score=candidate.fit_score,
                fit_reasons=candidate.fit_reasons,
                google_maps_uri=candidate.google_maps_uri,
            )
            for candidate in response.candidates[: response.page_size]
        ]
        return VenueShortlistResponse(
            items=items,
            search_context=VenueShortlistSearchContext(
                city_area=str(arguments.get("city") or response.city),
                venue_setting=venue_setting if venue_setting in {"restaurant", "event_space", "either"} else "either",
                cuisine=cuisine,
                event_type=event_type,
                guest_count=guest_count,
                budget=BudgetRange.model_validate(budget) if budget else None,
                indoor_outdoor=indoor_outdoor,
                page_size=arguments.get("page_size") or response.page_size,
                next_page_token=response.next_page_token,
                query=response.query,
            ),
            has_more=bool(response.next_page_token),
        )


tool_chat_runner = ToolChatRunner.from_settings()

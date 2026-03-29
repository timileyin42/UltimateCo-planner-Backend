from types import SimpleNamespace

import pytest

from app.services.tool_chat_service import ToolChatRunner


class FakeCompletions:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


class FakeClient:
    def __init__(self, responses):
        self.completions = FakeCompletions(responses)
        self.chat = SimpleNamespace(completions=self.completions)


def make_completion(message):
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


@pytest.mark.asyncio
async def test_tool_chat_runner_returns_preflight_when_first_prompt_is_missing_answers():
    fake_client = FakeClient([])
    runner = ToolChatRunner(
        client=fake_client,
        default_model="gpt-test",
        is_configured=True,
    )

    result = await runner.run_turn(
        user_prompt="Plan a birthday dinner.",
        messages=[],
    )

    assert result["assistant_message"] is None
    assert result["max_tool_rounds_reached"] is False
    assert result["tool_trace"] == []
    assert result["preflight"]["complete"] is False
    assert set(result["preflight"]["missing_fields"]) == {
        "city_area",
        "venue_setting",
        "cuisine",
        "date_time_or_month",
    }
    assert fake_client.completions.calls == []
    assert result["messages"][0]["role"] == "system"


@pytest.mark.asyncio
async def test_tool_chat_runner_dedupes_same_turn_tool_calls_and_returns_shortlist():
    tool_arguments = (
        '{"city":"Lekki, Lagos, Nigeria","event_type":"birthday dinner","indoor_outdoor":"indoor",'
        '"guest_count":20,"venue_setting":"restaurant","cuisine":"Nigerian","page_size":10}'
    )
    tool_call_message = SimpleNamespace(
        content=None,
        tool_calls=[
            SimpleNamespace(
                id="call_1",
                type="function",
                function=SimpleNamespace(
                    name="search_venues",
                    arguments=tool_arguments,
                ),
            ),
            SimpleNamespace(
                id="call_2",
                type="function",
                function=SimpleNamespace(
                    name="search_venues",
                    arguments=tool_arguments,
                ),
            ),
        ],
    )
    final_message = SimpleNamespace(content="Here are your first 10 venues.", tool_calls=None)
    fake_client = FakeClient([make_completion(tool_call_message), make_completion(final_message)])
    runner = ToolChatRunner(
        client=fake_client,
        default_model="gpt-test",
        is_configured=True,
    )
    invoke_calls = []

    async def fake_invoke_tool(name, arguments):
        invoke_calls.append((name, arguments))
        return {
            "tool_name": "search_venues",
            "query": "Nigerian restaurant in Lekki, Lagos, Nigeria",
            "city": "Lekki, Lagos, Nigeria",
            "included_type": "restaurant",
            "page_size": 10,
            "returned_count": 1,
            "next_page_token": "page-2",
            "search_uri": "https://maps.google.com/search/test",
            "candidates": [
                {
                    "place_id": "place-1",
                    "name": "Skyline Rooftop",
                    "formatted_address": "10 Admiralty Way, Lekki",
                    "rating": 4.7,
                    "user_rating_count": 210,
                    "price_level": "PRICE_LEVEL_MODERATE",
                    "fit_score": 0.91,
                    "fit_reasons": ["Matches restaurant search intent"],
                    "google_maps_uri": "https://maps.google.com/?cid=place-1",
                }
            ],
            "assumptions": ["Google price levels are relative hints, not hard quotes."],
        }

    runner.invoke_tool = fake_invoke_tool

    result = await runner.run_turn(
        user_prompt="Plan a birthday dinner in Lekki next Friday at 7pm.",
        messages=[],
        preflight_answers={
            "city_area": "Lekki, Lagos, Nigeria",
            "venue_setting": "restaurant",
            "cuisine": "Nigerian",
            "date_time_or_month": "Next Friday at 7pm",
        },
    )

    assert result["assistant_message"]["content"] == "Here are your first 10 venues."
    assert result["max_tool_rounds_reached"] is False
    assert len(invoke_calls) == 1
    assert len(result["tool_trace"]) == 2
    assert result["tool_trace"][0]["cache_hit"] is False
    assert result["tool_trace"][1]["cache_hit"] is True
    assert result["venue_shortlist"]["has_more"] is True
    assert result["venue_shortlist"]["search_context"]["city_area"] == "Lekki, Lagos, Nigeria"
    assert result["venue_shortlist"]["search_context"]["venue_setting"] == "restaurant"
    assert result["venue_shortlist"]["search_context"]["event_type"] == "birthday dinner"
    assert result["messages"][0]["role"] == "system"
    assert result["messages"][1]["content"].startswith("[tool_chat_intake]")

    first_call = fake_client.completions.calls[0]
    assert first_call["model"] == "gpt-test"
    assert first_call["tool_choice"] == "auto"
    assert first_call["messages"][0]["role"] == "system"
    assert first_call["messages"][1]["content"].startswith("[tool_chat_intake]")

    second_call = fake_client.completions.calls[1]
    assert second_call["messages"][-1]["role"] == "tool"
    assert second_call["messages"][-2]["tool_calls"][0]["function"]["name"] == "search_venues"


@pytest.mark.asyncio
async def test_tool_chat_runner_injects_selected_venue_place_id_from_shortlist_state():
    final_message = SimpleNamespace(content="I will use the selected place id.", tool_calls=None)
    fake_client = FakeClient([make_completion(final_message)])
    runner = ToolChatRunner(
        client=fake_client,
        default_model="gpt-test",
        is_configured=True,
    )

    shortlist = {
        "items": [
            {
                "place_id": "google-place-123",
                "name": "Ox restaurant & lounge",
                "formatted_address": "31 Kofo Abayomi St, Victoria Island, Lagos, Nigeria",
                "google_maps_uri": "https://maps.google.com/?cid=google-place-123",
            }
        ],
        "search_context": {
            "city_area": "Victoria Island, Lagos, Nigeria",
            "venue_setting": "restaurant",
            "event_type": "birthday dinner",
            "guest_count": 20,
            "budget": None,
            "indoor_outdoor": "either",
            "page_size": 10,
            "next_page_token": None,
            "query": "restaurant in Victoria Island, Lagos, Nigeria",
        },
        "has_more": False,
    }
    shortlist_message = runner._build_shortlist_system_message(  # noqa: SLF001
        runner._venue_shortlist_from_response(  # noqa: SLF001
            {
                "tool_name": "search_venues",
                "query": "restaurant in Victoria Island, Lagos, Nigeria",
                "city": "Victoria Island, Lagos, Nigeria",
                "page_size": 10,
                "returned_count": 1,
                "candidates": shortlist["items"],
                "assumptions": [],
            },
            arguments={
                "city": "Victoria Island, Lagos, Nigeria",
                "event_type": "birthday dinner",
                "guest_count": 20,
                "venue_setting": "restaurant",
                "indoor_outdoor": "either",
                "page_size": 10,
            },
        )
    )

    result = await runner.run_turn(
        user_prompt="Use venue #1: Ox restaurant & lounge, lunch is fine.",
        messages=[
            {"role": "system", "content": runner.default_system_prompt},
            {"role": "system", "content": shortlist_message},
        ],
    )

    assert result["assistant_message"]["content"] == "I will use the selected place id."
    first_call = fake_client.completions.calls[0]
    selection_system_messages = [
        message["content"]
        for message in first_call["messages"]
        if message["role"] == "system" and isinstance(message.get("content"), str)
    ]
    assert any("google-place-123" in message for message in selection_system_messages)

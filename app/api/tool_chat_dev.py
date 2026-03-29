from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.core.config import settings
from app.services.tool_chat_service import DEFAULT_TOOL_CHAT_SYSTEM_PROMPT

router = APIRouter()


@router.get("/tool-chat-dev", response_class=HTMLResponse)
async def tool_chat_dev_page() -> HTMLResponse:
    default_model = json.dumps(settings.OPENAI_MODEL)
    default_system_prompt = json.dumps(DEFAULT_TOOL_CHAT_SYSTEM_PROMPT)
    api_path = json.dumps(f"{settings.API_V1_STR}/tool-chat-dev/message")
    more_venues_path = json.dumps(f"{settings.API_V1_STR}/tool-chat-dev/venues/more")

    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>Tool Chat Dev</title>
        <style>
            :root {
                --bg: #f6f0e8;
                --panel: rgba(255, 250, 244, 0.88);
                --panel-strong: rgba(255, 247, 239, 0.98);
                --ink: #201816;
                --muted: #6d5f58;
                --line: rgba(83, 56, 42, 0.15);
                --accent: #bf5a36;
                --accent-2: #21433a;
                --assistant: #fff4ea;
                --user: #1f2a27;
                --user-ink: #f8f4ee;
                --trace-ok: #e8f4eb;
                --trace-error: #fdeceb;
                --shadow: 0 24px 60px rgba(32, 24, 22, 0.1);
            }

            * { box-sizing: border-box; }

            body {
                margin: 0;
                min-height: 100vh;
                font-family: "Avenir Next", "Segoe UI", sans-serif;
                color: var(--ink);
                background:
                    radial-gradient(circle at top left, rgba(255, 214, 178, 0.85), transparent 30%),
                    radial-gradient(circle at top right, rgba(191, 90, 54, 0.14), transparent 28%),
                    linear-gradient(180deg, #fbf5ee 0%, var(--bg) 100%);
            }

            .shell {
                width: min(1380px, calc(100vw - 32px));
                margin: 24px auto;
                padding: 20px;
                border: 1px solid var(--line);
                border-radius: 24px;
                background: rgba(255, 252, 247, 0.8);
                box-shadow: var(--shadow);
                backdrop-filter: blur(16px);
            }

            .topbar {
                display: flex;
                justify-content: space-between;
                gap: 16px;
                align-items: start;
                margin-bottom: 18px;
            }

            .eyebrow {
                display: inline-flex;
                align-items: center;
                gap: 8px;
                padding: 6px 10px;
                border-radius: 999px;
                background: rgba(191, 90, 54, 0.08);
                color: var(--accent);
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 0.08em;
                text-transform: uppercase;
            }

            h1 {
                margin: 10px 0 6px;
                font-family: Georgia, "Times New Roman", serif;
                font-size: clamp(2rem, 4vw, 3.2rem);
                line-height: 0.95;
                letter-spacing: -0.04em;
            }

            .lede {
                margin: 0;
                max-width: 760px;
                color: var(--muted);
                font-size: 14px;
                line-height: 1.6;
            }

            .notice {
                max-width: 360px;
                padding: 14px 16px;
                border-radius: 16px;
                border: 1px solid rgba(191, 90, 54, 0.22);
                background: rgba(255, 243, 235, 0.92);
                color: #693321;
                font-size: 13px;
                line-height: 1.55;
            }

            .grid {
                display: grid;
                grid-template-columns: 1.55fr 0.95fr;
                gap: 18px;
            }

            .stack {
                display: grid;
                gap: 18px;
                min-height: 0;
            }

            .panel {
                min-height: 0;
                border-radius: 20px;
                border: 1px solid var(--line);
                background: var(--panel);
                overflow: hidden;
            }

            .panel-head {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 14px 16px;
                border-bottom: 1px solid var(--line);
                background: var(--panel-strong);
            }

            .panel-head h2 {
                margin: 0;
                font-size: 15px;
                letter-spacing: 0.02em;
            }

            .panel-head span {
                color: var(--muted);
                font-size: 12px;
            }

            .chat-log, .trace-log {
                height: 400px;
                overflow: auto;
                padding: 16px;
            }

            .shortlist-log {
                max-height: 360px;
                overflow: auto;
                padding: 16px;
            }

            .empty {
                display: grid;
                place-items: center;
                min-height: 180px;
                padding: 24px;
                border: 1px dashed var(--line);
                border-radius: 18px;
                color: var(--muted);
                text-align: center;
                background: rgba(255, 255, 255, 0.35);
            }

            .message {
                max-width: 86%;
                margin-bottom: 14px;
                padding: 14px 16px;
                border-radius: 18px;
                white-space: pre-wrap;
                line-height: 1.55;
                font-size: 14px;
            }

            .message.user {
                margin-left: auto;
                background: var(--user);
                color: var(--user-ink);
                border-bottom-right-radius: 4px;
            }

            .message.assistant {
                background: var(--assistant);
                color: var(--ink);
                border-bottom-left-radius: 4px;
                border: 1px solid rgba(191, 90, 54, 0.12);
            }

            .message-meta {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 8px;
                font-size: 11px;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                color: var(--muted);
            }

            .trace-card {
                margin-bottom: 12px;
                padding: 14px;
                border-radius: 16px;
                border: 1px solid var(--line);
                background: rgba(255, 255, 255, 0.62);
            }

            .trace-card.ok { background: var(--trace-ok); }
            .trace-card.error { background: var(--trace-error); }

            .trace-card h3 {
                margin: 0 0 8px;
                font-size: 14px;
            }

            .trace-meta {
                color: var(--muted);
                font-size: 12px;
                margin-bottom: 10px;
            }

            .trace-card pre,
            .raw pre {
                margin: 0;
                overflow: auto;
                padding: 12px;
                border-radius: 12px;
                background: rgba(27, 31, 35, 0.92);
                color: #eef3f8;
                font-family: "SFMono-Regular", Menlo, Consolas, monospace;
                font-size: 12px;
                line-height: 1.55;
            }

            .settings {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 12px;
                padding: 16px;
                border-top: 1px solid var(--line);
                background: rgba(255, 255, 255, 0.42);
            }

            .field { display: grid; gap: 6px; }
            .field.hidden { display: none; }
            .field.span-2 { grid-column: span 2; }

            label {
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 0.05em;
                text-transform: uppercase;
                color: var(--muted);
            }

            input, select, textarea, button {
                font: inherit;
                border-radius: 14px;
                border: 1px solid var(--line);
            }

            input, select, textarea {
                width: 100%;
                padding: 12px 14px;
                background: rgba(255, 255, 255, 0.8);
                color: var(--ink);
            }

            textarea { resize: vertical; min-height: 108px; }

            .intake-panel {
                padding: 16px;
                border-top: 1px solid var(--line);
                background: rgba(255, 255, 255, 0.46);
            }

            .intake-copy {
                margin: 0 0 12px;
                color: var(--muted);
                font-size: 13px;
                line-height: 1.6;
            }

            .intake-grid {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 12px;
            }

            .intake-summary {
                margin-top: 12px;
                display: grid;
                gap: 8px;
            }

            .summary-row {
                padding: 10px 12px;
                border-radius: 14px;
                border: 1px solid var(--line);
                background: rgba(255, 255, 255, 0.66);
                font-size: 13px;
            }

            .summary-row strong {
                display: block;
                margin-bottom: 4px;
                font-size: 11px;
                letter-spacing: 0.06em;
                text-transform: uppercase;
                color: var(--muted);
            }

            .composer {
                padding: 16px;
                border-top: 1px solid var(--line);
                background: var(--panel-strong);
            }

            .composer-actions {
                display: flex;
                gap: 10px;
                justify-content: flex-end;
                margin-top: 12px;
            }

            button {
                cursor: pointer;
                padding: 12px 16px;
                font-weight: 700;
                background: var(--accent);
                color: #fff;
                border-color: transparent;
            }

            button.secondary {
                background: transparent;
                color: var(--accent-2);
                border-color: rgba(33, 67, 58, 0.2);
            }

            button:disabled { opacity: 0.6; cursor: wait; }

            .status {
                padding: 0 16px 16px;
                color: var(--muted);
                font-size: 13px;
            }

            details.raw {
                margin: 0 16px 16px;
                border-radius: 16px;
                border: 1px solid var(--line);
                background: rgba(255, 255, 255, 0.55);
                overflow: hidden;
            }

            details.raw summary {
                cursor: pointer;
                padding: 12px 14px;
                font-weight: 700;
            }

            .raw pre { border-radius: 0; }

            .venue-card {
                margin-bottom: 12px;
                padding: 16px;
                border-radius: 18px;
                border: 1px solid var(--line);
                background: rgba(255, 255, 255, 0.68);
            }

            .venue-card h3 {
                margin: 0 0 6px;
                font-size: 16px;
            }

            .venue-meta {
                margin: 0 0 10px;
                color: var(--muted);
                font-size: 13px;
                line-height: 1.55;
            }

            .venue-pills {
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
                margin: 0 0 12px;
            }

            .venue-pill {
                padding: 6px 10px;
                border-radius: 999px;
                background: rgba(33, 67, 58, 0.09);
                color: var(--accent-2);
                font-size: 12px;
                font-weight: 700;
            }

            .venue-links {
                display: flex;
                gap: 10px;
                flex-wrap: wrap;
            }

            .venue-links a,
            .venue-links button {
                padding: 10px 12px;
                border-radius: 12px;
                border: 1px solid rgba(33, 67, 58, 0.18);
                background: transparent;
                color: var(--accent-2);
                font-size: 13px;
                font-weight: 700;
                text-decoration: none;
            }

            .venue-actions {
                padding: 0 16px 16px;
            }

            .venue-id {
                margin: 0 0 12px;
                padding: 10px 12px;
                border-radius: 12px;
                background: rgba(32, 24, 22, 0.06);
                color: var(--muted);
                font-family: "SFMono-Regular", Menlo, Consolas, monospace;
                font-size: 11px;
                line-height: 1.5;
                overflow-wrap: anywhere;
            }

            .dev-details {
                margin: 0 16px 16px;
                border-radius: 16px;
                border: 1px solid var(--line);
                background: rgba(255, 255, 255, 0.55);
                overflow: hidden;
            }

            .dev-details summary {
                cursor: pointer;
                padding: 12px 14px;
                font-weight: 700;
                list-style: none;
            }

            .dev-details summary::-webkit-details-marker {
                display: none;
            }

            .dev-details[open] summary {
                border-bottom: 1px solid var(--line);
                background: rgba(255, 247, 239, 0.75);
            }

            .dev-body {
                padding: 0;
            }

            @media (max-width: 980px) {
                .topbar, .grid { grid-template-columns: 1fr; display: grid; }
                .notice { max-width: none; }
                .settings { grid-template-columns: 1fr; }
                .intake-grid { grid-template-columns: 1fr; }
                .field.span-2 { grid-column: span 1; }
                .chat-log, .trace-log { height: 320px; }
            }
        </style>
    </head>
    <body>
        <main class="shell">
            <section class="topbar">
                <div>
                    <div class="eyebrow">Dev Harness</div>
                    <h1>Tool calling from a real page.</h1>
                    <p class="lede">This page keeps the event-planning flow front and center: intake first, message thread second, venue shortlist third. Developer controls and traces stay tucked away unless you need them.</p>
                </div>
                <aside class="notice">
                    Google Places-backed tools will fail here the same way they fail in the CLI until your Places API access is fixed. That is expected behavior for this harness.
                </aside>
            </section>

            <section class="grid">
                <div class="panel">
                    <div class="panel-head">
                        <h2>Conversation</h2>
                        <span id="message-count">0 visible messages</span>
                    </div>
                    <div class="chat-log" id="chat-log"></div>
                    <section class="intake-panel">
                        <h2 style="margin: 0 0 8px; font-size: 15px;">Quick Intake</h2>
                        <p class="intake-copy" id="intake-copy">These answers are injected before the first model/tool round so the backend can avoid repeated venue and vendor searches.</p>
                        <div class="intake-grid">
                            <div class="field" data-intake-field="city_area">
                                <label for="city-area">City / Area</label>
                                <input id="city-area" type="text" placeholder="Lekki, Lagos, Nigeria" />
                            </div>
                            <div class="field" data-intake-field="venue_setting">
                                <label for="venue-setting">Venue Type</label>
                                <select id="venue-setting">
                                    <option value="">Select one</option>
                                    <option value="home">Home</option>
                                    <option value="restaurant">Restaurant</option>
                                    <option value="event_space">Event Space</option>
                                </select>
                            </div>
                            <div class="field" data-intake-field="cuisine">
                                <label for="cuisine">Cuisine</label>
                                <input id="cuisine" type="text" placeholder="Nigerian swallows, continental, barbecue" />
                            </div>
                            <div class="field" data-intake-field="date_time_or_month">
                                <label for="date-time-or-month">Date / Time</label>
                                <input id="date-time-or-month" type="text" placeholder="Next Friday at 7pm" />
                            </div>
                        </div>
                        <div class="intake-summary" id="intake-summary"></div>
                    </section>
                    <div class="composer">
                        <div class="field">
                            <label for="user-message">Message</label>
                            <textarea id="user-message" placeholder="Ask the planner something that should trigger tools."></textarea>
                        </div>
                        <div class="composer-actions">
                            <button class="secondary" id="reset-button" type="button">Reset</button>
                            <button id="send-button" type="button">Send</button>
                        </div>
                    </div>
                    <div class="status" id="status">Ready.</div>
                    <details class="dev-details">
                        <summary>Developer Settings</summary>
                        <div class="dev-body">
                            <div class="settings">
                                <div class="field">
                                    <label for="model">Model</label>
                                    <input id="model" type="text" />
                                </div>
                                <div class="field">
                                    <label for="tool-choice">Tool Choice</label>
                                    <select id="tool-choice">
                                        <option value="auto">auto</option>
                                        <option value="required">required</option>
                                        <option value="none">none</option>
                                    </select>
                                </div>
                                <div class="field">
                                    <label for="temperature">Temperature</label>
                                    <input id="temperature" type="number" min="0" max="2" step="0.1" value="0.2" />
                                </div>
                                <div class="field">
                                    <label for="max-rounds">Max Tool Rounds</label>
                                    <input id="max-rounds" type="number" min="1" max="20" step="1" value="8" />
                                </div>
                                <div class="field span-2">
                                    <label for="system-prompt">System Prompt</label>
                                    <textarea id="system-prompt"></textarea>
                                </div>
                            </div>
                            <div class="status" id="settings-hint"></div>
                        </div>
                    </details>
                    <details class="dev-details raw">
                        <summary>Raw Conversation JSON</summary>
                        <pre id="raw-json"></pre>
                    </details>
                </div>

                <div class="stack">
                    <div class="panel">
                        <div class="panel-head">
                            <h2>Venue Shortlist</h2>
                            <span id="shortlist-count">0 venues</span>
                        </div>
                        <div class="shortlist-log" id="shortlist-log"></div>
                        <div class="venue-actions">
                            <button id="more-venues-button" type="button" class="secondary">Show 10 more</button>
                        </div>
                    </div>

                    <details class="dev-details">
                        <summary>Developer Trace</summary>
                        <div class="dev-body">
                            <div class="panel-head">
                                <h2>Tool Trace</h2>
                                <span id="trace-count">0 tool calls</span>
                            </div>
                            <div class="trace-log" id="trace-log"></div>
                        </div>
                    </details>
                </div>
            </section>
        </main>

        <script>
            const API_PATH = __API_PATH__;
            const MORE_VENUES_PATH = __MORE_VENUES_PATH__;
            const DEFAULT_MODEL = __DEFAULT_MODEL__;
            const DEFAULT_SYSTEM_PROMPT = __DEFAULT_SYSTEM_PROMPT__;
            const STORAGE_VERSION = "2026-03-26-v3";
            const STORAGE_KEYS = {
                version: "tool-chat-dev.version",
                messages: "tool-chat-dev.messages",
                trace: "tool-chat-dev.trace",
                settings: "tool-chat-dev.settings",
                preflight: "tool-chat-dev.preflight",
                preflightAnswers: "tool-chat-dev.preflight-answers",
                shortlist: "tool-chat-dev.shortlist"
            };

            if (window.localStorage.getItem(STORAGE_KEYS.version) !== STORAGE_VERSION) {
                Object.values(STORAGE_KEYS).forEach((key) => window.localStorage.removeItem(key));
                window.localStorage.setItem(STORAGE_KEYS.version, STORAGE_VERSION);
            }

            const state = {
                messages: loadJson(STORAGE_KEYS.messages, []),
                trace: loadJson(STORAGE_KEYS.trace, []),
                settings: loadJson(STORAGE_KEYS.settings, null),
                preflight: loadJson(STORAGE_KEYS.preflight, null),
                preflightAnswers: loadJson(STORAGE_KEYS.preflightAnswers, {}),
                shortlist: loadJson(STORAGE_KEYS.shortlist, null),
                sending: false,
            };

            const elements = {
                chatLog: document.getElementById("chat-log"),
                traceLog: document.getElementById("trace-log"),
                shortlistLog: document.getElementById("shortlist-log"),
                rawJson: document.getElementById("raw-json"),
                messageCount: document.getElementById("message-count"),
                traceCount: document.getElementById("trace-count"),
                shortlistCount: document.getElementById("shortlist-count"),
                status: document.getElementById("status"),
                settingsHint: document.getElementById("settings-hint"),
                model: document.getElementById("model"),
                toolChoice: document.getElementById("tool-choice"),
                temperature: document.getElementById("temperature"),
                maxRounds: document.getElementById("max-rounds"),
                systemPrompt: document.getElementById("system-prompt"),
                userMessage: document.getElementById("user-message"),
                intakeCopy: document.getElementById("intake-copy"),
                intakeSummary: document.getElementById("intake-summary"),
                cityArea: document.getElementById("city-area"),
                venueSetting: document.getElementById("venue-setting"),
                cuisine: document.getElementById("cuisine"),
                dateTimeOrMonth: document.getElementById("date-time-or-month"),
                sendButton: document.getElementById("send-button"),
                resetButton: document.getElementById("reset-button"),
                moreVenuesButton: document.getElementById("more-venues-button"),
            };

            function loadJson(key, fallback) {
                try {
                    const raw = window.localStorage.getItem(key);
                    return raw ? JSON.parse(raw) : fallback;
                } catch (_error) {
                    return fallback;
                }
            }

            function normalizeSettings(rawSettings) {
                const saved = rawSettings || {};
                const toolChoice = ["auto", "none", "required"].includes(saved.toolChoice)
                    ? saved.toolChoice
                    : "auto";
                const parsedRounds = Number(saved.maxToolRounds ?? 8);
                const maxToolRounds = Math.min(Math.max(Number.isFinite(parsedRounds) ? parsedRounds : 8, 1), 20);
                const parsedTemperature = Number(saved.temperature ?? 0.2);
                return {
                    model: saved.model || DEFAULT_MODEL,
                    toolChoice,
                    temperature: Number.isFinite(parsedTemperature) ? parsedTemperature : 0.2,
                    maxToolRounds,
                    systemPrompt: saved.systemPrompt || DEFAULT_SYSTEM_PROMPT,
                };
            }

            function readSettings() {
                return normalizeSettings({
                    model: elements.model.value.trim() || DEFAULT_MODEL,
                    toolChoice: elements.toolChoice.value,
                    temperature: Number(elements.temperature.value || 0.2),
                    maxToolRounds: Math.min(Number(elements.maxRounds.value || 8), 20),
                    systemPrompt: elements.systemPrompt.value.trim() || DEFAULT_SYSTEM_PROMPT,
                });
            }

            function readPreflightAnswers() {
                return {
                    city_area: elements.cityArea.value.trim() || undefined,
                    venue_setting: elements.venueSetting.value || undefined,
                    cuisine: elements.cuisine.value.trim() || undefined,
                    date_time_or_month: elements.dateTimeOrMonth.value.trim() || undefined,
                };
            }

            function mergeAnswers(base, incoming) {
                const merged = { ...(base || {}) };
                Object.entries(incoming || {}).forEach(([key, value]) => {
                    if (value) {
                        merged[key] = value;
                    }
                });
                return merged;
            }

            function persist() {
                state.preflightAnswers = mergeAnswers(state.preflightAnswers, readPreflightAnswers());
                window.localStorage.setItem(STORAGE_KEYS.messages, JSON.stringify(state.messages));
                window.localStorage.setItem(STORAGE_KEYS.trace, JSON.stringify(state.trace));
                window.localStorage.setItem(STORAGE_KEYS.preflight, JSON.stringify(state.preflight));
                window.localStorage.setItem(STORAGE_KEYS.preflightAnswers, JSON.stringify(state.preflightAnswers));
                window.localStorage.setItem(STORAGE_KEYS.shortlist, JSON.stringify(state.shortlist));
                window.localStorage.setItem(STORAGE_KEYS.settings, JSON.stringify(readSettings()));
            }

            function applySettings() {
                const saved = normalizeSettings(state.settings);
                elements.model.value = saved.model;
                elements.toolChoice.value = saved.toolChoice;
                elements.temperature.value = String(saved.temperature);
                elements.maxRounds.value = String(saved.maxToolRounds);
                elements.systemPrompt.value = saved.systemPrompt;
            }

            function applyPreflightAnswers() {
                const answers = state.preflightAnswers || {};
                elements.cityArea.value = answers.city_area || "";
                elements.venueSetting.value = answers.venue_setting || "";
                elements.cuisine.value = answers.cuisine || "";
                elements.dateTimeOrMonth.value = answers.date_time_or_month || "";
            }

            function visibleMessages() {
                return state.messages.filter((message) => message.role === "user" || message.role === "assistant");
            }

            function missingPreflightFields() {
                if (!state.preflight || state.preflight.complete !== false) {
                    return [];
                }
                const answers = readPreflightAnswers();
                return (state.preflight.missing_fields || []).filter((fieldId) => !answers[fieldId]);
            }

            function renderMessages() {
                const messages = visibleMessages();
                elements.messageCount.textContent = `${messages.length} visible messages`;

                if (!messages.length) {
                    elements.chatLog.innerHTML = `<div class="empty">Your browser is holding the compact conversation state. Send a prompt to start the intake and tool loop.</div>`;
                    return;
                }

                elements.chatLog.innerHTML = messages.map((message) => {
                    const content = escapeHtml(message.content || (message.tool_calls ? "Assistant requested tools." : ""));
                    const hasToolCalls = Array.isArray(message.tool_calls) && message.tool_calls.length;
                    const meta = hasToolCalls ? `${message.tool_calls.length} tool call${message.tool_calls.length === 1 ? "" : "s"}` : "message";
                    return `
                        <article class="message ${message.role}">
                            <div class="message-meta">
                                <span>${message.role}</span>
                                <span>${meta}</span>
                            </div>
                            <div>${content.replace(new RegExp("\\n", "g"), "<br />")}</div>
                        </article>
                    `;
                }).join("");
                elements.chatLog.scrollTop = elements.chatLog.scrollHeight;
            }

            function renderTrace() {
                elements.traceCount.textContent = `${state.trace.length} tool call${state.trace.length === 1 ? "" : "s"}`;

                if (!state.trace.length) {
                    elements.traceLog.innerHTML = `<div class="empty">Tool execution details will appear here once the model asks for a function.</div>`;
                    return;
                }

                elements.traceLog.innerHTML = state.trace.map((entry) => {
                    const ok = entry.result && entry.result.ok;
                    return `
                        <section class="trace-card ${ok ? "ok" : "error"}">
                            <h3>${escapeHtml(entry.tool_name || "unknown_tool")}</h3>
                            <div class="trace-meta">tool_call_id: ${escapeHtml(entry.tool_call_id || "n/a")} | cache_hit: ${entry.cache_hit ? "yes" : "no"}</div>
                            <pre>${escapeHtml(JSON.stringify(entry.arguments ?? entry.raw_arguments, null, 2))}</pre>
                            <div class="trace-meta" style="margin: 10px 0 8px;">result</div>
                            <pre>${escapeHtml(JSON.stringify(entry.result, null, 2))}</pre>
                        </section>
                    `;
                }).join("");
                elements.traceLog.scrollTop = elements.traceLog.scrollHeight;
            }

            function renderPreflight() {
                const missing = state.preflight && state.preflight.complete === false
                    ? (state.preflight.missing_fields || [])
                    : [];
                const answers = state.preflightAnswers || {};

                document.querySelectorAll("[data-intake-field]").forEach((fieldElement) => {
                    const fieldId = fieldElement.getAttribute("data-intake-field");
                    const visible = !missing.length || missing.includes(fieldId);
                    fieldElement.classList.toggle("hidden", !visible);
                });

                if (missing.length) {
                    elements.intakeCopy.textContent = "Fill only the missing answers below. The backend will inject them before the first model call and then continue with the original prompt.";
                } else {
                    elements.intakeCopy.textContent = "These answers are injected before the first model/tool round so the backend can avoid repeated venue and vendor searches.";
                }

                const summaryItems = [
                    ["City / Area", answers.city_area],
                    ["Venue Type", answers.venue_setting],
                    ["Cuisine", answers.cuisine],
                    ["Date / Time", answers.date_time_or_month],
                ].filter(([, value]) => value);

                if (!summaryItems.length) {
                    elements.intakeSummary.innerHTML = "";
                    return;
                }

                elements.intakeSummary.innerHTML = summaryItems.map(([label, value]) => `
                    <div class="summary-row">
                        <strong>${escapeHtml(label)}</strong>
                        <span>${escapeHtml(value)}</span>
                    </div>
                `).join("");
            }

            function renderShortlist() {
                const shortlist = state.shortlist;
                const items = shortlist && Array.isArray(shortlist.items) ? shortlist.items : [];
                elements.shortlistCount.textContent = `${items.length} venue${items.length === 1 ? "" : "s"}`;
                elements.moreVenuesButton.disabled = state.sending || !(shortlist && shortlist.has_more);

                if (!items.length) {
                    elements.shortlistLog.innerHTML = `<div class="empty">Venue recommendations with Google Maps links will appear here after a venue search.</div>`;
                    return;
                }

                elements.shortlistLog.innerHTML = items.map((item, index) => {
                    const fitReasons = Array.isArray(item.fit_reasons) ? item.fit_reasons : [];
                    const rating = item.rating != null
                        ? `${item.rating}${item.user_rating_count != null ? ` (${item.user_rating_count} ratings)` : ""}`
                        : "n/a";
                    return `
                        <article class="venue-card">
                            <h3>${index + 1}. ${escapeHtml(item.name || "Unnamed venue")}</h3>
                            <p class="venue-meta">${escapeHtml(item.formatted_address || "No address provided")}</p>
                            <div class="venue-pills">
                                <span class="venue-pill">Rating: ${escapeHtml(rating)}</span>
                                <span class="venue-pill">Price: ${escapeHtml(item.price_level || "n/a")}</span>
                                <span class="venue-pill">Fit score: ${escapeHtml(item.fit_score ?? "0")}</span>
                            </div>
                            <p class="venue-meta">${escapeHtml(fitReasons.join(", ") || "No fit reasons available.")}</p>
                            <div class="venue-id">Place ID: ${escapeHtml(item.place_id || "n/a")}</div>
                            <div class="venue-links">
                                <button type="button" data-use-venue="${index}">Use this venue</button>
                                ${item.google_maps_uri ? `<a href="${escapeHtml(item.google_maps_uri)}" target="_blank" rel="noopener noreferrer">Open in Google Maps</a>` : ""}
                            </div>
                        </article>
                    `;
                }).join("");
            }

            function renderRaw() {
                elements.rawJson.textContent = JSON.stringify(
                    {
                        messages: state.messages,
                        preflight: state.preflight,
                        preflight_answers: state.preflightAnswers,
                        venue_shortlist: state.shortlist,
                    },
                    null,
                    2
                );
            }

            function render() {
                renderMessages();
                renderTrace();
                renderPreflight();
                renderShortlist();
                renderRaw();
                renderSettingsHint();
                persist();
            }

            function renderSettingsHint() {
                const settings = readSettings();
                const toolChoiceHint = settings.toolChoice === "required"
                    ? "required forces a tool call every assistant round and commonly causes loop warnings."
                    : `${settings.toolChoice} lets the model stop naturally once it has enough tool output.`;
                elements.settingsHint.textContent = `Effective tool choice: ${settings.toolChoice}. Effective server cap: ${settings.maxToolRounds} rounds, but the API route will never exceed 20. ${toolChoiceHint}`;
            }

            function setStatus(text) {
                elements.status.textContent = text;
            }

            function setSending(sending) {
                state.sending = sending;
                elements.sendButton.disabled = sending;
                elements.resetButton.disabled = sending;
                elements.moreVenuesButton.disabled = sending || !(state.shortlist && state.shortlist.has_more);
            }

            function escapeHtml(value) {
                return String(value)
                    .replace(new RegExp("&", "g"), "&amp;")
                    .replace(new RegExp("<", "g"), "&lt;")
                    .replace(new RegExp(">", "g"), "&gt;")
                    .replace(new RegExp('"', "g"), "&quot;")
                    .replace(new RegExp("'", "g"), "&#39;");
            }

            async function sendMessage() {
                const message = elements.userMessage.value.trim();
                if (!message || state.sending) {
                    return;
                }

                const blockedFields = missingPreflightFields();
                if (blockedFields.length) {
                    setStatus(`Fill the missing intake fields first: ${blockedFields.join(", ")}`);
                    return;
                }

                const settings = readSettings();
                state.preflightAnswers = mergeAnswers(state.preflightAnswers, readPreflightAnswers());
                setSending(true);
                setStatus("Running tool loop...");

                try {
                    const response = await fetch(API_PATH, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            user_message: message,
                            messages: state.messages,
                            preflight_answers: state.preflightAnswers,
                            model: settings.model,
                            system_prompt: settings.systemPrompt,
                            tool_choice: settings.toolChoice,
                            temperature: settings.temperature,
                            max_tool_rounds: settings.maxToolRounds,
                        }),
                    });

                    const payload = await response.json();
                    if (!response.ok) {
                        throw new Error(payload.detail || "Request failed.");
                    }

                    state.messages = Array.isArray(payload.messages) ? payload.messages : [];
                    if (Array.isArray(payload.tool_trace) && payload.tool_trace.length) {
                        state.trace = state.trace.concat(payload.tool_trace);
                    }
                    if (payload.preflight) {
                        state.preflight = payload.preflight;
                        state.preflightAnswers = mergeAnswers(state.preflightAnswers, payload.preflight.collected);
                        applyPreflightAnswers();
                    }
                    if (payload.venue_shortlist) {
                        state.shortlist = payload.venue_shortlist;
                    }

                    if (!payload.preflight || payload.preflight.complete !== false) {
                        elements.userMessage.value = "";
                    }
                    render();
                    if (payload.preflight && payload.preflight.complete === false) {
                        setStatus(payload.warning || "Fill the missing intake answers, then send again.");
                    } else {
                        setStatus(payload.warning || "Turn completed.");
                    }
                } catch (error) {
                    setStatus(`Error: ${error.message}`);
                } finally {
                    setSending(false);
                }
            }

            async function loadMoreVenues() {
                if (state.sending || !state.shortlist || !state.shortlist.has_more) {
                    return;
                }

                setSending(true);
                setStatus("Loading 10 more venue options...");

                try {
                    const response = await fetch(MORE_VENUES_PATH, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            search_context: state.shortlist.search_context,
                            page_token: state.shortlist.search_context.next_page_token,
                        }),
                    });

                    const payload = await response.json();
                    if (!response.ok) {
                        throw new Error(payload.detail || "Request failed.");
                    }

                    state.shortlist = payload.venue_shortlist;
                    render();
                    setStatus("Loaded more venue options.");
                } catch (error) {
                    setStatus(`Error: ${error.message}`);
                } finally {
                    setSending(false);
                }
            }

            function resetConversation() {
                state.messages = [];
                state.trace = [];
                state.preflight = null;
                state.preflightAnswers = {};
                state.shortlist = null;
                window.localStorage.removeItem(STORAGE_KEYS.messages);
                window.localStorage.removeItem(STORAGE_KEYS.trace);
                window.localStorage.removeItem(STORAGE_KEYS.preflight);
                window.localStorage.removeItem(STORAGE_KEYS.preflightAnswers);
                window.localStorage.removeItem(STORAGE_KEYS.shortlist);
                applyPreflightAnswers();
                render();
                setStatus("Conversation reset. The next send will start with the current system prompt.");
            }

            elements.sendButton.addEventListener("click", sendMessage);
            elements.resetButton.addEventListener("click", resetConversation);
            elements.moreVenuesButton.addEventListener("click", loadMoreVenues);
            elements.shortlistLog.addEventListener("click", (event) => {
                const target = event.target.closest("[data-use-venue]");
                if (!target) {
                    return;
                }
                const index = Number(target.getAttribute("data-use-venue"));
                const item = state.shortlist && Array.isArray(state.shortlist.items) ? state.shortlist.items[index] : null;
                if (!item) {
                    return;
                }
                const mapsLinkSegment = item.google_maps_uri ? ` Google Maps link: ${item.google_maps_uri}.` : "";
                elements.userMessage.value = `Use venue #${index + 1}: ${item.name}. Google Place ID: ${item.place_id}.${mapsLinkSegment}`;
                elements.userMessage.focus();
                setStatus(`Composer updated with venue #${index + 1}. Send when ready.`);
            });
            elements.userMessage.addEventListener("keydown", (event) => {
                if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
                    sendMessage();
                }
            });

            [
                elements.model,
                elements.toolChoice,
                elements.temperature,
                elements.maxRounds,
                elements.systemPrompt,
                elements.cityArea,
                elements.venueSetting,
                elements.cuisine,
                elements.dateTimeOrMonth
            ].forEach((element) => {
                element.addEventListener("change", persist);
                element.addEventListener("input", persist);
            });

            applySettings();
            applyPreflightAnswers();
            render();
            setStatus("Ready. Press Cmd/Ctrl+Enter to send.");
        </script>
    </body>
    </html>
    """

    html = html.replace("__API_PATH__", api_path)
    html = html.replace("__MORE_VENUES_PATH__", more_venues_path)
    html = html.replace("__DEFAULT_MODEL__", default_model)
    html = html.replace("__DEFAULT_SYSTEM_PROMPT__", default_system_prompt)
    return HTMLResponse(content=html)

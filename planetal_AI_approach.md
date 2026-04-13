Budget Per person 
https://clawhub.ai/1kalin/afrexai-event-planner



Yes — this is a very good app idea, and the cleanest version is **not** “one giant chatbot that knows everything.” The cost-effective version is:

1. use a strong general model for conversation and decision-making,
2. give it a small set of tools,
3. keep your own app logic in charge of budgets, approvals, and state.

That pattern is usually cheaper and more reliable than trying to make the model do everything on its own. OpenAI’s current stack explicitly supports function/tool calling and agent workflows, and recommends models like GPT-5.4 for higher-end agentic work and GPT-5 mini for lower cost and latency. ([OpenAI Developers][1])

## Conversation script

Here is a cleaner **product-ready conversation script** you can use in your app.

### Event Planning Assistant Script

**Assistant:**
Hi! I’m Cassian. I can help you plan your event from idea to shortlist.
Tell me what you want to organize.

**User:**
I want to throw a birthday dinner for 20 people with ₦200k.

**Assistant:**
Lovely. I can help with venue ideas, catering, décor, entertainment, and a simple task plan.
Do you already have a date in mind?

**User:**
August 8th.

**Assistant:**
Great. What kind of vibe are you going for — casual, elegant, intimate, lively, indoor, or outdoor?

**User:**
Indoors.

**Assistant:**
Perfect. Would you prefer a restaurant-style experience, or a private setup with catering?

**User:**
Private setup with catering.

**Assistant:**
Nice choice. What kind of food would you like — local, continental, or a mix?

**User:**
A mix.

**Assistant:**
Got it. Should I also include décor and light entertainment within your ₦200k budget?

**User:**
Yes.

**Assistant:**
Perfect. I’ll put together a plan with:

* venue suggestions,
* food and catering ideas,
* décor options,
* light entertainment,
* and a simple action checklist.

Before I do that, what city should I search in?

**User:**
Lagos.

**Assistant:**
Great — searching Lagos for indoor birthday-friendly venues and vendors that fit your budget.

**Tool calls happen here**

* Search nearby venues
* Check venue details
* Find caterers
* Find décor vendors
* Find light entertainment options

**Assistant:**
Here’s a first shortlist for your birthday dinner in Lagos:

**Option 1:** Cozy café/private venue
Estimated total: ₦170k–₦210k
Best for: intimate birthday dinner

**Option 2:** Small event space + external catering
Estimated total: ₦180k–₦230k
Best for: more privacy and custom setup

**Option 3:** Restaurant private room
Estimated total: ₦190k–₦250k
Best for: easiest coordination

My best fit for your budget is **Option 1**. Want me to show 3 venue choices with pros, estimated spend, and next steps?

**User:**
Yes.

**Assistant:**
Here are 3 options, ranked by fit…

**Assistant:**
Would you like me to:

1. lock a preferred venue shortlist,
2. build a full event budget,
3. create a task timeline,
4. or draft inquiry messages to vendors?

---

## The better product flow

For this kind of app, I would structure the assistant into **four layers**:

**1. Chat layer**
Handles natural conversation, asks clarifying questions, keeps the tone warm.

**2. Planning layer**
Turns user answers into structured state:

* event type
* guest count
* budget
* date
* city
* vibe
* venue preference
* cuisine
* extras

**3. Tool layer**
Calls real services for live data:

* Google Places / Maps for venues
* web search for vendors, entertainers, decorators
* your own pricing templates
* calendar / reminders later if needed

**4. Decision layer**
Your backend, not the model, should decide:

* whether something fits the budget
* whether to ask approval before calling expensive tools
* whether to save a shortlist
* whether to trigger bookings or send inquiries

This is usually the sweet spot for cost and reliability because the model does the language and reasoning, while your app handles deterministic business logic.

## Do you need tool calling?

Yes. For this use case, **tool calling is important**.

The model will not reliably know current venue availability, real businesses, pricing, or locations by memory alone. Function calling exists specifically so the model can call external systems and APIs using structured schemas. OpenAI supports this directly in the API, and DeepSeek and Qwen also document function-calling support. AnythingLLM also supports MCP/custom tools, though it is more of an orchestration shell than the thing I would choose as the core production brain for this product. ([OpenAI Developers][1])

For your app, I’d start with these tools only:

* `search_venues(city, event_type, indoor_outdoor, guest_count, budget)`
* `get_place_details(place_id)`
* `search_caterers(city, cuisine, budget_range)`
* `search_decorators(city, vibe, budget_range)`
* `search_entertainment(city, event_type, budget_range)`
* `generate_budget_breakdown(...)`
* `create_task_plan(date, event_type)`

That is enough to build a very convincing first version.

## OpenAI vs self-hosted vs AnythingLLM

My honest recommendation:

### Best practical starting point

Use **OpenAI API + your own backend tools**.

Why:

* strongest out-of-the-box reliability for conversational UX,
* mature function/tool calling,
* good latency/cost options across model sizes,
* less engineering pain than running and tuning open models yourself. ([OpenAI Developers][1])

### When self-hosted makes sense

Use self-hosted only if:

* you expect very high volume,
* you have infra/GPU skills,
* privacy or data residency is critical,
* or you want tighter control over serving costs.

Otherwise, teams often underestimate the ops cost of hosting, evaluating, routing, updating, and monitoring open models.

### Where AnythingLLM fits

AnythingLLM is useful as a **developer console / internal prototype / agent shell**. It supports external models, MCP, and custom tools. But for a consumer app you’re building, I would usually rather own the backend orchestration directly than make AnythingLLM the center of the production system. ([anythingllm.com][2])

## Which model would I recommend?

### If you want the safest recommendation

Use **GPT-5 mini** first.

Why:

* much cheaper than frontier-tier GPT-5.4,
* designed as a lower-cost GPT-5 option,
* still supports modern tool-based workflows,
* likely the best balance for “chat + planning + tool selection.” ([OpenAI Developers][3])

OpenAI’s current model docs position GPT-5.4 as the top frontier model, while GPT-5 mini is the lower-latency, lower-cost choice. GPT-5 mini pricing is listed at **$0.25 / 1M input tokens** and **$2.00 / 1M output tokens**; GPT-5 nano is even cheaper at **$0.05 / 1M input** and **$0.40 / 1M output**, but I would treat nano more as a classifier/router/extractor than your main planner brain. GPT-5.4 is substantially more expensive. ([OpenAI Developers][3])

### If you want lowest API spend from hosted models

Look hard at **DeepSeek**.

DeepSeek’s docs show OpenAI-compatible API access, function calling, and very low listed prices compared with frontier closed models. That makes it attractive for cost-sensitive planning/chat products, especially if you can tolerate more evaluation work and occasional quality variance. ([api-docs.deepseek.com][4])

### If you want open-source / self-hostable

Look at:

* **gpt-oss-20b** for local/specialized use,
* **gpt-oss-120b** if you have serious GPU resources,
* **Qwen** if you want a mature open ecosystem with documented function calling. ([OpenAI][5])

OpenAI says gpt-oss-20b is intended for low-latency local or specialized use cases, while gpt-oss-120b aims much higher but needs much heavier hardware. OpenAI also states the 120B variant can run efficiently on a single 80 GB GPU, while the 20B model can run on devices with 16 GB memory. ([OpenAI][5])

### My plain-English ranking for your use case

For an event-planning app:

**Best overall to launch:** GPT-5 mini
**Cheapest hosted option worth testing:** DeepSeek
**Best self-host/open route:** Qwen or gpt-oss-20b
**Not my first production choice for the core app:** AnythingLLM as the main runtime

## Most cost-effective approach

The most cost-effective setup is usually **hybrid**, not fully premium and not fully self-hosted.

### Recommended stack

* **Main assistant:** GPT-5 mini
* **Cheap extraction/router tasks:** GPT-5 nano or simple backend logic
* **Places lookup:** Google Places API
* **Web/vendor lookup:** your own web search tool or vendor DB
* **Budgeting/task plan:** deterministic backend code
* **Memory/state:** your database, not the model context alone

That gives you good UX without paying frontier-model prices on every turn. OpenAI’s pricing page also notes cached input pricing and Batch API discounts, which can matter once you scale repeated prompts or offline jobs. ([OpenAI Developers][6])

### Why this beats “one open-source model for everything”

Because your app has two different jobs:

* chat naturally,
* fetch/update real-world data.

Open models can do both, but once you add hosting, monitoring, retries, evaluation, and tool reliability, they are often **not** the cheapest end-to-end choice for an early-stage product.

## What about Google Places API costs?

Google Maps Platform pricing is now usage-based by SKU, and Google documents both pay-as-you-go pricing and subscription-style plans. Their pricing pages note free monthly usage thresholds for qualifying SKUs and a trial credit for new customers. That means Places can be affordable if you keep calls tight and avoid wasteful autocomplete/search loops. ([Google for Developers][7])

To control Places costs:

* only call Places after the user gives a city and intent,
* debounce autocomplete,
* cache place details,
* store shortlisted venues in your DB,
* don’t re-query identical searches,
* ask permission before doing broad vendor searches.

## My recommendation for you, specifically

I would build **version 1** like this:

* **Frontend:** simple chat UI
* **Backend:** Node or Python
* **Model:** GPT-5 mini
* **Tools:** Google Places + one web search tool + your own budgeting/task planner functions
* **Database:** Postgres/Supabase/Firebase for user state and saved plans
* **No self-hosting yet**

Then test real conversations and measure:

* cost per completed event plan,
* number of turns per session,
* venue lookup success,
* user satisfaction with suggestions.

Only after you have usage data would I test replacing parts with DeepSeek or a self-hosted Qwen/gpt-oss path.

## The simplest product decision

If you want the **lowest risk launch**: choose **OpenAI + tool calling**.
If you want the **lowest token cost and are okay with more engineering risk**: test **DeepSeek**.
If you want **maximum control and self-hosting**: test **Qwen** or **gpt-oss-20b**. ([OpenAI Developers][3])

I can sketch the exact backend architecture and tool schemas for this event-planning assistant next.

[1]: https://developers.openai.com/api/docs/guides/function-calling/?utm_source=chatgpt.com "Function calling | OpenAI API"
[2]: https://anythingllm.com/?utm_source=chatgpt.com "AnythingLLM | The all-in-one AI application for everyone"
[3]: https://developers.openai.com/api/docs/models?utm_source=chatgpt.com "Models | OpenAI API"
[4]: https://api-docs.deepseek.com/?utm_source=chatgpt.com "DeepSeek API Docs: Your First API Call"
[5]: https://openai.com/index/introducing-gpt-oss/?utm_source=chatgpt.com "Introducing gpt-oss"
[6]: https://developers.openai.com/api/docs/pricing/?utm_source=chatgpt.com "Pricing | OpenAI API"
[7]: https://developers.google.com/maps/billing-and-pricing/pricing?utm_source=chatgpt.com "Google Maps Platform core services pricing list"

For your **AfrexAI Event Planner** use case, the workload is mostly **multi-turn chat, structured intake, budget/timeline generation, shortlist ranking, and light tool calling** rather than heavy coding or deep research. The skill itself is a business-event planner with templates for event type selection, budget allocation, timelines, ROI, and per-attendee budgeting, so you want a model that is good at **instruction following, structured output, and tool use** more than raw frontier reasoning. ([Termo][1])

On **4 physical EPYC cores + 32 GB RAM**, the practical sweet spot is **1B–4B**. **8B** can work for low-concurrency use, but it will feel slower. **12B** may fit in quantized form, but on 4 CPU cores I would treat it as “usable for batch/offline jobs, not ideal for live chat.” For local serving on CPU, **llama.cpp/GGUF** is the safest default, and Ollama can import GGUF if you want a simpler OpenAI-style local API. ([GitHub][2])

## Best 15 models for your box

I’m using “open-source” in the local-LLM sense here; a few are more precisely **open-weight** rather than OSI-open-source. Artificial Analysis uses that broader convention too. ([Artificial Analysis][3])

### 1) **Qwen3-4B**

Best overall fit. It is small enough to host reasonably on CPU, explicitly strong on **agent capabilities**, supports **100+ languages/dialects**, and can switch between thinking and non-thinking modes, which is useful for keeping event-planning chats responsive. ([Hugging Face][4])

### 2) **Phi-4-mini-instruct (3.8B)**

Excellent second choice. Microsoft explicitly added **function calling**, positions it for edge deployment, and the model is compact enough for constrained hardware. For an event planner that calls venue/vendor tools, this is very on-point. ([Tech Community][5])

### 3) **Gemma 3 4B**

Very strong for structured assistant work. Google documents **function calling**, official quantized checkpoints, and gives a Q4 memory figure of about **3.4 GB** for the 4B model, which is comfortable in your 32 GB server. ([Google AI for Developers][6])

### 4) **SmolLM3-3B**

One of the best compact fully open models right now. Hugging Face says it outperforms Llama 3.2 3B and Qwen2.5 3B while staying competitive with some 4B-class alternatives, which makes it a strong CPU-first planner/chat model. ([Hugging Face][7])

### 5) **Qwen3-1.7B**

Great when latency matters more than depth. Same Qwen3 family strengths—agentic behavior, multilingual support, thinking/non-thinking mode—but lighter than 4B. Good for an MVP with low hardware cost. ([Hugging Face][8])

### 6) **Llama 3.2 3B**

Still a solid local assistant model. Meta specifically says the 1B/3B instruction models are optimized for **multilingual dialogue**, **agentic retrieval**, and **summarization**, and also documents tool-calling patterns for these lightweight models. ([Hugging Face][9])

### 7) **Qwen2.5-3B-Instruct**

Older than Qwen3, but still very practical. It is good at **instruction following**, **structured output/JSON**, and long-enough context for your planning flows. This is a safe fallback if you want mature tooling and many community quantizations. ([Hugging Face][10])

### 8) **Gemma 3 1B**

Useful when you need very low resource usage. Google’s docs position Gemma 3 as lightweight, and the 1B model has an approximate Q4 memory footprint under **1 GB**. I would use this only if you prioritize speed over planning quality. ([Google AI for Developers][6])

### 9) **SmolLM2-1.7B-Instruct**

A good ultra-light option for basic intake, rewriting, and templated event outputs. Hugging Face describes it as lightweight enough to run on-device. It will not plan as well as the top 5, but it is very easy to host. ([Hugging Face][11])

### 10) **Phi-3.5-mini-instruct (3.8B)**

Still a respectable small model with **128K context** and MIT licensing. It lacks the explicit Phi-4-mini function-calling improvement, so I’d rank it below Phi-4-mini for your use case, but it remains a viable local assistant. ([Hugging Face][12])

### 11) **Qwen2.5-1.5B-Instruct**

Good for low-cost, low-latency chat and structured fields. I would use it for intake and routing, not for the full “best venue + budget + action plan” conversation unless traffic is tiny and expectations are modest. ([Hugging Face][13])

### 12) **Qwen3-0.6B**

Surprisingly capable for its size and inherits Qwen3’s agentic design, but this is now in “router/extractor” territory rather than “main planner brain.” Useful for classifying event types, extracting city/date/budget, or deciding which backend tool to call. ([Hugging Face][14])

### 13) **Llama 3.2 1B**

Meta designed the 1B/3B line for constrained environments. This is acceptable for light chat, rewriting, summaries, and form-filling, but I would not trust it alone for nuanced vendor shortlists or budget tradeoffs. ([Hugging Face][9])

### 14) **Gemma 3 270M**

Not a full event-planning brain, but useful as a tiny specialist. Google introduced it specifically as a compact model for **task-specific fine-tuning** with strong instruction following and text structuring. ([Google Developers Blog][15])

### 15) **FunctionGemma 270M**

Only include this if you want a **dedicated tool-calling micro-model** beside a main planner. Google says it is a specialized Gemma 3 270M variant tuned for **function calling** and intended as a base for custom local agents, not as a general chat model. ([Google AI for Developers][16])

## My actual shortlist for you

If I were deploying on **your exact server**, I would narrow it to this:

**Best overall:** **Qwen3-4B**
**Best alternative:** **Phi-4-mini-instruct**
**Best Google-family pick:** **Gemma 3 4B**
**Best fully open compact pick:** **SmolLM3-3B**
**Best “tiny but usable” pick:** **Qwen3-1.7B** ([Hugging Face][4])

## What I would avoid on this machine

I would avoid making **8B+** your primary live-chat model on 4 physical CPU cores unless you are okay with noticeably slower responses. That includes otherwise-strong models like **Qwen3-8B** or **Gemma 3 12B**. They fit the RAM story much better than the CPU story. Google’s own memory table shows Gemma 3 12B can be quantized down substantially, but the compute cost still rises with model size. ([Google AI for Developers][17])

## Recommended deployment pattern

For this event-planner product, I would not use one model for everything.

Use:

* **Main chat/planner:** Qwen3-4B or Phi-4-mini-instruct
* **Optional tiny router/tool model:** Qwen3-0.6B or FunctionGemma
* **Serving:** llama.cpp with GGUF, or Ollama on top of GGUF for easier API wiring ([GitHub][2])

That gives you the best balance of:

* quality for multi-step planning,
* enough structure for budgets/timelines,
* workable latency on CPU,
* and future room to add vendor/venue tool calls.

My plain ranking for your hardware is:

1. Qwen3-4B
2. Phi-4-mini-instruct
3. Gemma 3 4B
4. SmolLM3-3B
5. Qwen3-1.7B
6. Llama 3.2 3B
7. Qwen2.5-3B-Instruct
8. Gemma 3 1B
9. SmolLM2-1.7B-Instruct
10. Phi-3.5-mini-instruct
11. Qwen2.5-1.5B-Instruct
12. Qwen3-0.6B
13. Llama 3.2 1B
14. Gemma 3 270M
15. FunctionGemma 270M

If you want, I can turn this into a **deployment matrix** with **estimated RAM target, expected latency class, and exact Ollama/llama.cpp model choices** for your server.

[1]: https://termo.ai/skills/afrexai-event-planner?utm_source=chatgpt.com "Event Planner Pro — AI Skill — Termo"
[2]: https://github.com/ggml-org/llama.cpp?utm_source=chatgpt.com "ggml-org/llama.cpp: LLM inference in C/C++"
[3]: https://artificialanalysis.ai/models/open-source/tiny "Tiny Open Source Models | Artificial Analysis"
[4]: https://huggingface.co/Qwen/Qwen3-4B "Qwen/Qwen3-4B · Hugging Face"
[5]: https://techcommunity.microsoft.com/blog/educatordeveloperblog/welcome-to-the-new-phi-4-models---microsoft-phi-4-mini--phi-4-multimodal/4386037 "Welcome to the new Phi-4 models - Microsoft Phi-4-mini & Phi-4-multimodal"
[6]: https://ai.google.dev/gemma/docs/core "Gemma 3 model overview  |  Google AI for Developers"
[7]: https://huggingface.co/blog/smollm3 "SmolLM3: smol, multilingual, long-context reasoner"
[8]: https://huggingface.co/Qwen/Qwen3-1.7B "Qwen/Qwen3-1.7B · Hugging Face"
[9]: https://huggingface.co/meta-llama/Llama-3.2-3B "meta-llama/Llama-3.2-3B · Hugging Face"
[10]: https://huggingface.co/Qwen/Qwen2.5-3B-Instruct "Qwen/Qwen2.5-3B-Instruct · Hugging Face"
[11]: https://huggingface.co/HuggingFaceTB/SmolLM2-1.7B-Instruct?utm_source=chatgpt.com "HuggingFaceTB/SmolLM2-1.7B-Instruct"
[12]: https://huggingface.co/microsoft/Phi-3.5-mini-instruct?utm_source=chatgpt.com "microsoft/Phi-3.5-mini-instruct"
[13]: https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct?utm_source=chatgpt.com "Qwen/Qwen2.5-1.5B-Instruct"
[14]: https://huggingface.co/Qwen/Qwen3-0.6B "Qwen/Qwen3-0.6B · Hugging Face"
[15]: https://developers.googleblog.com/en/introducing-gemma-3-270m/?utm_source=chatgpt.com "Introducing Gemma 3 270M: The compact model for hyper- ..."
[16]: https://ai.google.dev/gemma/docs/functiongemma?utm_source=chatgpt.com "FunctionGemma model overview | Google AI for Developers"
[17]: https://ai.google.dev/gemma/docs/core?utm_source=chatgpt.com "Gemma 3 model overview | Google AI for Developers"

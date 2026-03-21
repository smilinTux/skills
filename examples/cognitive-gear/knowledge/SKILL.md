---
name: cognitive-gear
description: Switch between cognitive modes — SPRINT (fast), CRUISE (normal), and DEEP DIVE (research). Each mode configures the right model + memory depth for the task. Use when the user says "sprint mode", "cruise mode", "deep dive", "go fast", "think deep", "research mode", or asks to switch operational modes.
---

# Cognitive Gear — Operational Modes

Three gears. Pick the one that matches the task.

## Modes

### 🏎️ SPRINT — Fast execution
**When:** Quick answers, casual chat, simple lookups, routine tasks, "just do it" energy.
**Model:** Sonnet-class or equivalent fast model with tool support.
**Memory:** `skmemory_search` only (keyword match, instant).
**Thinking:** Off.
**Behavior:** Answer in 1-3 sentences. No deep analysis. Ship it.

**Trigger:** `/gear sprint`, "go fast", "sprint mode", "quick mode"

### 🚗 CRUISE — Balanced work (DEFAULT)
**When:** Project work, code review, planning, email drafts, multi-step tasks.
**Model:** Opus-class or equivalent deep reasoning model with tools.
**Memory:** `skmemory_search` + `skmemory_context` (tiered loading).
**Thinking:** Adaptive (model decides).
**Behavior:** Full answers with context. Check memory before responding about people/projects. Normal depth.

**Trigger:** `/gear cruise`, "normal mode", "cruise mode"

### 🔬 DEEP DIVE — Research & analysis
**When:** Complex analysis, cross-referencing projects, connecting dots, strategic planning, investigating issues, "figure this out" tasks.
**Model:** Opus-class with extended thinking enabled.
**Memory:** Full stack — all layers fired:
1. `skmemory_search` — keyword memories
2. `skmemory_search_deep` — full-content deep search
3. `memory_search` — MEMORY.md + memory/*.md files (daily notes, journals)
4. `skmemory_context` — tiered context loading
5. Notion pages when project-relevant
6. Nextcloud/Drive files when collaboration-relevant

**Thinking:** On (extended/streaming).
**Behavior:** Thorough. Cross-reference multiple sources. Call out contradictions. Synthesize across memory layers. Take your time.

**Trigger:** `/gear deep`, "deep dive", "research mode", "think deep", "figure this out"

## Memory Protocol Reference

| Layer | SPRINT | CRUISE | DEEP DIVE |
|-------|--------|--------|-----------|
| skmemory_search | ✅ | ✅ | ✅ |
| skmemory_search_deep | ❌ | ❌ | ✅ |
| skmemory_context | ❌ | ✅ | ✅ |
| memory_search (files) | ❌ | ❌ | ✅ |
| memory_get (file snippets) | ❌ | ❌ | ✅ |
| Notion/Nextcloud/Drive | ❌ | As needed | ✅ always |

## Switching Gears

When switching:
1. Set the model via `session_status(model=...)` or equivalent
2. Announce the shift (one line): 🏎️ / 🚗 / 🔬
3. Follow the memory protocol for that gear on all subsequent responses

## Cost Awareness

- SPRINT: Cheapest — fast model, minimal memory calls
- CRUISE: Moderate — deep model, standard memory
- DEEP DIVE: Most expensive — deep model + thinking + exhaustive memory search

Proactively suggest downshifting when deep dive has been running for a while without need.

## Model Mapping (Reference)

Agents should map these to their available models:

| Gear | OpenClaw Alias | Anthropic | Notes |
|------|---------------|-----------|-------|
| SPRINT | `claude` | claude-sonnet-4 | Or `kimi`, `fast` |
| CRUISE | `opus` | claude-opus-4 | Default daily driver |
| DEEP DIVE | `opus` + thinking | claude-opus-4 | Extended thinking on |

Local alternatives for SPRINT: `default` (qwen2.5:7b), `kimi` (kimi-k2).
Local alternatives for CRUISE/DEEP: `smart` (deepseek-r1:14b) for reasoning-only tasks.

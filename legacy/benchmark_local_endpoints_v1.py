#!/usr/bin/env python3
import os
import sys
import json
import time
import uuid
import re
import socket
import urllib.request
import urllib.error
import subprocess
import argparse
from hashlib import sha256
from pathlib import Path

# Endpoints
OSAURUS_URL = "http://localhost:1337/v1/chat/completions"
OMLX_URL = "http://localhost:8100/v1/chat/completions"
OPTIQ_URL = "http://127.0.0.1:8080/v1/chat/completions"
OPTIQ_MODELS_URL = "http://127.0.0.1:8080/v1/models"

# Load environment file
def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())

load_env_file(Path.home() / ".local-model-tools" / ".env")
OMLX_KEY = os.environ.get("OMLX_KEY", "")

# Fallback regex tokenizer
def fallback_tokenize(text: str) -> int:
    # Splits on words and individual punctuation marks, matching typical LLM token tokenization closely
    tokens = re.findall(r"\w+|[^\w\s]", text)
    return len(tokens)

# Get macOS memory stats via vm_stat
def get_macos_memory_stats() -> dict:
    stats = {}
    try:
        res = subprocess.run(["vm_stat"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        for line in res.stdout.splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                stats[key.strip()] = val.strip().replace(".", "")
    except Exception:
        pass
    return stats

# Extract raw pageable memory from vm_stat page sizes
def get_memory_pressure_summary() -> str:
    stats = get_macos_memory_stats()
    if not stats:
        return "Unknown (vm_stat failed)"
    try:
        page_size = 4096  # macOS page size is 4KB
        free = int(stats.get("Pages free", 0)) * page_size / (1024**3)
        active = int(stats.get("Pages active", 0)) * page_size / (1024**3)
        inactive = int(stats.get("Pages inactive", 0)) * page_size / (1024**3)
        speculative = int(stats.get("Pages speculative", 0)) * page_size / (1024**3)
        wired = int(stats.get("Pages wired down", 0)) * page_size / (1024**3)
        occupied = active + inactive + speculative + wired
        return f"Wired: {wired:.1f}GB, Free: {free:.1f}GB, Total Occupied: {occupied:.1f}GB"
    except Exception:
        return "Error parsing memory stats"

# Run a single completion request
def run_completion_request(url: str, api_key: str, model: str, prompt: str, max_tokens: int = 512, temperature: float = 0.0) -> dict:
    headers = {
        "Content-Type": "application/json"
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    data = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "temperature": temperature,
        "top_p": 1.0,
        "max_tokens": max_tokens,
        "stream_options": {
            "include_usage": True
        }
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    start_time = time.perf_counter()
    ttft = None
    chunk_count = 0
    full_response = []
    reasoning_response = []

    usage_prompt_tokens = None
    usage_completion_tokens = None
    usage_total_tokens = None
    finish_reason = "unknown"

    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            for line in response:
                line = line.decode("utf-8").strip()
                if not line.startswith("data: "):
                    continue

                data_str = line[6:]
                if data_str == "[DONE]":
                    break

                try:
                    chunk = json.loads(data_str)
                    chunk_count += 1

                    # Parse usage if present in chunk
                    usage = chunk.get("usage")
                    if usage:
                        usage_prompt_tokens = usage.get("prompt_tokens")
                        usage_completion_tokens = usage.get("completion_tokens")
                        usage_total_tokens = usage.get("total_tokens")

                    choices = chunk.get("choices", [])
                    if choices:
                        choice = choices[0]
                        finish_reason = choice.get("finish_reason") or finish_reason
                        delta = choice.get("delta", {})

                        content = delta.get("content", "")
                        reasoning = delta.get("reasoning_content", "")

                        if content or reasoning:
                            if ttft is None:
                                ttft = time.perf_counter() - start_time
                            if content:
                                full_response.append(content)
                            if reasoning:
                                reasoning_response.append(reasoning)
                except Exception:
                    continue
    except urllib.error.URLError as e:
        return {"error": f"Connection error: {e.reason}"}
    except socket.timeout:
        return {"error": "Timeout error"}
    except Exception as e:
        return {"error": f"General failure: {str(e)}"}

    end_time = time.perf_counter()
    total_time = end_time - start_time
    text = "".join(full_response)

    # Fallback to regex tokenizer if usage is missing
    if usage_completion_tokens is None:
        full_generated_text = "".join(reasoning_response) + text
        usage_completion_tokens = fallback_tokenize(full_generated_text)
        usage_prompt_tokens = fallback_tokenize(prompt)
        usage_total_tokens = usage_completion_tokens + usage_prompt_tokens
        used_fallback = True
    else:
        used_fallback = False

    # Check for empty generation / fake success
    if (usage_completion_tokens or 0) == 0 and len(text.strip()) == 0:
        return {"error": "Empty completion / 0 tokens (Server returned OK but no content)"}

    # Calculate throughput metrics
    generation_time = total_time - (ttft or 0)
    tps = usage_completion_tokens / generation_time if usage_completion_tokens > 0 and generation_time > 0 else 0
    cps = len(text) / generation_time if len(text) > 0 and generation_time > 0 else 0

    # Validate JSON structured output
    is_valid_json = False
    if "{" in text and "}" in text:
        start_idx = text.find("{")
        end_idx = text.rfind("}")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            json_str = text[start_idx:end_idx + 1]
            # Strip markdown fences if present
            if json_str.startswith("```"):
                lines = json_str.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                json_str = "\n".join(lines).strip()
            try:
                json.loads(json_str)
                is_valid_json = True
            except Exception:
                pass

    return {
        "ttft_ms": round((ttft or 0) * 1000, 2) if ttft else None,
        "total_time_s": round(total_time, 2),
        "prompt_tokens": usage_prompt_tokens,
        "completion_tokens": usage_completion_tokens,
        "total_tokens": usage_total_tokens,
        "tokens_per_second": round(tps, 2),
        "chars_per_second": round(cps, 2),
        "chunk_count": chunk_count,
        "chars_count": len(text),
        "text": text,
        "finish_reason": finish_reason,
        "used_fallback": used_fallback,
        "is_valid_json": is_valid_json,
        "sha256": sha256(text.encode("utf-8")).hexdigest()[:10],
        "empty": len(text.strip()) == 0,
        "truncated": finish_reason == "length"
    }

# Statistical aggregator
# Distinguishes "no valid samples" (count=0, stats=None) from "samples that happen to be 0",
# so a metric that was never captured (e.g. TTFT never observed) can't be displayed as a real 0.0.
def aggregate_stats(values: list[float]) -> dict:
    n = len(values)
    if n == 0:
        return {"mean": None, "median": None, "min": None, "max": None, "stddev": None, "count": 0}
    mean = sum(values) / n
    sorted_vals = sorted(values)
    median = sorted_vals[n // 2] if n % 2 != 0 else (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2
    variance = sum((x - mean) ** 2 for x in values) / n
    stddev = variance ** 0.5
    return {
        "mean": round(mean, 2),
        "median": round(median, 2),
        "min": round(min(values), 2),
        "max": round(max(values), 2),
        "stddev": round(stddev, 2),
        "count": n
    }

def fmt_stat(value, suffix: str = "") -> str:
    return "N/A" if value is None else f"{value:.1f}{suffix}" if isinstance(value, float) else f"{value}{suffix}"

# Decide whether runs in a single category must be uniformly retokenized.
# Per the methodology handoff: if usage is unavailable/inconsistent between endpoints,
# every endpoint in that comparison must be tokenized the same way, not mixed.
def needs_uniform_fallback(runs: list[dict]) -> bool:
    methods = {r.get("used_fallback") for r in runs if "error" not in r}
    return len(methods) > 1

def apply_uniform_fallback(run: dict, prompt: str) -> None:
    run["completion_tokens"] = fallback_tokenize(run["text"])
    run["prompt_tokens"] = fallback_tokenize(prompt)
    run["total_tokens"] = run["completion_tokens"] + run["prompt_tokens"]
    generation_time = run["total_time_s"] - ((run["ttft_ms"] or 0) / 1000)
    run["tokens_per_second"] = round(run["completion_tokens"] / generation_time, 2) if run["completion_tokens"] > 0 and generation_time > 0 else 0
    run["used_fallback"] = True
    run["uniform_fallback_applied"] = True

# Build the compatibility matrix from actual per-target results for this scenario,
# instead of a hardcoded table copy-pasted from an unrelated model.
def build_compatibility_matrix(targets: list[dict], results: dict) -> str:
    rows = ["| Stack | Model | Loaded | Notes |", "| :--- | :--- | :--- | :--- |"]
    for target in targets:
        name = target["name"]
        model = target["model"]
        lifecycle_failure = results.get(name, {}).get("_lifecycle_failed")
        loaded = "No" if lifecycle_failure else "Yes"
        notes = lifecycle_failure if lifecycle_failure else target.get("artifact_check", "")
        rows.append(f"| {name} | `{model}` | {loaded} | {notes} |")
    return "\n".join(rows)

# Build a real interpretation from the data actually collected, instead of static filler text.
def build_interpretation(targets: list[dict], results: dict, comparison_type: str) -> str:
    lines = [f"**Declared comparison type:** {comparison_type}", ""]
    succeeded = [t["name"] for t in targets if not results.get(t["name"], {}).get("_lifecycle_failed")]
    failed = [t["name"] for t in targets if results.get(t["name"], {}).get("_lifecycle_failed")]

    if failed:
        lines.append(f"**Unavailable this run:** {', '.join(failed)} — no conclusion possible for these stacks.")
    if len(succeeded) < 2:
        lines.append("**Fewer than two stacks produced data** — no cross-stack speed comparison is possible from this run.")
        return "\n".join(lines)

    for cat in sorted({cat for name in succeeded for cat in results.get(name, {})}):
        cat_stats = {name: results[name][cat] for name in succeeded if cat in results[name] and results[name][cat].get("status") == "success"}
        if len(cat_stats) < 2:
            continue
        ranked = sorted(cat_stats.items(), key=lambda kv: (kv[1]["tokens_per_second"]["mean"] or 0), reverse=True)
        fastest_name, fastest_stats = ranked[0]
        fastest_tps = fastest_stats["tokens_per_second"]["mean"]
        fallback_note = " (fallback-tokenized for fairness)" if fastest_stats.get("uniform_fallback_applied") else ""
        lines.append(f"- **{cat}:** fastest was {fastest_name} at {fmt_stat(fastest_tps, ' tps')}{fallback_note}.")
        if fastest_stats.get("ttft_ms", {}).get("count", 0) == 0:
            lines.append(f"  - Note: TTFT was never captured for {fastest_name} in this category (see raw chunk diagnostics) — do not read its TTFT cell as a real 0ms.")

    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(description="Overhauled Local LLM Endpoint Benchmark Suite")
    parser.add_argument("--runs", type=int, default=5, help="Number of benchmark runs per prompt category (default: 5)")
    parser.add_argument("--scenario", type=str, required=True, help="The model scenario to test (e.g. gemma-4-12b)")
    args = parser.parse_args()

    # 1. Define Prompt Categories Suite
    # Long context prompt utilizes a copy of the vault onboarding policies guidelines
    long_context_prefix = """Before reading a sensitive note, the cloud-hosted agent must:
1. Tell Jason that the note's relevant content may be transmitted to the provider.
2. Identify the note or sensitive domain it proposes to read.
3. Obtain explicit current-session permission.
4. Read only the minimum material needed.
5. Avoid reproducing private details in standard notes or external outputs.
Permission to access the vault generally is not permission to transmit every sensitive note to a cloud provider.
Never read, print, copy, or store credentials unless Jason explicitly requests a narrowly scoped local troubleshooting action.
Never place these in the vault, chat, logs, Git, or generated notes:
- passwords or recovery codes
- API keys or access tokens
- private keys
- macOS Keychain secrets
- Obsidian Local REST API credentials
- Osaurus access keys
- Google Cloud service-account credentials
- Restic repository passwords
- ignored credential files
Refer only to the credential type and approved storage location.
The vault is a local-only Git repository with no remote.
- Do not add a remote.
- Do not push.
- Do not bypass validation or secret scanning.
- Do not stage or commit credentials or ignored files.
- Scheduled validated checkpoint commits are authorized only through the installed Deep Wiki maintenance workflow.
- Manual commits require the authority defined by the active Git policy.
Restic backups and Google Cloud credentials are managed outside ordinary note-writing workflows. Never edit backup repositories directly."""

    prompts = {
        "A_ShortChat": {
            "prompt": "Identify the capital of South Korea and write a single short sentence explaining its significance.",
            "max_tokens": 128
        },
        "B_MediumReasoning": {
            "prompt": "Explain why Apple Silicon unified memory is highly efficient for running large language models compared to discrete GPU setups. Write a structured response in exactly 3 bullet points.",
            "max_tokens": 512
        },
        "C_LongContext": {
            "prompt": f"Analyze the following system information rules and constraints. Explain the key safety boundaries defined. Keep your summary under 100 words.\n\n{long_context_prefix}",
            "max_tokens": 256
        },
        "D_RepeatedPrefix_Run1": {
            "prompt": f"{long_context_prefix}\n\nQuestion: What does the policy say about credential storage? Answer in one short sentence.",
            "max_tokens": 256
        },
        "D_RepeatedPrefix_Run2": {
            "prompt": f"{long_context_prefix}\n\nQuestion: What does the policy say about pushing the Git repository? Answer in one short sentence.",
            "max_tokens": 256
        },
        "E_ToolCallJSON": {
            "prompt": "Create a valid JSON object summarizing a system health check. The JSON must contain exactly three keys: 'server_status' (string, 'healthy'), 'api_latency_ms' (integer, 42), and 'active_users' (array of strings, e.g., ['jason', 'agent']). Output only the JSON object, with no other text.",
            "max_tokens": 512
        }
    }

    # 2. Define the Scenarios Matrix
    # comparison_type is an honest label per the handoff's requirement to record whether a
    # comparison is same-artifact-controlled, same-family/cross-quant, or native-best-stack.
    # None of these scenarios currently pin an identical artifact+quant across targets
    # (each target lists its own natively-preferred quant), so all are native-best-stack
    # comparisons until a same-artifact pair is explicitly configured.
    SCENARIOS = {
        "vibethinker-3b": {
            "family": "VibeThinker-3B",
            "comparison_type": "native-best-stack (unverified quant equivalence)",
            "targets": [
                {"name": "Osaurus/vMLX Native", "url": OSAURUS_URL, "key": "", "model": "vibethinker-3b-mxfp8", "artifact_check": "Native"},
                {"name": "oMLX Server Direct", "url": OMLX_URL, "key": OMLX_KEY, "model": "VibeThinker-3B-MLX-oQ4", "artifact_check": "Native"},
                {"name": "OptiQ MLX Server", "url": OPTIQ_URL, "key": "", "model": "mlx-community/VibeThinker-3B-OptiQ-4bit", "artifact_check": "OptiQ", "requires_lifecycle_check": True}
            ]
        },
        "gemma-4-12b": {
            "family": "Gemma-4-12B",
            "comparison_type": "native-best-stack (unverified quant equivalence)",
            "targets": [
                {"name": "Osaurus/vMLX Native", "url": OSAURUS_URL, "key": "", "model": "gemma-4-12b-it-qat-jang_4m", "artifact_check": "Native"},
                {"name": "oMLX Server Direct", "url": OMLX_URL, "key": OMLX_KEY, "model": "gemma-4-12B-agentic-fable5-composer2.5-v2-3.5x-tau2-oQ4-MLX", "artifact_check": "Native"},
                {"name": "OptiQ MLX Server", "url": OPTIQ_URL, "key": "", "model": "mlx-community/gemma-4-12B-it-qat-OptiQ-4bit", "artifact_check": "OptiQ", "requires_lifecycle_check": True}
            ]
        },
        "ornith-1.0-35b": {
            "family": "Ornith-1.0-35B",
            "comparison_type": "native-best-stack (unverified quant equivalence)",
            "targets": [
                {"name": "Osaurus/vMLX Native", "url": OSAURUS_URL, "key": "", "model": "ornith-1.0-35b-jang_4m", "artifact_check": "Native"},
                {"name": "oMLX Server Direct", "url": OMLX_URL, "key": OMLX_KEY, "model": "Ornith-1.0-35B-MLX-oQ4-FP16", "artifact_check": "Native"}
            ]
        },
        "nex-n2-mini": {
            "family": "Nex-N2-Mini",
            "comparison_type": "native-best-stack (unverified quant equivalence)",
            "targets": [
                {"name": "oMLX Server Direct", "url": OMLX_URL, "key": OMLX_KEY, "model": "Nex-N2-mini-oQ4", "artifact_check": "Native"},
                {"name": "OptiQ MLX Server", "url": OPTIQ_URL, "key": "", "model": "mlx-community/Nex-N2-mini-mlx-optiq-static-mixed-3_6bits", "artifact_check": "OptiQ", "requires_lifecycle_check": True}
            ]
        },
        "lfm2.5-8b": {
            "family": "LFM2.5-8B",
            "comparison_type": "native-best-stack (unverified quant equivalence)",
            "targets": [
                {"name": "Osaurus/vMLX Native", "url": OSAURUS_URL, "key": "", "model": "lfm2.5-8b-a1b-jang_2l", "artifact_check": "Native"},
                {"name": "oMLX Server Direct", "url": OMLX_URL, "key": OMLX_KEY, "model": "LFM2.5-8B-A1B-oQ4-fp16", "artifact_check": "Native"}
            ]
        },
        "qwen-agentworld-35b": {
            "family": "Qwen-AgentWorld-35B",
            "comparison_type": "native-best-stack (single stack, no cross-stack comparison possible)",
            "targets": [
                {"name": "oMLX Server Direct", "url": OMLX_URL, "key": OMLX_KEY, "model": "Qwen-AgentWorld-35B-A3B-oQ4", "artifact_check": "Native"}
            ]
        },
        "qwen-3.6-35b": {
            "family": "Qwen-3.6-35B",
            "comparison_type": "native-best-stack (single stack, no cross-stack comparison possible)",
            "targets": [
                {"name": "Osaurus/vMLX Native", "url": OSAURUS_URL, "key": "", "model": "qwen3.6-35b-a3b-mxfp4-mtp", "artifact_check": "Native"}
            ]
        },
        "diffusiongemma-26b": {
            "family": "DiffusionGemma-26B",
            "comparison_type": "native-best-stack (single stack, no cross-stack comparison possible)",
            "targets": [
                {"name": "oMLX Server Direct", "url": OMLX_URL, "key": OMLX_KEY, "model": "diffusiongemma-26B-A4B-it-mxfp4", "artifact_check": "Native"}
            ]
        }
    }

    if args.scenario not in SCENARIOS:
        print(f"Error: Unknown scenario '{args.scenario}'. Available scenarios: {', '.join(SCENARIOS.keys())}")
        sys.exit(1)

    scenario_config = SCENARIOS[args.scenario]
    targets = scenario_config["targets"]
    for t in targets:
        t["family"] = scenario_config["family"]

    results = {}

    print("Beginning Benchmark Overhaul Suite...")
    print(f"Memory Status: {get_memory_pressure_summary()}")

    # Step 1: environment/model verification check, once per target
    available_targets = []
    for target in targets:
        target_name = target["name"]
        print(f"\n==========================================")
        print(f"Target: {target_name} ({target['model']})")
        print(f"==========================================")

        try:
            models_url = target["url"].replace("/v1/chat/completions", "/v1/models")
            headers = {}
            if target.get("key"):
                headers["Authorization"] = f"Bearer {target['key']}"

            req = urllib.request.Request(models_url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as res:
                models_data = json.loads(res.read().decode("utf-8"))

            loaded_models = [m.get("id", "") for m in models_data.get("data", [])]
            model_found = any(target["model"] in m_id or m_id in target["model"] for m_id in loaded_models)

            if not model_found:
                print(f"Error: Model '{target['model']}' not loaded on server. Loaded models: {loaded_models}")
                results[target_name] = {"_lifecycle_failed": "Model Not Loaded"}
                continue

        except Exception as e:
            if target.get("requires_lifecycle_check"):
                print("Error: OptiQ server not running, see OptiQ Server and Lab Cheat Sheet")
            else:
                print(f"Error: Server Offline or unreachable at {models_url} ({str(e)})")
            results[target_name] = {"_lifecycle_failed": "Server Offline"}
            continue

        results[target_name] = {}
        available_targets.append(target)

    # Step 2: category-major loop, so fallback-tokenization consistency can be enforced
    # across every stack being compared within a single prompt category.
    for cat_name, cat_data in prompts.items():
        print(f"\nCategory: {cat_name}")
        raw_by_target = {}

        for target in available_targets:
            target_name = target["name"]
            print(f"  Warming up {target_name}...")
            warmup_res = run_completion_request(
                target["url"], target["key"], target["model"],
                cat_data["prompt"], cat_data["max_tokens"]
            )
            if "error" in warmup_res:
                print(f"    Warmup Failed: {warmup_res['error']}")
                results[target_name][cat_name] = {"status": "failed", "error": warmup_res["error"]}
                continue

            timed_runs = []
            failures = 0
            for run_idx in range(args.runs):
                print(f"  {target_name} run {run_idx + 1}/{args.runs}...")
                run_res = run_completion_request(
                    target["url"], target["key"], target["model"],
                    cat_data["prompt"], cat_data["max_tokens"]
                )
                if "error" in run_res:
                    print(f"    Run Failed: {run_res['error']}")
                    failures += 1
                else:
                    timed_runs.append(run_res)
                time.sleep(1)  # cool down

            if not timed_runs:
                results[target_name][cat_name] = {"status": "failed", "error": f"All {args.runs} runs failed"}
                continue

            raw_by_target[target_name] = {"warmup": warmup_res, "timed": timed_runs, "failures": failures}

        # Enforce uniform tokenization across this category's targets if methods are mixed
        all_runs_this_cat = []
        for d in raw_by_target.values():
            all_runs_this_cat.append(d["warmup"])
            all_runs_this_cat.extend(d["timed"])
        if needs_uniform_fallback(all_runs_this_cat):
            for run in all_runs_this_cat:
                apply_uniform_fallback(run, cat_data["prompt"])

        # Aggregate
        for target_name, d in raw_by_target.items():
            warmup_res = d["warmup"]
            timed_runs = d["timed"]
            ttfts = [r["ttft_ms"] for r in timed_runs if r["ttft_ms"] is not None]
            tps_vals = [r["tokens_per_second"] for r in timed_runs]
            total_times = [r["total_time_s"] for r in timed_runs]
            tokens_generated = [r["completion_tokens"] for r in timed_runs]
            chunks_streamed = [r["chunk_count"] for r in timed_runs]

            results[target_name][cat_name] = {
                "status": "success",
                "failures": d["failures"],
                "warmup_ttft_ms": warmup_res["ttft_ms"],
                "warmup_tps": warmup_res["tokens_per_second"],
                "ttft_ms": aggregate_stats(ttfts),
                "tokens_per_second": aggregate_stats(tps_vals),
                "total_time_s": aggregate_stats(total_times),
                "completion_tokens": aggregate_stats(tokens_generated),
                "raw_chunks": aggregate_stats(chunks_streamed),
                "json_valid_ratio": sum(1 for r in timed_runs if r["is_valid_json"]) / len(timed_runs),
                "fallback_count": sum(1 for r in timed_runs if r["used_fallback"]),
                "uniform_fallback_applied": any(r.get("uniform_fallback_applied") for r in timed_runs),
                "last_sample_text": timed_runs[-1]["text"],
                "last_sample_sha": timed_runs[-1]["sha256"]
            }

    # 3. Write Report
    date_str = time.strftime("%Y-%m-%d")
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    report_file = Path(f"/Users/jrazz/Documents/ObsidianNotes/20 Records/Projects/Local Model Stack/Tier 5/Model Benchmark Report - {args.scenario} - {date_str}.md")

    print(f"\nCompiling benchmark metrics report to: {report_file}...")

    compatibility_matrix_md = build_compatibility_matrix(targets, results)
    interpretation_md = build_interpretation(targets, results, scenario_config["comparison_type"])

    low_run_warning = ""
    if args.runs < 5:
        low_run_warning = f"\n> [!CAUTION] Low Sample Size\n> This benchmark was executed with only {args.runs} runs per category. For official baseline reporting, use the recommended minimum of 5-8 runs."

    report_markdown = f"""---
uid: {str(uuid.uuid4())}
type: record
authorship: agent
sensitivity: standard
status: active
created: {date_str}
updated: {date_str}
sources: []
supersedes: []
aliases:
  - "Model Benchmark Report - {args.scenario} - {date_str}"
  - "Local Model serving Benchmark {args.scenario} {date_str}"
---

# Local Model Serving Benchmark: {args.scenario} ({date_str})

**Execution Timestamp:** `{timestamp}`
**Warmups:** 1 warmup request per category (reported separately)
**Timed Runs:** {args.runs} timed runs averaged per prompt category
**System Memory State:** `{get_memory_pressure_summary()}`
{low_run_warning}

## Executive Summary
This report presents a corrected, multi-dimensional benchmarking evaluation of local model serving. Token counting uses API-reported `usage` fields where available; if any stack in a category lacked usage, every stack in that category was retokenized with the same fallback tokenizer for a fair comparison (see `uniform_fallback_applied` per category below).

---

## 1. Compatibility Matrix
{compatibility_matrix_md}

---

## 2. Performance Summary Table

Below is the comparative performance breakdown grouped by prompt category.

| Prompt Category / Server | Warmup TTFT | Warmup TPS | Mean TTFT (ms) | Mean TPS | StdDev TPS | Success/Runs |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""

    for cat in sorted(prompts.keys()):
        report_markdown += f"| **{cat}** | | | | | | |\n"
        for target in targets:
            name = target["name"]
            stats = results.get(name, {}).get(cat, {})
            if results.get(name, {}).get("_lifecycle_failed"):
                fail_reason = results[name]["_lifecycle_failed"]
                report_markdown += f"| {name} | Offline | - | - | - | - | {fail_reason} |\n"
            elif not stats or stats.get("status") != "success":
                err = stats.get("error", "Offline/Failed")
                report_markdown += f"| {name} | Failed | - | - | - | - | 0/{args.runs} ({err}) |\n"
            else:
                w_ttft = fmt_stat(stats['warmup_ttft_ms'], " ms") if stats['warmup_ttft_ms'] is not None else "N/A"
                w_tps = fmt_stat(stats['warmup_tps'], " tps")
                m_ttft = fmt_stat(stats['ttft_ms']['mean'], " ms")
                m_tps = fmt_stat(stats['tokens_per_second']['mean'], " tps")
                s_tps = "N/A" if stats['tokens_per_second']['stddev'] is None else f"±{stats['tokens_per_second']['stddev']:.2f}"
                success_ratio = f"{args.runs - stats['failures']}/{args.runs}"
                fallback_flag = " (fallback-tokenized)" if stats.get("uniform_fallback_applied") else ""

                report_markdown += f"| {name} | {w_ttft} | {w_tps} | {m_ttft} | {m_tps} | {s_tps} | {success_ratio}{fallback_flag} |\n"

    report_markdown += """
---

## 3. Statistical Variance Breakdown

Detailed metrics for each successful run cohort (mean, median, min, max, stddev). "N/A" means the metric was never captured for any run in that cohort — not that its true value was zero.

### Time to First Token (TTFT in ms)
| Serving Stack | Prompt Category | Mean | Median | Min | Max | StdDev | Samples |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""

    for target in targets:
        name = target["name"]
        for cat in sorted(prompts.keys()):
            stats = results.get(name, {}).get(cat, {})
            if stats and stats.get("status") == "success":
                t = stats["ttft_ms"]
                report_markdown += f"| {name} | {cat} | {fmt_stat(t['mean'])} | {fmt_stat(t['median'])} | {fmt_stat(t['min'])} | {fmt_stat(t['max'])} | {fmt_stat(t['stddev'])} | {t['count']}/{args.runs} |\n"

    report_markdown += """
### Inference Output Throughput (Real Tokens/Sec)
| Serving Stack | Prompt Category | Mean | Median | Min | Max | StdDev | Samples |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""

    for target in targets:
        name = target["name"]
        for cat in sorted(prompts.keys()):
            stats = results.get(name, {}).get(cat, {})
            if stats and stats.get("status") == "success":
                t = stats["tokens_per_second"]
                report_markdown += f"| {name} | {cat} | {fmt_stat(t['mean'])} | {fmt_stat(t['median'])} | {fmt_stat(t['min'])} | {fmt_stat(t['max'])} | {fmt_stat(t['stddev'])} | {t['count']}/{args.runs} |\n"

    # Repeated-prefix comparison evaluation
    report_markdown += """
---

## 4. Repeated Prefix Cache Evaluation
This section highlights the benefit of KV-cache reuse when running multiple turns with the same large system prompt prefix:

"""

    for target in targets:
        name = target["name"]
        run1 = results.get(name, {}).get("D_RepeatedPrefix_Run1", {})
        run2 = results.get(name, {}).get("D_RepeatedPrefix_Run2", {})

        if run1.get("status") == "success" and run2.get("status") == "success":
            r1_ttft = run1["ttft_ms"]["mean"]
            r2_ttft = run2["ttft_ms"]["mean"]
            if r1_ttft is None or r2_ttft is None:
                report_markdown += f"- **{name}:** TTFT was not captured for one or both turns — cache benefit cannot be evaluated.\n"
                continue
            diff = r1_ttft - r2_ttft
            pct = (diff / r1_ttft) * 100 if r1_ttft > 0 else 0

            report_markdown += f"- **{name}:** First Turn Avg TTFT: **{r1_ttft:.1f}ms** | Second Turn Avg TTFT: **{r2_ttft:.1f}ms** | "
            if diff > 0:
                report_markdown += f"Cache Hit Benefit: **{diff:.1f}ms faster** ({pct:.1f}% reduction in prefill latency)\n"
            else:
                report_markdown += f"No cache benefit observed ({diff:.1f}ms difference)\n"

    # Structured Output JSON correctness evaluation
    report_markdown += """
---

## 5. Structured JSON Output Correctness
Correctness rates for the JSON health check schema extraction:

"""

    for target in targets:
        name = target["name"]
        stats = results.get(name, {}).get("E_ToolCallJSON", {})
        if stats and stats.get("status") == "success":
            ratio = stats["json_valid_ratio"] * 100
            report_markdown += f"- **{name}:** JSON Syntax Validity: **{ratio:.1f}%** | Last Output SHA: `{stats['last_sample_sha']}`\n"

    report_markdown += f"""
---

## 6. Interpretation and Key Conclusions

{interpretation_md}

## 7. Next Steps & Phase 2 Setup
1. **Identical weights test:** Configure an explicit same-artifact scenario (identical model file + quantization on every stack) to answer the Controlled serving-stack question directly — no current scenario declares one.
2. **OptiQ MLX Phase:** Prepare and test `mlx-optiq` on mixed-precision models.
"""

    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(report_markdown)
    print(f"Dated report written successfully!")


def _selftest() -> None:
    # aggregate_stats: empty input must be distinguishable from real zeros
    empty = aggregate_stats([])
    assert empty["count"] == 0 and empty["mean"] is None, "empty aggregate should report None, not 0.0"
    real_zero = aggregate_stats([0.0, 0.0])
    assert real_zero["count"] == 2 and real_zero["mean"] == 0.0, "a real 0.0 sample should still show mean 0.0"

    # fmt_stat should render None as N/A and never crash on it
    assert fmt_stat(None) == "N/A"
    assert fmt_stat(12.345, " ms") == "12.3 ms"

    # needs_uniform_fallback: mixed methods across stacks in one category must be detected
    ok_run = {"used_fallback": False}
    fallback_run = {"used_fallback": True}
    error_run = {"error": "boom"}
    assert needs_uniform_fallback([ok_run, ok_run]) is False
    assert needs_uniform_fallback([ok_run, fallback_run]) is True
    assert needs_uniform_fallback([ok_run, fallback_run, error_run]) is True, "error runs should be ignored, not hide a real mismatch"

    # apply_uniform_fallback must retokenize even a run that originally had real usage
    run = {"text": "hello world", "total_time_s": 2.0, "ttft_ms": 500.0, "used_fallback": False}
    apply_uniform_fallback(run, "prompt text")
    assert run["used_fallback"] is True and run["uniform_fallback_applied"] is True
    assert run["completion_tokens"] == fallback_tokenize("hello world")

    # compatibility matrix must reflect actual lifecycle results, not a static table
    targets = [{"name": "A", "model": "model-a", "artifact_check": "Native"}, {"name": "B", "model": "model-b", "artifact_check": "OptiQ"}]
    results = {"A": {"_lifecycle_failed": "Model Not Loaded"}, "B": {}}
    matrix = build_compatibility_matrix(targets, results)
    assert "model-a" in matrix and "Model Not Loaded" in matrix
    assert "model-b" in matrix and "OptiQ" in matrix

    print("Self-check passed.")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        main()

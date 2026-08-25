"""Pre-flight live smoke test — proves all four services really answer.

The pytest suite runs fully offline (FALLBACK), which deliberately proves nothing
about the live endpoints. Run this before a demo, or from the manual
``live-smoke`` workflow, to check the real APIs:

    MAI_EXECUTION_MODE=strict python scripts/live_smoke.py

Each check is deliberately cheap (short prompts, 768x768 image). By default all
four services must be configured and pass. Use ``--allow-partial`` only to validate
an intentionally configured subset.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mai import MAIClient, audio_extension_for_mime  # noqa: E402
from mai.fallback import ENTITIES  # noqa: E402

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_region_capacity",
            "description": "Get capacity for a region.",
            "parameters": {
                "type": "object",
                "properties": {"region": {"type": "string"}},
                "required": ["region"],
            },
        },
    }
]


def missing_services(cfg) -> list[str]:
    readiness = {
        "Thinking-1": cfg.foundry_ready,
        "Image": cfg.image_ready,
        "Voice-2": cfg.speech_ready,
        "Transcribe-1.5": cfg.transcribe_ready,
    }
    return [name for name, ready in readiness.items() if not ready]


def main(client: MAIClient | None = None, allow_partial: bool = False) -> int:
    client = client or MAIClient()
    cfg = client.cfg
    mode = "strict" if cfg.strict else "demo"
    print(f"MAI live smoke test (execution mode: {mode})")
    if not cfg.strict:
        print("  note: in demo mode a failure degrades to fallback and is reported, not raised.")

    missing = missing_services(cfg)
    if missing and not allow_partial:
        print(f"FAILED: full validation requires configuration for {', '.join(missing)}")
        print("Use --allow-partial only when intentionally validating a configured subset.")
        return 1

    results: list[tuple[str, bool, str]] = []

    def record(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name} {detail}")

    # ── Thinking-1: a short answer, then a tool call ───────────────────────────
    if cfg.foundry_ready:
        try:
            resp = client.chat_completion(
                [{"role": "user", "content": "Reply with exactly: OK"}],
                max_completion_tokens=4096,
            )
            content = (resp["choices"][0]["message"].get("content") or "").strip()
            record("Thinking-1 chat", bool(content), f"-> {content[:40]!r}")
        except Exception as exc:
            record("Thinking-1 chat", False, str(exc)[:160])

        try:
            msg = None
            for kind, val in client.chat_completion_stream(
                [{"role": "user", "content": "Use the tool for eastus."}],
                tools=TOOLS,
                # This budget includes hidden reasoning and visible output.
                max_completion_tokens=4096,
                reasoning_display="encrypted",
            ):
                if kind == "message":
                    msg = val
            calls = (msg or {}).get("tool_calls") or []
            record("Thinking-1 tools + streaming", bool(calls), f"-> {len(calls)} tool call(s)")
        except Exception as exc:
            record("Thinking-1 tools + streaming", False, str(exc)[:160])
    else:
        print("  [SKIP] Thinking-1 (no MAI_FOUNDRY_* configured)")

    # ── Image: one small generation ────────────────────────────────────────────
    if cfg.image_ready:
        res = client.generate_image("A plain red circle on a white background.", 768, 768)
        record(
            "Image generation",
            res.is_live and bool(res.data),
            f"-> {res.source}, {len(res.data or b'')} bytes, {res.elapsed:.1f}s",
        )
    else:
        print("  [SKIP] Image (no MAI_IMAGE_* configured)")

    # ── Voice + Transcribe: synthesize a phrase, then read it back ─────────────
    audio = None
    audio_mime = None
    if cfg.speech_ready:
        tts = client.synthesize("Live smoke test for MAI Voice.", voice="en-US-Ethan:MAI-Voice-2")
        audio = tts.data
        audio_mime = tts.meta.get("mime")
        record(
            "Voice-2 synthesis",
            tts.is_live and bool(tts.data),
            f"-> {tts.source}, {len(tts.data or b'')} bytes",
        )
    else:
        print("  [SKIP] Voice-2 (no MAI_SPEECH_KEY/REGION configured)")

    if cfg.transcribe_ready and audio:
        tr = client.transcribe(
            audio,
            filename="smoke" + audio_extension_for_mime(audio_mime),
            mime=audio_mime,
            phrases=ENTITIES,
            locales=["en"],
        )
        record("Transcribe-1.5", tr.is_live and bool(tr.data), f"-> {tr.source}, {tr.data[:48]!r}")
    elif cfg.transcribe_ready:
        print("  [SKIP] Transcribe-1.5 (no audio produced to transcribe)")
    else:
        print("  [SKIP] Transcribe-1.5 (no MAI_SPEECH_ENDPOINT configured)")

    failed = [name for name, ok, _ in results if not ok]
    print()
    if not results:
        print("No services configured — nothing was verified.")
        return 1
    if failed:
        print(f"FAILED: {', '.join(failed)}")
        return 1
    print(f"All {len(results)} live checks passed.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate live MAI service configuration.")
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Validate only configured services instead of requiring all four.",
    )
    args = parser.parse_args()
    os.environ.setdefault("MAI_EXECUTION_MODE", "strict")
    raise SystemExit(main(allow_partial=args.allow_partial))

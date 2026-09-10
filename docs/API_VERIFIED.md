# MAI API — verified surface

> Last verified against Microsoft Learn on **2026-08-25**.
> This file is the source of truth for the code in `mai/`. If Microsoft changes
> something, update here first, then `mai/config.py`.

The selected capabilities are a subset of the MAI family. Microsoft Learn currently
labels MAI-Thinking-1 and the selected Image, Transcribe, and Voice capabilities as
preview. Preview contracts and availability can change.

This 2026-08-25 hardening pass verified the contract from official documentation and
offline tests. It did **not** call live Azure endpoints. Empirical notes below are from
the original authorized AI CoE live validation on 2026-08-13 and are explicitly
distinguished from the documentation-only review.

Two later rounds of authorized live verification against an East US Foundry resource are
recorded separately: the strict smoke script passed for all four service areas on
2026-08-27, and the image generation and edit measured in
[`IMAGE_PRESERVATION.md`](IMAGE_PRESERVATION.md) ran live on 2026-08-28. Neither round
changed the documented contract below.

Section 0 (authentication) was added on 2026-09-10 when the sample moved to keyless
Microsoft Entra ID. It is documentation-derived and carries its own verification note;
the sections below it are unchanged and keep their earlier verification status.

---

## 0. Authentication

The app authenticates **keyless** by default (`MAI_AUTH_MODE=entra`), with
Microsoft Entra ID and Azure RBAC. `DefaultAzureCredential` resolves a managed
identity in Azure and the developer's `az login` locally. Resource keys remain
supported through `MAI_AUTH_MODE=key`.

The two service families use **different token audiences**. They are not
interchangeable: sending one where the other is expected fails with a 401.

| Service | Scope | Role | Header |
|---|---|---|---|
| Thinking-1, Image-2.5 | `https://ai.azure.com/.default` | Cognitive Services User | `Authorization: Bearer <token>` |
| Transcribe-1.5 | `https://cognitiveservices.azure.com/.default` | Cognitive Services Speech User | `Authorization: Bearer <token>` |
| Voice-2 (TTS) | `https://cognitiveservices.azure.com/.default` | Cognitive Services Speech User | `Authorization: Bearer aad#<resourceId>#<token>` |

Three consequences worth knowing, all of them enforced in `mai/config.py`:

- ⚠️ **Speech requires a custom subdomain.** Entra tokens are rejected on the
  regional endpoints, so the resource must be reachable as
  `https://<name>.cognitiveservices.azure.com`. That property is not reversible.
- ⚠️ **Keyless TTS cannot use the regional host.** `Bearer` tokens are scoped to
  the host that owns them, so keyless synthesis moves from
  `<region>.tts.speech.microsoft.com` to the resource's own subdomain. A resource
  key works against either host, which is why the key path can share that URL.
- ⚠️ **The `cognitiveservices/v1` path does not take a bare token.** It expects
  the ARM resource ID and the token combined as `aad#<resourceId>#<token>`, hence
  `MAI_SPEECH_RESOURCE_ID`. The transcription API takes a bare token.

Role definition IDs used by `infra/main.bicep` (resolved from the live directory
on 2026-09-10): Cognitive Services User `a97b65f3-24c7-4388-baec-2e87135dc908`,
Cognitive Services Speech User `f2dc8367-1007-4938-bd23-fe263f013447`.

> **Verification status.** This section is documentation-derived (2026-09-10) and
> has **not** been confirmed against a live endpoint. The keyless wire format is
> covered by offline tests in `tests/test_auth.py`, which prove what the client
> sends, not what the service accepts. Run `scripts/live_smoke.py` in strict mode
> against your own resource before relying on it, and record the result here.

Sources:
- https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/configure-entra-id
- https://learn.microsoft.com/en-us/azure/ai-services/speech-service/how-to-configure-azure-ad-auth
- https://learn.microsoft.com/en-us/azure/ai-services/speech-service/rest-text-to-speech

---

## 1. MAI-Thinking-1 (reasoning + function calling)

- **Endpoint (used by this repo):** `POST {FOUNDRY_ENDPOINT}/mai/v1/chat/completions`
  - `FOUNDRY_ENDPOINT` = `https://<your-resource>.services.ai.azure.com`
  - No `api-version` query parameter is required.
  - This repository uses the native path documented for MAI-Thinking-1.
- **Auth:** keyless `Authorization: Bearer <Entra token>` (default), or header
  `api-key: <KEY>`. See section 0.
- **Documented body fields used here:** `model`, `messages`, `tools`,
  `max_completion_tokens`, `stream`, `reasoning_display`.
  - `model` = the **deployment name** (typically `MAI-Thinking-1`).
- **Function calling:** `tools=[{"type":"function","function":{...}}]`. Response in
  `choices[0].message.tool_calls[]`. The current app does not send undocumented
  `tool_choice` or `temperature` fields.
- **Context:** 256K tokens.

### Parameter contract — verified empirically (2026-08-13)

Each row was sent against a live `MAI-Thinking-1` deployment:

| Parameter | Result |
| --- | --- |
| `max_tokens` | ❌ **HTTP 400** — `` `max_tokens` is not supported; use `max_completion_tokens` instead `` (on **both** paths) |
| `max_completion_tokens` | ✅ 200 |
| `temperature` | Accepted by that deployment, but absent from the current documented parameter list; **not sent by this repo** |
| `reasoning_display: "encrypted"` | ✅ 200 on `/mai/v1/` · ❌ 400 `unrecognized_request_argument` on `/openai/v1/` |
| `tools` without `tool_choice` | ✅ 200, returned `tool_calls` |

### Reasoning state across tool rounds

With `reasoning_display: "encrypted"`, the assistant message carries an opaque
`reasoning` envelope; in streaming it arrives on `delta.reasoning`. Append that
assistant message back **verbatim** on the next round so the model keeps its state;
never inspect, render, or log the envelope.

### Streaming quirks

- ⚠️ Each tool call arrives **complete in its own chunk, with `id` but no `index`**
  (not fragmented like standard OpenAI streaming). A parser that assumes OpenAI's
  indexed deltas will concatenate arguments into invalid JSON. `_tc_slot` in
  `mai/client.py` handles both shapes.
- ⚠️ An error can be delivered **inside** the stream after partial content (e.g. a
  safety block): a `{"error": {...}}` event followed by `[DONE]`. Ignoring non-`choices`
  events would present truncated text as a complete answer — `mai/client.py` raises
  `MAIStreamError` instead.
- `usage`, `model`, `system_fingerprint` and the request id arrive at the top level of
  chunks and are surfaced for observability.

List a project's real deployments with
`GET {project_endpoint}/deployments?api-version=2025-05-01`.

Sources:
- https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai-thinking
- https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure

---

## 2. MAI-Image-2.5 (generation + editing)

- **Base:** `https://<your-resource>.services.ai.azure.com`
- **Generation:** `POST {base}/mai/v1/images/generations`
  - Headers: `Content-Type: application/json`, plus auth (section 0)
  - JSON body: `{ "model": <deployment>, "prompt": str, "width": int, "height": int }`
  - `width`/`height` ≥ 768; `width * height` ≤ 1_048_576. Output is always **PNG**.
- **Editing:** `POST {base}/mai/v1/images/edits`  ← the "Surgical Edit" demo
  - **multipart/form-data**. Auth header only (section 0); no manual `Content-Type`.
  - `data = { "model": <deployment>, "prompt": str }`
  - `files = { "image": (name, bytes, "image/png" | "image/jpeg") }`
- **Response (both):** `{ "data": [ { "b64_json": "<base64 PNG>" } ] }`
- **Valid models / deployments:**
  - `MAI-Image-2.5-Pro`   (gen + edit)  version `2026-06-19`
  - `MAI-Image-2.5-Flash` (gen + edit)  version `2026-06-02`  ← fast / high-volume
  - `MAI-Image-2.5`       (gen + edit)  version `2026-06-02`
  - Additional models may appear in the catalog; check the linked page for current
    lifecycle and deployment availability.
- **Notes:** image-to-image editing is supported by the 2.5 models documented on the
  linked page. Region and deployment availability must be checked at deployment time.

Source: https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai-image

---

## 3. MAI-Transcribe-1.5 (LLM Speech API / fast transcription)

- **Endpoint:** `POST https://<your-resource>.cognitiveservices.azure.com/speechtotext/transcriptions:transcribe?api-version=2025-10-15`
- **Auth:** keyless `Authorization: Bearer <Entra token>` (default), or header
  `Ocp-Apim-Subscription-Key: <SPEECH_KEY>`. See section 0.
- **Body:** `multipart/form-data`
  - `audio` = file (WAV, MP3, or FLAC; < 300 MB)
  - `definition` = JSON string:
    ```json
    {
      "locales": ["en"],
      "phraseList": { "phrases": ["Contoso", "Jessie", "Rehaan"] },
      "enhancedMode": {
        "enabled": true,
        "model": "mai-transcribe-1.5",
        "transcribeStyle": "verbatim"
      }
    }
    ```
  - `phraseList` provides entity biasing.
  - Omit `locales` → automatic multilingual mode.
- **Model lineup (Learn, 2026-09-10):** `MAI-Transcribe-2`, `MAI-Transcribe-1.5`, and
  `MAI-Transcribe-1`, **deprecated on 2026-08-20**. The article is now titled after
  Transcribe-2. This repo still targets `mai-transcribe-1.5`, which is the version its
  live runs were measured against; moving to Transcribe-2 is a deliberate change, not a
  default.

### ⚠️ Drift found on 2026-09-10, not yet reconciled with a live run

Re-reading the source page against this file turned up three differences. They are
recorded here rather than silently corrected in code, because this repo's rule is that a
claim is only "verified" when a live run says so.

| Item | What this file used to say | What Learn says now |
| --- | --- | --- |
| Diarization | "Not supported" | Supported via `diarization.enabled`. Requests fail at roughly 15 minutes and longer in preview (408, or 500/503 `diarization_unavailable`) |
| `transcribeStyle` default | Readability-optimized, with `verbatim` as the opt-in | **`verbatim` is the default**, and `clean` is the readability-optimized value |
| `transcribeStyle` path | Flat, `enhancedMode.transcribeStyle` | Nested, `enhancedMode.modelOptions.transcribeStyle`, alongside `modelOptions.timestamps` |

`mai/client.py` sends the **flat** form, and that is what the 2026-08-27 strict smoke run
exercised successfully against a `mai-transcribe-1.5` deployment. The nested form is
documented for Transcribe-2. Both can be true: the parameter may have moved with the new
generation. Do not "fix" the path without a live run that proves it.

The inverted default matters more. The client omits `transcribeStyle` unless the demo's
verbatim toggle is on, which assumed that omitting it meant readability-optimized. If the
default really is `verbatim`, then that toggle changes nothing and the demo's baseline is
already verbatim. Sending `clean` explicitly when the toggle is off would make the intent
unambiguous, but whether `mai-transcribe-1.5` accepts `clean` is unverified. **Resolve
both with one strict smoke run before the next talk**, then update this section.

- **Not supported:** prompt-tuning.
- **Response:** fast-transcription format; text usually appears in `combinedPhrases[].text`
  (the code parses several shapes defensively).

Source: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/mai-transcribe

> Naming note: this project follows the currently documented `mai-transcribe-1.5`
> identifier.

---

## 4. MAI-Voice-2 (expressive TTS)

- **API:** the same Azure Speech APIs/SDKs as the neural voices. Via REST:
  - **Endpoint:** `POST https://<region>.tts.speech.microsoft.com/cognitiveservices/v1`
  - **Endpoint (keyless):** `POST https://<your-resource>.cognitiveservices.azure.com/cognitiveservices/v1`
    (an Entra token is rejected by the regional host; see section 0)
  - Headers:
    - `Content-Type: application/ssml+xml`
    - `X-Microsoft-OutputFormat: audio-24khz-160kbitrate-mono-mp3`
    - `User-Agent: <app name>` (documented as required)
    - `Authorization: Bearer aad#<resourceId>#<token>`, or
      `Ocp-Apim-Subscription-Key: <SPEECH_KEY>`
  - Body: SSML. Output: MP3 (per the output format).
- **Expressive SSML:** `mstts:express-as` with `style` and `styledegree` (0.01–2.0).
- **Real voices (the `<voice name="...">` value):**
  - `en-US-Harper:MAI-Voice-2` (F), `en-US-Ethan:MAI-Voice-2` (M), `en-US-Olivia:MAI-Voice-2` (F)
  - `es-MX-Valeria:MAI-Voice-2` (F), `es-MX-Alejo:MAI-Voice-2` (M)
  - `es-ES-Marta:MAI-Voice-2` (F)
  - `...:MAI-Voice-2-Flash` variants are also documented on the linked page.
- **Supported styles depend on the voice** (important for the personalities demo):
  - en-US voices (Harper/Ethan/Olivia): `angry, confused, determined, excited, happy,
    hopeful, joyful, regretful, relieved, sad, shouting, softvoice, whispering, ...`
    → **`excited` yes, `empathy` no**.
  - `es-ES-Marta`, `nl-NL-Sander`, `ru-RU-*`, `th-TH-*`, `tr-TR-*`:
    `adventurous, caring, empathy, curious, encouraging, excited, friendly, cheerful,
    nostalgic, reflective, sad, disappointed, serious`
    → **`empathy` and `excited` yes**.
  - This is why the code validates the requested style against the voice and falls back
    to the closest supported one (`mai/config.py::resolve_style`).
- **Voice cloning / personal voice:** gated (Limited Access Review). Not used in the demos.

Source: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/mai-voices

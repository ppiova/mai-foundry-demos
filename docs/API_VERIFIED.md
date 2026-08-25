# MAI API — verified surface

> Last verified against Microsoft Learn on **2026-08-25**.
> This file is the source of truth for the code in `mai/`. If Microsoft changes
> something, update here first, then `mai/config.py`.

The selected capabilities are a subset of the MAI family. Microsoft Learn currently
labels MAI-Thinking-1 and the selected Image, Transcribe, and Voice capabilities as
preview. Preview contracts and availability can change.

This 2026-08-25 hardening pass verified the contract from official documentation and
offline tests. It did **not** call live Azure endpoints. Empirical notes below are from
an earlier authorized live check on 2026-08-24 and are explicitly distinguished from
the documented contract.

---

## 1. MAI-Thinking-1 (reasoning + function calling)

- **Endpoint (used by this repo):** `POST {FOUNDRY_ENDPOINT}/mai/v1/chat/completions`
  - `FOUNDRY_ENDPOINT` = `https://<your-resource>.services.ai.azure.com`
  - No `api-version` query parameter is required.
  - This repository uses the native path documented for MAI-Thinking-1.
- **Auth:** header `api-key: <KEY>` (or `Authorization: Bearer <Entra token>`).
- **Documented body fields used here:** `model`, `messages`, `tools`,
  `max_completion_tokens`, `stream`, `reasoning_display`.
  - `model` = the **deployment name** (typically `MAI-Thinking-1`).
- **Function calling:** `tools=[{"type":"function","function":{...}}]`. Response in
  `choices[0].message.tool_calls[]`. The current app does not send undocumented
  `tool_choice` or `temperature` fields.
- **Context:** 256K tokens.

### Parameter contract — verified empirically (2026-08-24)

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
  - Headers: `Content-Type: application/json`, `api-key: <KEY>`
  - JSON body: `{ "model": <deployment>, "prompt": str, "width": int, "height": int }`
  - `width`/`height` ≥ 768; `width * height` ≤ 1_048_576. Output is always **PNG**.
- **Editing:** `POST {base}/mai/v1/images/edits`  ← the "Surgical Edit" demo
  - **multipart/form-data**. Header: `api-key: <KEY>` (no manual `Content-Type`).
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
- **Auth:** header `Ocp-Apim-Subscription-Key: <SPEECH_KEY>`
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
  - `phraseList` (up to ~200 phrases) and `transcribeStyle` are **only** in `mai-transcribe-1.5`.
  - `transcribeStyle`: defaults to readability-optimized; `"verbatim"` preserves filler
    words and disfluencies.
  - Omit `locales` → automatic multilingual mode.
- **Not supported:** diarization, prompt-tuning.
- **Model used here:** `mai-transcribe-1.5`. Check the linked page for current model
  lifecycle information.
- **Response:** fast-transcription format; text usually appears in `combinedPhrases[].text`
  (the code parses several shapes defensively).

Source: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/mai-transcribe

> Naming note: this project follows the currently documented `mai-transcribe-1.5`
> identifier.

---

## 4. MAI-Voice-2 (expressive TTS)

- **API:** the same Azure Speech APIs/SDKs as the neural voices. Via REST:
  - **Endpoint:** `POST https://<region>.tts.speech.microsoft.com/cognitiveservices/v1`
  - Headers:
    - `Content-Type: application/ssml+xml`
    - `X-Microsoft-OutputFormat: audio-24khz-160kbitrate-mono-mp3`
    - `Ocp-Apim-Subscription-Key: <SPEECH_KEY>`
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

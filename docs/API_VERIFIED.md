# MAI API — verified surface

> Verified against Microsoft's public documentation on **2026-08-13**.
> This file is the source of truth for the code in `mai/`. If Microsoft changes
> something, update here first, then `mai/config.py`.

All referenced models exist and are documented. Three are in **public preview**
(Image, Transcribe, Voice); **MAI-Thinking-1** is described as **private preview /
"public access coming soon"** in developer coverage.

---

## 1. MAI-Thinking-1 (reasoning + function calling)

- **Compatibility:** OpenAI Chat Completions (Foundry v1).
- **Endpoint:** `POST {FOUNDRY_ENDPOINT}/openai/v1/chat/completions`
  - `FOUNDRY_ENDPOINT` = `https://<your-resource>.services.ai.azure.com`
    (also accepts `https://<your-resource>.openai.azure.com`)
  - With the v1 API, no `api-version` is required.
- **Auth:** header `api-key: <KEY>` (or `Authorization: Bearer <Entra token>`).
- **Body:** standard OpenAI JSON — `model`, `messages`, `tools`, `tool_choice`.
  - `model` = the **deployment name** (typically `MAI-Thinking-1`).
- **Function calling:** `tools=[{"type":"function","function":{...}}]`,
  `tool_choice="auto"`. Response in `choices[0].message.tool_calls[]`.
- **Context:** 256K tokens.
- **Streaming (`stream:true`):** supported. ⚠️ Quirk verified 2026-08-13: on this
  deployment each tool call arrives **complete in its own chunk, with `id` but no
  `index`** (not fragmented like standard OpenAI streaming). The parser in
  `mai/client.py` (`_tc_slot`) handles both formats.
- **Verified working (2026-08-13):** base `https://<your-resource>.services.ai.azure.com`,
  path `/openai/v1/chat/completions`, header `api-key`, `model="MAI-Thinking-1"`,
  accepts `temperature` and `max_completion_tokens`. List a project's real deployments
  with `GET {project_endpoint}/deployments?api-version=2025-05-01`.

Sources:
- https://learn.microsoft.com/en-us/azure/foundry/openai/api-version-lifecycle
- https://microsoft.ai/news/introducing-mai-thinking-1/

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
  - `MAI-Image-2e`        (gen only)    version `2026-04-09`  ⚠️ **deprecating — can no longer be deployed** (use `MAI-Image-2.5-Flash` instead)
  - `MAI-Image-2`         (gen only)    version `2026-02-20`
- **Notes:** image-to-image editing is supported only by the 2.5 family. MAI image
  models are **region-limited** (available in West Central US, East US, West US, West
  Europe, Sweden Central, South India, UAE North — notably **not** East US 2).

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
- **Models:** `mai-transcribe-1.5` (current), `mai-transcribe-1` (deprecated 2026-08-20).
- **Response:** fast-transcription format; text usually appears in `combinedPhrases[].text`
  (the code parses several shapes defensively).

Source: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/mai-transcribe

> ⚠️ Naming note: some early materials referenced `MAI-Transcribe-2`. The current
> public docs list only `mai-transcribe-1.5` and `mai-transcribe-1` — this project
> standardizes on **1.5**.

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
  - `...:MAI-Voice-2-Flash` variants for low latency.
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

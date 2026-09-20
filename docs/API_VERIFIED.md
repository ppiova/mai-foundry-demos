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
Microsoft Entra ID. The 2026-09-11 observations recorded in
[PR #14](https://github.com/ppiova/mai-foundry-demos/pull/14) subsequently verified
Image and Speech keyless paths and resolved the Transcribe-1.5 style questions.
Thinking keyless remains unverified.

## Verification at a glance

These are historical observations, not a guarantee that a preview API or a region
still behaves the same way today. The current branch includes changes after the
published `v1.1.1` release; that release predates the keyless implementation.

| Capability / path | Recorded live evidence | What remains outside that evidence |
|---|---|---|
| Thinking, original pre-keyless path | 2026-08-27: chat and streamed tool calls passed the strict smoke | Not proof of the current keyless path, or that every generated migration plan satisfies the constraints |
| Thinking, Entra | Not verified in the 2026-09-11 run: subscription quota prevented deployment | End-to-end Entra inference needs a new authorized run |
| Image, Entra | 2026-09-11: generation and edit returned LIVE output | The automated smoke checks generation only; image preservation is a separate exercise |
| Voice, Entra | 2026-09-11: synthesis worked on the regional TTS host with the `aad#` composite | Not a comparison of all voices, styles or languages |
| Transcribe-1.5, Entra | 2026-09-11: transcription; one clip matched with default vs explicit `verbatim`; flat `clean` returned HTTP 400 | Not a benchmark of entity biasing, diarization or Transcribe-2 |
| Image preservation observation | 2026-08-28: one recorded generation/edit pair, with [reproducible measurements](IMAGE_PRESERVATION.md) | Not a multi-image benchmark or a guarantee of preservation |

### What a passing check means

- Offline tests prove local behavior and mocked request contracts, not service acceptance.
- `scripts/live_smoke.py` checks chat, one streamed tool request, image generation,
  voice synthesis and transcription. A configured service that cannot be exercised
  fails, including Transcribe when Voice produces no live audio. `--allow-partial`
  permits missing configuration, not untested configured services.
- The smoke does not run a full migration plan, edit an image, compare voice styles
  or measure entity accuracy. Use the relevant demo to inspect those behaviors and
  record the inputs, outputs and limitations.
- A successful image response must identify the configured generation deployment.
  A replacement deployment or missing provenance cannot count as a pass.

When adding evidence, record the commit or release, date, model/deployment version,
region, authentication path actually used, command or scenario, and result.
Include failures and untested cases. Do not publish tokens, resource keys, private
audio or identifiable user data with the record.

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

- ⚠️ **Speech requires a custom subdomain.** A resource without one is not
  eligible for Microsoft Entra authentication at all; that property is not
  reversible once set. This is a prerequisite, not the host requests go to (see
  the next point).
- ⚠️ **Keyless TTS still uses the regional host, not the custom subdomain.**
  Verified live on 2026-09-11 against a real `AIServices` account:
  `POST https://<name>.cognitiveservices.azure.com/cognitiveservices/v1` returns
  **404** for a bearer token, with or without the `aad#` composite.
  `POST https://<region>.tts.speech.microsoft.com/cognitiveservices/v1` with
  `Authorization: Bearer aad#<resourceId>#<token>` returns **200** with real
  audio. The docs' own worked example shows the custom-subdomain host, which
  reads as though it should work; it did not, on this account. Key-mode TTS
  already used the regional host, so this fix made the two auth modes share the
  same URL rather than diverge on it.
- ⚠️ **The `cognitiveservices/v1` path does not take a bare token.** It expects
  the ARM resource ID and the token combined as `aad#<resourceId>#<token>`, hence
  `MAI_SPEECH_RESOURCE_ID`. The transcription API takes a bare token.

Role definition IDs used by `infra/main.bicep` (resolved from the live directory
on 2026-09-10): Cognitive Services User `a97b65f3-24c7-4388-baec-2e87135dc908`,
Cognitive Services Speech User `f2dc8367-1007-4938-bd23-fe263f013447`.

> **Verification status.** Confirmed live on 2026-09-11 against a real
> `AIServices` account (`mai-foundry-demos-ppiova`, `eastus`, deployed with
> `infra/main.bicep`, `disableLocalAuth = true`): keyless **Image generation**
> and **Image edit** both went LIVE end to end, and keyless **Voice-2 synthesis**
> went LIVE once the TTS host fix above was applied. RBAC propagation took close
> to the documented five minutes. MAI-Thinking-1 was not deployed in this run
> (subscription-wide quota exhausted; see `infra/README.md`), so the Thinking
> audience and role are still documentation-derived. See the note on
> `DefaultAzureCredential` credential precedence below if a keyless call fails
> with 401 even though the role is assigned correctly.

### ⚠️ `DefaultAzureCredential` can silently pick the wrong identity

Encountered live on 2026-09-11, and worth naming because the symptom looks
exactly like an RBAC propagation delay and is not one.

`DefaultAzureCredential` tries several credential sources in a fixed order and
uses whichever succeeds first. In an execution environment that exposes a
Managed Identity reachable over IMDS, `ManagedIdentityCredential` succeeds
before the chain ever reaches `AzureCliCredential`, even when the developer is
correctly signed in with `az login` and that user has the correct roles. The
app then authenticates as the managed identity, not the developer, gets a
persistent 401, and never recovers no matter how long RBAC has had to
propagate. This is silent: nothing in the error message says which identity was
actually used.

To check which identity a failing call is really using, decode the token's
claims (no signature verification needed for this):

```python
from azure.identity import AzureCliCredential  # or DefaultAzureCredential
import base64, json

token = AzureCliCredential().get_token("https://ai.azure.com/.default").token
payload = token.split(".")[1]
payload += "=" * (-len(payload) % 4)
claims = json.loads(base64.urlsafe_b64decode(payload))
print(claims.get("idtyp"), claims.get("oid"), claims.get("appid"))
```

`idtyp: "app"` with an unfamiliar `appid` means some other identity won the
credential chain. Confirm by testing `AzureCliCredential` directly, in isolation
from the rest of the chain (same shape as the snippet above): if that succeeds
and matches your own `az ad signed-in-user show`, the fix is to stop relying on
automatic precedence for local development, not to wait longer.

Not yet fixed in `mai/auth.py`, which still constructs a bare
`DefaultAzureCredential()`. Worth an explicit override (an env var to force
`AzureCliCredential`, or `DefaultAzureCredential(exclude_managed_identity_credential=True)`
for local runs) as a follow-up; recorded here rather than fixed silently, since
it changes what `mai/auth.py` does by default and deserves its own review.

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
- A stream that ends without a finish reason or `[DONE]` raises
  `MAIStreamError` rather than returning partial content as a completed message.

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

### `transcribeStyle` on `mai-transcribe-1.5`: fully resolved live on 2026-09-11

Drift was first noticed on 2026-09-10 re-reading the Learn source against this file,
recorded then as open questions rather than corrected on documentation alone, per this
repo's rule that a claim is only "verified" when a live run says so. Two live tests
against a real `mai-transcribe-1.5` deployment (`mai-foundry-demos-ppiova`, keyless)
resolve the style questions; diarization was not exercised:

| Item | Was documented as | Learn now says | Live result |
| --- | --- | --- | --- |
| Diarization | "Not supported" | Supported via `diarization.enabled` (fails past ~15 min in preview) | Not exercised this round |
| `transcribeStyle` default | Readability-optimized, `verbatim` opt-in | `verbatim` is the default, `clean` is readability-optimized | **Confirmed.** Same clip, transcribed once with `transcribeStyle` omitted and once with `"verbatim"` explicit, produced **byte-identical text**, filler words and a false-start correction intact both times |
| `transcribeStyle` path | Flat, `enhancedMode.transcribeStyle` | Nested, `enhancedMode.modelOptions.transcribeStyle`, for Transcribe-2 | **Confirmed the flat form still works** for 1.5: `"verbatim"` succeeds on it live |
| `transcribeStyle: "clean"` on 1.5 | Not previously tested | Documented as a Transcribe-2 value | **Rejected.** `POST .../transcribe` with `enhancedMode.transcribeStyle: "clean"` on the flat path returns **HTTP 400**: `"transcribeStyle='clean' is not supported by MAI transcription model 'mai-transcribe-1.5'."` |

**Conclusion: `mai-transcribe-1.5` only ever produces verbatim output.** `clean` is a
Transcribe-2 value this model rejects outright, and the default was already verbatim, so
there is no way to get a readability-optimized transcript from `mai-transcribe-1.5`
through this parameter at all.

This means `demos/transcribe_bias.py`'s verbatim toggle is a no-op against a live
`mai-transcribe-1.5` deployment: both positions produce the same transcript, because the
model has no other style to switch to. Not a client bug, since sending `"clean"` would
just turn a working call into a guaranteed 400. The demo now says so next to the toggle
rather than implying it changes the output. Moving to `MAI-Transcribe-2` would make the
toggle meaningful again, at the cost of the nested `modelOptions` path and a separate
model-availability check; not done here, since `mai-transcribe-1.5` is what the rest of
this file's live verification (2026-08-27, 2026-09-11) was measured against.

- **Not supported:** prompt-tuning.
- **Response:** fast-transcription format; text usually appears in `combinedPhrases[].text`
  (the code parses several shapes defensively).

Source: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/mai-transcribe

> Naming note: this project follows the currently documented `mai-transcribe-1.5`
> identifier.

---

## 4. MAI-Voice-2 (expressive TTS)

- **API:** the same Azure Speech APIs/SDKs as the neural voices. Via REST:
  - **Endpoint (both auth modes):** `POST https://<region>.tts.speech.microsoft.com/cognitiveservices/v1`.
    Verified live (2026-09-11): the resource's own custom subdomain 404s on this
    path for a bearer token; the regional host is what actually works, for a key
    and for an Entra token alike. See section 0.
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

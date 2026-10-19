# Localization plan

## Status

Localization is planned, not implemented. Initial locales should be English (`en-IN`), Marathi (`mr-IN`), and Hindi (`hi-IN`), matching the current Maharashtra prototype scope. Add languages only after a fluent local reviewer checks the terminology and user testing confirms the wording is understandable.

## Stable language boundary

- Keep machine/API identifiers stable and language-neutral: canonical district and soil values, request field names, and the model's crop class IDs do not change with locale.
- Translate UI labels, help text, validation messages, accessibility labels, safety notices, and fixed API warning templates using stable keys.
- Render crop names via reviewed locale dictionaries keyed by the original model label; never translate labels before model inference or change the stored class ID.
- Do not guess or translate unknown units. First establish and verify the dataset measurement units, then present unit-aware guidance.
- Keep recommendations, scores, and uncertainty wording semantically identical across locales. A translated score must not become a stronger claim.
- Do not send crop-care instructions through unreviewed machine translation. Later chatbot answers require a reviewed agronomy source and a human-reviewed language path.

## Implementation sequence

1. Freeze the request/response contract and create a glossary with local agriculture reviewers.
2. Add versioned UI message bundles such as `en-IN.json`, `mr-IN.json`, and `hi-IN.json`; fail CI if keys are missing or duplicated.
3. Add an explicit locale preference to the web/mobile clients. For API-generated messages, use a documented `Accept-Language` policy or explicit locale field and return the selected locale in the response.
4. Keep API category codes canonical and localize only their display strings in the client.
5. Test every screen at mobile widths and on Android with each script, including long Marathi/Hindi strings, screen readers, font scaling, and offline/error states.
6. Have a fluent reviewer validate translations and a target-user group test comprehension before release.

## Learning topics

Learn resource bundles, Unicode/script rendering, locale fallback, accessibility semantics, API versioning, and translator review workflows. Localization is product design and safety work, not a bulk string-replacement step.

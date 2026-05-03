# Prompt Templates

This directory contains system prompt templates for the debate agents.

## Structure

```
prompts/
├── default/              # Default prompt variant
│   ├── strategist.md     # System prompt for strategist agent (German)
│   ├── strategist-en.md  # System prompt for strategist agent (English)
│   ├── critic.md         # System prompt for critic agent (German)
│   ├── critic-en.md      # System prompt for critic agent (English)
│   ├── optimizer.md      # System prompt for optimizer agent (German)
│   ├── optimizer-en.md   # System prompt for optimizer agent (English)
│   ├── moderator.md      # System prompt for moderator agent (German)
│   └── moderator-en.md   # System prompt for moderator agent (English)
└── variants/             # Alternative prompt variants
    ├── kantian/          # Kantian philosophical perspective
    └── steiner/          # Steiner/Waldorf perspective
```

## Language Selection

The prompt service automatically selects the language variant based on the debate language:
- `language: "de"` → loads `{role}.md` (German)
- `language: "en"` → loads `{role}-en.md` (English), falls back to `{role}.md`

## Creating Custom Prompts

1. Copy an existing prompt file
2. Edit the content to match your desired agent behavior
3. For new variants, create a subdirectory under `variants/`

## Note

These files contain no secrets and are safe templates. They are excluded from
git by default to allow per-user customization. To share prompts, create
`*-example.md` files which are tracked by git.

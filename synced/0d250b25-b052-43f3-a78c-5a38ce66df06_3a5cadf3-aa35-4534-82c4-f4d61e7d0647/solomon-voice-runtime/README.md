# Solomon Voice Runtime

This Claude Skill turns connected tools into a governed voice-operated runtime for Operations Command.

## What it does

- Automatically selects relevant connectors from natural spoken commands
- Reads and reconciles connected operational data without unnecessary permission prompts
- Executes routine internal actions from one explicit command
- Verifies writes after execution
- Uses short, voice-friendly Command Cards
- Preserves confirmation for sensitive or externally consequential actions
- Blocks financial, legal, credential, destructive, and other high-assurance actions from ordinary voice authorization
- Continues operating when one connector is unavailable

## Important limitation

A Skill controls Claude's workflow. It does **not**:

- Install connectors
- Grant OAuth scopes
- Turn read-only tools into write tools
- Bypass connector confirmations
- Bypass Claude plan, organization, role, or platform restrictions
- Provide background wake-word listening outside Claude's supported voice interface

Claude can use only connectors and tools that are connected, enabled, and available to the authenticated user.

## Install in Claude

1. Open **Customize → Skills**.
2. Select **Create skill** or **Upload a skill**.
3. Upload `solomon-voice-runtime.zip`.
4. Enable **Solomon Voice Runtime**.
5. Open a new Claude conversation.
6. Ensure the needed connectors are enabled in **Customize → Connectors**.
7. Set connector **Tool access** to **Auto** for the smoothest voice routing, or **On demand** when many connectors are active.
8. Enter Claude voice mode.
9. Say: **“Connector status.”**
10. Test the commands in `resources/VOICE_ACCEPTANCE_TESTS.md`.

## Recommended companion skills

This runtime is designed to coexist with focused workflow skills, including a Clover-specific operations skill. Skills may compose automatically when Claude determines that multiple skills are relevant.

## Default action policy

| Class | Default behavior |
|---|---|
| Read/search/analyze | Automatic |
| Draft/prepare | Automatic |
| Routine internal reversible write | Execute from one explicit command |
| External or sensitive write | Readback confirmation |
| Financial/legal/credential/destructive | Hard stop or separate approval process |

## Suggested first command

> Begin Daily Operations.

## Package structure

```text
solomon-voice-runtime.zip
└── solomon-voice-runtime/
    ├── skill.md
    ├── README.md
    └── resources/
        ├── CONNECTOR_POLICY.md
        ├── COMMAND_LIBRARY.md
        ├── VOICE_ACCEPTANCE_TESTS.md
        └── START_PROMPT.txt
```

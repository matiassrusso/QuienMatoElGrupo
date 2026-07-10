import sys, json, re

data = json.load(sys.stdin)
file_path = (data.get("tool_input") or {}).get("file_path", "") or ""

if re.search(r"(^|[\\/])\.env", file_path):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "Blocked: .env files are protected to prevent accidental secret edits/leaks. Edit them manually outside Claude Code if intentional.",
        }
    }))

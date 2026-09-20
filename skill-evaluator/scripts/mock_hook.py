#!/usr/bin/env python3
"""Native PreToolUse Bash mock. Never execute the evaluated command."""

import json
import re
import shlex
import sys
from pathlib import Path


def decision(payload, config):
    command = payload.get("tool_input", {}).get("command", "")
    for pattern in config["patterns"]:
        if re.fullmatch(pattern, command):
            result = config["mock_data"][pattern]
            replacement = "printf %s " + shlex.quote(str(result.get("stdout", "")))
            if result.get("stderr"):
                replacement += (
                    "; printf %s " + shlex.quote(str(result["stderr"])) + " >&2"
                )
            replacement += "; exit " + str(int(result.get("exit_code", 0)))
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "updatedInput": {"command": replacement},
                    "additionalContext": "SKILL_EVAL_MOCK: canned response; original command was not executed",
                }
            }
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "UNMOCKED_EXTERNAL_CALL: Bash command has no exact configured mock",
        }
    }


if __name__ == "__main__":
    try:
        print(
            json.dumps(
                decision(
                    json.load(sys.stdin), json.loads(Path(sys.argv[1]).read_text())
                )
            )
        )
    except Exception:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": "Mock infrastructure failure",
                    }
                }
            )
        )
        sys.exit(0)

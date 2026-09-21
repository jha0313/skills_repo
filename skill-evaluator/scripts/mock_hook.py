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
                    "additionalContext": "SKILL_EVAL_MOCK: 고정 응답이며 원래 명령은 실행하지 않았습니다",
                }
            }
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "UNMOCKED_EXTERNAL_CALL: Bash 명령에 정확히 일치하는 mock 설정이 없습니다",
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
                        "permissionDecisionReason": "Mock 실행 환경 오류",
                    }
                }
            )
        )
        sys.exit(0)

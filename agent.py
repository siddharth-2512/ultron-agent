import os
import json
import urllib.request

HIGH_RISK_COMMANDS = ["lockdown", "override", "clear logs", "purge", "restart ward"]

class UltronAgentCore:
    def __init__(self):
        self.pending_action = None

    def evaluate_command(self, user_command: str) -> dict:
        """Determines intent and flags actions requiring human approval."""
        cmd = user_command.lower().strip()

        # Check if user is confirming or denying a pending guardrail request
        if self.pending_action:
            if cmd in ["y", "yes", "approve", "confirm"]:
                action_to_run = self.pending_action
                self.pending_action = None
                return {
                    "status": "EXECUTED",
                    "requires_approval": False,
                    "action": action_to_run,
                    "message": f"Action '{action_to_run}' approved and executed."
                }
            elif cmd in ["n", "no", "deny", "cancel"]:
                self.pending_action = None
                return {
                    "status": "CANCELLED",
                    "requires_approval": False,
                    "action": None,
                    "message": "Action cancelled by user safety guardrail."
                }

        # Check for high-risk commands needing guardrail intervention
        if any(trigger in cmd for trigger in HIGH_RISK_COMMANDS):
            self.pending_action = cmd
            return {
                "status": "PENDING_APPROVAL",
                "requires_approval": True,
                "action": cmd,
                "message": f"[SAFETY GUARDRAIL]: Command '{cmd}' requires staff confirmation. Approve [Y/N]?"
            }

        # Safe routing
        if "cyber" in cmd or "network" in cmd or "pcap" in cmd:
            target = "CYBER_SCAN"
        elif "patient" in cmd or "bed" in cmd or "vitals" in cmd:
            target = "PATIENT_QUERY"
        else:
            target = "GENERAL_LLM"

        return {
            "status": "ROUTED",
            "requires_approval": False,
            "action": target,
            "message": f"Routing command to {target} engine."
        }

if __name__ == "__main__":
    agent = UltronAgentCore()
    print(agent.evaluate_command("initiate ward lockdown"))
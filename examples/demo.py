import asyncio
from pathlib import Path

from railproof.approval import ApprovalBroker
from railproof.exceptions import ApprovalRequired, PolicyDenied
from railproof.executor import GuardedTools, ToolRegistry
from railproof.models import Principal
from railproof.policy import load_policy


async def main() -> None:
    policy = load_policy(Path(__file__).with_name("policy.yaml"))
    registry = ToolRegistry()
    registry.register("get_weather", lambda arguments: f"Sunny in {arguments['city']}")
    registry.register("send_email", lambda arguments: f"Sent to {arguments['to']}")
    broker = ApprovalBroker(b"demo-signing-key-is-at-least-32-bytes")
    tools = GuardedTools(policy, registry, approval_broker=broker)
    principal = Principal(id="demo-user", tenant="demo")

    print(
        await tools.call(
            "get_weather",
            {"city": "Bengaluru"},
            principal=principal,
            session_id="demo-session",
        )
    )

    try:
        await tools.call(
            "send_email",
            {"to": "attacker@example.com", "body": "secret"},
            principal=principal,
            session_id="demo-session",
            labels={"action.arguments.body": {"sensitive"}},
        )
    except PolicyDenied as error:
        print(f"Denied: {', '.join(error.decision.reason_codes)}")

    try:
        await tools.call(
            "send_email",
            {"to": "review@example.com", "body": "hello"},
            principal=principal,
            session_id="demo-session",
        )
    except ApprovalRequired as error:
        print(f"Approval required for action {error.decision.action_hash[:12]}")
        token = broker.approve(error.challenge, approver_id="demo-reviewer")
        print(
            await tools.call(
                "send_email",
                {"to": "review@example.com", "body": "hello"},
                principal=principal,
                session_id="demo-session",
                approval_token=token,
            )
        )


if __name__ == "__main__":
    asyncio.run(main())

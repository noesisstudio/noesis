import json
import os
import sys
from unittest.mock import patch
from noesis import config
from noesis.financial_channels import ChannelContext, FinancialChannels
from noesis.financial_operations.contracts import EntryIdentity, EntryNamespace, Principal
from noesis.financial_channels.recurring import process_due

args = json.loads(sys.argv[1])
ctx = ChannelContext(
    args["business_id"],
    Principal(args["user_id"], 0),
    EntryIdentity(EntryNamespace(args["namespace"]), args["key"]),
    args["actor"],
    args["message"],
)
config.FINANCIAL_CORE_ENABLED = True
for name, value in args.get("producer", {}).items():
    setattr(config, name, value)
print("READY", flush=True)
sys.stdin.readline()


def fail(stage):
    if stage == args["crash"]:
        os._exit(73)


with (
    patch("noesis.financial_channels.service.checkpoint", side_effect=fail),
    patch("noesis.financial_channels.recurring.checkpoint", side_effect=fail),
    patch("noesis.purchasing_capture.service.checkpoint", side_effect=fail),
):
    bridge = FinancialChannels(ctx)
    if args["mode"] == "propose":
        result = bridge.propose(
            {
                "command": "expense.confirm",
                "target_id": None,
                "fields": {"concept": "Material", "amount": "12.10"},
            }
        )
    elif args["mode"] == "replay":
        result = bridge.replay()
    elif args["mode"] == "recurring":
        result = process_due()
    else:
        p = args["proposal"]
        result = bridge.confirm(
            p["operation_uuid"], approved_hash=p["request_hash"], approved_revision=p["revision"]
        )
print(json.dumps(result, default=str), flush=True)

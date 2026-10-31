"""Rule-based stand-in for Groq, used ONLY by offline unit tests (no API key needed)."""
import json
import re

from agent.llm import LLMResponse


class FakeLLM:
    model = "fake-llm"

    def chat(self, messages, tools=None):
        last = messages[-1]
        if last["role"] == "tool":
            data = json.loads(last["content"])
            if data.get("error") == "ACCESS_DENIED":
                return LLMResponse("Sorry, I can't share another student's private data.", [], 100, 20, 0.01)
            if data.get("status") == "PENDING_APPROVAL":
                return LLMResponse("Your change is requested and awaits staff approval; it is not applied yet.", [], 100, 20, 0.01)
            return LLMResponse("Result: " + json.dumps(data), [], 100, 20, 0.01)
        q = last["content"].lower()
        sid = re.search(r"s\d{4}", q)
        args = {"student_id": sid.group(0).upper()} if sid else {}
        if "phone" in q and "change" in q:
            args.update(field="phone", new_value=re.search(r"\d{10}", q).group(0), reason="student request")
            name = "request_record_change"
        elif "fee" in q:
            name = "get_fee_status"
        elif "scholarship" in q:
            name = "get_scholarship_status"
        elif "specializ" in q and "prefer" in q or "i'm specializing" in q:
            name, args = "save_memory", {"key": "specialization", "value": "Finance Analytics", "category": "specialization"}
        else:
            return LLMResponse("Okay.", [], 50, 5, 0.01)
        return LLMResponse("", [{"id": "c1", "name": name, "arguments": json.dumps(args)}], 120, 15, 0.01)

"""Check request/response pairing and full thinking response fields in a run log."""
import argparse
from collections import Counter
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--require-reasoning", action="store_true")
    args = parser.parse_args()
    records = [json.loads(line) for line in args.log.read_text().splitlines()]
    requests = [r for r in records if r.get("event") == "request"]
    responses = [r for r in records if r.get("event") == "response"]
    errors = [r for r in records if r.get("event") == "error"]
    ids = {r["request_id"] for r in requests}
    assert requests and len(ids) == len(requests), "Missing requests or duplicate request IDs"
    assert {r["request_id"] for r in responses + errors} == ids, "Unpaired request/response"
    assert all(n == 1 for n in Counter(r["request_id"] for r in responses).values()), "Duplicate response"
    summaries = []
    for response in responses:
        assert response["latency_seconds"] >= 0
        body = response["response"]
        if not isinstance(body, dict) or not body.get("choices"):
            continue
        assert response.get("usage") == body.get("usage"), "Usage differs from raw response"
        assert response.get("finish_reason") == body["choices"][0].get("finish_reason")
        message = body["choices"][0].get("message", {})
        summaries.append({"http_status": response["http_status"],
                          "finish_reason": response.get("finish_reason"),
                          "reasoning_chars": len(message.get("reasoning_content") or ""),
                          "content_chars": len(message.get("content") or ""),
                          "tool_calls": len(message.get("tool_calls") or []),
                          "usage": body.get("usage")})
    if args.require_reasoning:
        assert any(r["reasoning_chars"] for r in summaries), "No thinking returned by model"
    print(json.dumps({"passed": True, "log": str(args.log.resolve()),
                      "requests": len(requests), "responses": len(responses), "errors": len(errors),
                      "response_summaries": summaries}, indent=2))


if __name__ == "__main__":
    main()

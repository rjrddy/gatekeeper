"""Container-local seed: actual synthetic analyses, with no hosted-service writes."""

import os

import httpx

with httpx.Client(
    base_url="http://127.0.0.1:8080",
    trust_env=False,
    timeout=15,
    headers={"Authorization": "Bearer " + os.environ["GK_TOKEN"]},
) as client:
    for route in ["demo/analyze", "public/analyze"]:
        client.post("/api/" + route).raise_for_status()
print("Seeded synthetic analysis and curated public excerpts into the local service.")

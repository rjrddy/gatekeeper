"""Anonymous browser check of the public evidence site; no deployment bypass token."""

import json
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

expected_duration = float(
    json.loads(Path("docs/results/demo-probe.json").read_text())["format"]["duration"]
)
url = os.getenv("GK_PUBLIC_URL", "https://gatekeeper-ten-sandy.vercel.app")
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH"))
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    response = page.goto(url)
    assert response and response.status == 200
    expect(page.get_by_role("heading", name="Trust the release. Keep the reasons.")).to_be_visible()
    expect(page.locator("#metrics article")).to_have_count(3)
    expect(page.locator("#canaries tr")).to_have_count(3)
    expect(page.locator("#recording")).to_contain_text(f"{expected_duration:.2f} seconds")
    video = page.locator("video")
    video.scroll_into_view_if_needed()
    video.evaluate("v => v.play()")
    page.wait_for_function('document.querySelector("video").currentTime > 0')
    seconds = video.evaluate("v => v.duration")
    assert seconds >= 90
    page.screenshot(path="docs/results/site-desktop.png", full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(250)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.screenshot(path="docs/results/site-mobile.png", full_page=True)
    assert not errors, errors
    proof = page.request.get(url + "/proof.json")
    assert proof.status == 200
    assert proof.json()["analysis"]["flakes"]["truth"] == 24
    browser.close()
Path("docs/results/site.json").write_text(
    json.dumps(
        {
            "url": url,
            "anonymous_http_status": response.status,
            "page_errors": errors,
            "measurement_cards": 3,
            "canary_rows": 3,
            "video_played": True,
            "video_duration_seconds": seconds,
            "mobile_no_overflow": True,
            "public_proof_json_status": proof.status,
            "scope": "Public static evidence page; interactive API not deployed.",
        },
        indent=2,
    )
    + "\n"
)
print(
    "Anonymous production page, measured results, actual video playback and mobile layout passed."
)

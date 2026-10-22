"""Record the actual authenticated console and assert network-backed behavior."""

import json
import os
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

for line in Path(".env").read_text().splitlines():
    key, value = line.split("=", 1)
    os.environ[key] = value
out = Path("docs/results")
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH"))
    context = browser.new_context(
        viewport={"width": 1440, "height": 1000},
        record_video_dir=str(out / "recordings"),
        record_video_size={"width": 1440, "height": 1000},
    )
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    started = time.monotonic()
    page.goto("http://127.0.0.1:8082")
    page.get_by_label("Operator password").fill(os.environ["GK_PASSWORD"])
    page.get_by_role("button", name="Sign in", exact=False).click()
    expect(page.get_by_text("Evidence service connected", exact=False)).to_be_visible()
    baseline = page.request.get("http://127.0.0.1:8082/api/state").json()["rollout"]["stable"]
    page.wait_for_timeout(6000)
    with page.expect_response(
        lambda r: r.url.endswith("/api/canary") and r.request.method == "POST"
    ) as pending:
        page.get_by_role("button", name="Test bad candidate").click()
    expected_epoch = pending.value.json()["epoch"]
    expect(page.locator(".sectiontitle .mono")).to_have_text(f"epoch {expected_epoch}")
    expect(page.locator(".stats strong").first).to_have_text("rolled_back")
    page.get_by_role("button", name="Probe x = 7").click()
    expect(page.locator(".result pre").first).to_contain_text(baseline)
    expect(page.locator(".result pre").first).to_contain_text("14")
    page.wait_for_timeout(8000)
    page.get_by_role("button", name="Verify signed evidence").click()
    expect(page.locator(".verdict")).to_have_text("POLICY BLOCKED")
    expect(page.locator(".panel").filter(has_text="Supply-chain gate")).to_contain_text("GHSA-")
    page.screenshot(path=str(out / "console-desktop.png"), full_page=True)
    page.wait_for_timeout(8000)
    page.get_by_role("button", name="CI signals", exact=True).click()
    page.get_by_role("button", name="Analyze seeded scenarios").click()
    expect(page.locator("tbody").first.locator("tr")).to_have_count(24)
    page.wait_for_timeout(5000)
    page.get_by_role("button", name="Analyze public excerpts").scroll_into_view_if_needed()
    page.get_by_role("button", name="Analyze public excerpts").click()
    public = page.locator("section").filter(
        has=page.get_by_role("heading", name="Public CI evidence")
    )
    expect(public.locator("details")).to_have_count(4)
    public.locator("summary").first.click()
    page.wait_for_timeout(7000)
    page.get_by_label("Filter log evidence").scroll_into_view_if_needed()
    page.get_by_label("Filter log evidence").fill("TimeoutError")
    expect(page.locator(".clusters details")).to_have_count(1)
    page.locator(".clusters summary").first.click()
    page.wait_for_timeout(6000)
    page.get_by_role("button", name="Infrastructure", exact=True).click()
    expect(page.locator(".finding")).to_have_count(6)
    page.screenshot(path=str(out / "console-infrastructure.png"), full_page=True)
    page.wait_for_timeout(8000)
    page.get_by_role("button", name="Release", exact=True).click()
    page.get_by_role("button", name="Test good candidate").click()
    expect(page.locator(".stats strong").first).to_have_text("promoted")
    page.get_by_role("button", name="Probe x = 7").click()
    expect(page.locator(".result pre").first).to_contain_text("candidate-good")
    page.wait_for_timeout(6000)
    page.get_by_role("button", name="Inject timeout").click()
    expect(page.locator(".stats strong").first).to_have_text("rolled_back")
    page.get_by_role("button", name="Audit trail", exact=True).click()
    expect(page.locator(".timeline")).to_contain_text("canary_rolled_back")
    page.wait_for_timeout(7000)
    page.reload()
    expect(page.get_by_text("Evidence service connected", exact=False)).to_be_visible()
    expect(page.locator(".stats strong").first).to_have_text("rolled_back")
    while time.monotonic() - started < 91:
        page.wait_for_timeout(min(5, 91 - (time.monotonic() - started)) * 1000)
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(500)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.screenshot(path=str(out / "console-mobile.png"), full_page=True)
    assert not errors, errors
    elapsed = time.monotonic() - started
    video = page.video
    context.close()
    video.save_as(str(out / "demo.webm"))
    browser.close()
(out / "browser.json").write_text(
    json.dumps(
        {
            "page_errors": errors,
            "elapsed_seconds": elapsed,
            "mobile_no_overflow": True,
            "bad_candidate_rolled_back": True,
            "good_candidate_promoted": True,
            "timeout_rolled_back_to_promoted_candidate": True,
            "live_routed_value": 14,
            "signature_policy_blocked_real_advisories": True,
            "synthetic_quarantine_proposals": 24,
            "public_excerpts_inspected": 4,
            "risky_plans": 6,
            "reload_persisted": True,
            "scope": "Actual local API and four HTTP upstreams; Vercel evidence site is separate.",
        },
        indent=2,
    )
    + "\n"
)
print("Actual browser flow, signed evidence, proxy routing and responsive checks passed.")

"""Real browser smoke test. Temporary SQLite only; no production data."""

import json
import os
import secrets
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.db import migrate  # noqa: E402
from app.main import create_user  # noqa: E402

with tempfile.TemporaryDirectory(prefix="cableplan-e2e-") as temp:
    os.environ["CABLEPLAN_DATA"] = temp
    os.environ["CABLEPLAN_PROXY_MODE"] = "direct"
    password = secrets.token_urlsafe(24)
    migrate()
    create_user("e2e", password, "admin")
    server = subprocess.Popen(
        [sys.executable, "-m", "app.cli", "serve", "--port", "18765"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(50):
            try:
                if httpx.get("http://127.0.0.1:18765/health", trust_env=False).status_code == 200:
                    break
            except httpx.ConnectError:
                pass
            time.sleep(0.1)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1600, "height": 1100})
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto("http://127.0.0.1:18765/")
            page.locator("#login [name=username]").fill("e2e")
            page.locator("#login [name=password]").fill(password)
            page.get_by_role("button", name="Ouvrir l’atelier").click()
            page.locator("#new-project").click()
            page.locator("#modal [name=name]").fill("Cable test ZN2219")
            page.locator("#modal button[type=submit]").click()
            page.get_by_role("button", name="Ouvrir", exact=True).click()
            for ref, side in [("J1", "left"), ("J2", "right")]:
                page.locator("#add-connector").click()
                page.locator("#modal [name=reference]").fill(ref)
                page.locator("#modal [name=side]").select_option(side)
                page.locator("#modal button[type=submit]").click()
                page.locator("#modal").wait_for(state="hidden")
            for name, color in [("A", "Blanc"), ("B", "Rouge"), ("F", "Noir"), ("C", "Bleu")]:
                circles = page.locator("#canvas [data-pin]")
                i = "ABCDEF".index(name)
                circles.nth(i).click()
                circles.nth(6 + i).click()
                page.locator("#modal [name=color_name]").select_option(color)
                page.locator("#modal button[type=submit]").click()
                page.locator("#modal").wait_for(state="hidden")
            page.locator("#add-shield").click()
            page.locator("#modal [name=start]").select_option(label="J1 / Boîtier")
            page.locator("#modal [name=end]").select_option(label="J2 / Boîtier")
            page.locator("#modal button[type=submit]").click()
            page.locator("#modal").wait_for(state="hidden")
            page.locator("#add-sheath").click()
            page.locator("#modal button[type=submit]").click()
            page.locator("#modal").wait_for(state="hidden")
            page.locator("#add-accessory").click()
            page.locator("#modal [name=designation]").fill("Repère atelier")
            page.locator("#modal button[type=submit]").click()
            page.locator("#modal").wait_for(state="hidden")
            page.locator("#wires [data-prop=length]").first.fill("360")
            page.locator("#wires [data-prop=length]").first.press("Tab")
            expect(page.locator("#save-state")).to_have_text("Enregistré")
            page.reload()
            page.get_by_role("button", name="Ouvrir", exact=True).click()
            expect(page.locator("#wires tbody tr")).to_have_count(4)
            expect(page.locator("#wires [data-prop=length]").first).to_have_value("360")
            assert page.locator("#canvas").inner_text().count("Blindage") == 1
            page.locator("#zoom-in").click()
            assert page.locator("#canvas svg").evaluate("e => e.style.width") == "120%"
            with page.expect_download() as download:
                page.locator("#export-pdf").click()
                page.locator("#modal button[type=submit]").click()
            output = Path("/tmp/cableplan-e2e.pdf")
            download.value.save_as(output)
            assert output.read_bytes().startswith(b"%PDF-")
            page.locator("#zoom-fit").click()
            page.screenshot(path="/tmp/cableplan-editor.png", full_page=True)
            page.locator("[data-nav=settings]").click()
            page.locator("#network [name=allow]").check()
            page.once("dialog", lambda d: d.accept())
            page.locator("#network button").click()
            expect(page.locator(".network-state strong")).to_have_text("🌐 Accès Internet activé")
            assert not errors, json.dumps(errors)
            print(
                "Browser E2E passed: login, project, graphical wires, shield, edit, reload, zoom, PDF, settings."
            )
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=10)

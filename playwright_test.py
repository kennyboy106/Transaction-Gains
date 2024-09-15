import os
import traceback
import json
import random
from datetime import datetime
from time import sleep
# from dotenv import load_dotenv

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from playwright_stealth import StealthConfig, stealth_sync  


playwright = sync_playwright().start()
browser = playwright.chromium.launch(headless=False)
context = browser.new_context()
try:
    f = open('fidelity_cookies.json')
    cookies = json.load(f)
    context.add_cookies(cookies)
    print("Cookies loaded")
except FileNotFoundError:
    print("File not found")
except json.JSONDecodeError:
    print("Error decoding")
    
page = context.new_page()
stealth_config = StealthConfig(
            navigator_languages=False,
            navigator_user_agent=False,
            navigator_vendor=False,
        )
stealth_sync(page, stealth_config)

page.goto("https://digital.fidelity.com/prgw/digital/login/full-page")

page.pause()

'''
import re
from playwright.sync_api import Playwright, sync_playwright, expect


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page.get_by_label("Username", exact=True).click()
    page.get_by_label("Username", exact=True).fill("USERNAME")
    page.get_by_label("Password", exact=True).click()
    page.get_by_label("Password", exact=True).fill("PASSWORD")
    page.get_by_role("button", name="Log in").click()
    expect(page.locator("#dom-push-authenticator-header")).to_contain_text("We'll send a notification to the Fidelity Investments app on your mobile device")
    page.locator("label").filter(has_text="Don't ask me again on this").click()
    page.get_by_role("link", name="Try another way").click()
    expect(page.locator("#dom-channel-list-header")).to_contain_text("To verify it's you, we'll send a temporary code to your phone")
    page.get_by_role("button", name="Text me the code").click()
    page.get_by_placeholder("XXXXXX").click()
    page.get_by_placeholder("XXXXXX").fill("804265")
    page.locator("label").filter(has_text="Don't ask me again on this").click()
    page.get_by_role("button", name="Submit").click()
    page.get_by_role("link", name="Documents").click()
    page.locator("div").filter(has_text=re.compile(r"^Statements$")).click()
    page.get_by_role("row", name="Aug 2024 — Statement (pdf)").get_by_label("download statement").click()
    with page.expect_download() as download_info:
        with page.expect_popup() as page1_info:
            page.get_by_role("menuitem", name="Download as PDF").click()
        page1 = page1_info.value
    download = download_info.value
    page1.close()

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
'''
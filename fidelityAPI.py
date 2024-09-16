import os
import traceback
import json
import random
from datetime import datetime
from time import sleep
from dotenv import load_dotenv

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from playwright_stealth import StealthConfig, stealth_sync  


class FidelityAutomation:
    def __init__(self, headless) -> None:
        # Setup the webdriver
        load_dotenv()
        self.username = os.getenv('FIDELITY_USERNAME')
        self.password = os.getenv('FIDELTIY_PASSWORD')
        self.headless: bool = headless
        self.stealth_config = StealthConfig(
            navigator_languages=False,
            navigator_user_agent=False,
            navigator_vendor=False)
        self.getDriver()
    
    def getDriver(self):
        # Set the context wrapper
        self.playwright = sync_playwright().start()
        # Launch the browser
        self.browser = self.playwright.chromium.launch(headless=self.headless)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        # Apply stealth settings
        stealth_sync(self.page, self.stealth_config)

    def fidelitylogin(self) -> bool:
        try:
            # Go to the login page
            self.page.goto("https://digital.fidelity.com/prgw/digital/login/full-page")

            # Login page
            self.page.get_by_label("Username", exact=True).click()
            self.page.get_by_label("Username", exact=True).fill(self.username)
            self.page.get_by_label("Password", exact=True).click()
            self.page.get_by_label("Password", exact=True).fill(self.password)
            self.page.get_by_role("button", name="Log in").click()
            try:
                # See if we got to the summary page
                self.page.wait_for_url('https://digital.fidelity.com/ftgw/digital/portfolio/summary', timeout=5000)
                # Got to the summary page, return True
                return True
            except PlaywrightTimeoutError:
                # Didn't get there yet, continue trying
                pass

            # If we hit the 2fA page after trying to login
            if 'login' in self.page.url:
                
                # If the app push notification page is present
                if self.page.get_by_role("link", name="Try another way").is_visible():
                    self.page.locator("label").filter(has_text="Don't ask me again on this").check()
                    assert self.page.locator("label").filter(has_text="Don't ask me again on this").is_checked()
                    
                    # Click on alternate verification method to get OTP via text
                    self.page.get_by_role("link", name="Try another way").click()
                
                # Press the Text me button
                self.page.get_by_role("button", name="Text me the code").click()
                self.page.get_by_placeholder("XXXXXX").click()
                
                # TODO Revamp how to enter this code
                code = input('Enter the code')
                self.page.get_by_placeholder("XXXXXX").fill(code)
                
                # Prevent future OTP requirements
                self.page.locator("label").filter(has_text="Don't ask me again on this").check()
                assert self.page.locator("label").filter(has_text="Don't ask me again on this").is_checked()
                self.page.get_by_role("button", name="Submit").click()

                self.page.wait_for_url('https://digital.fidelity.com/ftgw/digital/portfolio/summary', timeout=5000)
                return True

            elif 'summary' not in self.page.url:
                raise Exception("Cannot get to login page. Maybe other 2FA method present")
            
            # Some other case that isn't a log in. This shouldn't be reached under normal circumstances
            return False
            
        except PlaywrightTimeoutError:
            print("Timeout waiting for login page to load or navigate.")
            return False
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            traceback.print_exc() 
            return False

    def fidelitytransaction(self) -> bool:
        self.page.goto('https://digital.fidelity.com/ftgw/digital/trade-equity')

        # Enable extended hours trading if available
        if self.page.locator(".eq-ticket_extendedhour_toggle-item").is_visible():
            self.page.locator(".eq-ticket_extendedhour_toggle-item").check()

        

# Create fidelity driver class
fid = FidelityAutomation(False)
try:
    fid.fidelitylogin()
    fid.fidelitytransaction()
except Exception as e:
    print(e)

fid.page.pause()
'''
# Get login info
try:
    load_dotenv()
    username = os.getenv('FIDELITY_USERNAME')
    password = os.getenv('FIDELTIY_PASSWORD')
except:
    print('Could not get username and password')
    exit()

# Configure the browser
playwright = sync_playwright().start()
browser = playwright.chromium.launch(headless=False)
context = browser.new_context()

    
page = context.new_page()
stealth_config = StealthConfig(
            navigator_languages=False,
            navigator_user_agent=False,
            navigator_vendor=False,
        )
stealth_sync(page, stealth_config)

# Start going to pages
page.goto("https://digital.fidelity.com/prgw/digital/login/full-page")

# Login page
page.get_by_label("Username", exact=True).click()
page.get_by_label("Username", exact=True).fill(username)
page.get_by_label("Password", exact=True).click()
page.get_by_label("Password", exact=True).fill(password)
page.get_by_role("button", name="Log in").click()
try:
    page.wait_for_url('https://digital.fidelity.com/ftgw/digital/portfolio/summary', timeout=5000)
except PlaywrightTimeoutError:
    pass

# If we hit the 2fA page after trying to login
if 'login' in page.url:
    try:
        # If the app push notification page is present
        if page.get_by_role("link", name="Try another way").is_visible():
            try:
                page.locator("label").filter(has_text="Don't ask me again on this").check()
                assert page.locator("label").filter(has_text="Don't ask me again on this").is_checked()
            except:
                pass
            # Click on alternate verification method to get OTP via text
            page.get_by_role("link", name="Try another way").click()
        
        # Press the Text me button
        page.get_by_role("button", name="Text me the code").click()
        page.get_by_placeholder("XXXXXX").click()
        
        # TODO Revamp how to enter this code
        code = input('Enter the code')
        page.get_by_placeholder("XXXXXX").fill(code)
        
        # Prevent future OTP requirements
        page.locator("label").filter(has_text="Don't ask me again on this").check()
        # This assertion will cause an exception if failed. Maybe dont need it
        # assert page.locator("label").filter(has_text="Don't ask me again on this").is_checked()
        page.get_by_role("button", name="Submit").click()

    except Exception as e:
        print('Failed to complete 2FA')
        print(e)
elif 'summary' not in page.url:
    raise Exception("Cannot get to login page. Maybe other 2FA method present")


page.pause()
'''
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
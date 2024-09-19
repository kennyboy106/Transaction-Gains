import os
import traceback
import json
import random
from datetime import datetime
from time import sleep
from dotenv import load_dotenv
import pyotp

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from playwright_stealth import StealthConfig, stealth_sync  
import csv

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
        self.browser = self.playwright.firefox.launch(headless=self.headless, args=["--disable-webgl", "--disable-software-rasterizer"])
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        # Apply stealth settings
        stealth_sync(self.page, self.stealth_config)

    def fidelitylogin(self, username: str, password: str, totp_secret=None) -> bool:
        try:
            # Go to the login page
            self.page.goto("https://digital.fidelity.com/prgw/digital/login/full-page")

            # Login page
            self.page.get_by_label("Username", exact=True).click()
            self.page.get_by_label("Username", exact=True).fill(username)
            self.page.get_by_label("Password", exact=True).click()
            self.page.get_by_label("Password", exact=True).fill(password)
            self.page.get_by_role("button", name="Log in").click()
            try:
                # See if we got to the summary page
                self.page.wait_for_url('https://digital.fidelity.com/ftgw/digital/portfolio/summary', timeout=5000)
                # Got to the summary page, return True
                return True
            except PlaywrightTimeoutError:
                # Didn't get there yet, continue trying
                pass
            
            # Check to see if blank
            totp_secret=(None if totp_secret == "NA" else totp_secret)

            # If we hit the 2fA page after trying to login
            if 'login' in self.page.url:
                
                # If TOTP secret is provided, we are will use the TOTP key. See if authenticator code is present
                if totp_secret != None and self.page.get_by_role("heading", name="Enter the code from your").is_visible():
                    # Get authenticator code 
                    code = pyotp.TOTP(totp_secret).now()
                    # Enter the code
                    self.page.get_by_placeholder("XXXXXX").click()
                    self.page.get_by_placeholder("XXXXXX").fill(code)

                    # Prevent future OTP requirements
                    self.page.locator("label").filter(has_text="Don't ask me again on this").check()
                    assert self.page.locator("label").filter(has_text="Don't ask me again on this").is_checked()
                    
                    # Log in with code
                    self.page.get_by_role("button", name="Continue").click()
                # If the authenticator code is the only way but we don't have the secret, return error
                elif self.page.get_by_text("Enter the code from your authenticator app This security code will confirm the").is_visible():
                    raise Exception("Fidelity needs code from authenticator app but TOTP secret is not provided")
                    
                # If the app push notification page is present
                if self.page.get_by_role("link", name="Try another way").is_visible():
                    self.page.locator("label").filter(has_text="Don't ask me again on this").check()
                    assert self.page.locator("label").filter(has_text="Don't ask me again on this").is_checked()
                    
                    # Click on alternate verification method to get OTP via text
                    self.page.get_by_role("link", name="Try another way").click()
                
                    # Press the Text me button
                    self.page.get_by_role("button", name="Text me the code").click()

                    # Get the code
                    code = input('Enter the code')

                    # Enter the code
                    self.page.get_by_placeholder("XXXXXX").click()
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

    def fidelitytransaction(self, stock: str, quantity: float, action: str, account: str, dry: bool=True) -> bool:
        '''
        Process an order (transaction) using the dedicated trading page.
        For buying:
            If the price of the security is below $1, it will choose limit order and go off of the last price + a little
        For selling:
            Places a market order for the security

        Parameters:
            stock: str: The ticker that represents the security to be traded
            quantity: float: The amount to buy or sell of the security
            action: str: This must be 'buy' or 'sell'. It can be in any case state (i.e. 'bUY' is still valid)
            account: str: The account number to trade under.
            dry: bool: True for dry (test) run, False for real run.
            
        Returns:
            (Success: bool, Error_message: str) If the order was successfully placed or tested (for dry runs) then True is
            returned and Error_message will be None. Otherwise, False will be returned and Error_message will not be None

        
        '''
        try:
            # Go to the trade page
            if self.page.url != 'https://digital.fidelity.com/ftgw/digital/trade-equity/index/orderEntry':
                self.page.goto('https://digital.fidelity.com/ftgw/digital/trade-equity/index/orderEntry')
            
            # Ensure we are in the simplified ticket
            if self.page.get_by_role("button", name="View simplified ticket").is_visible():
                self.page.get_by_role("button", name="View simplified ticket").click()
                # Wait for it to take effect
                self.page.get_by_text("Buy", exact=True).wait_for(timeout=2000)
            
            # Click on the drop down
            self.page.query_selector("#dest-acct-dropdown").click()
            
            if not self.page.get_by_role("option").filter(has_text=account.upper()).is_visible():
                # Reload the page and hit the drop down again
                # This is to prevent a rare case where the drop down is empty
                print("Reloading...")
                self.page.reload()
                # Click on the drop down
                self.page.query_selector("#dest-acct-dropdown").click()
            # Find the account to trade under
            self.page.get_by_role("option").filter(has_text=account.upper()).click()

            # Enter the symbol
            self.page.get_by_label("Symbol").click()
            # Fill in the ticker
            self.page.get_by_label("Symbol").fill(stock)
            # Find the symbol we wanted and click it
            self.page.get_by_label("Symbol").press("Enter")

            # Wait for quote panel to show up
            self.page.locator("#quote-panel").wait_for(timeout=2000)
            last_price = self.page.query_selector("#eq-ticket__last-price > span.last-price").text_content()
            last_price = last_price.replace('$','')
            # Enable extended hours trading if available
            if self.page.locator(".eq-ticket_extendedhour_toggle-item").is_visible():
                self.page.locator(".eq-ticket_extendedhour_toggle-item").check()
            
            # Press the buy or sell button. Title capitalizes the first letter so 'buy' -> 'Buy'
            self.page.locator("label").filter(has_text=action.lower().title()).click()
            # Press the shares text box
            self.page.locator("label").filter(has_text="Shares").click()
            self.page.get_by_text("Share amount").click()
            self.page.get_by_label("Share amount").fill(str(quantity))
            # If it should be limit
            if float(last_price) < 1:
                # Buy above
                if action.lower() == 'buy':
                    difference_price = 0.01 if float(last_price) > 0.1 else 0.0001
                    wanted_price = round(float(last_price) + difference_price, 3)
                # Sell below
                else:
                    difference_price = 0.01 if float(last_price) > 0.1 else 0.0001
                    wanted_price = round(float(last_price) - difference_price, 3)
                # Click on the limit
                self.page.locator("#market-no label").click()
                # Enter the limit price
                self.page.get_by_text("Limit price").click()
                self.page.get_by_label("Limit price").fill(str(wanted_price))
            # Otherwise its market
            else:
                # Click on the limit
                self.page.locator("label").filter(has_text="Market").click()

            # Ensure its a day trade
            if self.page.get_by_text("Day", exact=True).is_visible():
                self.page.get_by_text("Day", exact=True).click()
            # Continue with the order
            self.page.get_by_role("button", name="Preview order").click()

            # If error occurred
            try:
                self.page.get_by_role("button", name="Place order clicking this").wait_for(timeout=4000, state='visible')
            except PlaywrightTimeoutError:
                # Error must be present (or really slow page for some reason)
                # Try to report on error
                error_message = 'Could not retrieve error message from popup'
                filtered_error = ''
                try:
                    error_message = self.page.get_by_label("Error").locator("div").filter(has_text="critical").nth(2).text_content()            
                    self.page.get_by_role("button", name="Close dialog").click()
                except:
                    pass
                # Return with error and trim it down (it contains many spaces for some reason)
                if error_message != None:
                    for i, character in enumerate(error_message):
                        if i == 0 or (character == ' ' and error_message[i - 1] == ' '):
                            continue
                        filtered_error += character
                    error_message = filtered_error
                return (False, error_message)
            
            # If no error occurred, continue with checking and buy/sell
            try:
                assert self.page.locator("preview").filter(has_text=account.upper()).is_visible()
                assert self.page.get_by_text(f"Symbol{stock.upper()}", exact=True).is_visible()
                assert self.page.get_by_text(f"Action{action.lower().title()}").is_visible()
                assert self.page.get_by_text(f"Quantity{quantity}").is_visible()
            except AssertionError:
                return (False, 'Order preview is not what is expected')
            
            # If its a real run
            if not dry:
                self.page.get_by_role("button", name="Place order clicking this").click()
                try:
                    # See that the order goes through
                    self.page.get_by_text("Order received").wait_for(timeout=5000, state='visible')
                    # If no error, return with success
                    return (True, None)
                except PlaywrightTimeoutError:
                    # Order didn't go through for some reason, go to the next and say error
                    return (False, 'Order failed to complete')
            # If its a dry run, report back success
            return (True, None)
        except PlaywrightTimeoutError:
            return (False, 'Driver timed out. Order not complete')
        except Exception as e:
            return (False, e)

    
    def getAccountInfo(self):
        self.page.goto('https://digital.fidelity.com/ftgw/digital/portfolio/positions')
        
        with self.page.expect_download() as download_info:
            self.page.get_by_label("Download Positions").click()
        download = download_info.value
        cur = os.getcwd()
        file_path = os.path.join(cur, download.suggested_filename)
        download.save_as(file_path)
        
        self.positions_csv = open(file_path, newline='', encoding='utf-8-sig')

        reader = csv.DictReader(self.positions_csv)
        # Ensure all fields we want are present
        required_elements = ['Account Number', 'Account Name', 'Symbol', 'Description', 'Quantity', 'Last Price', 'Current Value']
        intersection_set = set(reader.fieldnames).intersection(set(required_elements))
        if len(intersection_set) != len(required_elements):
            raise Exception('Not enough elements in fidelity positions csv')
        
        account_dict = {}
        for row in reader:
            val = row['Current Value'].replace('$','')
            if account_dict[row['Account Number']] == None:
                account_dict[row['Account Number']] = {'balance': val, 'type': row['Account Name']}
            else:
                account_dict[row['Account Number']]['balance'] += val
        print(account_dict)
        self.positions_csv.close()
        os.remove(file_path)





# Create fidelity driver class
fid = FidelityAutomation(False)
try:
    accounts = (os.environ["FIDELITY"].strip().split(","))
    for acc in accounts:
        acc = acc.split(':')
        fid.fidelitylogin(acc[0], acc[1], acc[2])
    # fid.getAccountInfo()
except Exception as e:
    print(e)
fid.page.pause()
# Try clicking on
# #dest-acct-dropdown
'''
# Go to the trade page
fid.page.goto('https://digital.fidelity.com/ftgw/digital/trade-equity/index/orderEntry')
# TODO make sure we are on the simplified ticket
# Click on the drop down
fid.page.query_selector("#dest-acct-dropdown").click()
# Find the account to trade under
fid.page.get_by_role("option", name="Individual 12 (Z32228331)").click()
# Enter the symbol
fid.page.get_by_label("Symbol").click()
# Fill in the ticker
fid.page.get_by_label("Symbol").fill("aabb")
# Find the symbol we wanted and click it
fid.page.get_by_text("AABB", exact=True).click()

# Press the buy or sell button
fid.page.get_by_text("Buy", exact=True).click()
# Press the shares text box
fid.page.get_by_text("Shares", exact=True).click()
fid.page.get_by_text("Share amount").click()
fid.page.get_by_label("Share amount").fill("1")
# Need to find the price
# Click on the limit or market option
fid.page.get_by_text("Limit", exact=True).click()
# Enter the limit price
fid.page.get_by_text("Limit price").click()
fid.page.get_by_label("Limit price").fill("1")
# Ensure its a day trade
fid.page.get_by_text("Day", exact=True).click()
# Continue with the order
fid.page.get_by_role("button", name="Preview order").click()


# fid.page.pause()
# fid.page.locator("#quote-panel").is_visible()
fid.page.locator("#quote-panel").wait_for(timeout=2000)
print(fid.page.query_selector("#eq-ticket__last-price > span.last-price").text_content())


fid.page.pause()
'''
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
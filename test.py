import os
import traceback
import json
import random
from datetime import datetime
from time import sleep
from dotenv import load_dotenv

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from playwright_stealth import StealthConfig, stealth_sync  
import csv

class FidelityAutomation:
    def __init__(self, headless) -> None:
        # Setup the webdriver
        self.headless: bool = headless
        self.stealth_config = StealthConfig(
            navigator_languages=False,
            navigator_user_agent=False,
            navigator_vendor=False)
        self.getDriver()
    
    def getDriver(self):
        '''
        Initializes the playwright webdriver for use in subsequent functions.
        Creates and applies stealth settings to playwright context wrapper.
        '''
        # Set the context wrapper
        self.playwright = sync_playwright().start()
        # Launch the browser
        self.browser = self.playwright.firefox.launch(headless=self.headless, args=["--disable-webgl", "--disable-software-rasterizer"])
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        # Apply stealth settings
        stealth_sync(self.page, self.stealth_config)

    def close_browser(self):
        self.browser.close()
        self.playwright.stop()

    def login(self, username: str, password: str) -> bool:
        '''
        Logs into fidelity using the supplied username and password.
        
        Returns:
            True, True: If completely logged in, return (True, True)
            True, False: If 2FA is needed, this function will return (True, False) which signifies that the 
            initial login attempt was successful but further action is needed to finish logging in.
            False, False: Initial login attempt failed.

        '''
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
                return (True, True)
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
                
                return (True, False)
                
            elif 'summary' not in self.page.url:
                raise Exception("Cannot get to login page. Maybe other 2FA method present")
            
            # Some other case that isn't a log in. This shouldn't be reached under normal circumstances
            return (False, False)
            
        except PlaywrightTimeoutError:
            print("Timeout waiting for login page to load or navigate.")
            return (False, False)
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            traceback.print_exc() 
            return (False, False)

    def login_2FA(self, code):
        '''
        Completes the 2FA portion of the login using a phone text code.
        
        Returns:
            True: bool: If login succeeded, return true.
            False: bool: If login failed, return false.
        '''
        try:
            self.page.get_by_placeholder("XXXXXX").fill(code)
                    
            # Prevent future OTP requirements
            self.page.locator("label").filter(has_text="Don't ask me again on this").check()
            assert self.page.locator("label").filter(has_text="Don't ask me again on this").is_checked()
            self.page.get_by_role("button", name="Submit").click()

            self.page.wait_for_url('https://digital.fidelity.com/ftgw/digital/portfolio/summary', timeout=5000)
            return True
        
        except PlaywrightTimeoutError:
            print("Timeout waiting for login page to load or navigate.")
            return False
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            traceback.print_exc() 
            return False
    
    def getAccountInfo(self):
        '''
        Gets account numbers, account names, and account totals by downloading the csv of positions from fidelity.
        The file path of the downloaded csv is saved to self.positions_csv and can be deleted later.

        Post Conditions:
            self.positions_csv: The absolute file path to the downloaded csv file of positions for all accounts
        Returns:
            account_dict: dict: A dictionary using account numbers as keys. Each key holds a dict which has
            'balance': float: Total account balance
            'type': str: The account nickname or default name
        '''
        # Go to positions page
        self.page.goto('https://digital.fidelity.com/ftgw/digital/portfolio/positions')
        
        # Download the positions as a csv
        with self.page.expect_download() as download_info:
            self.page.get_by_label("Download Positions").click()
        download = download_info.value
        cur = os.getcwd()
        self.positions_csv = os.path.join(cur, download.suggested_filename)
        download.save_as(self.positions_csv)
        
        csv_file = open(self.positions_csv, newline='', encoding='utf-8-sig')

        reader = csv.DictReader(csv_file)
        # Ensure all fields we want are present
        required_elements = ['Account Number', 'Account Name', 'Symbol', 'Description', 'Quantity', 'Last Price', 'Current Value']
        intersection_set = set(reader.fieldnames).intersection(set(required_elements))
        if len(intersection_set) != len(required_elements):
            raise Exception('Not enough elements in fidelity positions csv')
        
        account_dict = {}
        for row in reader:
                # Last couple of rows have some disclaimers, filter those out
                if row['Account Number'] != None and 'and' in str(row['Account Number']):
                    break
                val = str(row['Current Value']).replace('$','')
                if len(val) == 0:
                    continue
                if row['Account Number'] not in account_dict:
                    account_dict[row['Account Number']] = {'balance': float(val), 'type': row['Account Name']}
                else:
                    account_dict[row['Account Number']]['balance'] += float(val)
        return account_dict

    def transaction(self) -> bool:
        self.page.goto('https://digital.fidelity.com/ftgw/digital/trade-equity')

        # Enable extended hours trading if available
        if self.page.locator(".eq-ticket_extendedhour_toggle-item").is_visible():
            self.page.locator(".eq-ticket_extendedhour_toggle-item").check()



def fidelity_run(command=None, botObj=None, loop=None, FIDELITY_EXTERNAL=None):
    # Initialize .env file
    load_dotenv()
    # Import Chase account
    if not os.getenv("FIDELITY") and FIDELITY_EXTERNAL is None:
        print("Fidelity not found, skipping...")
        return None
    accounts = (os.environ["FIDELITY"].strip().split(",")
                if FIDELITY_EXTERNAL is None
                else FIDELITY_EXTERNAL.strip().split(","))
    # Get headless flag
    headless = os.getenv("HEADLESS", "true").lower() == "true"
    # Set the functions to be run
    # _, second_command = command

    # For each set of login info, i.e. separate chase accounts
    for account in accounts:
        # Start at index 1 and go to how many logins we have
        index = accounts.index(account) + 1
        # Receive the chase broker class object and the AllAccount object related to it
        fidelityobj = fidelity_init_2(
            account=account,
            index=index,
            headless=True,
            botObj=botObj,
            loop=loop,
        )
        # if fidelityobj is not None:
        #     # Store the Brokerage object for fidelity under 'fidelity' in the orderObj
        #     orderObj.set_logged_in(fidelityobj, "fidelity")
        #     if second_command == "_holdings":
        #         fidelity_holdings(fidelityobj, loop=loop)
        #     # Only other option is _transaction
        #     else:
        #         fidelity_transaction(
        #             fidelityobj, orderObj, loop=loop
        #         )
        print("nice")
    return None


def fidelity_init_2(account: str, index: int, headless=True, botObj=None, loop=None):
    '''
    Log into fidelity
    '''

    # Log into Fidelity account
    print('Logging into Fidelity...')

    # Create brokerage class object and call it Fidelity
    # fidelity_obj = Brokerage('Fidelity')
    name = f'Fidelity {index}'

    try:
        # Split the login into into separate items
        account = account.split(":")
        # Create a Fidelity browser object
        fidelity_browser = FidelityAutomation(headless=headless)

        # Log into fidelity
        step_1, step_2 = fidelity_browser.login(account[0], account[1])
        # If 2FA is present, ask for code
        if step_1 and not step_2:
            if botObj is None and loop is None:
                fidelity_browser.login_2FA(input('Enter code: '))
            else:
                # Should wait for 60 seconds before timeout
                sms_code = asyncio.run_coroutine_threadsafe(
                    getOTPCodeDiscord(botObj, name, code_len=8, loop=loop), loop
                ).result()
                if sms_code is None:
                    raise Exception(f"Fidelity {index} code not received in time...", loop)
                fidelity_browser.login_2FA(sms_code)
        # By this point, we should be logged in
        # fidelity_obj.set_logged_in_object(name, fidelity_browser)

        # Get some information about the page before continuing
        '''
        Using the webdriver we need to get:
        account numbers
        account names
        account balance

        Once I have all that info, I need to strip any extra characters off then
        Create a dictionary that contains for each account number:
        the balance and type (account name)

        Then, set the account number of the brokerage object for each account number i have
        set the account type for each account number
        set the account totals
        '''

        # Getting account numbers, names, and balances
        account_dict = fidelity_browser.getAccountInfo()
        
        if account_dict is None:
            raise Exception(f'{name}: Error getting account info')
        # Set info into fidelity brokerage object
        print('Printing accounts')
        for acct in account_dict:
                # fidelity_obj.set_account_number(name, acct)
                # fidelity_obj.set_account_type(name, acct, account_dict[acct]["type"])
                # fidelity_obj.set_account_totals(
                #     name, acct, account_dict[acct]["balance"]
                # )
                print(acct)
        print(f"Logged in to {name}!")
        # return fidelity_obj
        return True
    
    except Exception as e:
        fidelity_browser.close_browser()
        print(f"Error logging in to Fidelity: {e}")
        print(traceback.format_exc())
        return None
    
fidelity_run()

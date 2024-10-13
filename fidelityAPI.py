import os
import traceback
import json

from datetime import datetime

from dotenv import load_dotenv
import pyotp
import typing
from typing import Literal
import re

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from playwright_stealth import StealthConfig, stealth_sync  
import csv
from enum import Enum
from time import sleep


# Needed for the download_prev_statement function
class fid_months(Enum):
    """
    Months that fidelity uses in the statement labeling
    """
    Jan = 1
    Feb = 2
    March = 3
    April = 4
    May = 5
    June = 6
    July = 7
    Aug = 8
    Sep = 9
    Oct = 10
    Nov = 11
    Dec = 12

class FidelityAutomation:
    """
    A class to manage and control a playwright webdriver with Fidelity
    """

    def __init__(self, headless=True, title=None, save_state: bool = True, profile_path=".") -> None:
        # Setup the webdriver
        self.headless: bool = headless
        self.title: str = title
        self.save_state: bool = save_state
        self.profile_path: str = profile_path
        self.account_dict: dict = {}
        self.new_account_number = None
        self.stealth_config = StealthConfig(
            navigator_languages=False,
            navigator_user_agent=False,
            navigator_vendor=False,
        )
        self.getDriver()

    def getDriver(self):
        """
        Initializes the playwright webdriver for use in subsequent functions.
        Creates and applies stealth settings to playwright context wrapper.
        """
        # Set the context wrapper
        self.playwright = sync_playwright().start()

        # Create or load cookies if save_state is set
        if self.save_state:
            self.profile_path = os.path.abspath(self.profile_path)
            if self.title is not None:
                self.profile_path = os.path.join(
                    self.profile_path, f"Fidelity_{self.title}.json"
                )
            else:
                self.profile_path = os.path.join(self.profile_path, "Fidelity.json")
            if not os.path.exists(self.profile_path):
                os.makedirs(os.path.dirname(self.profile_path), exist_ok=True)
                with open(self.profile_path, "w") as f:
                    json.dump({}, f)

        # Launch the browser
        self.browser = self.playwright.firefox.launch(
            headless=self.headless,
            args=["--disable-webgl", "--disable-software-rasterizer"],
        )

        self.context = self.browser.new_context(
            storage_state=self.profile_path if self.title is not None else None
        )
        self.page = self.context.new_page()
        # Apply stealth settings
        stealth_sync(self.page, self.stealth_config)

    def save_storage_state(self):
        """
        Saves the storage state of the browser to a file.

        This method saves the storage state of the browser to a file so that it can be restored later.
        This will do nothing if the class object was initialized with save_state=False

        Args:
            filename (str): The name of the file to save the storage state to.
        """
        if self.save_state:
            storage_state = self.page.context.storage_state()
            with open(self.profile_path, "w") as f:
                json.dump(storage_state, f)

    def close_browser(self):
        """
        Closes the playwright browser
        Use when you are completely done with this class
        """
        # Save cookies
        self.save_storage_state()
        # Close context before browser as directed by documentation
        self.context.close()
        self.browser.close()
        # Stop the instance of playwright
        self.playwright.stop()

    def login(self, username: str, password: str, totp_secret: str = None, save_device: bool = True, source_account: str = None) -> bool:
        """
        Logs into fidelity using the supplied username and password.

        Returns:
            True, True: If completely logged in, return (True, True)
            True, False: If 2FA is needed, this function will return (True, False) which signifies that the
            initial login attempt was successful but further action is needed to finish logging in.
            False, False: Initial login attempt failed.
        """
        try:
            # Go to the login page
            self.page.goto(
                url="https://digital.fidelity.com/prgw/digital/login/full-page",
                timeout=60000,
            )

            # Login page
            self.page.get_by_label("Username", exact=True).click()
            self.page.get_by_label("Username", exact=True).fill(username)
            self.page.get_by_label("Password", exact=True).click()
            self.page.get_by_label("Password", exact=True).fill(password)
            self.page.get_by_role("button", name="Log in").click()
            # Wait for loading spinner to go away
            self.wait_for_loading_sign()

            # See if the summary page has been reached
            self.page.wait_for_load_state(timeout=60000, state="load")
            if "summary" in self.page.url:
                return (True, True)

            # Check to see if TOTP secret is blank or "NA"
            totp_secret = None if totp_secret == "NA" else totp_secret

            # If we hit the 2fA page after trying to login
            if "login" in self.page.url:
                self.wait_for_loading_sign()
                widget = self.page.locator("#dom-widget div").first
                widget.wait_for(timeout=5000, state='visible')
                # If TOTP secret is provided, we are will use the TOTP key. See if authenticator code is present
                if (totp_secret is not None and self.page.get_by_placeholder("XXXXXX").is_visible()):
                    # Get authenticator code
                    code = pyotp.TOTP(totp_secret).now()
                    # Enter the code
                    self.page.get_by_placeholder("XXXXXX").click()
                    self.page.get_by_placeholder("XXXXXX").fill(code)

                    # Prevent future OTP requirements
                    if save_device:
                        # Check this box
                        self.page.locator("label").filter(has_text="Don't ask me again on this").check()
                        if (not self.page.locator("label").filter(has_text="Don't ask me again on this").is_checked()):
                            raise Exception("Cannot check 'Don't ask me again on this device' box")

                    # Log in with code
                    self.page.get_by_role("button", name="Continue").click()

                    # Wait for loading spinner to go away
                    self.wait_for_loading_sign()

                    # See if we got to the summary page
                    self.page.wait_for_url(
                        "https://digital.fidelity.com/ftgw/digital/portfolio/summary",
                        timeout=5000,
                    )

                    # After successful login, store the source account if provided
                    if source_account:
                        self.source_account = source_account
                    print(f"Source account saved: {self.source_account}")

                    # Got to the summary page, return True
                    return (True, True)

                # If the authenticator code is the only way but we don't have the secret, return error
                if self.page.get_by_text(
                    "Enter the code from your authenticator app This security code will confirm the"
                ).is_visible():
                    raise Exception(
                        "Fidelity needs code from authenticator app but TOTP secret is not provided"
                    )

                # If the app push notification page is present
                if self.page.get_by_role("link", name="Try another way").is_visible():
                    self.page.locator("label").filter(has_text="Don't ask me again on this").check()
                    if (not self.page.locator("label").filter(has_text="Don't ask me again on this").is_checked()):
                        raise Exception("Cannot check 'Don't ask me again on this device' box")

                    # Click on alternate verification method to get OTP via text
                    self.page.get_by_role("link", name="Try another way").click()

                # Press the Text me button
                self.page.get_by_role("button", name="Text me the code").click()
                self.page.get_by_placeholder("XXXXXX").click()

                return (True, False)

            # Can't get to summary and we aren't on the login page, idk what's going on
            raise Exception("Cannot get to login page. Maybe other 2FA method present")

        except PlaywrightTimeoutError:
            print("Timeout waiting for login page to load or navigate.")
            return (False, False)
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            traceback.print_exc()
            return (False, False)

    def login_2FA(self, code):
        """
        Completes the 2FA portion of the login using a phone text code.

        Returns:
            True: bool: If login succeeded, return true.
            False: bool: If login failed, return false.
        """
        try:
            self.page.get_by_placeholder("XXXXXX").fill(code)

            # Prevent future OTP requirements
            self.page.locator("label").filter(
                has_text="Don't ask me again on this"
            ).check()
            if (
                not self.page.locator("label")
                .filter(has_text="Don't ask me again on this")
                .is_checked()
            ):
                raise Exception("Cannot check 'Don't ask me again on this device' box")
            self.page.get_by_role("button", name="Submit").click()

            self.page.wait_for_url(
                "https://digital.fidelity.com/ftgw/digital/portfolio/summary",
                timeout=5000,
            )
            return True

        except PlaywrightTimeoutError:
            print("Timeout waiting for login page to load or navigate.")
            return False
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            traceback.print_exc()
            return False

    def getAccountInfo(self):
        """
        Gets account numbers, account names, and account totals by downloading the csv of positions from fidelity.

        Post Conditions:
            self.account_dict is populated with holdings for each account
        Returns:
            account_dict: dict: A dictionary using account numbers as keys. Each key holds a dict which has:
            'balance': float: Total account balance
            'type': str: The account nickname or default name
            'stocks': list: A list of dictionaries for each stock found. The dict has:
                'ticker': str: The ticker of the stock held
                'quantity': str: The quantity of stocks with 'ticker' held
                'last_price': str: The last price of the stock with the $ sign removed
                'value': str: The total value of the position
        """
        # Go to positions page
        self.page.goto("https://digital.fidelity.com/ftgw/digital/portfolio/positions")

        # Download the positions as a csv
        with self.page.expect_download() as download_info:
            self.page.get_by_label("Download Positions").click()
        download = download_info.value
        cur = os.getcwd()
        positions_csv = os.path.join(cur, download.suggested_filename)
        # Create a copy to work on with the proper file name known
        download.save_as(positions_csv)

        csv_file = open(positions_csv, newline="", encoding="utf-8-sig")

        reader = csv.DictReader(csv_file)
        # Ensure all fields we want are present
        required_elements = [
            "Account Number",
            "Account Name",
            "Symbol",
            "Description",
            "Quantity",
            "Last Price",
            "Current Value",
        ]
        intersection_set = set(reader.fieldnames).intersection(set(required_elements))
        if len(intersection_set) != len(required_elements):
            raise Exception("Not enough elements in fidelity positions csv")

        for row in reader:
            # Last couple of rows have some disclaimers, filter those out
            if row["Account Number"] is not None and "and" in str(
                row["Account Number"]
            ):
                break
            # Get the value and remove '$' from it
            val = str(row["Current Value"]).replace("$", "")
            # Get the last price
            last_price = str(row["Last Price"]).replace("$", "")
            # Get quantity
            quantity = row["Quantity"]
            # Get ticker
            ticker = str(row["Symbol"])

            # Don't include this if present
            if "Pending" in ticker:
                continue
            # If the value isn't present, move to next row
            if len(val) == 0:
                continue
            if val.lower() == "n/a":
                val = 0
            # If the last price isn't available, just use the current value
            if len(last_price) == 0:
                last_price = val
            # If the quantity is missing, just use 1
            if len(quantity) == 0:
                quantity = 1

            # If the account number isn't populated yet, add it
            if row["Account Number"] not in self.account_dict:
                # Add retrieved info.
                # Yeah I know is kinda messy and hard to think about but it works
                # Just need a way to store all stocks with the account number
                # 'stocks' is a list of dictionaries. Each ticker gets its own index and is described by a dictionary
                self.account_dict[row["Account Number"]] = {
                    "balance": float(val),
                    "type": row["Account Name"],
                    "stocks": [
                        {
                            "ticker": ticker,
                            "quantity": quantity,
                            "last_price": last_price,
                            "value": val,
                        }
                    ],
                }
            # If it is present, add to it
            else:
                self.account_dict[row["Account Number"]]["stocks"].append(
                    {
                        "ticker": ticker,
                        "quantity": quantity,
                        "last_price": last_price,
                        "value": val,
                    }
                )
                self.account_dict[row["Account Number"]]["balance"] += float(val)

        # Close the file
        csv_file.close()
        os.remove(positions_csv)

        return self.account_dict

    def summary_holdings(self) -> dict:
        """
        NOTE: The getAccountInfo function MUST be called before this, otherwise an empty dictionary will be returned
        Returns a dictionary containing dictionaries for each stock owned across all accounts.
        The keys of the outer dictionary are the tickers of the stocks owned.
        Ex: unique_stocks['NVDA'] = {'quantity': 2.0, 'last_price': 120.23, 'value': 240.46}
        'quantity': float: The number of stocks held of 'ticker'
        'last_price': float: The last price of the stock
        'value': float: The total value of the stocks held
        """

        unique_stocks = {}

        for account_number in self.account_dict:
            for stock_dict in self.account_dict[account_number]["stocks"]:
                # Create a list of unique holdings
                if stock_dict["ticker"] not in unique_stocks:
                    unique_stocks[stock_dict["ticker"]] = {
                        "quantity": float(stock_dict["quantity"]),
                        "last_price": float(stock_dict["last_price"]),
                        "value": float(stock_dict["value"]),
                    }
                else:
                    unique_stocks[stock_dict["ticker"]]["quantity"] += float(
                        stock_dict["quantity"]
                    )
                    unique_stocks[stock_dict["ticker"]]["value"] += float(
                        stock_dict["value"]
                    )

        # Create a summary of holdings
        summary = ""
        for stock, st_dict in unique_stocks.items():
            summary += f"{stock}: {round(st_dict['quantity'], 2)} @ {st_dict['last_price']} = {round(st_dict['value'], 2)}\n"
        return unique_stocks

    def transaction(self, stock: str, quantity: float, action: str, account: str, dry: bool = True) -> bool:
        """
        Process an order (transaction) using the dedicated trading page.
        NOTE: If you use this function repeatedly but change the stock between ANY call,
        RELOAD the page before calling this

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
        """
        try:
            # Go to the trade page
            if (self.page.url != "https://digital.fidelity.com/ftgw/digital/trade-equity/index/orderEntry"):
                self.page.goto("https://digital.fidelity.com/ftgw/digital/trade-equity/index/orderEntry")

            # Click on the drop down
            self.page.query_selector("#dest-acct-dropdown").click()

            if (not self.page.get_by_role("option").filter(has_text=account.upper()).is_visible()):
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
            last_price = last_price.replace("$", "")

            # Ensure we are in the expanded ticket
            if self.page.get_by_role("button", name="View expanded ticket").is_visible():
                self.page.get_by_role("button", name="View expanded ticket").click()
                # Wait for it to take effect
                self.page.get_by_role("button", name="Calculate shares").wait_for(timeout=2000)

            # When enabling extended hour trading
            extended = False
            precision = 3
            # Enable extended hours trading if available
            if self.page.get_by_text("Extended hours trading").is_visible():
                if self.page.get_by_text("Extended hours trading: OffUntil 8:00 PM ET").is_visible():
                    self.page.get_by_text("Extended hours trading: OffUntil 8:00 PM ET").check()
                extended = True
                precision = 2

            # Press the buy or sell button. Title capitalizes the first letter so 'buy' -> 'Buy'
            self.page.query_selector(".eq-ticket-action-label").click()
            self.page.get_by_role("option", name=action.lower().title(), exact=True).wait_for()
            self.page.get_by_role("option", name=action.lower().title(), exact=True).click()

            # Press the shares text box
            self.page.locator("#eqt-mts-stock-quatity div").filter(has_text="Quantity").click()
            self.page.get_by_text("Quantity", exact=True).fill(str(quantity))

            # If it should be limit
            if float(last_price) < 1 or extended:
                # Buy above
                if action.lower() == "buy":
                    difference_price = 0.01 if float(last_price) > 0.1 else 0.0001
                    wanted_price = round(float(last_price) + difference_price, precision)
                # Sell below
                else:
                    difference_price = 0.01 if float(last_price) > 0.1 else 0.0001
                    wanted_price = round(float(last_price) - difference_price, precision)

                # Click on the limit default option when in extended hours
                self.page.query_selector("#dest-dropdownlist-button-ordertype > span:nth-child(1)").click()
                self.page.get_by_role("option", name="Limit", exact=True).click()
                # Enter the limit price
                self.page.get_by_text("Limit price", exact=True).click()
                self.page.get_by_label("Limit price").fill(str(wanted_price))
            # Otherwise its market
            else:
                # Click on the market
                self.page.locator("#order-type-container-id").click()
                self.page.get_by_role("option", name="Market", exact=True).click()

            # Continue with the order
            self.page.get_by_role("button", name="Preview order").click()

            # If error occurred
            try:
                self.page.get_by_role("button", name="Place order clicking this").wait_for(timeout=4000, state="visible")
            except PlaywrightTimeoutError:
                # Error must be present (or really slow page for some reason)
                # Try to report on error
                error_message = ""
                filtered_error = ""
                try:
                    error_message = (self.page.get_by_label("Error").locator("div").filter(has_text="critical").nth(2).text_content(timeout=2000))
                    self.page.get_by_role("button", name="Close dialog").click()
                except Exception:
                    pass
                if error_message == "":
                    try:
                        error_message = self.page.wait_for_selector('.pvd-inline-alert__content font[color="red"]', timeout=2000).text_content()
                        self.page.get_by_role("button", name="Close dialog").click()
                    except Exception:
                        pass
                # Return with error and trim it down (it contains many spaces for some reason)
                if error_message != "":
                    for i, character in enumerate(error_message):
                        if (
                            (character == " " and error_message[i - 1] == " ")
                            or character == "\n"
                            or character == "\t"
                        ):
                            continue
                        filtered_error += character

                    filtered_error = filtered_error.replace("critical", "").strip()
                    error_message = filtered_error.replace("\n", "")
                else:
                    error_message = "Could not retrieve error message from popup"
                return (False, error_message)

            # If no error occurred, continue with checking the order preview
            if (
                not self.page.locator("preview").filter(has_text=account.upper()).is_visible()
                or not self.page.get_by_text(f"Symbol{stock.upper()}", exact=True).is_visible()
                or not self.page.get_by_text(f"Action{action.lower().title()}").is_visible()
                or not self.page.get_by_text(f"Quantity{quantity}").is_visible()
            ):
                return (False, "Order preview is not what is expected")

            # If its a real run
            if not dry:
                self.page.get_by_role("button", name="Place order clicking this").click()
                try:
                    # See that the order goes through
                    self.page.get_by_text("Order received").wait_for(timeout=5000, state="visible")
                    # If no error, return with success
                    return (True, None)
                except PlaywrightTimeoutError:
                    # Order didn't go through for some reason, go to the next and say error
                    return (False, "Order failed to complete")
            # If its a dry run, report back success
            return (True, None)
        except PlaywrightTimeoutError:
            return (False, "Driver timed out. Order not complete")
        except Exception as e:
            return (False, e)

    def getAccountInfo(self):
        """
        Gets account numbers, account names, and account totals by downloading the csv of positions from fidelity.

        Post Conditions:
            self.account_dict is populated with holdings for each account
        Returns:
            account_dict: dict: A dictionary using account numbers as keys. Each key holds a dict which has:
            'balance': float: Total account balance
            'type': str: The account nickname or default name
            'stocks': list: A list of dictionaries for each stock found. The dict has:
                'ticker': str: The ticker of the stock held
                'quantity': str: The quantity of stocks with 'ticker' held
                'last_price': str: The last price of the stock with the $ sign removed
                'value': str: The total value of the position
        """
        # Go to positions page
        self.page.goto("https://digital.fidelity.com/ftgw/digital/portfolio/positions")

        # Download the positions as a csv
        with self.page.expect_download() as download_info:
            self.page.get_by_label("Download Positions").click()
        download = download_info.value
        cur = os.getcwd()
        positions_csv = os.path.join(cur, download.suggested_filename)
        # Create a copy to work on with the proper file name known
        download.save_as(positions_csv)

        csv_file = open(positions_csv, newline="", encoding="utf-8-sig")

        reader = csv.DictReader(csv_file)
        # Ensure all fields we want are present
        required_elements = [
            "Account Number",
            "Account Name",
            "Symbol",
            "Description",
            "Quantity",
            "Last Price",
            "Current Value",
        ]
        intersection_set = set(reader.fieldnames).intersection(set(required_elements))
        if len(intersection_set) != len(required_elements):
            raise Exception("Not enough elements in fidelity positions csv")

        for row in reader:
            # Last couple of rows have some disclaimers, filter those out
            if row["Account Number"] is not None and "and" in str(
                row["Account Number"]
            ):
                break
            # Get the value and remove '$' from it
            val = str(row["Current Value"]).replace("$", "")
            # Get the last price
            last_price = str(row["Last Price"]).replace("$", "")
            # Get quantity
            quantity = row["Quantity"]
            # Get ticker
            ticker = str(row["Symbol"])

            # Don't include this if present
            if "Pending" in ticker:
                continue
            # If the value isn't present, move to next row
            if len(val) == 0:
                continue
            if val.lower() == "n/a":
                val = 0
            # If the last price isn't available, just use the current value
            if len(last_price) == 0:
                last_price = val
            # If the quantity is missing, just use 1
            if len(quantity) == 0:
                quantity = 1

            # If the account number isn't populated yet, add it
            if row["Account Number"] not in self.account_dict:
                # Add retrieved info.
                # Yeah I know is kinda messy and hard to think about but it works
                # Just need a way to store all stocks with the account number
                # 'stocks' is a list of dictionaries. Each ticker gets its own index and is described by a dictionary
                self.account_dict[row["Account Number"]] = {
                    "balance": float(val),
                    "type": row["Account Name"],
                    "stocks": [
                        {
                            "ticker": ticker,
                            "quantity": quantity,
                            "last_price": last_price,
                            "value": val,
                        }
                    ],
                }
            # If it is present, add to it
            else:
                self.account_dict[row["Account Number"]]["stocks"].append(
                    {
                        "ticker": ticker,
                        "quantity": quantity,
                        "last_price": last_price,
                        "value": val,
                    }
                )
                self.account_dict[row["Account Number"]]["balance"] += float(val)

        # Close the file
        csv_file.close()
        os.remove(positions_csv)

        return self.account_dict

    def open_account(self, 
        type: typing.Optional[Literal["roth", "brokerage"]] = None, 
        transfer: float = None
        ):

        """
        Parameters:
            type: str: The type of account to open.
            transfer: float: amount of money you want to transfer
        """
        # TEST FLAG TO ENSURE NO ACCIDENTAL OPENING
        print("OPENING ACCOUNT, PLEASE CONTINUE")
    
        # self.page.pause()
        
        # Got roth working
        if type == "roth":
            # Go to open roth page
            self.page.goto(url="https://digital.fidelity.com/ftgw/digital/aox/RothIRAccountOpening/PersonalInformation")
            self.wait_for_loading_sign()

            # open an account
            self.page.get_by_role("button", name="Open account").click()
            self.wait_for_loading_sign()
            congrats_message = self.page.get_by_role("heading", name="Congratulations, your account")
            congrats_message.wait_for(state="visible")

            # Navigate to the Message center
            self.page.goto("https://servicemessages.fidelity.com/ftgw/amtd/messageCenter")
            self.wait_for_loading_sign()

            # Get the account number from the first row of the messages table
            message_table = self.page.locator(".messages-table")
            first_row = message_table.locator("tbody tr").first
            account_cell = first_row.locator("td:nth-child(4)")  # 4th column is the Account column
            account_text = account_cell.inner_text()

            # Extract the account number using regex
            match = re.search(r'ROTH IRA\s*\((\d+)\)', account_text)
            if match:
                self.new_account_number = match.group(1)
                print(f"New Roth IRA account number found: {self.new_account_number}")
            else:
                print("Could not find Roth IRA account number in the message table.")
                return (False, None)

        # got brokerage working
        if type == "brokerage":
            # Go to open individual brokerage page
            self.page.goto(url="https://digital.fidelity.com/ftgw/digital/aox/BrokerageAccountOpening/JointSelectionPage")
            self.wait_for_loading_sign()

            # First section
            self.page.get_by_role("button", name="Next").click()
            self.wait_for_loading_sign()

            # If application is already started, then there will only be 1 "Next" button
            self.page.get_by_role("button", name="Next").click()
            self.wait_for_loading_sign()
            
            # Open account
            self.page.get_by_role("button", name="Open account").click()
            self.wait_for_loading_sign()

            # Navigate to the Message center
            self.page.goto("https://servicemessages.fidelity.com/ftgw/amtd/messageCenter")
            self.wait_for_loading_sign()

            # Get the account number from the first row of the messages table
            message_table = self.page.locator(".messages-table")
            first_row = message_table.locator("tbody tr").first
            account_cell = first_row.locator("td:nth-child(4)")  # 4th column is the Account column
            account_text = account_cell.inner_text()
            
            # Extract the account number from the text (it's in parentheses)
            match = re.search(r'\((Z\d+)\)', account_text)
            if match:
                self.new_account_number = match.group(1)
                print(f"New account created: {self.new_account_number}")
            else:
                print("Could not find brokerage account number in the message table.")
                return (False, None)
            
        if self.new_account_number:
            
            # Start funding the account
            new_account = self.fund_account(self.source_account, self.new_account_number, transfer)
            
            if new_account:
                print(f"Successfully funded your account: {self.new_account_number} ")
                return (True, self.new_account_number)
            else:
                print(f"Failed to transfer your account funds")
                return (False, None)
        
        return (False, None)

            
    def fund_account(self, source_account: str, new_account_number: str, transfer_amount: float) -> bool:
        """
        Funds the newly created account by transferring money from a source account.
        
        Args:
        source_account (str): The account number of the source account.
        new_account_number (str): The account number of the newly created account.
        transfer_amount (float): The amount to transfer.
        
        Returns:
        bool: True if the transfer was successful, False otherwise.
        """
        try:
            # Navigate to the transfer page
            self.page.goto(url="https://digital.fidelity.com/ftgw/digital/transfer/?quicktransfer=cash-shares")
            self.wait_for_loading_sign()

            # Select the source account from the 'From' dropdown
            from_select = self.page.get_by_label("From")
            options = from_select.locator("option").all()
            source_value = None
            for option in options:
                if source_account in option.inner_text():
                    source_value = option.get_attribute("value")
                    break
            
            if source_value is None:
                print(f"Source account {source_account} not found in dropdown")
                return False
            
            from_select.select_option(source_value)
            self.wait_for_loading_sign()

            # Select the new account from the 'To' dropdown
            to_select = self.page.get_by_label("To", exact=True)
            options = to_select.locator("option").all()
            new_account_value = None
            for option in options:
                if new_account_number in option.inner_text():
                    new_account_value = option.get_attribute("value")
                    break
            
            if new_account_value is None:
                print(f"New account {new_account_number} not found in 'To' dropdown")
                return False
            
            to_select.select_option(new_account_value)
            self.wait_for_loading_sign()

            # Get the available balance
            available_balance = self.page.locator("tr.pvd-table__row:nth-child(2) > td:nth-child(2)").inner_text()
            available_balance = float(available_balance.replace("$", "").replace(",", ""))

            # Check if there's enough balance
            if transfer_amount > available_balance:
                print(f"Insufficient funds. Available: ${available_balance}, Attempted transfer: ${transfer_amount}")
                return False

            # Enter the transfer amount
            self.page.locator("#transfer-amount").fill(str(transfer_amount))

            # Submit the transfer
            self.page.get_by_role("button", name="Continue").click()
            self.wait_for_loading_sign()
            self.page.get_by_role("button", name="Submit").click()
            self.wait_for_loading_sign()

            # Check if the transfer was successful
            success_message = self.page.get_by_role("heading", name="You've submitted the transfer")
            if success_message.is_visible():
                print(f"Successfully transferred ${transfer_amount} from account {source_account} to new account {new_account_number}")
                return True
            else:
                print("Transfer submission failed")
                return False

        except Exception as e:
            print(f"An error occurred during the transfer: {str(e)}")
            return False
       
        

    def enable_pennystock_trading(self, account: str) -> bool:
        """
        Enables penny stock trading for the account given.
        The account is just the account number, no nickname
        
        TODO make account parameter into a list so i can just iterate through all available accounts 
        (this might not work becuase new accounts dont have positions and dont show up in the account info function)
        
        """
        # Maybe need to go through the normal way of getting to this page and not via url
        self.page.goto(url="https://digital.fidelity.com/ftgw/digital/portfolio/features")
        self.page.get_by_label("Manage Penny Stock Trading").click()

        self.page.wait_for_load_state(state="load", timeout=30000)
        self.wait_for_loading_sign()
        if self.page.get_by_role("button", name="Start").is_visible():
            self.page.get_by_role("button", name="Start").click()
        self.wait_for_loading_sign()

        # Ensure the page is loaded
        select_account_title = self.page.get_by_role("heading", name="Select an account")
        select_account_title.wait_for(timeout=30000, state="visible")

        # There are 2 versions of this. A checkbox and a drop down

        # Checkbox version
        # This one seems to have trouble with infinite loading sign
        if self.page.locator("label").filter(has_text=account).is_visible():
            # This seems to never work for checkbox version so reload and try for dropdown version
            # return self.enable_pennystock_trading(account=account)
            self.page.locator("label").filter(has_text=account).click()

        # Dropdown version
        if self.page.get_by_label("Your eligible accounts").is_visible():
            self.page.get_by_label("Your eligible accounts").select_option(account)
        
        # Continue with enabling
        self.page.get_by_role("button", name="Continue").click()
        try:
            self.wait_for_loading_sign(timeout=60000)
        except PlaywrightTimeoutError:
            # Reload
            return self.enable_pennystock_trading(account=account)

        self.page.wait_for_url(url="https://digital.fidelity.com/ftgw/digital/easy/hrt/pst/termsandconditions")
        self.wait_for_loading_sign()
        # Accept the risks
        self.page.query_selector(".pvd-checkbox__label").click()
        self.page.get_by_role("button", name="Submit").click()
        self.wait_for_loading_sign()
        # Verify success
        success_ribbon = self.page.get_by_role("heading", name="Success!")
        success_ribbon.wait_for(state="visible", timeout=30000)
        return True
    
    def download_prev_statement(self, date: str):
        """
        Downloads the multi-account statement for the given month.
        TODO: feature that goes to certrain year or period if given date is more than 6 months before current date
        TODO: ranges of date matching. Fidelity sometimes combines statements of months. Ex: Jan - April

        Parameters:
            date: str: The month and year for the statement to download. Format of MM/YYYY
        """

        # Trim date down
        month = date[:2]
        year = date[-4:]

        # Convert to month
        month = fid_months(int(month)).name
        
        # Build statement name string
        beginning = str(month) + " " + year
        # Convert to 3 letter month followed by year
        self.page.goto(url="https://digital.fidelity.com/ftgw/digital/portfolio/documents/dochub")
        self.page.get_by_role("row", name=f"{beginning} — Statement (pdf)").get_by_label("download statement").click()
        with self.page.expect_download() as download_info:
            with self.page.expect_popup() as page1_info:
                self.page.get_by_role("menuitem", name="Download as PDF").click()
            page1 = page1_info.value
        download = download_info.value
        cur = os.getcwd()
        statement = os.path.join(cur, download.suggested_filename)
        # Create a copy to work on with the proper file name known
        download.save_as(statement)
        page1.close()
        return statement

    def wait_for_loading_sign(self, timeout: int = 30000):
        # Wait for all kinds of loading signs
        signs = [self.page.locator("div:nth-child(2) > .loading-spinner-mask-after").first,
                 self.page.locator(".pvd-spinner__mask-inner").first,
                 self.page.locator("pvd-loading-spinner").first,
                ]
        for sign in signs:
            sign.wait_for(timeout=timeout, state="hidden") 

    def transfer_acc_to_acc(self, source_account: str, destination_account: str):
        """
        WORK IN PROGRESS. NOT FULLY IMPLEMENTED
        """
        # Go to the transfer between accounts page
        self.page.goto(url="https://digital.fidelity.com/ftgw/digital/transfer/?quicktransfer=cash-shares")
        self.page.wait_for_load_state("load")
        self.wait_for_loading_sign()
        
        # Select the source account
        self.page.get_by_label("From").select_option(source_account)
        self.wait_for_loading_sign()

        # Ensure account has the money to transfer
        available = self.page.query_selector("tr.pvd-table__row:nth-child(2) > td:nth-child(2)").text_content()
        available = float(available.replace("$", ""))
        pass

# --------------------------------------- TEST AREA --------------------------------------- #
# Create fidelity driver class
browser = FidelityAutomation(headless=False, save_state=False)
try:
    # Delete old variable in envrionment
    if os.getenv("FIDELITY"):
        os.environ.pop("FIDELITY")
    # Initialize .env file
    load_dotenv()
    # Import Fidelity account
    if not os.getenv("FIDELITY"):
        raise Exception("Fidelity not found, skipping...")

    accounts = (os.environ["FIDELITY"].strip().split(","))
    for account in accounts:
        account = account.split(':')
        step_1, step_2 = browser.login(
            username=account[0],
            password=account[1],
            totp_secret=account[2] if len(account) > 2 else None,
            source_account=account[3],
            save_device=False,
        )
        print("Logged in")

        # User input for account type and transfer amount
        account_type = input("Enter account type to open (roth/brokerage): ").lower()
        while account_type not in ["roth", "brokerage"]:
            account_type = input("Invalid input. Please enter 'roth' or 'brokerage': ").lower()
        
        transfer_amount = float(input("Enter the amount to transfer to the new account: "))
        
        success, account_num = browser.open_account(account_type, transfer_amount)
        
        if success:
            print(f"Successfully opened {account_type} account")
        if account_num:
            print(f"New account number: {account_num}")
        
        enable_penny_stocks = input("Do you want to enable penny stock trading for this account? (y/n): ").lower()
        if enable_penny_stocks == 'y':
            browser.enable_pennystock_trading(account_num)
            print("Penny stock trading enabled")
except Exception as e:
    print(e)

exit_con = 1
while exit_con:

    browser.page.pause()
    choice = input("""
                   0: Quit\n
                   1: locator string\n
                   2: CSS selector string\n
                   3: Get by text\n
                   4: Get by role\n
                   5: Get by label\n
                   6: Goto url\n
                   7: Get text of CSS selector\n
                   """)
    choice = int(choice)
    try:
        if choice > 0:
            str_in = input("Enter the str to click")
            if choice == 1:
                browser.page.locator(str_in).click()
            if choice == 2:
                browser.page.query_selector(str_in).click()
            if choice == 3:
                browser.page.get_by_text(str_in).click()
            if choice == 4:
                browser.page.get_by_role(str_in).click()
            if choice == 5:
                browser.page.get_by_label(str_in).click()
            if choice == 6:
                browser.page.goto(str_in)
            if choice == 7:
                print(browser.page.query_selector(str_in).text_content())
        else:
            exit_con = 0
    except:
        pass
        

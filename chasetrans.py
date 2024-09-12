import os
import traceback
import json
import random
from datetime import datetime
from time import sleep
from dotenv import load_dotenv

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from playwright_stealth import StealthConfig, stealth_sync  

class ChaseAutomation:
    def __init__(self, headless):
        load_dotenv()  # Load environment variables from .env file
        self.username = os.getenv('CHASE_USERNAME')
        self.password = os.getenv('CHASE_PASSWORD')
        self.last_four = os.getenv('CHASE_LAST_FOUR')
        self.cookies_file = 'chase_cookies.json'
        self.cookies_loaded = False
        self.headless: bool = headless
        self.stealth_config = StealthConfig(
            navigator_languages=False,
            navigator_user_agent=False,
            navigator_vendor=False,
        )
        self.getDriver()

    def getDriver(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=self.headless)
        self.context = self.browser.new_context()
        self.load_cookies()  # Load cookies before creating the page
        self.page = self.context.new_page()
        stealth_sync(self.page, self.stealth_config)


    def load_cookies(self):
        try:
            with open(self.cookies_file, 'r') as f:
                cookies = json.load(f)
            self.context.add_cookies(cookies)
            self.cookies_loaded = True
            print(f"Cookies loaded from {self.cookies_file}")
        except FileNotFoundError:
            print(f"Cookie file {self.cookies_file} not found. Proceeding without cookies.")
        except json.JSONDecodeError:
            print(f"Error decoding {self.cookies_file}. Proceeding without cookies.")


    def chaselogin(self):
        try:
            self.page.goto('https://secure05c.chase.com/web/auth/#/logon/logon/chaseOnline')
            
            print("Waiting for login element...")
            # Wait for the login element to be visible
            login_element = self.page.wait_for_selector("#userId-input", timeout=30000)
            
            if login_element:
                print("Login element found. Attempting to log in...")

                username_box = self.page.query_selector("#userId-input")
                password_box = self.page.query_selector("#password-input")
                username_box.type(self.username, delay=random.randint(50, 500))
                password_box.type(self.password, delay=random.randint(50, 500))
                self.page.click("#signin-button")
                self.page.wait_for_url("https://secure.chase.com/web/auth/dashboard#/dashboard/overview", timeout=120000)
                sleep(5)
                # Check the current URL
                current_url = self.page.url
                if "dashboard#" in current_url:
                    print("Successfully logged in. Dashboard detected.")
                    if not self.cookies_loaded:
                        self.save_cookies()
                    return True
                elif self.page.get_by_role("heading", name="Confirm Your Identity").is_visible():
                    print("2FA required. Handling 2FA process...")
                    return self.verify_2fa()
                else:
                    print(f"Unexpected page after login attempt: {current_url}")
                    return False
            else:
                print("Login element not found.")
                return False
        except PlaywrightTimeoutError:
            print("Timeout waiting for login page to load or navigate.")
            return False
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            traceback.print_exc() 
            return False
    
        #2fa prompts 
    def verify_2fa(self):
        print("Timeout waiting for dashboard. Checking for 2FA...")
        if self.page.get_by_role("heading", name="Confirm Your Identity").is_visible():
            print("2FA detected. Handling 2FA process...")

            login_2fa = self.page.get_by_role("heading", name="Confirm Your Identity")
            if login_2fa:
                auth_by_app = self.page.get_by_label("We'll send a push notification")
                if auth_by_app:
                    auth_by_app.wait_for(timeout=10000)
                    auth_by_app.click()
                    print("Chase is asking for 2fa from the phone app. You have 120sec to approve it.")
                    self.page.wait_for_url("https://secure.chase.com/web/auth/dashboard#/dashboard/overview", timeout=120000)
                    self.save_cookies()
                    return True
                else:
                    pass
                select_text = self.page.get_by_label("Get a text. We'll text a one-")
                if select_text:
                    select_text.wait_for(timeout=10000)
                    select_text.click()
                    try:
                        radio_button = self.page.get_by_label(f"xxx-xxx-{self.last_four}")
                        radio_button.wait_for(timeout=10000)
                        radio_button.wait_for(state="visible")
                        radio_button.check()
                    except PlaywrightTimeoutError:
                        pass
                    next_btn = self.page.get_by_role("button", name="Next")
                    next_btn.wait_for(timeout=10000)
                    next_btn.click()
                else:
                    pass
                next_btn = self.page.get_by_role("button", name="Next")
                next_btn.wait_for(timeout=10000)
                next_btn.click()
                return self.input_code()
            else:
                pass
        else:
            print("Login unsuccessful or dashboard not detected.")
            return False
        
        #code input for otp
    def input_code(self):
        try:
            code_entry = self.page.get_by_label("Enter your code")
            code_entry.wait_for(timeout=15000)
            
            code = input("Enter the 2FA code received via text: ")
            code_entry.type(code, delay=random.randint(50, 500))
            self.page.get_by_role("button", name="Next").click()
            
            try:
                self.page.wait_for_url("https://secure.chase.com/web/auth/dashboard#/dashboard/overview", timeout=30000)
                print("2FA successful. Dashboard reached.")
                self.save_cookies()
                return True
            except PlaywrightTimeoutError:
                print("Failed to reach dashboard after entering 2FA code.")
                return False
        except Exception as e:
            print(f"Error during 2FA code input: {str(e)}")
            traceback.print_exc()
            return False


        #downloads the user monthly statements 
    def chaseStatements(self):
        try:
            # Navigate to the statements page
            print("Navigating to statements page...")
            self.page.get_by_role("button", name="Main menu").click()
            self.page.wait_for_load_state('networkidle')
            self.page.get_by_test_id("requestAccountStatements").click()
            self.page.wait_for_load_state('networkidle')
            sleep(3)  # Short delay to ensure page is fully loaded

            # Wait for the statements table to appear
            print("Waiting for statements table to load...")
            self.page.wait_for_selector('#accountsTable-0', timeout=30000)
            
            print("\n-----------------------------------------------------")
            print("Finding the most recent multi-account statement...")
            
            # Locate the most recent multi-account statement row
            multi_statement = self.page.query_selector('tr.table-row:has-text("Multi")')
            
            if not multi_statement:
                print("No multi-account statement found.")
                return False

            # Extract the date of the statement
            date_text = multi_statement.query_selector('td:first-child').inner_text()
            statement_date = datetime.strptime(date_text, '%b %d, %Y')
            
            print(f"Attempting to download statement dated {statement_date.strftime('%B %d, %Y')}...")
            print("------------------------------------------------------\n")
            
            # Find the download button for the statement
            download_button = multi_statement.query_selector('a.iconwrap-link:has(.download-icon)')

            if not download_button:
                print("Download button not found.")
                return False

            print("Clicking download button...")
            # Set up a download listener and click the download button
            with self.page.expect_download(timeout=30000) as download_info:
                download_button.click()
            download = download_info.value
            
            # Prepare the directory for saving the statement
            current_directory = os.getcwd()
            statements_folder = os.path.join(current_directory, "chase_statements")
            os.makedirs(statements_folder, exist_ok=True)
            
            # Generate the file path for the downloaded statement
            file_path = os.path.join(statements_folder, download.suggested_filename)
            print(f"Saving statement to {file_path}...")
            
            # Save the downloaded file
            download.save_as(file_path)

            print("Statement downloaded successfully.")
            return True
        except PlaywrightTimeoutError:
            print("Timeout error occurred while downloading the statement.")
            return False
        except Exception as e:
            print(f"An error occurred while downloading statements: {str(e)}")
            traceback.print_exc()
            return False


    def save_cookies(self):
        if not os.path.exists(self.cookies_file):
            cookies = self.context.cookies()
            with open(self.cookies_file, 'w') as f:
                json.dump(cookies, f)
            print(f"Cookies saved to {self.cookies_file}")
        else:
            print(f"Cookies file {self.cookies_file} already exists. Not overwriting.")

    def close(self):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()


if __name__ == "__main__":
    automation = None
    try:

        automation = ChaseAutomation(headless=False)
        login_success = automation.chaselogin()
        if login_success:
            print("Proceeding with automation...")
            statements_success = automation.chaseStatements()
            if statements_success:
                print("Statements downloaded successfully.")
            else:
                print("Failed to download statements.")
        else:
            print("Login failed. Exiting...")
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        traceback.print_exc()
    finally:
        if automation:
            automation.close()
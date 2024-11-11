from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import time
import logging
import re
import json
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('instagram_scraper.log'),
        logging.StreamHandler()
    ]
)

class InstagramScraper:
    def __init__(self, username, password, headless=True):
        self.username = username
        self.password = password
        self.followers = set()
        self.emails = []
        self.setup_driver(headless)
        
    def setup_driver(self, headless):
        """Configure and initialize Chrome WebDriver"""
        try:
            chrome_options = Options()
            if headless:
                chrome_options.add_argument("--headless")
            chrome_options.add_argument("--disable-notifications")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.wait = WebDriverWait(self.driver, 10)
            logging.info("WebDriver initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize WebDriver: {str(e)}")
            raise

    def login(self):
        """Handle Instagram login with error checking"""
        try:
            logging.info("Attempting to log in to Instagram...")
            self.driver.get("https://www.instagram.com/accounts/login/")
            time.sleep(5)  # Wait for initial load

            # Enter username
            username_input = self.wait.until(EC.presence_of_element_located((By.NAME, "username")))
            username_input.clear()
            username_input.send_keys(self.username)
            logging.info("Username entered successfully")

            # Enter password
            password_input = self.driver.find_element(By.NAME, "password")
            password_input.clear()
            password_input.send_keys(self.password)
            logging.info("Password entered successfully")

            # Click login button
            login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            login_button.click()
            logging.info("Login button clicked")

            # Wait for login to complete
            time.sleep(10)
            
            # Verify login success
            try:
                self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "svg[aria-label='Home']")))
                logging.info("Successfully logged in to Instagram")
            except TimeoutException:
                logging.error("Login verification failed - please check credentials")
                raise Exception("Login failed")

        except Exception as e:
            logging.error(f"Login failed: {str(e)}")
            self.save_error_screenshot("login_error")
            raise

    def get_followers(self, target_user, max_followers=None):
        """Get followers with improved scrolling and error handling"""
        try:
            logging.info(f"Fetching followers for user: {target_user}")
            self.driver.get(f"https://www.instagram.com/{target_user}/followers/")
            time.sleep(5)  # Wait for modal to load
            
            followers_set = set()
            last_height = 0
            scroll_attempts = 0
            max_scroll_attempts = 3
            
            while True:
                # Get current followers
                follower_elements = self.wait.until(
                    EC.presence_of_all_elements_located((By.XPATH, "//a[contains(@class, 'notranslate')]"))
                )
                
                # Process current batch
                for follower in follower_elements:
                    try:
                        follower_username = follower.get_attribute('href').split('/')[-2]
                        followers_set.add(follower_username)
                        logging.debug(f"Added follower: {follower_username}")
                    except StaleElementReferenceException:
                        continue
                
                logging.info(f"Current number of followers collected: {len(followers_set)}")
                
                # Check if we've reached max_followers
                if max_followers and len(followers_set) >= max_followers:
                    logging.info(f"Reached maximum followers limit: {max_followers}")
                    break
                
                # Scroll down
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                
                # Check if we've reached the bottom
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    scroll_attempts += 1
                    if scroll_attempts >= max_scroll_attempts:
                        logging.info("Reached end of followers list")
                        break
                else:
                    scroll_attempts = 0
                    last_height = new_height
                
            self.followers = followers_set
            logging.info(f"Successfully collected {len(self.followers)} followers")
            return self.followers
            
        except Exception as e:
            logging.error(f"Error getting followers: {str(e)}")
            self.save_error_screenshot("followers_error")
            return set()

    def extract_emails(self):
        """Extract emails from follower bios with improved error handling and validation"""
        logging.info("Starting email extraction from follower bios")
        emails = []
        processed_count = 0
        
        for follower in self.followers:
            try:
                processed_count += 1
                if processed_count % 10 == 0:
                    logging.info(f"Processed {processed_count}/{len(self.followers)} followers")
                
                self.driver.get(f"https://www.instagram.com/{follower}/")
                time.sleep(1)  # Small delay to prevent rate limiting
                
                bio = self.wait.until(
                    EC.presence_of_element_located((By.XPATH, "//meta[@property='og:description']"))
                ).get_attribute("content")
                
                # Use regex to find email patterns
                email_pattern = r'[\w\.-]+@[\w\.-]+'
                found_emails = re.findall(email_pattern, bio)
                
                for email in found_emails:
                    if self.validate_email(email):
                        emails.append(email)
                        logging.info(f"Found valid email for {follower}: {email}")
                
            except TimeoutException:
                logging.warning(f"Timeout while processing follower: {follower}")
                continue
            except Exception as e:
                logging.warning(f"Error processing follower {follower}: {str(e)}")
                continue
        
        self.emails = emails
        logging.info(f"Email extraction completed. Found {len(emails)} email addresses")
        self.save_results()
        return emails

    def validate_email(self, email):
        """Basic email validation"""
        pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
        return bool(re.match(pattern, email))

    def save_results(self):
        """Save results to a JSON file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results = {
            "timestamp": timestamp,
            "total_followers_processed": len(self.followers),
            "total_emails_found": len(self.emails),
            "emails": list(self.emails)
        }
        
        filename = f"instagram_results_{timestamp}.json"
        with open(filename, 'w') as f:
            json.dump(results, f, indent=4)
        logging.info(f"Results saved to {filename}")

    def save_error_screenshot(self, error_type):
        """Save screenshot when an error occurs"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"error_{error_type}_{timestamp}.png"
        self.driver.save_screenshot(filename)
        logging.info(f"Error screenshot saved as {filename}")

    def cleanup(self):
        """Clean up resources"""
        try:
            self.driver.quit()
            logging.info("Browser session closed successfully")
        except Exception as e:
            logging.error(f"Error during cleanup: {str(e)}")

def main():
    # Replace with your credentials
    scraper = InstagramScraper(
        username="ralauas",
        password="21126Ac8*",
        headless=True
    )
    
    try:
        scraper.login()
        followers = scraper.get_followers("quark.cr", max_followers=1000)  # Limit to 1000 followers
        emails = scraper.extract_emails()
        
        logging.info(f"Final Results:")
        logging.info(f"Total Followers Processed: {len(followers)}")
        logging.info(f"Total Emails Found: {len(emails)}")
        logging.info(f"Emails: {emails}")
        
    except Exception as e:
        logging.error(f"Script failed: {str(e)}")
    finally:
        scraper.cleanup()

if __name__ == "__main__":
    main()
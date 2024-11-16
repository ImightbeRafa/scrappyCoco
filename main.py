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
from dotenv import load_dotenv
import os
import random

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('instagram_scraper.log'),
        logging.StreamHandler()
    ]
)

# Load environment variables from .env file
load_dotenv()

class InstagramScraper:
    def __init__(self, headless=True):
        # Updated constructor
        self.username = os.getenv('INSTAGRAM_USERNAME')
        self.password = os.getenv('INSTAGRAM_PASSWORD')
        
        # Validate credentials
        if not self.username or not self.password:
            raise ValueError("Instagram credentials not found in environment variables. "
                           "Please check your .env file contains INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD")
        
        self.followers = set()
        self.emails = []
        self.setup_driver(headless)
        
    def setup_driver(self, headless):
        """Configure and initialize Chrome WebDriver"""
        try:
            chrome_options = Options()
            if headless:
                chrome_options.add_argument("--headless=new")  # Updated headless mode
            chrome_options.add_argument("--disable-notifications")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--window-size=1920,1080")  # Set window size
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.wait = WebDriverWait(self.driver, 20)  # Increased wait time
            logging.info("WebDriver initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize WebDriver: {str(e)}")
            raise

    def login(self):
        """Handle Instagram login with error checking"""
        try:
            logging.info("Attempting to log in to Instagram...")
            self.driver.get("https://www.instagram.com/")
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

            # Wait for login to complete and handle potential pop-ups
            time.sleep(10)
            
            # Handle "Save Login Info" popup if it appears
            try:
                not_now_button = self.driver.find_element(By.XPATH, "//button[text()='Not Now']")
                not_now_button.click()
                logging.info("Handled 'Save Login Info' popup")
                time.sleep(2)
            except:
                logging.info("No 'Save Login Info' popup found")

            # Handle notifications popup if it appears
            try:
                not_now_button = self.driver.find_element(By.XPATH, "//button[text()='Not Now']")
                not_now_button.click()
                logging.info("Handled notifications popup")
            except:
                logging.info("No notifications popup found")

            # Verify login success
            try:
                self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[aria-label='Home']")))
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
            
            # First navigate to user's profile
            self.driver.get(f"https://www.instagram.com/{target_user}/")
            time.sleep(5)
            
            # Click on followers count to open modal
            followers_link = self.wait.until(EC.presence_of_element_located(
                (By.XPATH, "//a[contains(@href, '/followers')]")
            ))
            followers_link.click()
            time.sleep(5)
            
            # Wait for followers modal to load
            modal = self.wait.until(EC.presence_of_element_located(
                (By.XPATH, "//div[@role='dialog']")
            ))
            
            followers_set = set()
            last_height = 0
            scroll_attempts = 0
            max_scroll_attempts = 3
            
            # Find the scrollable element in the modal
            scrollable_div = modal.find_element(By.XPATH, ".//div[contains(@class, '_aano')]")
            
            while True:
                # Get current followers
                follower_elements = modal.find_elements(
                    By.XPATH, ".//a[@role='link' and contains(@href, '/')]"
                )
                
                # Process current batch
                for follower in follower_elements:
                    try:
                        follower_username = follower.get_attribute('href').split('/')[-2]
                        if follower_username and follower_username not in followers_set:
                            followers_set.add(follower_username)
                            logging.info(f"Added follower: {follower_username}")
                    except StaleElementReferenceException:
                        continue
                    except Exception as e:
                        logging.warning(f"Error processing follower element: {str(e)}")
                        continue
                
                logging.info(f"Current number of followers collected: {len(followers_set)}")
                
                # Check if we've reached max_followers
                if max_followers and len(followers_set) >= max_followers:
                    logging.info(f"Reached maximum followers limit: {max_followers}")
                    break
                
                # Scroll the modal
                self.driver.execute_script(
                    "arguments[0].scrollTop = arguments[0].scrollHeight", 
                    scrollable_div
                )
                time.sleep(3)  # Increased wait time for loading
                
                # Check if we've reached the bottom
                new_height = self.driver.execute_script(
                    "return arguments[0].scrollHeight", 
                    scrollable_div
                )
                
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
                time.sleep(2)  # Increased delay
                
                try:
                    # Try to get bio text directly
                    bio_element = self.wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".-vDIg"))
                    )
                    bio = bio_element.text
                except:
                    # Fallback to meta description
                    bio = self.wait.until(
                        EC.presence_of_element_located((By.XPATH, "//meta[@property='og:description']"))
                    ).get_attribute("content")
                
                # Use regex to find email patterns
                email_pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
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
            
            # Add a random delay between profile visits
            time.sleep(random.uniform(1, 3))
        
        self.emails = emails
        logging.info(f"Email extraction completed. Found {len(emails)} email addresses")
        self.save_results()
        return emails

    def validate_email(self, email):
        """Enhanced email validation"""
        pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
        if not re.match(pattern, email):
            return False
        if len(email) > 254:
            return False
        try:
            local_part, domain = email.split('@')
            if len(local_part) > 64:
                return False
            if domain.endswith('.'):
                return False
        except:
            return False
        return True

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
    scraper = None  # Initialize scraper as None
    try:
        # Add .env file check
        if not os.path.exists('.env'):
            logging.warning(".env file not found, creating template...")
            with open('.env', 'w') as f:
                f.write("INSTAGRAM_USERNAME=your_username_here\n")
                f.write("INSTAGRAM_PASSWORD=your_password_here\n")
                f.write("TARGET_USERNAME=default_target\n")
                f.write("MAX_FOLLOWERS=1000\n")
            logging.info("Please update the .env file with your credentials and run the script again.")
            return

        # Updated scraper initialization
        scraper = InstagramScraper(headless=False)
        
        scraper.login()
        time.sleep(5)
        
        # Get settings from environment variables
        target_username = os.getenv('TARGET_USERNAME', 'default_target')
        max_followers = int(os.getenv('MAX_FOLLOWERS', '1000'))
        
        followers = scraper.get_followers(target_username, max_followers)
        emails = scraper.extract_emails()
        
        logging.info(f"Final Results:")
        logging.info(f"Total Followers Processed: {len(followers)}")
        logging.info(f"Total Emails Found: {len(emails)}")
        logging.info(f"Emails: {emails}")
        
    except Exception as e:
        logging.error(f"Script failed: {str(e)}")
    finally:
        if scraper:  # Only cleanup if scraper was initialized
            scraper.cleanup()

if __name__ == "__main__":
    main()
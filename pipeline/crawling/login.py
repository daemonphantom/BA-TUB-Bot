from seleniumwire import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv
import time
import os
from .misc import get_logger

logger = get_logger(__name__)

load_dotenv()

username = os.getenv("TUB_USERNAME")
password = os.getenv("TUB_PASSWORD")

def login(driver, username, password):
    # Step 1: Open the ISIS login page
    driver.get("https://isis.tu-berlin.de/login/index.php")

    # Step 2: Click the "TU-Login" button by ID
    tu_login_btn = WebDriverWait(driver, 5).until(
        EC.element_to_be_clickable((By.ID, "shibbolethbutton"))
    )
    tu_login_btn.click()

    # Step 3: Wait for redirect and login form
    WebDriverWait(driver, 5).until(
        EC.presence_of_element_located((By.ID, "username"))
    )

    # Step 4: Fill in username and password
    driver.find_element(By.ID, "username").send_keys(username)
    driver.find_element(By.ID, "password").send_keys(password)

    # Step 5: Submit the form
    driver.find_element(By.ID, "login-button").click()

    # Optional: Wait for login to complete (adjust this as needed)
    time.sleep(2)
    logger.info("✅ Logged in successfully!")

if __name__ == "__main__":
    # Create a Selenium WebDriver (e.g. with Chrome)
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    
    # Optional: run headless if you don't want to see the browser
    # options.add_argument("--headless")
    
    driver = webdriver.Chrome(options=options)

    try:
        login(driver, username, password)
        logger.info("✅ Logged in successfully!")
    except Exception as e:
        logger.error(f"❌ Login failed: {e}")
    finally:
        driver.quit()

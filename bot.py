import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from fake_useragent import UserAgent
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import json
import time
import re
import requests
import uuid
import sys
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QMessageBox,
    QCheckBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

# 🌐 Chrome binary path (macOS)
chrome_path = "/Users/macbook/Desktop/Google Chrome.app/Contents/MacOS/Google Chrome"

# 🎭 Generate a random user agent for stealth
ua = UserAgent()
user_agent = ua.random

# 🔑 Load credentials from config file
try:
    with open("config.json", "r") as file:
        config = json.load(file)
        email = config["email"]
        password = config["password"]
        API_URL = config["API_URL"]
        API_KEY = config["API_KEY"]
        session_token = config["session_token"]
except FileNotFoundError:
    print("Error: config.json not found. Please create it with email, password, API_URL, and API_KEY.")
    exit(1)

# 🚗 Validate UK number plate format
def validate_number_plate(number_plate):
    pattern = r"^[A-Z]{1,2}\d{1,2}[A-Z]{1,3}$"
    return bool(re.match(pattern, number_plate))

# ⏳ Helper function for interacting with elements
def wait_and_interact(driver, by, selector, action="click", wait_time=30):
    try:
        if action == "click":
            WebDriverWait(driver, wait_time).until(
                EC.element_to_be_clickable((by, selector))
            ).click()
            return None
        elif action == "send_keys":
            element = WebDriverWait(driver, wait_time).until(
                EC.visibility_of_element_located((by, selector))
            )
            return element
    except TimeoutException:
        return f"⏰ Timeout waiting for {selector}"
    except Exception as e:
        return f"❌ Error with {selector}: {e}"

# Worker thread for running the lookup
class LookupWorker(QThread):
    log_signal = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, number_plate):
        super().__init__()
        self.number_plate = number_plate

    def run(self):
        self.log_signal.emit(f"\n🚗 Starting lookup for {self.number_plate}...")
        
        # 🌟 Start the browser off-screen but active
        self.log_signal.emit("[*] Launching browser...")
        try:
            options = uc.ChromeOptions()
            options.add_argument("--incognito")
            options.add_argument(f"user-agent={ua.random}")
            options.add_argument("--window-size=800,600")
            options.add_argument("--window-position=0,0")  # Start at top-left
            options.binary_location = chrome_path
            driver = uc.Chrome(options=options)
            driver.set_window_position(-800, 0)  # Move off-screen after launch
            self.log_signal.emit("✅ Done!")
        except Exception as e:
            self.log_signal.emit(f"❌ Failed to launch browser: {e}")
            self.finished.emit()
            return

        # 🌐 Navigate to Compare the Market
        try:
            self.log_signal.emit("[*] Opening Compare the Market...")
            driver.get("https://www.comparethemarket.com/")
            time.sleep(2)  # Brief delay to ensure page loads fully
            self.log_signal.emit("✅ Success!")
        except Exception as e:
            self.log_signal.emit(f"❌ Failed to open site: {e}")
            self.finished.emit()
            return

        # 🍪 Accept cookies
        result = wait_and_interact(driver, By.XPATH, '//*[@id="cmgr-accept-all-cookies"]', wait_time=60)
        if isinstance(result, str):
            self.log_signal.emit(result)
        else:
            self.log_signal.emit("✅ Cookies accepted!")

        # 🔐 Sign in
        result = wait_and_interact(driver, By.XPATH, '//*[@id="Market_HomePage_GlobalHeader_SignIn"]')
        if isinstance(result, str):
            self.log_signal.emit(result)

        email_field = wait_and_interact(driver, By.XPATH, '//*[@id="Signin_SignInPage_Email"]', "send_keys")
        if isinstance(email_field, str):
            self.log_signal.emit(email_field)
        else:
            email_field.send_keys(email)

        password_field = wait_and_interact(driver, By.XPATH, '//*[@id="Signin_SignInPage_PasswordQuestion"]', "send_keys")
        if isinstance(password_field, str):
            self.log_signal.emit(password_field)
        else:
            password_field.send_keys(password)

        result = wait_and_interact(driver, By.XPATH, '//*[@id="Signin_SignInPage_SignIn"]')
        if isinstance(result, str):
            self.log_signal.emit(result)
        self.log_signal.emit("[*] Logging in...")
        self.log_signal.emit("✅ Signed in!")

        # 🚗 Navigate to vehicle lookup
        result = wait_and_interact(driver, By.XPATH, '//*[@id="MyCTM_Dashboard_Car_Edit_Valid_0"]')
        if isinstance(result, str):
            self.log_signal.emit(result)
        result = wait_and_interact(driver, By.ID, "your-car-heading-edit-link")
        if isinstance(result, str):
            self.log_signal.emit(result)
        result = wait_and_interact(driver, By.ID, "vehicle-details-change")
        if isinstance(result, str):
            self.log_signal.emit(result)

        # 📝 Enter number plate
        vehicle_input_field = wait_and_interact(driver, By.XPATH, '//*[@id="vehicleRegistration-input"]', "send_keys")
        if isinstance(vehicle_input_field, str):
            self.log_signal.emit(vehicle_input_field)
        else:
            vehicle_input_field.send_keys(self.number_plate)

        # 🌐 Fetch vehicle data via API
        self.log_signal.emit("[*] Fetching vehicle data...")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-api-key": API_KEY,
            "X-Correlation-Id": str(uuid.uuid4()),
        }
        data = {"registrationNumber": self.number_plate}

        try:
            response = requests.post(API_URL, headers=headers, json=data)
            response.raise_for_status()
            vehicle_data = response.json()
            self.log_signal.emit("✅ Success!")
            self.log_signal.emit("\n🚗 Vehicle Information:")
            for key, value in [
                ("Make", "make"),
                ("Model", "model"),
                ("Color", "colour"),
                ("Year", "yearOfManufacture"),
                ("Engine", "engineCapacity"),
                ("Fuel", "fuelType"),
                ("Tax Status", "taxStatus"),
                ("MOT Status", "motStatus"),
                ("MOT Expiry", "motExpiryDate"),
                ("Tax Due", "taxDueDate"),
                ("Last V5C", "dateOfLastV5CIssued"),
            ]:
                self.log_signal.emit(f"{key}: {vehicle_data.get(value, 'Not Available')}")
        except requests.RequestException as e:
            self.log_signal.emit(f"❌ API call failed: {e}")

        # 📋 Navigate through form steps
        buttons = [
            "vehiclelookup-next-button",
            "yourcar-next-button",
            "carvalue-next-button",
            "ownership_not_owned",
            "car_usage-02YN",
            "carusage-next-button",
            "carstorage-next-button",
            "othercars-next-button",
            "aboutyou-next-button",
            "yourhousehold-next-button",
            "youremployment-next-button",
            "your-licence-next-button",
            "licencerestrictions-next-button",
            "claimsandconvictions-next-button",
            "additionaldrivers-next-button",
            "carowner-next-button",
            "yourcover-next-button",
            "noclaimsdiscount-next-button",
            "additionalproducts-next-button",
            "contactinfo-next-button",
        ]
        for btn in buttons:
            result = wait_and_interact(driver, By.XPATH, f'//*[@id="{btn}"]')
            if isinstance(result, str):
                self.log_signal.emit(result)

        # 💰 Fetch quotes
        try:
            result = wait_and_interact(driver, By.XPATH, "//*[@id='main']/div/div/div/button")
            if isinstance(result, str):
                self.log_signal.emit(result)
            else:
                self.log_signal.emit("✅ Fetching quotes...")
        except TimeoutException:
            self.log_signal.emit("⏰ Timeout waiting for quotes button.")

        # 📊 Display quotes
        try:
            WebDriverWait(driver, 50).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "li.quote-card"))
            )
            quote_cards = driver.find_elements(By.CSS_SELECTOR, "li.quote-card")
            for i, card in enumerate(quote_cards[:3]):
                annual = (
                    card.find_element(By.CSS_SELECTOR, "dd.annual-total").text
                    if card.find_elements(By.CSS_SELECTOR, "dd.annual-total")
                    else "Not available"
                )
                monthly = (
                    card.find_element(By.CSS_SELECTOR, "dl.monthly dd.headline-price").text
                    if card.find_elements(By.CSS_SELECTOR, "dl.monthly dd.headline-price")
                    else "Not available"
                )
                telematics = (
                    "with Blackbox"
                    if card.find_elements(By.CSS_SELECTOR, "li.strapline.telematics")
                    else "without Blackbox"
                )
                self.log_signal.emit(
                    f"💸 Quote {i+1}: Annual: {annual} | Monthly: {monthly} | {telematics}"
                )
        except TimeoutException:
            self.log_signal.emit("❌ No quotes found within timeout.")
        except Exception as e:
            self.log_signal.emit(f"❌ Quote error: {e}")

        # 📅 Select latest policy start date
        try:
            dropdown = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "policyStartDateDropdown"))
            )
            select = Select(dropdown)
            select.select_by_index(len(select.options) - 1)
            self.log_signal.emit(f"✅ Selected date: {select.first_selected_option.text}")
        except Exception as e:
            self.log_signal.emit(f"❌ Date selection error: {e}")

        # 👋 Finish and close browser
        self.log_signal.emit(f"🚗 Plate number: {self.number_plate}")
        driver.quit()
        self.log_signal.emit("✅ Lookup completed!")
        self.finished.emit()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Car Lookup Tool")
        self.setMinimumSize(400, 300)
        self.resize(600, 400)

        # Center the window on screen
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

        # Main widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Input layout
        self.input_layout = QHBoxLayout()
        self.input_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.label = QLabel("Enter UK Number Plate:")
        self.input_layout.addWidget(self.label)

        self.entry = QLineEdit()
        self.entry.setFixedWidth(150)
        self.input_layout.addWidget(self.entry)

        self.start_button = QPushButton("Start Lookup")
        self.start_button.clicked.connect(self.start_lookup)
        self.input_layout.addWidget(self.start_button)

        # Login window button
        self.login_window_button = QPushButton("Login")
        self.login_window_button.clicked.connect(self.open_login_window)
        self.input_layout.addWidget(self.login_window_button)

        self.layout.addLayout(self.input_layout)

        # Text area
        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setMinimumHeight(200)
        self.layout.addWidget(self.text_area)

        # Initial message
        self.text_area.append("🚗 Car Lookup Tool Started! Enter a number plate to begin.")
        
        # Stretch to keep elements centered
        self.layout.addStretch()
        self.get_cars_button = QPushButton("Get Cars")
        self.input_layout.addWidget(self.get_cars_button)
        

    def start_lookup(self):
        number_plate = self.entry.text().strip().upper()
        if not validate_number_plate(number_plate):
            QMessageBox.critical(self, "Error", "Invalid UK number plate format. Example: AB12CDE")
            return
        if QMessageBox.question(
            self,
            "Confirm",
            f"Is {number_plate} correct?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.No:
            return

        self.entry.clear()
        self.start_button.setEnabled(False)
        self.worker = LookupWorker(number_plate)
        self.worker.log_signal.connect(self.log)
        self.worker.finished.connect(self.lookup_finished)
        self.worker.start()

    def log(self, message):
        self.text_area.append(message)
        self.text_area.ensureCursorVisible()

    def lookup_finished(self):
        self.start_button.setEnabled(True)

    def login_comparethemarket(self):
        self.text_area.append("Launching browser...")
        try:
            options = uc.ChromeOptions()
            options.add_argument("--incognito")
            options.add_argument(f"user-agent={ua.random}")
            options.add_argument("--window-size=800,600")
            options.binary_location = chrome_path
            self.driver = uc.Chrome(options=options)
            self.driver.get("https://www.comparethemarket.com/")

            # Accept cookies
            result = wait_and_interact(
                self.driver, By.XPATH, '//*[@id="cmgr-accept-all-cookies"]', wait_time=60
            )
            if isinstance(result, str):
                self.text_area.append(result)
            else:
                self.text_area.append("✅ Cookies accepted!")

            # Click the Sign in button
            result = wait_and_interact(
                self.driver, By.XPATH, '//*[@id="Market_HomePage_GlobalHeader_SignIn"]'
            )
            if isinstance(result, str):
                self.text_area.append(result)
            else:
                self.text_area.append("✅ Sign in button clicked!")

            # Display instructions to user
            self.text_area.append("Please enter your email and password in the browser window.")
            self.text_area.append("Then click 'Save Credentials' below when done.")

            # Add a "Save Credentials" button to your login window
            save_button = QPushButton("Save Credentials")
            self.login_window.layout().addWidget(save_button)
            save_button.clicked.connect(self.save_credentials)
        except Exception as e:
            self.text_area.append(f"❌ Failed to launch browser: {e}")
            
    def get_session(self):
        
        element = WebDriverWait(self.driver, 10).until(
             EC.element_to_be_clickable((By.XPATH, '//*[@id="MyCTM_Dashboard_Car_Edit_Valid_0"]'))
            )
        element.click()
        current_url = self.driver.current_url
        try:
                with open("config.json", "r") as file:
                    config = json.load(file)
        except FileNotFoundError:
                config = {}

            # Update the session token with the current URL
        config["session_token"] = current_url

            # Write the updated config back to file
        try:
            with open("config.json", "w") as file:
                json.dump(config, file, indent=4)
            self.text_area.append(f"✅ Session token saved: {current_url}")
        except Exception as e:
                self.text_area.append(f"❌ Failed to write config: {e}")

    def save_credentials(self):
        self.text_area.append("Attempting to save credentials...")
        try:
            # First check if we can access the elements
            email_field = self.driver.find_element(By.XPATH, '//*[@id="Signin_SignInPage_Email"]')
            password_field = self.driver.find_element(By.XPATH, '//*[@id="Signin_SignInPage_PasswordQuestion"]')
        
            self.text_area.append("✅ Found input fields")

        # Get values
            email_value = email_field.get_attribute("value")
            password_value = password_field.get_attribute("value")
        
            self.text_area.append(f"Email length: {len(email_value)} characters")
            self.text_area.append(f"Password length: {len(password_value)} characters")
        
        # Save to config file
            try:
             with open("config.json", "r") as file:
                config = json.load(file)
                self.text_area.append("✅ Loaded existing config")

            except FileNotFoundError:
              config = {}
              self.text_area.append("Creating new config file")
        
        # Update config
            config["email"] = email_value
            config["password"] = password_value
        
        # Write config
            with open("config.json", "w") as file:
                json.dump(config, file, indent=4)
                self.text_area.append("✅ Wrote to config file")
        
            self.text_area.append("✅ Credentials stored in config.json!")
            self.driver.find_element(By.XPATH, '//*[@id="Signin_SignInPage_SignIn"]').click()
            self.get_session()
            self.driver.quit()
        

        except Exception as e:
            import traceback
            self.text_area.append(f"❌ Failed to save credentials: {str(e)}")
            self.text_area.append(traceback.format_exc())
            
            
    def delete_credentials(self):
        try:
            with open("config.json", "r") as file:
                config = json.load(file)
                config["email"] = ""
                config["password"] = ""
                config["session_token"] = ""
            with open("config.json", "w") as file:
                json.dump(config, file, indent=4)
            self.text_area.append("✅ Credentials deleted!")
        except FileNotFoundError:
            self.text_area.append("❌ No credentials found to delete.")
        except Exception as e:
            self.text_area.append(f"❌ Error deleting credentials: {e}")
            

    def open_login_window(self):
        
        # Create a new login window widget
        login_window = QWidget()
        login_window.setWindowTitle("Login")
        login_window.resize(300, 200)

        # Create a new layout for the login window
        layout = QVBoxLayout()
        login_window.setLayout(layout)

        # Create the login button and add it to the layout
        login_button = QPushButton("Comparethemarket Login")
        layout.addWidget(login_button)
        reset_credentials = QPushButton("Delete Credentials")
        layout.addWidget(reset_credentials)
        reset_credentials.clicked.connect(self.delete_credentials)
        login_button.clicked.connect(self.login_comparethemarket)
        

        # Create and add a label indicating login status
        if email == "":
            loginCheck = QLabel("Not logged in ❌", login_window)
        else: 
            loginCheck = QLabel("Logged in ✅", login_window)
        layout.addWidget(loginCheck)

        # Show the login window and keep a reference to avoid garbage collection
        login_window.show()
        self.login_window = login_window
        
    


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

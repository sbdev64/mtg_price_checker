import os
import time
import queue
import pickle
import hashlib
import concurrent.futures
from threading import Lock
from urllib.parse import quote

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

from cardmarket_scraper.config.settings import CACHE_FILE


class CardMarketScraper:
    """
    Scrapes CardMarket for Magic: The Gathering card prices from specific sellers.
    Optimized with parallel processing and caching.
    """

    def __init__(
        self,
        headless=True,
        languages=["en"],
        sellers=None,
        sleep_time=0.5,
        max_workers=3,
    ):
        self.languages = languages if isinstance(languages, list) else [languages]
        self.base_url = "https://www.cardmarket.com/{0}/Magic/Users/{1}/Offers/Singles"
        self.sellers = sellers or [
            "MagicBarcelona",
            "TEMPEST-STORE",
            "ManaVortex-POOL4YOU",
            "Mazvigosl",
            "Itaca",
            "Metropolis-Center",
            "willybizarre",
            "GENEXCOMICS",
            "Eurekagames",
            "DUAL-GAMES",
        ]
        self.sleep_time = sleep_time
        self.max_workers = max_workers
        self.headless = headless

        # Initialize cache
        self.cache_file = CACHE_FILE
        self.cache = self.load_cache()
        self.cache_lock = Lock()

        # Create driver pool
        self.drivers = []
        self.driver_queue = queue.Queue()

        print(f"Initializing {max_workers} browser instances...")
        for i in range(max_workers):
            driver = self._create_driver(headless)
            self.drivers.append(driver)
            self.driver_queue.put(driver)
        print("Browser instances ready!")

    def _create_driver(self, headless):
        """Create an optimized Chrome driver instance with better headless support."""
        chrome_options = Options()

        if headless:
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-software-rasterizer")
            chrome_options.add_argument("--disable-background-timer-throttling")
            chrome_options.add_argument("--disable-backgrounding-occluded-windows")
            chrome_options.add_argument("--disable-renderer-backgrounding")
            chrome_options.add_argument("--disable-features=TranslateUI")
            chrome_options.add_argument("--disable-ipc-flooding-protection")

        # Common performance optimizations
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-plugins")
        chrome_options.add_argument("--disable-images")
        chrome_options.add_argument("--no-first-run")
        chrome_options.add_argument("--no-default-browser-check")
        chrome_options.add_argument("--disable-default-apps")
        chrome_options.add_argument("--disable-popup-blocking")
        chrome_options.add_argument("--disable-prompt-on-repost")
        chrome_options.add_argument("--disable-hang-monitor")
        chrome_options.add_argument("--disable-client-side-phishing-detection")
        chrome_options.add_argument("--disable-component-update")
        chrome_options.add_argument("--disable-domain-reliability")
        chrome_options.add_argument("--disable-features=VizDisplayCompositor")
        chrome_options.add_argument("--window-size=1920x1080")

        # Suppress logs
        chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        chrome_options.add_argument("--log-level=3")
        chrome_options.add_argument("--silent")
        chrome_options.add_argument("--disable-logging")
        chrome_options.add_argument("--disable-dev-tools")

        # Anti-detection tweaks
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        try:
            service = Service(ChromeDriverManager().install())
            if os.name == "nt":
                service.log_path = "NUL"
            else:
                service.log_path = "/dev/null"

            os.environ["WDM_LOG_LEVEL"] = "0"

            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.implicitly_wait(1)
            driver.set_page_load_timeout(30)
            return driver
        except Exception as e:
            print(f"Error creating driver: {e}")
            raise

    def load_cache(self):
        try:
            with open(self.cache_file, "rb") as f:
                cache = pickle.load(f)
                print(f"Loaded {len(cache)} cached results")
                return cache
        except FileNotFoundError:
            print("No cache file found, starting fresh")
            return {}

    def save_cache(self):
        with self.cache_lock:
            with open(self.cache_file, "wb") as f:
                pickle.dump(self.cache, f)
            print(f"Saved {len(self.cache)} results to cache")

    def get_cache_key(self, card_name, languages, sellers):
        key_data = f"{card_name}_{sorted(languages)}_{sorted(sellers)}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def get_card_price_with_driver(self, driver, seller, card_name, language):
        encoded_name = quote(card_name)
        language_id = "1" if language == "en" else "4"
        url = f"{self.base_url.format(language, seller)}?name={encoded_name}&idLanguage={language_id}&sortBy=price_asc"

        try:
            driver.get(url)
            if self.sleep_time > 0:
                time.sleep(self.sleep_time)

            # Accept cookies if prompted
            try:
                cookie_button = WebDriverWait(driver, 2).until(
                    EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
                )
                cookie_button.click()
                time.sleep(0.5)
            except TimeoutException:
                pass

            # Wait for table
            try:
                WebDriverWait(driver, 3).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "table-body"))
                )
                time.sleep(0.5)

                price_elements = driver.find_elements(
                    By.CSS_SELECTOR,
                    "span.color-primary.small.text-end.text-nowrap.fw-bold",
                )

                lowest_price = float("inf")
                for price_element in price_elements:
                    try:
                        price = float(
                            price_element.text.replace("€", "")
                            .replace(",", ".")
                            .strip()
                        )
                        lowest_price = min(lowest_price, price)
                    except (ValueError, AttributeError):
                        continue

                return (lowest_price, url) if lowest_price != float("inf") else (None, None)

            except TimeoutException:
                return (None, None)

        except Exception as e:
            if not self.headless:
                print(f"  [!] Error checking {seller} ({language.upper()}): {str(e)}")
            return (None, None)

    def get_card_price_threadsafe(self, seller, card_name, language):
        driver = self.driver_queue.get()
        try:
            return self.get_card_price_with_driver(driver, seller, card_name, language)
        finally:
            self.driver_queue.put(driver)

    def find_all_prices_parallel(self, card_name):
        cache_key = self.get_cache_key(card_name, self.languages, self.sellers)
        with self.cache_lock:
            if cache_key in self.cache:
                print("  Using cached result")
                return self.cache[cache_key]

        all_prices = {}
        seller_results = {}

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as executor:
            future_to_info = {}
            for seller in self.sellers:
                for language in self.languages:
                    future = executor.submit(
                        self.get_card_price_threadsafe, seller, card_name, language
                    )
                    future_to_info[future] = (seller, language)

            for future in concurrent.futures.as_completed(future_to_info):
                seller, language = future_to_info[future]
                try:
                    price, url = future.result()
                    if seller not in seller_results:
                        seller_results[seller] = {}
                    seller_results[seller][language] = {"price": price, "url": url}

                    if price is not None:
                        print(f"  {seller} ({language.upper()}): {price:.2f} €")
                    else:
                        print(f"  {seller} ({language.upper()}): Not found")

                except Exception as e:
                    if not self.headless:
                        print(f"  [!] Error with {seller} ({language.upper()}): {e}")
                    if seller not in seller_results:
                        seller_results[seller] = {}
                    seller_results[seller][language] = {"price": None, "url": None}

        for seller, lang_prices in seller_results.items():
            valid_prices = [p for p in lang_prices.values() if p["price"] is not None]
            if valid_prices:
                # pick the entry with the lowest price
                all_prices[seller] = min(valid_prices, key=lambda x: x["price"])
            else:
                all_prices[seller] = {"price": None, "url": None}

        # ✅ Always return a dict, never None
        result = all_prices

        with self.cache_lock:
            self.cache[cache_key] = result

        return result

    def find_all_prices(self, card_name):
        return self.find_all_prices_parallel(card_name)

    def close(self):
        print("Closing browser instances...")
        for driver in self.drivers:
            try:
                driver.quit()
            except Exception as e:
                if not self.headless:
                    print(f"Error closing driver: {e}")

        self.save_cache()
        print("All browsers closed and cache saved!")
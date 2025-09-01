import os
import sys
import time
import argparse
import re
import queue
import pickle
import hashlib
import warnings
import logging
import os
from urllib.parse import quote
import concurrent.futures
from threading import Lock

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from tabulate import tabulate

# Suppress warnings and logs
warnings.filterwarnings("ignore")
logging.getLogger().setLevel(logging.ERROR)
os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"

def clean_card_name(line):
    line = re.sub(r'^\d+\s+', '', line)
    line = re.split(r'\s+\(', line)[0]
    return line.strip()

def clean_decklist_inplace(input_file):
    """
    Cleans the decklist in-place.
    """
    with open(input_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    cleaned_lines = [clean_card_name(line) for line in lines if line.strip()]

    with open(input_file, "w", encoding="utf-8") as f:
        for name in cleaned_lines:
            f.write(name + "\n")

    print(f"Decklist cleaned: {input_file}")

class CardMarketScraper:
    """
    Scrapes CardMarket for Magic: The Gathering card prices from specific sellers.
    Optimized with parallel processing and caching.
    """

    def __init__(self, headless=True, languages=['en'], sellers=None, sleep_time=0.5, max_workers=3):
        self.languages = languages if isinstance(languages, list) else [languages]
        self.base_url = "https://www.cardmarket.com/{0}/Magic/Users/{1}/Offers/Singles"
        self.sellers = sellers or [
            "MagicBarcelona", "TEMPEST-STORE", "ManaVortex-POOL4YOU", "Mazvigosl",
            "Itaca", "Metropolis-Center", "willybizarre", "GENEXCOMICS", 
            "Eurekagames", "DUAL-GAMES"
        ]
        self.sleep_time = sleep_time
        self.max_workers = max_workers
        self.headless = headless
        
        # Initialize cache
        self.cache_file = "cardmarket_cache.pkl"
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
            chrome_options.add_argument('--headless=new')
            # Additional headless-specific options to fix GPU issues
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-software-rasterizer')
            chrome_options.add_argument('--disable-background-timer-throttling')
            chrome_options.add_argument('--disable-backgrounding-occluded-windows')
            chrome_options.add_argument('--disable-renderer-backgrounding')
            chrome_options.add_argument('--disable-features=TranslateUI')
            chrome_options.add_argument('--disable-ipc-flooding-protection')
        
        # Common performance optimizations
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-plugins')
        chrome_options.add_argument('--disable-images')
        chrome_options.add_argument('--no-first-run')
        chrome_options.add_argument('--no-default-browser-check')
        chrome_options.add_argument('--disable-default-apps')
        chrome_options.add_argument('--disable-popup-blocking')
        chrome_options.add_argument('--disable-prompt-on-repost')
        chrome_options.add_argument('--disable-hang-monitor')
        chrome_options.add_argument('--disable-client-side-phishing-detection')
        chrome_options.add_argument('--disable-component-update')
        chrome_options.add_argument('--disable-domain-reliability')
        chrome_options.add_argument('--disable-features=VizDisplayCompositor')
        chrome_options.add_argument('--window-size=1920x1080')
        
        # Enhanced logging suppression
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument('--log-level=3')  # Suppress INFO, WARNING, ERROR
        chrome_options.add_argument('--silent')
        chrome_options.add_argument('--disable-logging')
        chrome_options.add_argument('--disable-dev-tools')

        # Suppress specific warnings
        chrome_options.add_argument('--disable-features=VizDisplayCompositor,VizServiceDisplayCompositor')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--disable-features=MediaRouter')
        chrome_options.add_argument('--disable-speech-api')
        chrome_options.add_argument('--disable-voice-input')
        chrome_options.add_argument("--disable-speech-api")
        chrome_options.add_argument("--disable-voice-input")
        chrome_options.add_argument("--mute-audio")
        
        # Set user agent to avoid detection
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

        try:
            service = Service(ChromeDriverManager().install())
            # Suppress service logs completely
            if os.name == 'nt':  # Windows
                service.log_path = 'NUL'
            else:  # Unix/Linux/Mac
                service.log_path = '/dev/null'
            
            # Suppress ChromeDriverManager logs
            os.environ['WDM_LOG_LEVEL'] = '0'
            
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.implicitly_wait(1)
            
            # Set page load timeout
            driver.set_page_load_timeout(30)
            
            return driver
        except Exception as e:
            print(f"Error creating driver: {e}")
            raise

    def load_cache(self):
        """Load cached results from disk."""
        try:
            with open(self.cache_file, 'rb') as f:
                cache = pickle.load(f)
                print(f"Loaded {len(cache)} cached results")
                return cache
        except FileNotFoundError:
            print("No cache file found, starting fresh")
            return {}

    def save_cache(self):
        """Save cache to disk."""
        with self.cache_lock:
            with open(self.cache_file, 'wb') as f:
                pickle.dump(self.cache, f)
            print(f"Saved {len(self.cache)} results to cache")

    def get_cache_key(self, card_name, languages, sellers):
        """Generate a unique cache key for the card search."""
        key_data = f"{card_name}_{sorted(languages)}_{sorted(sellers)}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def get_card_price_with_driver(self, driver, seller, card_name, language):
        """
        Get the lowest price for a specific card from a seller using a specific driver.
        """
        encoded_name = quote(card_name)
        language_id = "1" if language == "en" else "4"
        url = f"{self.base_url.format(language, seller)}?name={encoded_name}&idLanguage={language_id}&sortBy=price_asc"

        try:
            driver.get(url)
            if self.sleep_time > 0:
                time.sleep(self.sleep_time)

            # Accept cookies if prompted (shorter timeout)
            try:
                cookie_button = WebDriverWait(driver, 2).until(
                    EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
                )
                cookie_button.click()
                time.sleep(0.5)  # Brief pause after clicking cookies
            except TimeoutException:
                pass

            # Wait for table to load (shorter timeout)
            try:
                WebDriverWait(driver, 3).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "table-body"))
                )
                
                # Give a moment for content to fully load
                time.sleep(0.5)
                
                price_elements = driver.find_elements(
                    By.CSS_SELECTOR,
                    "span.color-primary.small.text-end.text-nowrap.fw-bold"
                )

                lowest_price = float('inf')
                for price_element in price_elements:
                    price_text = price_element.text
                    try:
                        price = float(price_text.replace('€', '').replace(',', '.').strip())
                        lowest_price = min(lowest_price, price)
                    except (ValueError, AttributeError):
                        continue

                return lowest_price if lowest_price != float('inf') else None

            except TimeoutException:
                return None

        except Exception as e:
            if not self.headless:  # Only print detailed errors in non-headless mode
                print(f"  [!] Error checking {seller} ({language.upper()}): {str(e)}")
            return None

    def get_card_price_threadsafe(self, seller, card_name, language):
        """Thread-safe wrapper for getting card prices."""
        driver = self.driver_queue.get()
        try:
            return self.get_card_price_with_driver(driver, seller, card_name, language)
        finally:
            self.driver_queue.put(driver)

    def find_all_prices_parallel(self, card_name):
        """
        Find prices for a card across all sellers and languages using parallel processing.
        """
        # Check cache first
        cache_key = self.get_cache_key(card_name, self.languages, self.sellers)
        with self.cache_lock:
            if cache_key in self.cache:
                print(f"  Using cached result")
                return self.cache[cache_key]

        all_prices = {}
        seller_results = {}

        # Create tasks for each seller-language combination
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_info = {}
            
            for seller in self.sellers:
                for language in self.languages:
                    future = executor.submit(self.get_card_price_threadsafe, seller, card_name, language)
                    future_to_info[future] = (seller, language)

            # Collect results
            for future in concurrent.futures.as_completed(future_to_info):
                seller, language = future_to_info[future]
                try:
                    price = future.result()
                    if seller not in seller_results:
                        seller_results[seller] = {}
                    seller_results[seller][language] = price
                    
                    if price is not None:
                        print(f"  {seller} ({language.upper()}): {price:.2f} €")
                    else:
                        print(f"  {seller} ({language.upper()}): Not found")
                        
                except Exception as e:
                    if not self.headless:  # Only print detailed errors in non-headless mode
                        print(f"  [!] Error with {seller} ({language.upper()}): {e}")
                    if seller not in seller_results:
                        seller_results[seller] = {}
                    seller_results[seller][language] = None

        # Process results to get best price per seller
        found_any = False
        for seller, lang_prices in seller_results.items():
            valid_prices = [p for p in lang_prices.values() if p is not None]
            if valid_prices:
                all_prices[seller] = min(valid_prices)
                found_any = True
            else:
                all_prices[seller] = None

        result = all_prices if found_any else None
        
        # Cache the result
        with self.cache_lock:
            self.cache[cache_key] = result
            
        return result

    def find_all_prices(self, card_name):
        """
        Public interface for finding prices (uses parallel processing).
        """
        return self.find_all_prices_parallel(card_name)

    def close(self):
        """
        Close all browser instances and save cache.
        """
        print("Closing browser instances...")
        for driver in self.drivers:
            try:
                driver.quit()
            except Exception as e:
                if not self.headless:
                    print(f"Error closing driver: {e}")
        
        # Save cache
        self.save_cache()
        print("All browsers closed and cache saved!")

def get_top_price(prices):
    """
    Get the lowest price and seller.
    """
    if not prices:
        return ("N/A", "N/A")
    price_list = [(price, seller) for seller, price in prices.items() if price is not None]
    if not price_list:
        return ("N/A", "N/A")
    price_list.sort()
    return price_list[0]

def generate_seller_summary(results, sellers):
    """
    Generate a summary of each seller's performance.
    """
    seller_summary = {}
    
    for seller in sellers:
        seller_summary[seller] = {
            'count': 0,
            'total': 0.0,
            'cards': []
        }
    
    for result in results:
        if result['best_seller'] != "N/A" and result['best_price'] != "N/A":
            seller = result['best_seller']
            price = result['best_price']
            card = result['card']
            
            seller_summary[seller]['count'] += 1
            seller_summary[seller]['total'] += price
            seller_summary[seller]['cards'].append(f"{card} ({price:.2f} €)")
    
    return seller_summary

def save_html_output(filename, decklist_results, expansion_results, not_found_results, original_cards, languages, execution_time, decklist_total, expansion_total, total_price, sellers):
    """
    Save the results as a simple HTML file.
    """
    # Ensure the filename has .html extension and is in the decks folder
    if not filename.endswith('.html'):
        filename += '.html'
    
    if not os.path.exists('decks'):
        os.makedirs('decks')
    
    if not filename.startswith('decks/'):
        filename = os.path.join('decks', filename)
    
    languages_str = "+".join([lang.upper() for lang in languages])
    
    html = [
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head>",
        "<meta charset='UTF-8'>",
        "<title>CardMarket Results</title>",
        "<style>",
        "body { font-family: Arial, sans-serif; margin: 2em; }",
        "h2, h3 { color: #2c3e50; }",
        "table { border-collapse: collapse; width: 100%; margin-bottom: 2em; }",
        "th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }",
        "th { background: #f4f4f4; }",
        ".not-found { color: #c0392b; }",
        ".seller-summary { margin-bottom: 2em; }",
        ".lowest-price { background-color: #d4edda; font-weight: bold; }",
        ".price-cell { text-align: center; }",
        ".summary-table { margin-top: 1em; }",
        ".card-list { font-size: 0.9em; max-width: 300px; }",
        "</style>",
        "</head>",
        "<body>",
        f"<h1>CardMarket Results ({languages_str})</h1>",
        f"<p><b>Total cards searched:</b> {len(original_cards)}</p>",
        f"<p><b>Cards not found:</b> {len(not_found_results)}</p>",
        f"<p><b>Total price:</b> {total_price:.2f} €</p>",
        f"<p><b>Execution time:</b> {execution_time:.2f} seconds</p>",
    ]

    # Decklist section
    if decklist_results:
        html.append("<h2>Decklist (≤2.0€)</h2>")
        headers = ["#", "Card Name"] + sellers
        html.append("<table>")
        html.append("<tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr>")
        for row in decklist_results:
            html.append("<tr>")
            html.append(f"<td>{row['index']}</td>")
            html.append(f"<td>{row['card']}</td>")
            for seller in sellers:
                price = row['prices'].get(seller)
                if price is not None:
                    css_class = "price-cell lowest-price" if seller == row['best_seller'] else "price-cell"
                    html.append(f"<td class='{css_class}'>{price:.2f} €</td>")
                else:
                    html.append("<td class='price-cell not-found'>-</td>")
            html.append("</tr>")
        html.append("</table>")
        html.append(f"<p><b>Total cards in decklist:</b> {len(decklist_results)}</p>")
        html.append(f"<p><b>Decklist total value:</b> {decklist_total:.2f} €</p>")
        
        # Add seller summary for decklist
        decklist_summary = generate_seller_summary(decklist_results, sellers)
        html.append("<h3>Decklist - Seller Summary</h3>")
        html.append("<table class='summary-table'>")
        html.append("<tr><th>Seller</th><th>Cards Count</th><th>Total Amount</th><th>Cards</th></tr>")
        
        # Sort by count (descending) then by total amount (descending)
        sorted_sellers = sorted(decklist_summary.items(), 
                              key=lambda x: (x[1]['count'], x[1]['total']), 
                              reverse=True)
        
        for seller, data in sorted_sellers:
            if data['count'] > 0:
                cards_list = "<br>".join(data['cards'])
                html.append(f"<tr>")
                html.append(f"<td><b>{seller}</b></td>")
                html.append(f"<td>{data['count']}</td>")
                html.append(f"<td>{data['total']:.2f} €</td>")
                html.append(f"<td class='card-list'>{cards_list}</td>")
                html.append(f"</tr>")
        html.append("</table>")
        html.append("<hr>")

    # Expansion section
    if expansion_results:
        html.append("<h2>Expansion (>2.0€)</h2>")
        headers = ["#", "Card Name"] + sellers
        html.append("<table>")
        html.append("<tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr>")
        for row in expansion_results:
            html.append("<tr>")
            html.append(f"<td>{row['index']}</td>")
            html.append(f"<td>{row['card']}</td>")
            for seller in sellers:
                price = row['prices'].get(seller)
                if price is not None:
                    css_class = "price-cell lowest-price" if seller == row['best_seller'] else "price-cell"
                    html.append(f"<td class='{css_class}'>{price:.2f} €</td>")
                else:
                    html.append("<td class='price-cell not-found'>-</td>")
            html.append("</tr>")
        html.append("</table>")
        html.append(f"<p><b>Total cards in expansion:</b> {len(expansion_results)}</p>")
        html.append(f"<p><b>Expansion total value:</b> {expansion_total:.2f} €</p>")
        
        # Add seller summary for expansion
        expansion_summary = generate_seller_summary(expansion_results, sellers)
        html.append("<h3>Expansion - Seller Summary</h3>")
        html.append("<table class='summary-table'>")
        html.append("<tr><th>Seller</th><th>Cards Count</th><th>Total Amount</th><th>Cards</th></tr>")
        
        # Sort by count (descending) then by total amount (descending)
        sorted_sellers = sorted(expansion_summary.items(), 
                              key=lambda x: (x[1]['count'], x[1]['total']), 
                              reverse=True)
        
        for seller, data in sorted_sellers:
            if data['count'] > 0:
                cards_list = "<br>".join(data['cards'])
                html.append(f"<tr>")
                html.append(f"<td><b>{seller}</b></td>")
                html.append(f"<td>{data['count']}</td>")
                html.append(f"<td>{data['total']:.2f} €</td>")
                html.append(f"<td class='card-list'>{cards_list}</td>")
                html.append(f"</tr>")
        html.append("</table>")
        html.append("<hr>")

    # Not found section
    if not_found_results:
        html.append("<h2>Cards Not Found</h2>")
        html.append("<table>")
        html.append("<tr><th>#</th><th>Card Name</th><th>Reason</th></tr>")
        for row in not_found_results:
            html.append(f"<tr><td>{row['index']}</td><td>{row['card']}</td><td class='not-found'>{row['reason']}</td></tr>")
        html.append("</table>")
        html.append(f"<p><b>Total cards not found:</b> {len(not_found_results)}</p>")
        html.append("<hr>")

    # List input cards at the end in original format
    html.append("<h2>Input Cards List</h2><pre>")
    for card in original_cards:
        html.append(card)
    html.append("</pre>")

    html.append("</body></html>")

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(html))
    print(f"HTML summary saved to {filename}")

def main():
    parser = argparse.ArgumentParser(description="CardMarket MTG Price Checker (auto-cleans decklist) - Optimized Version")
    parser.add_argument('--input', required=True, help='Input decklist file (txt)')
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode')
    parser.add_argument('--lang', default='en', choices=['en', 'es', 'all'], help='Language for search (en, es, or all)')
    parser.add_argument('--sleep', type=float, default=0.5, help='Sleep time between requests (seconds)')
    parser.add_argument('--workers', type=int, default=3, help='Number of parallel workers (default: 3)')
    args = parser.parse_args()

    # Determine which languages to search
    if args.lang == 'all':
        languages = ['en', 'es']
    else:
        languages = [args.lang]

    start_time = time.time()
    scraper = None
    sellers_list = None

    try:
        # Read original card list before cleaning
        try:
            with open(args.input, 'r', encoding='utf-8') as file:
                original_cards = [line.rstrip('\n\r') for line in file if line.strip()]
        except FileNotFoundError:
            print(f"Error: {args.input} file not found!")
            return

        # Step 1: Clean the decklist in-place
        clean_decklist_inplace(args.input)

        # Read cleaned card list
        try:
            with open(args.input, 'r', encoding='utf-8') as file:
                cards = [line.strip() for line in file if line.strip()]
        except FileNotFoundError:
            print(f"Error: {args.input} file not found!")
            return

        languages_str = "+".join([lang.upper() for lang in languages])
        print(f"Searching for best prices for {len(cards)} cards in {languages_str}...")
        print(f"Using {args.workers} parallel workers\n")
        
        scraper = CardMarketScraper(
            headless=args.headless,
            languages=languages,
            sleep_time=args.sleep,
            max_workers=args.workers
        )

        # Store sellers list before closing scraper
        sellers_list = scraper.sellers

        decklist_results = []    # ≤2.0€
        expansion_results = []   # >2.0€
        not_found_results = []   # Not found or >10€
        decklist_total = 0.0
        expansion_total = 0.0

        for index, card in enumerate(cards, 1):
            print(f"\n[{index}/{len(cards)}] Processing: {card}")
            prices = scraper.find_all_prices(card)

            if prices:
                best_price, best_seller = get_top_price(prices)

                # Check if price is above 10 euros - treat as not found
                if best_price != "N/A" and best_price > 10.0:
                    print(f"  [!] Price above 10€ ({best_price:.2f} €) - treating as not found")
                    not_found_results.append({
                        'index': index,
                        'card': card,
                        'reason': f"Price above 10€ ({best_price:.2f} €)"
                    })
                else:
                    card_data = {
                        'index': index,
                        'card': card,
                        'prices': prices,
                        'best_price': best_price,
                        'best_seller': best_seller
                    }
                    
                    if best_price != "N/A":
                        if best_price <= 2.0:
                            decklist_results.append(card_data)
                            decklist_total += best_price
                        else:
                            expansion_results.append(card_data)
                            expansion_total += best_price
                    else:
                        not_found_results.append({
                            'index': index,
                            'card': card,
                            'reason': "No prices found"
                        })
            else:
                not_found_results.append({
                    'index': index,
                    'card': card,
                    'reason': "No results from any seller"
                })

        execution_time = time.time() - start_time
        total_price = decklist_total + expansion_total

        # Close the browser as soon as scraping is done
        if scraper:
            scraper.close()
            scraper = None

        # Print header
        print(f"\nCard Search Results ({languages_str})")
        print(f"==================")
        print(f"Total cards searched: {len(cards)}")
        print(f"Cards not found: {len(not_found_results)}")
        print(f"Total price: {total_price:.2f} €")
        print(f"Execution time: {execution_time:.2f} seconds\n")

        # Print Decklist
        if decklist_results:
            print(f"\n{'-'*20} Decklist (≤2.0€) {'-'*20}")
            table_data = []
            for result in decklist_results:
                row = [result['index'], result['card'], f"{result['best_price']:.2f} €", result['best_seller']]
                table_data.append(row)
            headers = ["#", "Card Name", "Lowest Price", "Best Seller"]
            print(tabulate(table_data, headers=headers, tablefmt="grid"))
            print(f"Total cards in decklist: {len(decklist_results)}")
            print(f"Decklist total value: {decklist_total:.2f} €")
            
            # Print decklist seller summary
            decklist_summary = generate_seller_summary(decklist_results, sellers_list)
            print(f"\n{'-'*10} Decklist Seller Summary {'-'*10}")
            summary_data = []
            sorted_sellers = sorted(decklist_summary.items(), 
                                  key=lambda x: (x[1]['count'], x[1]['total']), 
                                  reverse=True)
            for seller, data in sorted_sellers:
                if data['count'] > 0:
                    summary_data.append([seller, data['count'], f"{data['total']:.2f} €"])
            if summary_data:
                print(tabulate(summary_data, headers=["Seller", "Cards", "Total"], tablefmt="grid"))
            print()

        # Print Expansion
        if expansion_results:
            print(f"\n{'-'*20} Expansion (>2.0€) {'-'*20}")
            table_data = []
            for result in expansion_results:
                row = [result['index'], result['card'], f"{result['best_price']:.2f} €", result['best_seller']]
                table_data.append(row)
            headers = ["#", "Card Name", "Lowest Price", "Best Seller"]
            print(tabulate(table_data, headers=headers, tablefmt="grid"))
            print(f"Total cards in expansion: {len(expansion_results)}")
            print(f"Expansion total value: {expansion_total:.2f} €")
            
            # Print expansion seller summary
            expansion_summary = generate_seller_summary(expansion_results, sellers_list)
            print(f"\n{'-'*10} Expansion Seller Summary {'-'*10}")
            summary_data = []
            sorted_sellers = sorted(expansion_summary.items(), 
                                  key=lambda x: (x[1]['count'], x[1]['total']), 
                                  reverse=True)
            for seller, data in sorted_sellers:
                if data['count'] > 0:
                    summary_data.append([seller, data['count'], f"{data['total']:.2f} €"])
            if summary_data:
                print(tabulate(summary_data, headers=["Seller", "Cards", "Total"], tablefmt="grid"))
            print()

        # Print Not Found
        if not_found_results:
            print(f"\n{'-'*20} Cards Not Found {'-'*20}")
            table_data = []
            for result in not_found_results:
                row = [result['index'], result['card'], result['reason']]
                table_data.append(row)
            headers = ["#", "Card Name", "Reason"]
            print(tabulate(table_data, headers=headers, tablefmt="grid"))
            print(f"Total cards not found: {len(not_found_results)}\n")

        # Ask for HTML filename directly
        default_filename = f"cardmarket_results_{args.lang}" if args.lang != 'all' else "cardmarket_results_all"
        filename = input(f"Enter filename for HTML output (default: {default_filename}): ").strip()
        if not filename:
            filename = default_filename
        
        save_html_output(
            filename=filename,
            decklist_results=decklist_results,
            expansion_results=expansion_results,
            not_found_results=not_found_results,
            original_cards=original_cards,
            languages=languages,
            execution_time=execution_time,
            decklist_total=decklist_total,
            expansion_total=expansion_total,
            total_price=total_price,
            sellers=sellers_list
        )

        # Exit after saving
        sys.exit(0)

    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")

    finally:
        # Double guarantee browser is closed
        if scraper:
            scraper.close()

if __name__ == "__main__":
    main()
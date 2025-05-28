import os
import sys
import time
import argparse
import re
from urllib.parse import quote

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from tabulate import tabulate

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
    """

    def __init__(self, headless=True, languages=['en'], sellers=None, sleep_time=1.0):
        self.languages = languages if isinstance(languages, list) else [languages]
        self.base_url = "https://www.cardmarket.com/{0}/Magic/Users/{1}/Offers/Singles"
        self.sellers = sellers or [
            "MagicBarcelona", "TEMPEST-STORE", "ManaVortex-POOL4YOU", "Mazvigosl",
            "Itaca", "Metropolis-Center", "willybizarre", "GENEXCOMICS", 
            "Eurekagames", "DUAL-GAMES"
        ]
        self.sleep_time = sleep_time

        chrome_options = Options()
        if headless:
            chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--window-size=1920x1080')
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.implicitly_wait(3)

    def get_card_price(self, seller, card_name, language):
        """
        Get the lowest price for a specific card from a seller in a specific language.
        """
        encoded_name = quote(card_name)
        language_id = "1" if language == "en" else "4"
        url = f"{self.base_url.format(language, seller)}?name={encoded_name}&idLanguage={language_id}&sortBy=price_asc"

        try:
            self.driver.get(url)
            time.sleep(self.sleep_time)

            # Accept cookies if prompted
            try:
                cookie_button = WebDriverWait(self.driver, 3).until(
                    EC.presence_of_element_located((By.ID, "onetrust-accept-btn-handler"))
                )
                cookie_button.click()
            except TimeoutException:
                pass

            # Wait for table to load
            try:
                WebDriverWait(self.driver, 3).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "table-body"))
                )
                price_elements = self.driver.find_elements(
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
                print(f"  [!] No results found for '{card_name}' from {seller} ({language.upper()})")
                return None

        except Exception as e:
            print(f"  [!] Error checking {seller} ({language.upper()}): {str(e)}")
            return None

    def find_all_prices(self, card_name):
        """
        Find prices for a card across all sellers and languages.
        """
        all_prices = {}
        found_any = False

        for seller in self.sellers:
            seller_prices = {}
            seller_found = False
            
            for language in self.languages:
                print(f"  Checking {seller} ({language.upper()})...", end=' ', flush=True)
                price = self.get_card_price(seller, card_name, language)
                if price is not None:
                    print(f"Found: {price:.2f} €")
                    seller_prices[language] = price
                    seller_found = True
                    found_any = True
                else:
                    print("Not found")
                    seller_prices[language] = None
            
            # Store the best price for this seller across all languages
            valid_prices = [p for p in seller_prices.values() if p is not None]
            if valid_prices:
                all_prices[seller] = min(valid_prices)
            else:
                all_prices[seller] = None

        return all_prices if found_any else None

    def close(self):
        """
        Close the browser.
        """
        if self.driver:
            self.driver.quit()

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
    parser = argparse.ArgumentParser(description="CardMarket MTG Price Checker (auto-cleans decklist)")
    parser.add_argument('--input', required=True, help='Input decklist file (txt)')
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode')
    parser.add_argument('--lang', default='en', choices=['en', 'es', 'all'], help='Language for search (en, es, or all)')
    parser.add_argument('--sleep', type=float, default=1.0, help='Sleep time between requests (seconds)')
    args = parser.parse_args()

    # Determine which languages to search
    if args.lang == 'all':
        languages = ['en', 'es']
    else:
        languages = [args.lang]

    start_time = time.time()
    scraper = None
    sellers_list = None  # Store sellers list before closing scraper

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
        print(f"Searching for best prices for {len(cards)} cards in {languages_str}...\n")
        
        scraper = CardMarketScraper(
            headless=args.headless,
            languages=languages,
            sleep_time=args.sleep
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

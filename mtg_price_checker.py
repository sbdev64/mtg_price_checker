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

    def __init__(self, headless=True, barcelona_threshold=0.50, language='en', sellers=None, sleep_time=1.0):
        self.language = language
        self.base_url = f"https://www.cardmarket.com/{language}/Magic/Users/{{0}}/Offers/Singles"
        self.sellers = sellers or ["MagicBarcelona", "TEMPEST-STORE", "ManaVortex-POOL4YOU", "Mazvigosl"]
        self.barcelona_threshold = barcelona_threshold
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

    def get_card_price(self, seller, card_name):
        """
        Get the lowest price for a specific card from a seller.
        """
        encoded_name = quote(card_name)
        language_id = "1" if self.language == "en" else "4"
        url = f"{self.base_url.format(seller)}?name={encoded_name}&idLanguage={language_id}&sortBy=price_asc"

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
                print(f"  [!] No results found for '{card_name}' from {seller}")
                return None

        except Exception as e:
            print(f"  [!] Error checking {seller}: {str(e)}")
            return None

    def find_all_prices(self, card_name):
        """
        Find prices for a card across all sellers.
        """
        prices = {}
        found_any = False

        for seller in self.sellers:
            print(f"  Checking {seller}...", end=' ', flush=True)
            price = self.get_card_price(seller, card_name)
            if price is not None:
                print(f"Found: {price:.2f} €")
                prices[seller] = price
                found_any = True
            else:
                print("Not found")
                prices[seller] = None

        return prices if found_any else None

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

def save_to_file(output_text, default_filename, cards):
    """
    Save results and input cards to a file.
    """
    save = input("\nWould you like to save these results to a file? (yes/no): ").lower()
    if save.startswith('y'):
        if not os.path.exists('decks'):
            os.makedirs('decks')

        filename = input(f"Enter filename (default: {default_filename}): ").strip()
        if not filename:
            filename = default_filename

        if not filename.endswith('.txt'):
            filename += '.txt'

        filepath = os.path.join('decks', filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(output_text)
            f.write("\nInput Cards List:\n")
            f.write("===============\n")
            for i, card in enumerate(cards, 1):
                f.write(f"{i}. {card}\n")
        print(f"Results saved to {filepath}")

def save_html_output(filename, decklist_results, expansion_results, cards, language, cards_not_found, execution_time):
    """
    Save the results as a simple HTML file.
    """
    html = [
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head>",
        "<meta charset='UTF-8'>",
        "<title>CardMarket Results</title>",
        "<style>",
        "body { font-family: Arial, sans-serif; margin: 2em; }",
        "h2 { color: #2c3e50; }",
        "table { border-collapse: collapse; width: 100%; margin-bottom: 2em; }",
        "th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }",
        "th { background: #f4f4f4; }",
        ".not-found { color: #c0392b; }",
        ".seller-summary { margin-bottom: 2em; }",
        "</style>",
        "</head>",
        "<body>",
        f"<h1>CardMarket Results ({language.upper()})</h1>",
        f"<p><b>Total cards searched:</b> {len(cards)}</p>",
        f"<p><b>Cards not found:</b> {cards_not_found}</p>",
        f"<p><b>Execution time:</b> {execution_time:.2f} seconds</p>",
    ]

    for title, results in [("Decklist (≤2.0€)", decklist_results), ("Expansion (>2.0€)", expansion_results)]:
        html.append(f"<h2>{title}</h2>")
        headers = ["#", "Card Name", "Lowest Price", "Best Seller"]
        html.append("<table>")
        html.append("<tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr>")
        for row in results:
            row_html = ""
            for cell in row:
                if isinstance(cell, str) and "Not found" in cell:
                    row_html += f"<td class='not-found'>{cell}</td>"
                else:
                    row_html += f"<td>{cell}</td>"
            html.append(f"<tr>{row_html}</tr>")
        html.append("</table>")
        html.append(f"<p><b>Total cards in this category:</b> {len(results)}/{len(cards)}</p>")

        # Seller breakdown
        seller_totals = {}
        for result in results:
            seller = result[3]
            if seller != "N/A":
                if seller not in seller_totals:
                    seller_totals[seller] = {"count": 0, "total": 0.0}
                seller_totals[seller]["count"] += 1
                try:
                    if result[2] != "Not found":
                        seller_totals[seller]["total"] += float(result[2].replace(" €", ""))
                except Exception:
                    pass
        if seller_totals:
            html.append("<div class='seller-summary'><b>Breakdown by seller:</b><ul>")
            for seller, data in seller_totals.items():
                html.append(f"<li>{seller}: {data['count']} cards - {data['total']:.2f} €</li>")
            html.append("</ul></div>")
        html.append("<hr>")

    # List input cards at the end
    html.append("<h2>Input Cards List</h2><ol>")
    for card in cards:
        html.append(f"<li>{card}</li>")
    html.append("</ol>")

    html.append("</body></html>")

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(html))
    print(f"HTML summary saved to {filename}")

def main():
    parser = argparse.ArgumentParser(description="CardMarket MTG Price Checker (auto-cleans decklist)")
    parser.add_argument('--input', required=True, help='Input decklist file (txt)')
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode')
    parser.add_argument('--lang', default='en', choices=['en', 'es'], help='Language for search')
    parser.add_argument('--sleep', type=float, default=1.0, help='Sleep time between requests (seconds)')
    args = parser.parse_args()

    # Step 1: Clean the decklist in-place
    clean_decklist_inplace(args.input)

    start_time = time.time()
    scraper = None
    output_text = ""

    try:
        # Read cleaned card list
        try:
            with open(args.input, 'r', encoding='utf-8') as file:
                cards = [line.strip() for line in file if line.strip()]
        except FileNotFoundError:
            print(f"Error: {args.input} file not found!")
            return

        print(f"Searching for best prices for {len(cards)} cards...\n")
        scraper = CardMarketScraper(
            headless=args.headless,
            barcelona_threshold=0.50,
            language=args.lang,
            sleep_time=args.sleep
        )

        decklist_results = []    # ≤2.0€
        expansion_results = []   # >2.0€
        cards_not_found = 0
        decklist_total = 0.0
        expansion_total = 0.0

        for index, card in enumerate(cards, 1):
            print(f"\n[{index}/{len(cards)}] Processing: {card}")
            prices = scraper.find_all_prices(card)

            if prices:
                best_price, best_seller = get_top_price(prices)

                # MagicBarcelona priority logic
                if prices.get("MagicBarcelona") is not None and best_seller != "MagicBarcelona":
                    if prices["MagicBarcelona"] <= (best_price + scraper.barcelona_threshold):
                        best_price = prices["MagicBarcelona"]
                        best_seller = "MagicBarcelona"
                        print(f"  [*] Selected MagicBarcelona price due to threshold ({best_price:.2f} €)")

                row = [
                    index,
                    card,
                    f"{best_price:.2f} €" if best_price != "N/A" else "N/A",
                    best_seller
                ]
                if best_price != "N/A":
                    if best_price <= 2.0:
                        decklist_results.append(row)
                        decklist_total += best_price
                    else:
                        expansion_results.append(row)
                        expansion_total += best_price
                else:
                    row = [index, card, "Not found", "N/A"]
                    decklist_results.append(row)
                    cards_not_found += 1
            else:
                row = [index, card, "Not found", "N/A"]
                decklist_results.append(row)
                cards_not_found += 1

        # Sort results
        for results in [decklist_results, expansion_results]:
            results.sort(key=lambda x: (x[3], x[1]))

        execution_time = time.time() - start_time

        # Close the browser as soon as scraping is done
        if scraper:
            scraper.close()
            scraper = None

        # Print header
        output_text += f"Card Search Results ({args.lang.upper()})\n"
        output_text += f"==================\n"
        output_text += f"Total cards searched: {len(cards)}\n"
        output_text += f"Cards not found: {cards_not_found}\n"
        output_text += f"Execution time: {execution_time:.2f} seconds\n\n"
        print(output_text)

        # Print Decklist
        headers = ["#", "Card Name", "Lowest Price", "Best Seller"]
        print(f"\n{'-'*20} Decklist (≤2.0€) {'-'*20}")
        print(tabulate(decklist_results, headers=headers, tablefmt="grid"))
        print(f"Total cards in decklist: {len(decklist_results)}/{len(cards)}")
        print(f"Total value: {decklist_total:.2f} €\n")

        # Print Expansion
        print(f"\n{'-'*20} Expansion (>2.0€) {'-'*20}")
        print(tabulate(expansion_results, headers=headers, tablefmt="grid"))
        print(f"Total cards in expansion: {len(expansion_results)}/{len(cards)}")
        print(f"Total value: {expansion_total:.2f} €\n")

        save_to_file(output_text, f"cardmarket_results_{args.lang}.txt", cards)

        # Save HTML output
        save_html_output(
            filename=f"cardmarket_results_{args.lang}.html",
            decklist_results=decklist_results,
            expansion_results=expansion_results,
            cards=cards,
            language=args.lang,
            cards_not_found=cards_not_found,
            execution_time=execution_time
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

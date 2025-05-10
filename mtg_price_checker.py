from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import quote
import time
from tabulate import tabulate
import os

class CardMarketScraper:
    def __init__(self, headless=False, barcelona_threshold=0.50, language='en'):
        self.language = language
        self.base_url = f"https://www.cardmarket.com/{language}/Magic/Users/{{0}}/Offers/Singles"
        self.sellers = ["MagicBarcelona", "TEMPEST-STORE", "ManaVortex-POOL4YOU", "Mazvigosl"]
        self.barcelona_threshold = barcelona_threshold
        
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
        """Get the lowest price for a specific card from a seller."""
        encoded_name = quote(card_name)
        language_id = "1" if self.language == "en" else "4"
        url = f"{self.base_url.format(seller)}?name={encoded_name}&idLanguage={language_id}&sortBy=price_asc"
        
        try:
            self.driver.get(url)
            time.sleep(1)
            
            try:
                cookie_button = WebDriverWait(self.driver, 3).until(
                    EC.presence_of_element_located((By.ID, "onetrust-accept-btn-handler"))
                )
                cookie_button.click()
            except TimeoutException:
                pass
            
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
                    try:
                        price_text = price_element.text
                        price = float(price_text.replace('€', '').replace(',', '.').strip())
                        lowest_price = min(lowest_price, price)
                    except (ValueError, AttributeError):
                        continue
                
                return lowest_price if lowest_price != float('inf') else None
                
            except TimeoutException:
                print(f"No results found for {card_name} from {seller}")
                return None
            
        except Exception as e:
            print(f"Error checking {seller}: {str(e)}")
            return None

    def find_all_prices(self, card_name):
        """Find prices for a card across all sellers."""
        prices = {}
        found_any = False
        
        for seller in self.sellers:
            print(f"Checking {seller}...", end=' ', flush=True)
            price = self.get_card_price(seller, card_name)
            
            if price:
                print(f"Found: {price:.2f} €")
                prices[seller] = price
                found_any = True
            else:
                print("Not found")
                prices[seller] = None
        
        return prices if found_any else None

    def close(self):
        """Close the browser"""
        if self.driver:
            self.driver.quit()

def get_top_4_prices(prices):
    """Get the top 4 lowest prices with their sellers."""
    if not prices:
        return [("N/A", "N/A")] * 4
    
    # Create list of (price, seller) tuples, excluding None values
    price_list = [(price, seller) for seller, price in prices.items() if price is not None]
    # Sort by price
    price_list.sort()
    
    # Pad with ("N/A", "N/A") if less than 4 prices
    while len(price_list) < 4:
        price_list.append(("N/A", "N/A"))
    
    return price_list[:4]

def print_version_results(title, results, total_price, seller_totals, total_cards_input, is_standard_version=False):
    """Print formatted results for a specific version"""
    print(f"\n{'-'*20} {title} {'-'*20}")
    
    # Use different headers based on version
    headers = ["#", "Card Name", "Lowest Price", "Best Seller"]
    if is_standard_version:
        headers.extend(["2nd Best", "3rd Best", "4th Best"])
    
    print(tabulate(results, headers=headers, tablefmt="grid"))
    print(f"Total cards in this version: {len(results)}/{total_cards_input}")
    print(f"Total value: {total_price:.2f} €")
    
    print("\nBreakdown by seller:")
    for seller, data in seller_totals.items():
        print(f"  {seller}: {data['count']} cards - {data['total']:.2f} €")
    print("-" * (42 + len(title)))

def save_to_file(output_text, default_filename, cards):
    """Save results and input cards to a file"""
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
            # Add input cards list at the end
            f.write("\nInput Cards List:\n")
            f.write("===============\n")
            for i, card in enumerate(cards, 1):
                f.write(f"{i}. {card}\n")
        print(f"Results saved to {filepath}")

def main():
    start_time = time.time()
    scraper = None
    output_text = ""
    
    try:
        # Ask for language preference
        while True:
            language = input("Enter language for search (en/es): ").lower()
            if language in ['en', 'es']:
                break
            print("Invalid language. Please enter 'en' for English or 'es' for Spanish.")

        scraper = CardMarketScraper(headless=False, barcelona_threshold=0.50, language=language)
        standard_results = []
        budget_results = []     # Under 2.0€
        budget_expansion_results = []  # Between 2.0€ and 3.0€
        cards_not_found = 0
        
        try:
            with open('input.txt', 'r', encoding='utf-8') as file:
                cards = [line.strip() for line in file if line.strip()]
        except FileNotFoundError:
            print("Error: input.txt file not found!")
            return
        
        print("Searching for best prices...")
        total_price = 0.0
        budget_total_price = 0.0
        budget_expansion_total_price = 0.0
        
        for index, card in enumerate(cards, 1):
            print(f"\nProcessing: {card}")
            prices = scraper.find_all_prices(card)
            
            if prices:
                # Get top 4 prices with sellers
                top_prices = get_top_4_prices(prices)
                
                # Apply MagicBarcelona priority logic to the best price only
                best_price, best_seller = top_prices[0]
                if prices.get("MagicBarcelona") is not None and best_seller != "MagicBarcelona":
                    if prices["MagicBarcelona"] <= (best_price + scraper.barcelona_threshold):
                        best_price = prices["MagicBarcelona"]
                        best_seller = "MagicBarcelona"
                        top_prices[0] = (best_price, best_seller)
                        print(f"Selected MagicBarcelona price due to threshold ({best_price:.2f} €)")
                
                # Format the result row with all top prices for standard version
                standard_row = [
                    index,
                    card,
                    f"{best_price:.2f} €",
                    best_seller
                ]
                
                # Add the 2nd, 3rd, and 4th best prices for standard version
                for price, seller in top_prices[1:]:
                    if price != "N/A":
                        standard_row.append(f"{price:.2f} € ({seller})")
                    else:
                        standard_row.append("N/A")
                
                standard_results.append(standard_row)
                total_price += best_price
                
                # Basic row format for budget versions
                basic_row = [
                    index,
                    card,
                    f"{best_price:.2f} €",
                    best_seller
                ]
                
                if best_price < 2.0:
                    budget_results.append(basic_row)
                    budget_total_price += best_price
                elif best_price < 3.0:
                    budget_expansion_results.append(basic_row)
                    budget_expansion_total_price += best_price
            else:
                standard_row = [index, card, "Not found", "N/A", "N/A", "N/A", "N/A"]
                basic_row = [index, card, "Not found", "N/A"]
                standard_results.append(standard_row)
                cards_not_found += 1
        
        # Sort all results by seller and then card name
        for results in [standard_results, budget_results, budget_expansion_results]:
            results.sort(key=lambda x: (x[3], x[1]))
        
        # Calculate execution time
        execution_time = time.time() - start_time
        
        # Print header
        output_text += f"Card Search Results ({language.upper()})\n"
        output_text += f"==================\n"
        output_text += f"Total cards searched: {len(cards)}\n"
        output_text += f"Cards not found: {cards_not_found}\n"
        output_text += f"Execution time: {execution_time:.2f} seconds\n\n"
        print(output_text)
        
        # Process and print each version
        versions = [
            ("Standard Version (All prices)", standard_results, total_price, True),
            ("Budget Version (Under 2.0€)", budget_results, budget_total_price, False),
            ("Budget Expansion (2.0€ - 3.0€)", budget_expansion_results, budget_expansion_total_price, False)
        ]
        
        for title, results, total, is_standard in versions:
            seller_totals = {}
            for result in results:
                seller = result[3]
                if seller != "N/A":
                    if seller not in seller_totals:
                        seller_totals[seller] = {"count": 0, "total": 0.0}
                    seller_totals[seller]["count"] += 1
                    if result[2] != "Not found":
                        seller_totals[seller]["total"] += float(result[2].replace(" €", ""))
            
            version_output = f"\n{'-'*20} {title} {'-'*20}\n"
            headers = ["#", "Card Name", "Lowest Price", "Best Seller"]
            if is_standard:
                headers.extend(["2nd Best", "3rd Best", "4th Best"])
            
            version_output += tabulate(results, headers=headers, tablefmt="grid")
            version_output += f"\nTotal cards in this version: {len(results)}/{len(cards)}\n"
            version_output += f"Total value: {total:.2f} €\n"
            version_output += "\nBreakdown by seller:\n"
            for seller, data in seller_totals.items():
                version_output += f"  {seller}: {data['count']} cards - {data['total']:.2f} €\n"
            version_output += "-" * (42 + len(title)) + "\n"
            
            print(version_output)
            output_text += version_output
        
        save_to_file(output_text, f"cardmarket_results_{language}.txt", cards)
        
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
    
    finally:
        if scraper:
            scraper.close()

if __name__ == "__main__":
    main()
import sys
import time
import argparse
from tabulate import tabulate

from cardmarket_scraper.utils.deck_utils import clean_decklist_inplace, get_top_price
from cardmarket_scraper.scraper.cardmarket import CardMarketScraper
from cardmarket_scraper.reporting.report_generator import save_html_output
from cardmarket_scraper.config.settings import PRICE_THRESHOLD_DECK, PRICE_THRESHOLD_MAX


def main():
    parser = argparse.ArgumentParser(
        description="CardMarket MTG Price Checker (auto-cleans decklist)"
    )
    parser.add_argument("--input", required=True, help="Input decklist file (txt)")
    parser.add_argument(
        "--headless", action="store_true", help="Run browser in headless mode"
    )
    parser.add_argument(
        "--lang",
        default="en",
        choices=["en", "es", "all"],
        help="Language for search (en, es, or all)",
    )
    parser.add_argument(
        "--sleep", type=float, default=0.5, help="Sleep time between requests (seconds)"
    )
    parser.add_argument(
        "--workers", type=int, default=3, help="Number of parallel workers (default: 3)"
    )
    args = parser.parse_args()

    languages = ["en", "es"] if args.lang == "all" else [args.lang]

    start_time = time.time()
    scraper = None
    sellers_list = None

    try:
        # Read original card list before cleaning
        try:
            with open(args.input, "r", encoding="utf-8") as file:
                original_cards = [line.rstrip("\n\r") for line in file if line.strip()]
        except FileNotFoundError:
            print(f"Error: {args.input} file not found!")
            return

        # Step 1: Clean the decklist in-place
        clean_decklist_inplace(args.input)

        # Read cleaned card list
        try:
            with open(args.input, "r", encoding="utf-8") as file:
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
            max_workers=args.workers,
        )

        sellers_list = scraper.sellers

        decklist_results = []
        expansion_results = []
        not_found_results = []
        decklist_total = 0.0
        expansion_total = 0.0

        for index, card in enumerate(cards, 1):
            print(f"\n[{index}/{len(cards)}] Processing: {card}")
            prices = scraper.find_all_prices(card)

            best_price, best_seller, best_url = get_top_price(prices)

            if best_price != "N/A":
                if best_price > PRICE_THRESHOLD_MAX:
                    print(
                        f"  [!] Price above {PRICE_THRESHOLD_MAX}€ "
                        f"({best_price:.2f} €) - treating as not found"
                    )
                    not_found_results.append(
                        {
                            "index": index,
                            "card": card,
                            "reason": f"Price above {PRICE_THRESHOLD_MAX}€ ({best_price:.2f} €)",
                        }
                    )
                else:
                    card_data = {
                        "index": index,
                        "card": card,
                        "prices": prices,
                        "best_price": best_price,
                        "best_seller": best_seller,
                        "best_url": best_url,
                    }

                    if best_price <= PRICE_THRESHOLD_DECK:
                        decklist_results.append(card_data)
                        decklist_total += best_price
                    else:
                        expansion_results.append(card_data)
                        expansion_total += best_price
            else:
                not_found_results.append(
                    {"index": index, "card": card, "reason": "No results from any seller"}
                )

        execution_time = time.time() - start_time
        total_price = decklist_total + expansion_total

        if scraper:
            scraper.close()
            scraper = None

        # Print summary
        print(f"\nCard Search Results ({languages_str})")
        print("==================")
        print(f"Total cards searched: {len(cards)}")
        print(f"Cards not found: {len(not_found_results)}")
        print(f"Total price: {total_price:.2f} €")
        print(f"Execution time: {execution_time:.2f} seconds\n")

        # Decklist
        if decklist_results:
            print(f"\n{'-'*20} Decklist (≤{PRICE_THRESHOLD_DECK}€) {'-'*20}")
            table_data = [
                [
                    result["index"],
                    result["card"],
                    f"{result['best_price']:.2f} €",
                    result["best_seller"],
                ]
                for result in decklist_results
            ]
            print(
                tabulate(
                    table_data,
                    headers=["#", "Card", "Price", "Seller"],
                    tablefmt="grid",
                )
            )
            print(f"Decklist total value: {decklist_total:.2f} €")

        # Expansion
        if expansion_results:
            print(f"\n{'-'*20} Expansion (> {PRICE_THRESHOLD_DECK}€) {'-'*20}")
            table_data = [
                [
                    result["index"],
                    result["card"],
                    f"{result['best_price']:.2f} €",
                    result["best_seller"],
                ]
                for result in expansion_results
            ]
            print(
                tabulate(
                    table_data,
                    headers=["#", "Card", "Price", "Seller"],
                    tablefmt="grid",
                )
            )
            print(f"Expansion total value: {expansion_total:.2f} €")

        # Not found
        if not_found_results:
            print(f"\n{'-'*20} Not Found {'-'*20}")
            table_data = [
                [result["index"], result["card"], result["reason"]]
                for result in not_found_results
            ]
            print(tabulate(table_data, headers=["#", "Card", "Reason"], tablefmt="grid"))

        # Save HTML
        default_filename = (
            f"cardmarket_results_{args.lang}"
            if args.lang != "all"
            else "cardmarket_results_all"
        )
        filename = input(
            f"Enter filename for HTML output (default: {default_filename}): "
        ).strip()
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
            sellers=sellers_list,
        )

        sys.exit(0)

    except Exception as e:
        print(f"Unexpected error: {str(e)}")

    finally:
        if scraper:
            scraper.close()


if __name__ == "__main__":
    main()
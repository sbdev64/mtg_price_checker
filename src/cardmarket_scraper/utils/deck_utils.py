import re


def clean_card_name(line: str) -> str:
    line = re.sub(r"^\d+\s+", "", line)
    line = re.split(r"\s+\(", line)[0]
    return line.strip()


def clean_decklist_inplace(input_file: str):
    with open(input_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    cleaned_lines = [clean_card_name(line) for line in lines if line.strip()]

    with open(input_file, "w", encoding="utf-8") as f:
        for name in cleaned_lines:
            f.write(name + "\n")

    print(f"Decklist cleaned: {input_file}")


def get_top_price(prices: dict):
    if not prices:
        return ("N/A", "N/A")
    price_list = [
        (price, seller) for seller, price in prices.items() if price is not None
    ]
    if not price_list:
        return ("N/A", "N/A")
    price_list.sort()
    return price_list[0]
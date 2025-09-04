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


def get_top_price(prices):
    """
    Get the lowest price, seller, and URL from a prices dict.
    Supports both new format (dict with price+url) and old format (float).
    """
    if not prices:
        return ("N/A", "N/A", None)

    price_list = []
    for seller, data in prices.items():
        if isinstance(data, dict):
            if data.get("price") is not None:
                price_list.append((data["price"], seller, data.get("url")))
        elif isinstance(data, (int, float)):
            price_list.append((data, seller, None))

    if not price_list:
        return ("N/A", "N/A", None)

    price_list.sort()
    return price_list[0]  # (price, seller, url)
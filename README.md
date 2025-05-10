# MTG Price Checker

A command-line tool to **clean and price-check Magic: The Gathering decklists** using CardMarket sellers.

## Features

- **Decklist Cleaner:**  
  Automatically formats your decklist, removing quantities and set/collector info, so only card names remain.

- **Price Checker:**  
  Scrapes CardMarket for the lowest prices from selected sellers for each card in your decklist.

- **Summary Output:**  
  Prints results in the terminal and can save them as `.txt` and `.html` files.

- **Supports English and Spanish** (`--lang en` or `--lang es`).

## Requirements

- Python 3.8+
- Google Chrome browser installed
- The following Python packages:
  - `selenium`
  - `webdriver-manager`
  - `tabulate`

Install dependencies with:

```bash
pip install selenium webdriver-manager tabulate
```

## Usage

### 1. Prepare your decklist

- The program supports Moxfield format. So you can input your decklist directly.  
- Your decklist should be a `.txt` file, one card per line.
- Each line can have a quantity and set info, e.g.:
  ```
  1 Kastral, the Windcrested (BLB) 335
  1 Aetherize (BLC) 161
  1 Arcane Signet (OTC) 252
  ```

### 2. Run the script

```bash
python mtg_price_checker.py --input mydeck.txt --lang en
```

**Arguments:**

- `--input` (required): Path to your decklist file.
- `--lang` (optional): `en` for English (default), `es` for Spanish.

**Example:**

```bash
python mtg_price_checker.py --input mydeck.txt --lang en --headless
```

### 3. Output

- The script will:
  1. **Clean your decklist in-place** (removes numbers and set info).
  2. **Scrape prices** for each card from CardMarket sellers.
  3. **Display results** in the terminal.
  4. **Prompt to save** results as a `.txt` file.
  5. **Automatically save** a summary as an `.html` file.

- Results are grouped into:
  - **Decklist (≤2.0€):** Cards costing 2 euros or less.
  - **Expansion (>2.0€):** Cards costing more than 2 euros.

## Notes

- **Your decklist will be overwritten** with the cleaned version.
- The script uses Chrome WebDriver; make sure Chrome is installed.
- If you want to keep your original decklist, make a backup before running.

## License

MIT License
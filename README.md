Perfect ✅ That’s the most **reliable and user-friendly** approach, especially for Windows users.  
I’ll update your **README.md** so it always uses `python -m cardmarket_scraper.main ...` as the default way to run, and mention the optional `cardmarket-scraper` shortcut for advanced users.  

Here’s the updated **README.md**:

---

# MTG Price Checker

A command-line tool to **clean and price-check Magic: The Gathering decklists** using CardMarket sellers.

## ✨ Features

- **Decklist Cleaner**  
  Automatically formats your decklist, removing quantities and set/collector info, so only card names remain.

- **Price Checker**  
  Scrapes CardMarket for the lowest prices from selected sellers for each card in your decklist.

- **Summary Output**  
  Prints results in the terminal and saves them as `.html` reports (with seller summaries).

- **Supports Multiple Languages**  
  Search in **English** (`--lang en`), **Spanish** (`--lang es`), or **both** (`--lang all`).

- **Parallel Scraping**  
  Uses multiple browser workers for faster results.

---

## 📦 Installation

### Requirements
- Python **3.9+**
- Google Chrome browser installed

### Install
Clone the repo and install in editable mode:

```bash
git clone https://github.com/yourusername/mtg_price_checker.git
cd mtg_price_checker
pip install -e .
```

---

## 🚀 Usage

### 1. Prepare your decklist
- The program supports **Moxfield format**.  
- Your decklist should be a `.txt` file, one card per line.  
- Each line can have a quantity and set info, e.g.:

```
1 Kastral, the Windcrested (BLB) 335
1 Aetherize (BLC) 161
1 Arcane Signet (OTC) 252
```

The script will **clean this automatically** into just card names.

---

### 2. Run the script

The most reliable way (works everywhere, including Windows):

```bash
python -m cardmarket_scraper.main --input mydeck.txt [options]
```

---

### 🔧 Command-line arguments

| Flag         | Required | Default | Description |
|--------------|----------|---------|-------------|
| `--input`    | ✅ Yes   | –       | Path to your decklist file (txt). |
| `--lang`     | ❌ No    | `en`    | Language for search: `en`, `es`, or `all`. |
| `--headless` | ❌ No    | False   | Run Chrome in headless mode (no visible browser). |
| `--sleep`    | ❌ No    | `0.5`   | Sleep time (seconds) between requests. |
| `--workers`  | ❌ No    | `3`     | Number of parallel browser workers. |

---

### 3. Examples

My most used run:
```bash
python -m cardmarket_scraper.main --input mydeck.txt --lang all --headless
```

Run in Spanish, headless mode:
```bash
python -m cardmarket_scraper.main --input mydeck.txt --lang es --headless
```

Run in both English + Spanish, with 5 workers and slower requests:
```bash
python -m cardmarket_scraper.main --input mydeck.txt --lang all --workers 5 --sleep 1.0 --headless
```

Recommend always --headless mode.

---

### 4. Output

- The script will:
  1. **Clean your decklist in-place** (removes numbers and set info).
  2. **Scrape prices** for each card from CardMarket sellers.
  3. **Display results** in the terminal (decklist, expansion, not found).
  4. **Prompt for an HTML filename** and save a detailed report in `decks/`.

- Results are grouped into:
  - **Decklist (≤2.0€)** → budget cards  
  - **Expansion (>2.0€)** → pricier cards  
  - **Not Found** → unavailable or >10€  

---

## ⚠️ Notes

- **Your decklist file will be overwritten** with the cleaned version.  
  → Make a backup if you want to keep the original.  
- The script uses **Chrome WebDriver** via `webdriver-manager`.  
  → Make sure Chrome is installed and up to date.  
- Cache is stored in `cardmarket_cache.pkl` to speed up repeated runs.  
- Advanced users: if your PATH is configured correctly, you can also run with:
  ```bash
  cardmarket-scraper --input mydeck.txt --lang en
  ```
  but `python -m cardmarket_scraper.main` is the recommended method.

---

## 📝 License

MIT License
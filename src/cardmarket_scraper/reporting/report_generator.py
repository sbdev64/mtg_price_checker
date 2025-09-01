import os


def generate_seller_summary(results, sellers):
    seller_summary = {s: {"count": 0, "total": 0.0, "cards": []} for s in sellers}

    for result in results:
        if result["best_seller"] != "N/A" and result["best_price"] != "N/A":
            seller = result["best_seller"]
            price = result["best_price"]
            card = result["card"]

            seller_summary[seller]["count"] += 1
            seller_summary[seller]["total"] += price
            seller_summary[seller]["cards"].append(f"{card} ({price:.2f} €)")

    return seller_summary


def save_html_output(
    filename,
    decklist_results,
    expansion_results,
    not_found_results,
    original_cards,
    languages,
    execution_time,
    decklist_total,
    expansion_total,
    total_price,
    sellers,
):
    if not filename.endswith(".html"):
        filename += ".html"

    if not os.path.exists("decks"):
        os.makedirs("decks")

    if not filename.startswith("decks/"):
        filename = os.path.join("decks", filename)

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

    # Decklist
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
                price = row["prices"].get(seller)
                if price is not None:
                    css_class = (
                        "price-cell lowest-price"
                        if seller == row["best_seller"]
                        else "price-cell"
                    )
                    html.append(f"<td class='{css_class}'>{price:.2f} €</td>")
                else:
                    html.append("<td class='price-cell not-found'>-</td>")
            html.append("</tr>")
        html.append("</table>")
        html.append(f"<p><b>Total cards in decklist:</b> {len(decklist_results)}</p>")
        html.append(f"<p><b>Decklist total value:</b> {decklist_total:.2f} €</p>")

    # Expansion
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
                price = row["prices"].get(seller)
                if price is not None:
                    css_class = (
                        "price-cell lowest-price"
                        if seller == row["best_seller"]
                        else "price-cell"
                    )
                    html.append(f"<td class='{css_class}'>{price:.2f} €</td>")
                else:
                    html.append("<td class='price-cell not-found'>-</td>")
            html.append("</tr>")
        html.append("</table>")
        html.append(f"<p><b>Total cards in expansion:</b> {len(expansion_results)}</p>")
        html.append(f"<p><b>Expansion total value:</b> {expansion_total:.2f} €</p>")

    # Not found
    if not_found_results:
        html.append("<h2>Cards Not Found</h2>")
        html.append("<table>")
        html.append("<tr><th>#</th><th>Card Name</th><th>Reason</th></tr>")
        for row in not_found_results:
            html.append(
                f"<tr><td>{row['index']}</td><td>{row['card']}</td><td class='not-found'>{row['reason']}</td></tr>"
            )
        html.append("</table>")
        html.append(f"<p><b>Total cards not found:</b> {len(not_found_results)}</p>")

    # Original cards
    html.append("<h2>Input Cards List</h2><pre>")
    for card in original_cards:
        html.append(card)
    html.append("</pre>")

    html.append("</body></html>")

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(html))
    print(f"HTML summary saved to {filename}")
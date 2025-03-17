#!/usr/bin/env python3
import argparse
import csv
import json

# ANSI color codes for terminal output (used for colored prints)
ANSI_COLORS = {
    'red': "\033[91m",
    'green': "\033[92m",
    'reset': "\033[0m"
}

def colored(text, color, enable_color=True):
    """
    Returns the text wrapped in ANSI color codes if enabled.
    """
    if enable_color and color in ANSI_COLORS:
        return f"{ANSI_COLORS[color]}{text}{ANSI_COLORS['reset']}"
    return str(text)

class PortfolioAnalyzer:
    """
    PortfolioAnalyzer loads and processes a CSV file containing portfolio data.
    It computes asset-level and transaction-level metrics and can export the
    analysis to CSV, JSON, or HTML.
    """
    def __init__(self, csv_file, current_prices, use_color=True):
        self.csv_file = csv_file                  # Path to the CSV file
        self.current_prices = current_prices      # Dictionary of current prices: {symbol: price}
        self.use_color = use_color                # Flag for colored output
        self.sections = {}                        # Dictionary for CSV sections
        self.trades_by_symbol = {}                # Processed trades grouped by asset symbol
        self.realized_summary = {}                # Processed realized/unrealized summary data
        self.deposits = []                        # Processed deposits & withdrawals (if needed)
        self.asset_metrics = {}                   # Computed asset-level metrics

    def parse_csv_sections(self):
        """
        Reads the CSV file and groups rows by the section name (the first column).
        The sections dictionary is stored in the instance.
        """
        sections = {}
        with open(self.csv_file, newline="", encoding="utf-8") as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                if not row:
                    continue
                section = row[0].strip()
                sections.setdefault(section, []).append(row)
        self.sections = sections

    def process_trades(self, trades_rows):
        """
        Processes the 'Trades' section rows.
        Finds the header row and converts subsequent data rows into dictionaries.
        Returns a dictionary grouped by asset symbol.
        """
        header = None
        trades = []
        for row in trades_rows:
            if len(row) < 3:
                continue
            if row[1].strip() == "Header":
                header = [x.strip() for x in row[2:]]
                continue
            if row[1].strip() == "Data" and header:
                data = {header[i]: row[i+2].strip() for i in range(min(len(header), len(row)-2))}
                trades.append(data)
        trades_by_symbol = {}
        for trade in trades:
            symbol = trade.get("Symbol")
            if symbol:
                trades_by_symbol.setdefault(symbol, []).append(trade)
        self.trades_by_symbol = trades_by_symbol

    def process_realized_summary(self, rows):
        """
        Processes the 'Realized & Unrealized Performance Summary' section.
        Stores a dictionary keyed by asset symbol.
        """
        header = None
        summary = {}
        for row in rows:
            if row[1].strip() == "Header":
                header = [x.strip() for x in row[2:]]
                continue
            if row[1].strip() == "Data" and header:
                data = {header[i]: row[i+2].strip() for i in range(min(len(header), len(row)-2))}
                symbol = data.get("Symbol", "Unknown")
                summary[symbol] = data
        self.realized_summary = summary

    def process_deposits(self, rows):
        """
        Processes the 'Deposits & Withdrawals' section.
        Stores a list of cash flow data dictionaries.
        """
        header = None
        deposits = []
        for row in rows:
            if row[1].strip() == "Header":
                header = [x.strip() for x in row[2:]]
                continue
            if row[1].strip() == "Data" and header:
                data = {header[i]: row[i+2].strip() for i in range(min(len(header), len(row)-2))}
                deposits.append(data)
        self.deposits = deposits

    def compute_asset_metrics(self):
        """
        Computes asset-level metrics by aggregating trades (only buy orders with positive quantity).
        Calculates total quantity, total cost, average purchase price, current value,
        absolute profit/loss, and percentage return.
        Also incorporates realized/unrealized performance if available.
        """
        asset_metrics = {}
        for symbol, trades in self.trades_by_symbol.items():
            total_quantity = 0.0
            total_cost = 0.0
            for trade in trades:
                try:
                    quantity = float(trade.get("Quantity", "0"))
                    # Only consider buy orders (positive quantity)
                    if quantity > 0:
                        t_price = float(trade.get("T. Price", "0"))
                        total_quantity += quantity
                        total_cost += quantity * t_price
                except ValueError:
                    continue
            avg_purchase_price = total_cost / total_quantity if total_quantity else 0
            # Use provided current price if available; otherwise default to average purchase price.
            current_price = self.current_prices.get(symbol, avg_purchase_price)
            current_value = total_quantity * current_price
            absolute_pl = current_value - total_cost
            percentage_return = (absolute_pl / total_cost * 100) if total_cost else None

            # Incorporate realized and unrealized performance if available.
            realized_data = self.realized_summary.get(symbol, {})
            try:
                realized_total = float(realized_data.get("Realized Total", "0"))
                unrealized_total = float(realized_data.get("Unrealized Total", "0"))
            except ValueError:
                realized_total = 0
                unrealized_total = 0

            asset_metrics[symbol] = {
                "total_quantity": total_quantity,
                "total_cost": total_cost,
                "avg_purchase_price": avg_purchase_price,
                "current_price": current_price,
                "current_value": current_value,
                "absolute_pl": absolute_pl,
                "percentage_return": percentage_return,
                "realized_total": realized_total,
                "unrealized_total": unrealized_total
            }
        self.asset_metrics = asset_metrics

    @staticmethod
    def compute_transaction_metrics(trade, current_price):
        """
        Computes per transaction metrics given a trade dictionary and current price.
        Returns a dictionary with quantity, trade price, cost, current value,
        profit/loss, and percentage return.
        """
        try:
            quantity = float(trade.get("Quantity", "0"))
            trade_price = float(trade.get("T. Price", "0"))
        except ValueError:
            return None

        cost = quantity * trade_price
        current_value = quantity * current_price
        pl = current_value - cost
        pct_return = (pl / cost * 100) if cost != 0 else None

        # Adjust percentage return if the trade is a sell (negative quantity)
        if quantity < 0 and pct_return is not None:
            pct_return = -pct_return

        return {
            "quantity": quantity,
            "trade_price": trade_price,
            "cost": cost,
            "current_value": current_value,
            "profit_loss": pl,
            "percentage_return": pct_return
        }

    def export_to_csv(self, filename):
        """
        Exports the computed asset metrics to a CSV file.
        """
        fieldnames = [
            "Asset", "Total Quantity", "Total Cost", "Avg Purchase Price",
            "Current Price", "Current Value", "Absolute P/L",
            "Percentage Return", "Realized Total", "Unrealized Total"
        ]
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for symbol, metrics in self.asset_metrics.items():
                writer.writerow({
                    "Asset": symbol,
                    "Total Quantity": metrics["total_quantity"],
                    "Total Cost": metrics["total_cost"],
                    "Avg Purchase Price": metrics["avg_purchase_price"],
                    "Current Price": metrics["current_price"],
                    "Current Value": metrics["current_value"],
                    "Absolute P/L": metrics["absolute_pl"],
                    "Percentage Return": metrics["percentage_return"],
                    "Realized Total": metrics["realized_total"],
                    "Unrealized Total": metrics["unrealized_total"]
                })

    def export_to_json(self, filename):
        """
        Exports the computed asset metrics to a JSON file.
        """
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.asset_metrics, f, indent=4)

    def export_to_html(self, filename):
        """
        Exports the computed asset metrics to an HTML file.
        """
        html = "<html><head><title>Portfolio Report</title></head><body>"
        html += "<h1>Portfolio Report</h1>"
        html += "<table border='1'><tr>"
        headers = [
            "Asset", "Total Quantity", "Total Cost", "Avg Purchase Price",
            "Current Price", "Current Value", "Absolute P/L",
            "Percentage Return", "Realized Total", "Unrealized Total"
        ]
        for h in headers:
            html += f"<th>{h}</th>"
        html += "</tr>"
        for symbol, metrics in self.asset_metrics.items():
            html += "<tr>"
            html += f"<td>{symbol}</td>"
            html += f"<td>{metrics['total_quantity']}</td>"
            html += f"<td>{metrics['total_cost']}</td>"
            html += f"<td>{metrics['avg_purchase_price']}</td>"
            html += f"<td>{metrics['current_price']}</td>"
            html += f"<td>{metrics['current_value']}</td>"
            html += f"<td>{metrics['absolute_pl']}</td>"
            html += f"<td>{metrics['percentage_return']}</td>"
            html += f"<td>{metrics['realized_total']}</td>"
            html += f"<td>{metrics['unrealized_total']}</td>"
            html += "</tr>"
        html += "</table></body></html>"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(html)

    def load_and_process(self):
        """
        High-level method to load the CSV file, process each section, and compute metrics.
        """
        self.parse_csv_sections()
        # Process Trades section
        if "Trades" in self.sections:
            self.process_trades(self.sections["Trades"])
        # Process Realized & Unrealized Performance Summary section
        if "Realized & Unrealized Performance Summary" in self.sections:
            self.process_realized_summary(self.sections["Realized & Unrealized Performance Summary"])
        # Process Deposits & Withdrawals section (if needed)
        if "Deposits & Withdrawals" in self.sections:
            self.process_deposits(self.sections["Deposits & Withdrawals"])
        # Compute asset-level metrics
        self.compute_asset_metrics()

    def display_metrics(self, detailed=False, detailed_tx=False):
        """
        Displays overall asset metrics and, optionally, detailed transaction data.
        """
        print("Portfolio Metrics by Asset:")
        for symbol, metrics in self.asset_metrics.items():
            ret = metrics.get('percentage_return')
            if ret is None:
                pct_str = "N/A"
            else:
                pct_str = f"{ret:.2f}%"
                pct_str = colored(pct_str, "green", self.use_color) if ret >= 0 else colored(pct_str, "red", self.use_color)
            print(f"Asset: {symbol}")
            print(f"  Total Quantity        : {metrics['total_quantity']}")
            print(f"  Total Cost            : {metrics['total_cost']:.2f}")
            print(f"  Average Purchase Price: {metrics['avg_purchase_price']:.2f}")
            print(f"  Current Price         : {metrics['current_price']:.2f}")
            print(f"  Current Value         : {metrics['current_value']:.2f}")
            print(f"  Absolute P/L          : {metrics['absolute_pl']:.2f}")
            print(f"  Percentage Return     : {pct_str}")
            print(f"  Realized P/L          : {metrics['realized_total']:.2f}")
            print(f"  Unrealized P/L        : {metrics['unrealized_total']:.2f}\n")

        # Display detailed per-transaction metrics if requested
        if detailed_tx:
            print("Per Transaction Details:")
            for symbol, trades in self.trades_by_symbol.items():
                current_price = self.current_prices.get(symbol, self.asset_metrics.get(symbol, {}).get("avg_purchase_price", 0))
                print(f"\nAsset: {symbol}")
                for idx, trade in enumerate(trades, start=1):
                    tx_metrics = self.compute_transaction_metrics(trade, current_price)
                    if tx_metrics is None:
                        continue
                    ret = tx_metrics.get("percentage_return")
                    if ret is None:
                        ret_str = "N/A"
                    else:
                        ret_str = f"{ret:.2f}%"
                        ret_str = colored(ret_str, "green", self.use_color) if ret >= 0 else colored(ret_str, "red", self.use_color)
                    print(f"  Transaction {idx}:")
                    print(f"    Quantity      : {tx_metrics['quantity']}")
                    print(f"    Trade Price   : {tx_metrics['trade_price']:.2f}")
                    print(f"    Cost          : {tx_metrics['cost']:.2f}")
                    print(f"    Current Value : {tx_metrics['current_value']:.2f}")
                    print(f"    P/L           : {tx_metrics['profit_loss']:.2f}")
                    print(f"    Return        : {ret_str}")

def parse_current_prices(price_list):
    """
    Parses current price entries provided as SYMBOL=PRICE.
    Returns a dictionary mapping asset symbols to their current prices.
    """
    current_prices = {}
    for item in price_list:
        if '=' in item:
            symbol, price_str = item.split('=', 1)
            try:
                current_prices[symbol.strip()] = float(price_str.strip())
            except ValueError:
                continue
    return current_prices

def main():
    parser = argparse.ArgumentParser(
        description="Mexem: Multi-Asset Portfolio Analyzer for Mexem Trading Platform."
    )
    parser.add_argument("-f", "--csv-file", type=str, required=True,
                        help="Path to the CSV file generated by Mexem trading platform.")
    parser.add_argument("-p", "--current-price", type=str, action="append", default=[],
                        help="Current price for assets in the format SYMBOL=PRICE. Can be used multiple times.")
    parser.add_argument("--export-csv", type=str, help="Export the report to a CSV file.")
    parser.add_argument("--export-json", type=str, help="Export the report to a JSON file.")
    parser.add_argument("--export-html", type=str, help="Export the report to an HTML file.")
    parser.add_argument("--detailed", action="store_true",
                        help="Show detailed asset-level report output.")
    parser.add_argument("--detailed-tx", action="store_true",
                        help="Show detailed per transaction report output.")
    parser.add_argument("--no-color", action="store_true",
                        help="Disable colored output.")
    args = parser.parse_args()

    # Parse current prices from the command-line
    current_prices = parse_current_prices(args.current_price)
    use_color = not args.no_color

    # Create an instance of PortfolioAnalyzer and load the CSV data
    analyzer = PortfolioAnalyzer(args.csv_file, current_prices, use_color)
    analyzer.load_and_process()

    # Display computed metrics on the console
    analyzer.display_metrics(detailed=args.detailed, detailed_tx=args.detailed_tx)

    # Compute overall portfolio summary metrics and display them
    total_cost = sum(m["total_cost"] for m in analyzer.asset_metrics.values())
    total_value = sum(m["current_value"] for m in analyzer.asset_metrics.values())
    overall_pl = total_value - total_cost
    overall_return = (overall_pl / total_cost * 100) if total_cost else None
    if overall_return is None:
        overall_return_str = "N/A"
    else:
        overall_return_str = f"{overall_return:.2f}%"
        overall_return_str = colored(overall_return_str, "green", use_color) if overall_return >= 0 else colored(overall_return_str, "red", use_color)
    print("Overall Portfolio Metrics:")
    print(f"  Total Cost       : {total_cost:.2f}")
    print(f"  Total Value      : {total_value:.2f}")
    print(f"  Absolute P/L     : {overall_pl:.2f}")
    print(f"  Percentage Return: {overall_return_str}")

    # Export reports if requested
    if args.export_csv:
        analyzer.export_to_csv(args.export_csv)
        print(f"\nReport exported to CSV: {args.export_csv}")
    if args.export_json:
        analyzer.export_to_json(args.export_json)
        print(f"\nReport exported to JSON: {args.export_json}")
    if args.export_html:
        analyzer.export_to_html(args.export_html)
        print(f"\nReport exported to HTML: {args.export_html}")

if __name__ == '__main__':
    main()


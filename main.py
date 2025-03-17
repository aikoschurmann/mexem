#!/usr/bin/env python3
import argparse
import csv
import json

# ANSI color codes for colored terminal output
ANSI_COLORS = {
    'red': "\033[91m",
    'green': "\033[92m",
    'blue': "\033[94m",
    'pink': "\033[95m",
    'yellow': "\033[93m",
    'reset': "\033[0m",
}

def colored(text, color, enable_color=True):
    """
    Wrap text in ANSI color codes if coloring is enabled.
    
    Args:
        text (str): The text to be colored.
        color (str): Color key (e.g., 'red', 'green').
        enable_color (bool): Flag to enable or disable colored output.
    
    Returns:
        str: Colored text if enabled; otherwise, plain text.
    """
    if enable_color and color in ANSI_COLORS:
        return f"{ANSI_COLORS[color]}{text}{ANSI_COLORS['reset']}"
    return str(text)

class PortfolioAnalyzer:
    """
    Analyzes portfolio data from a CSV file and computes asset-level and 
    transaction-level metrics. Provides options to export the analysis in 
    CSV, JSON, or HTML format.
    """
    def __init__(self, csv_file, current_prices, use_color=True):
        self.csv_file = csv_file
        self.current_prices = current_prices
        self.use_color = use_color
        self.sections = {}
        self.trades_by_symbol = {}
        self.realized_summary = {}
        self.deposits = []
        self.asset_metrics = {}

    def parse_csv_sections(self):
        """
        Reads the CSV file and groups rows by the section name (first column).
        """
        sections = {}
        with open(self.csv_file, newline="", encoding="utf-8") as file:
            reader = csv.reader(file)
            for row in reader:
                if not row:
                    continue
                section_name = row[0].strip()
                sections.setdefault(section_name, []).append(row)
        self.sections = sections
       

    def process_trades(self, rows):
        """
        Processes the 'Trades' section to extract and group trade data.
        
        Args:
            rows (list): CSV rows corresponding to the Trades section.
        """
        header = None
        trades = []
        for row in rows:
            if len(row) < 3:
                continue
            if row[1].strip().lower() == "header":
                header = [x.strip() for x in row[2:]]
                continue
            if row[1].strip().lower() == "data" and header:
                trade_data = {header[i]: row[i+2].strip() for i in range(min(len(header), len(row)-2))}
                trades.append(trade_data)
        trades_by_symbol = {}
        for trade in trades:
            symbol = trade.get("Symbol")
            if symbol:
                trades_by_symbol.setdefault(symbol, []).append(trade)
        self.trades_by_symbol = trades_by_symbol

    def process_realized_summary(self, rows):
        """
        Processes the 'Realized & Unrealized Performance Summary' section.
        
        Args:
            rows (list): CSV rows corresponding to the performance summary.
        """
        header = None
        summary = {}
        for row in rows:
            if row[1].strip().lower() == "header":
                header = [x.strip() for x in row[2:]]
                continue
            if row[1].strip().lower() == "data" and header:
                data = {header[i]: row[i+2].strip() for i in range(min(len(header), len(row)-2))}
                symbol = data.get("Symbol", "Unknown")
                summary[symbol] = data
        self.realized_summary = summary

    def process_deposits(self, rows):
        """
        Processes the 'Deposits & Withdrawals' section.
        
        Args:
            rows (list): CSV rows corresponding to deposits and withdrawals.
        """
        header = None
        deposits = []
        for row in rows:
            if row[1].strip().lower() == "header":
                header = [x.strip() for x in row[2:]]
                continue
            if row[1].strip().lower() == "data" and header:
                deposit_data = {header[i]: row[i+2].strip() for i in range(min(len(header), len(row)-2))}
                deposits.append(deposit_data)
        self.deposits = deposits

    def compute_asset_metrics(self):
        """
        Aggregates trade data for each asset and computes key metrics such as 
        total quantity, total cost, average purchase price, current value, 
        absolute profit/loss, and percentage return. Also integrates any 
        realized/unrealized performance data.
        """
        metrics = {}
        for symbol, trades in self.trades_by_symbol.items():
            total_qty = 0.0
            total_cost = 0.0
            for trade in trades:
                try:
                    qty = float(trade.get("Quantity", "0"))
                    price = float(trade.get("T. Price", "0"))
                    commission = float(trade.get("Comm/Fee", "0"))
                    total_qty += qty
                    total_cost += qty * price - commission
                except ValueError:
                    continue
            avg_price = total_cost / total_qty if total_qty else 0
            current_price = self.current_prices.get(symbol, avg_price)
            current_value = total_qty * current_price
            abs_pl = current_value - total_cost
            pct_return = (abs_pl / total_cost * 100) if total_cost else None

            realized_data = self.realized_summary.get(symbol, {})
            try:
                realized_total = float(realized_data.get("Realized Total", "0"))
                unrealized_total = float(realized_data.get("Unrealized Total", "0"))
            except ValueError:
                realized_total, unrealized_total = 0, 0

            metrics[symbol] = {
                "total_quantity": total_qty,
                "total_cost": total_cost,
                "avg_purchase_price": avg_price,
                "current_price": current_price,
                "current_value": current_value,
                "absolute_pl": abs_pl,
                "percentage_return": pct_return,
                "realized_total": realized_total,
                "unrealized_total": unrealized_total
            }
        self.asset_metrics = metrics

    @staticmethod
    def compute_transaction_metrics(trade, current_price):
        """
        Computes metrics for an individual transaction.
        
        Args:
            trade (dict): Trade data.
            current_price (float): Current market price for the asset.
        
        Returns:
            dict or None: Dictionary containing cost, current value, profit/loss, 
            and return percentage; or None if values cannot be computed.
        """
        try:
            qty = float(trade.get("Quantity", "0"))
            trade_price = float(trade.get("T. Price", "0"))
        except ValueError:
            return None

        cost = qty * trade_price
        current_val = qty * current_price
        profit_loss = current_val - cost
        pct_return = (profit_loss / cost * 100) if cost else None
        commission = float(trade.get("Comm/Fee", "0"))

        # For sell orders (negative quantity), invert the return percentage.
        if qty < 0 and pct_return is not None:
            pct_return = -pct_return

        return {
            "quantity": qty,
            "trade_price": trade_price,
            "cost": cost,
            "current_value": current_val,
            "profit_loss": profit_loss,
            "percentage_return": pct_return,
            "commission": commission
        }

    def export_to_csv(self, filename):
        """
        Exports the asset metrics to a CSV file.
        
        Args:
            filename (str): Output file path.
        """
        fieldnames = [
            "Asset", "Total Quantity", "Total Cost", "Avg Purchase Price",
            "Current Price", "Current Value", "Absolute P/L",
            "Percentage Return", "Realized Total", "Unrealized Total"
        ]
        with open(filename, "w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            for symbol, data in self.asset_metrics.items():
                writer.writerow({
                    "Asset": symbol,
                    "Total Quantity": data["total_quantity"],
                    "Total Cost": data["total_cost"],
                    "Avg Purchase Price": data["avg_purchase_price"],
                    "Current Price": data["current_price"],
                    "Current Value": data["current_value"],
                    "Absolute P/L": data["absolute_pl"],
                    "Percentage Return": data["percentage_return"],
                    "Realized Total": data["realized_total"],
                    "Unrealized Total": data["unrealized_total"]
                })

    def export_to_json(self, filename):
        """
        Exports the asset metrics to a JSON file.
        
        Args:
            filename (str): Output file path.
        """
        with open(filename, "w", encoding="utf-8") as file:
            json.dump(self.asset_metrics, file, indent=4)

    def export_to_html(self, filename):
        """
        Exports the asset metrics to an HTML file.
        
        Args:
            filename (str): Output file path.
        """
        html_content = (
            "<html><head><title>Portfolio Report</title></head><body>"
            "<h1>Portfolio Report</h1>"
            "<table border='1'><tr>"
        )
        headers = [
            "Asset", "Total Quantity", "Total Cost", "Avg Purchase Price",
            "Current Price", "Current Value", "Absolute P/L",
            "Percentage Return", "Realized Total", "Unrealized Total"
        ]
        for header in headers:
            html_content += f"<th>{header}</th>"
        html_content += "</tr>"
        for symbol, data in self.asset_metrics.items():
            html_content += "<tr>"
            html_content += f"<td>{symbol}</td>"
            html_content += f"<td>{data['total_quantity']}</td>"
            html_content += f"<td>{data['total_cost']}</td>"
            html_content += f"<td>{data['avg_purchase_price']}</td>"
            html_content += f"<td>{data['current_price']}</td>"
            html_content += f"<td>{data['current_value']}</td>"
            html_content += f"<td>{data['absolute_pl']}</td>"
            html_content += f"<td>{data['percentage_return']}</td>"
            html_content += f"<td>{data['realized_total']}</td>"
            html_content += f"<td>{data['unrealized_total']}</td>"
            html_content += "</tr>"
        html_content += "</table></body></html>"
        with open(filename, "w", encoding="utf-8") as file:
            file.write(html_content)

    def load_and_process(self):
        """
        Loads the CSV file, processes its sections, and computes asset metrics.
        """
        self.parse_csv_sections()
        if "Trades" in self.sections:
            self.process_trades(self.sections["Trades"])
        if "Realized & Unrealized Performance Summary" in self.sections:
            self.process_realized_summary(self.sections["Realized & Unrealized Performance Summary"])
        if "Deposits & Withdrawals" in self.sections:
            self.process_deposits(self.sections["Deposits & Withdrawals"])
        self.compute_asset_metrics()

    def display_metrics(self, detailed=False, detailed_tx=False):
        """
        Displays asset metrics and, optionally, detailed transaction data.
        
        Args:
            detailed (bool): Reserved for future detailed asset breakdown.
            detailed_tx (bool): If True, displays individual transaction details.
        """
        print(colored("Portfolio Metrics by Asset:", "blue", self.use_color))
        for symbol, data in self.asset_metrics.items():
            pct = data.get("percentage_return")
            pct_str = "N/A" if pct is None else f"{pct:.2f}%"
            pct_str = (colored(pct_str, "green", self.use_color) if pct and pct >= 0 
                       else colored(pct_str, "red", self.use_color))
            realized_str = colored(f"{data['realized_total']:.2f}", "green", self.use_color) \
                if data['realized_total'] >= 0 else colored(f"{data['realized_total']:.2f}", "red", self.use_color)
            unrealized_str = colored(f"{data['unrealized_total']:.2f}", "green", self.use_color) \
                if data['unrealized_total'] >= 0 else colored(f"{data['unrealized_total']:.2f}", "red", self.use_color)
            
            print(colored(f"Asset: {symbol}", "pink", self.use_color))
            print(f"  Total Quantity        : {data['total_quantity']}")
            print(f"  Total Cost            : {data['total_cost']:.2f}")
            print(f"  Avg Purchase Price    : {data['avg_purchase_price']:.2f}")
            print(f"  Current Price         : {data['current_price']:.2f}")
            print(f"  Current Value         : {data['current_value']:.2f}")
            print(f"  Percentage Return     : {pct_str}")
            print(f"  Realized P/L          : {realized_str}")
            print(f"  Unrealized P/L        : {unrealized_str}\n")

        if detailed_tx:
            print(colored("Transaction Details:", "blue", self.use_color))
            for symbol, trades in self.trades_by_symbol.items():
                current_price = self.current_prices.get(symbol, self.asset_metrics.get(symbol, {}).get("avg_purchase_price", 0))
                print(colored(f"Asset: {symbol}", "pink", self.use_color))
                for idx, trade in enumerate(trades, start=1):
                    tx = self.compute_transaction_metrics(trade, current_price)
                    if not tx:
                        continue
                    ret = tx.get("percentage_return")
                    ret_str = "N/A" if ret is None else f"{ret:.2f}%"
                    ret_str = (colored(ret_str, "green", self.use_color) if ret and ret >= 0 
                               else colored(ret_str, "red", self.use_color))
                    pl_str = f"{tx['profit_loss']:.2f}"
                    pl_str = (colored(pl_str, "green", self.use_color) if tx['profit_loss'] >= 0 
                              else colored(pl_str, "red", self.use_color))
                    
                    print(colored(f"  Transaction {idx}:", "yellow", self.use_color))
                    print(f"    Quantity      : {tx['quantity']}")
                    print(f"    Trade Price   : {tx['trade_price']:.2f}")
                    print(f"    Cost          : {tx['cost']:.2f}")
                    print(f"    Current Value : {tx['current_value']:.2f}")
                    print(f"    Profit/Loss   : {pl_str}")
                    print(f"    Return        : {ret_str}")
                    print(f"    Commission    : {tx['commission']:.2f}\n")

def parse_current_prices(price_entries):
    """
    Parses current price entries in the format SYMBOL=PRICE.
    
    Args:
        price_entries (list): List of strings like "AAPL=150.25".
    
    Returns:
        dict: Mapping of asset symbols to their float prices.
    """
    prices = {}
    for entry in price_entries:
        if '=' in entry:
            symbol, price_str = entry.split('=', 1)
            try:
                prices[symbol.strip()] = float(price_str.strip())
            except ValueError:
                continue
    return prices

def main():
    """
    Main entry point for the portfolio analyzer tool.
    """
    parser = argparse.ArgumentParser(
        description="Mexem: Multi-Asset Portfolio Analyzer for the Mexem Trading Platform."
    )
    parser.add_argument("-f", "--csv-file", type=str, required=True,
                        help="Path to the CSV file exported from Mexem containing transaction data.")
    parser.add_argument("-p", "--current-price", type=str, action="append", default=[],
                        help="Specify current asset price as SYMBOL=PRICE (e.g., AAPL=150.25).")
    parser.add_argument("--export-csv", type=str, help="Export report to a CSV file.")
    parser.add_argument("--export-json", type=str, help="Export report to a JSON file.")
    parser.add_argument("--export-html", type=str, help="Export report to an HTML file.")
    parser.add_argument("--detailed", action="store_true", help="Display detailed asset breakdown.")
    parser.add_argument("--detailed-tx", action="store_true", help="Display detailed transaction breakdown.")
    parser.add_argument("--no-color", action="store_true", help="Disable colored terminal output.")

    args = parser.parse_args()

    current_prices = parse_current_prices(args.current_price)
    use_color = not args.no_color

    analyzer = PortfolioAnalyzer(args.csv_file, current_prices, use_color)
    analyzer.load_and_process()
    analyzer.display_metrics(detailed=args.detailed, detailed_tx=args.detailed_tx)

    total_cost = sum(data["total_cost"] for data in analyzer.asset_metrics.values())
    total_value = sum(data["current_value"] for data in analyzer.asset_metrics.values())
    overall_pl = total_value - total_cost
    overall_pl_str = f"{overall_pl:.2f}"
    overall_pl_str = colored(overall_pl_str, "green", use_color) if overall_pl >= 0 else colored(overall_pl_str, "red", use_color)
    overall_return = (overall_pl / total_cost * 100) if total_cost else None
    overall_return_str = "N/A" if overall_return is None else f"{overall_return:.2f}%"
    overall_return_str = (colored(overall_return_str, "green", use_color) if overall_return and overall_return >= 0 
                          else colored(overall_return_str, "red", use_color))
    
    print(colored("Overall Portfolio Metrics:", "blue", use_color))
    print(f"  Total Cost       : {total_cost:.2f}")
    print(f"  Total Value      : {total_value:.2f}")
    print(f"  Absolute P/L     : {overall_pl_str}")
    print(f"  Percentage Return: {overall_return_str}")

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

import csv
import random
import tls_client
import time
import os
import threading

from contextlib import redirect_stderr
from fake_useragent import UserAgent
from concurrent.futures import ThreadPoolExecutor, as_completed

globalRatelimitEvent = threading.Event()

class BulkWalletChecker:

    def __init__(self):
        self.sendRequest = tls_client.Session(client_identifier='chrome_103')
        self.shorten = lambda s: f"{s[:4]}...{s[-5:]}" if len(s) >= 9 else s
        self.skippedWallets = 0
        self.proxyPosition = 0
        self.totalGrabbed = 0
        self.totalFailed = 0
        self.results = []
        self.debug = False

    def enableDebug(self, enabled: bool = True):
        self.debug = enabled
        return self

    def randomise(self):
        self.identifier = random.choice(
            [browser for browser in tls_client.settings.ClientIdentifiers.__args__
             if browser.startswith(('chrome', 'safari', 'firefox', 'opera'))]
        )
        parts = self.identifier.split('_')
        identifier, version, *rest = parts
        identifier = identifier.capitalize()
        
        self.sendRequest = tls_client.Session(random_tls_extension_order=True, client_identifier=self.identifier)
        self.sendRequest.timeout_seconds = 60

        if identifier == 'Opera':
            identifier = 'Chrome'
            osType = 'Windows'
        elif version.lower() == 'ios':
            osType = 'iOS'
        else:
            osType = 'Windows'

        try:
            self.user_agent = UserAgent(os=[osType]).random
        except Exception:
            self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:82.0) Gecko/20100101 Firefox/82.0"

        self.headers = {
            'Host': 'gmgn.ai',
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
            'dnt': '1',
            'priority': 'u=1, i',
            'referer': 'https://gmgn.ai/?chain=sol',
            'user-agent': self.user_agent
        }

    def loadProxies(self):
        with open("Dragon/data/Proxies/proxies.txt", 'r') as file:
            proxies = file.read().splitlines()

        formattedProxies = []
        for proxy in proxies:
            if ':' in proxy:
                parts = proxy.split(':')
                if len(parts) == 4:
                    ip, port, username, password = parts
                    formattedProxies.append({
                        'http': f"http://{username}:{password}@{ip}:{port}",
                        'https': f"http://{username}:{password}@{ip}:{port}"
                    })
                else:
                    formattedProxies.append({
                        'http': f"http://{proxy}",
                        'https': f"http://{proxy}"
                    })
            else:
                formattedProxies.append(f"http://{proxy}")
        return formattedProxies

    def configureProxy(self, proxy):
        if isinstance(proxy, dict):
            self.sendRequest.proxies = {
                'http': proxy.get('http'),
                'https': proxy.get('https')
            }
        elif isinstance(proxy, str):
            self.sendRequest.proxies = {
                'http': proxy,
                'https': proxy
            }
        else:
            self.sendRequest.proxies = None
        return proxy

    def getNextProxy(self):
        proxies = self.loadProxies()
        proxy = proxies[self.proxyPosition % len(proxies)]
        self.proxyPosition += 1
        return proxy

    def getWalletData(self, wallet: str, skipWallets: bool, useProxies):
        url = f"http://172.86.110.62:1337/defi/quotation/v1/smartmoney/sol/walletNew/{wallet}?period=7d"
        
        while True:
            try:
                if globalRatelimitEvent.is_set():
                    print(f"[🐲] Global rate limit active. Waiting for cooldown before processing wallet {wallet}...")
                    globalRatelimitEvent.wait() 

                self.randomise()
                proxy = self.getNextProxy() if useProxies else None
                self.configureProxy(proxy)
                response = self.sendRequest.get(url, headers=self.headers)

                if response.status_code == 429:
                    print(f"[🐲] Received 429 for wallet {wallet}. Triggering global cooldown for 7.5 seconds...")
                    globalRatelimitEvent.set()
                    time.sleep(7.5)
                    globalRatelimitEvent.clear()
                    continue

                if response.status_code == 200:
                    data = response.json()
                    if data['msg'] == "success":
                        data = data['data']
                        if skipWallets:
                            if 'buy_30d' in data and isinstance(data['buy_30d'], (int, float)) and data['buy_30d'] > 0:
                                self.totalGrabbed += 1
                                print(f"[🐲] Successfully grabbed data for {wallet} ({self.totalGrabbed})")
                                result = self.processWalletData(wallet, data)
                                return result
                            else:
                                self.skippedWallets += 1
                                if self.debug:
                                    print(f"[🐲] Skipping wallet {wallet} due to buy_30d <= 0")
                                print(f"[🐲] Skipped {self.skippedWallets} wallets", end="\r")
                                return None
                        else:
                            result = self.processWalletData(wallet, data)
                            return result
            except Exception as e:
                self.totalFailed += 1
                print(f"[🐲] Exception for {wallet}: {str(e)}. Retrying in 7.5 seconds...")
            time.sleep(7.5)

    def processWalletData(self, wallet, data):
        pnl7d = f"{data['pnl_7d']:,.2f}" if data['pnl_7d'] is not None else "-1.23"
        realizedProfit7dUSD = f"${data['realized_profit_7d']:,.2f}" if data['realized_profit_7d'] is not None else "-1.23"
        winrate7d = f"{data['winrate'] * 100:.2f}%" if data['winrate'] is not None else "-1.23"
        buy7d = f"{data['buy_7d']}" if data['buy_7d'] is not None else "-1.23"
        sell7d = f"{data['sell_7d']}" if data['sell_7d'] is not None else "-1.23"
        
        # Calculate Traded = Buys + Sell
        try:
            if data['buy_7d'] is not None and data['sell_7d'] is not None:
                traded = data['buy_7d'] + data['sell_7d']
                traded7d = f"{traded}"
            else:
                traded7d = "-1.23"
        except (TypeError, ValueError):
            traded7d = "-1.23"
        tokenNum = f"{data['token_num']}" if data['token_num'] is not None else "-1.23"
        pnlLtMinusDot5Num = f"{data['pnl_lt_minus_dot5_num']}" if data['pnl_lt_minus_dot5_num'] is not None else "-1.23"
        pnlMinusDot5To0xNum = f"{data['pnl_minus_dot5_0x_num']}" if data['pnl_minus_dot5_0x_num'] is not None else "-1.23"
        pnlLt2xNum = f"{data['pnl_lt_2x_num']}" if data['pnl_lt_2x_num'] is not None else "-1.23"
        pnl2xTo5xNum = f"{data['pnl_2x_5x_num']}" if data['pnl_2x_5x_num'] is not None else "-1.23"
        pnlGt5xNum = f"{data['pnl_gt_5x_num']}" if data['pnl_gt_5x_num'] is not None else "-1.23"
        solBalance = f"{data['sol_balance']}" if data.get('sol_balance') is not None else "0"

        # Calculate percentages for PnL ranges (divided by token_num * 100)
        try:
            if data['token_num'] is not None and data['token_num'] != 0:
                pnlLtMinusDot5Percent = f"{(data['pnl_lt_minus_dot5_num'] / data['token_num'] * 100):.2f}%" if data['pnl_lt_minus_dot5_num'] is not None else "?"
                pnlMinusDot5To0xPercent = f"{(data['pnl_minus_dot5_0x_num'] / data['token_num'] * 100):.2f}%" if data['pnl_minus_dot5_0x_num'] is not None else "?"
                pnlLt2xPercent = f"{(data['pnl_lt_2x_num'] / data['token_num'] * 100):.2f}%" if data['pnl_lt_2x_num'] is not None else "?"
                pnl2xTo5xPercent = f"{(data['pnl_2x_5x_num'] / data['token_num'] * 100):.2f}%" if data['pnl_2x_5x_num'] is not None else "?"
                pnlGt5xPercent = f"{(data['pnl_gt_5x_num'] / data['token_num'] * 100):.2f}%" if data['pnl_gt_5x_num'] is not None else "?"
            else:
                pnlLtMinusDot5Percent = "?"
                pnlMinusDot5To0xPercent = "?"
                pnlLt2xPercent = "?"
                pnl2xTo5xPercent = "?"
                pnlGt5xPercent = "?"
        except (TypeError, ZeroDivisionError):
            pnlLtMinusDot5Percent = "?"
            pnlMinusDot5To0xPercent = "?"
            pnlLt2xPercent = "?"
            pnl2xTo5xPercent = "?"
            pnlGt5xPercent = "?"

        # Calculate Fast tx % from risk data
        try:
            if data.get('risk') is not None and data['risk'].get('fast_tx_ratio') is not None:
                fast_tx_ratio = data['risk']['fast_tx_ratio']
                fastTxPercent = f"{fast_tx_ratio * 100:.2f}%"
            else:
                fastTxPercent = "110"
        except (TypeError, KeyError, AttributeError):
            fastTxPercent = "110"

        # Calculate no_buy_hold_ratio from risk data
        try:
            if data.get('risk') is not None and data['risk'].get('no_buy_hold_ratio') is not None:
                no_buy_hold_ratio = data['risk']['no_buy_hold_ratio']
                noBuyHoldRatio = f"{no_buy_hold_ratio * 100:.2f}%"
            else:
                noBuyHoldRatio = "110"
        except (TypeError, KeyError, AttributeError):
            noBuyHoldRatio = "110"
        averageHoldingDuration =  (
            f"{data['avg_holding_peroid']}s" if data['avg_holding_peroid'] < 60 
            else (
                f"{data['avg_holding_peroid'] / 60:.2f}m" if data['avg_holding_peroid'] < 3600 
                else f"{data['avg_holding_peroid'] / 3600:.2f}h"
            )
        ) if data['avg_holding_peroid'] is not None else "?"

        # Calculate Single buy = realizedProfit7dUSD/(pnl7d*buy7d)
        try:
            if (data['realized_profit_7d'] is not None and 
                data['pnl_7d'] is not None and 
                data['buy_7d'] is not None and 
                data['pnl_7d'] != 0 and 
                data['buy_7d'] != 0):
                single_buy = data['realized_profit_7d'] / (data['pnl_7d'] * data['buy_7d'])
                single_buy_formatted = f"{single_buy:.4f}"
            else:
                single_buy_formatted = "error"
        except (TypeError, ZeroDivisionError):
            single_buy_formatted = "error"


        if "Skipped" in data.get("tags", []):
            return {
                "wallet": wallet
            }

        # Removed any 30d winrate retrieval.
        return {
            "wallet": wallet,
            "PNL (*100%)": pnl7d,
            "USDProfit": realizedProfit7dUSD,
            "Winrate": winrate7d,
            "Single buy": single_buy_formatted,
            "Traded": traded7d,
            "Number of tokens traded": tokenNum,
            "Buys": buy7d,
            "Sell": sell7d,
            "PnL < -0.5x %": pnlLtMinusDot5Percent,
            "PnL -0.5x to 0x %": pnlMinusDot5To0xPercent,
            "PnL < 2x %": pnlLt2xPercent,
            "PnL 2x to 5x %": pnl2xTo5xPercent,
            "PnL > 5x %": pnlGt5xPercent,
            "Fast tx %": fastTxPercent,
            "No buy hold ratio": noBuyHoldRatio,
            "SOL balance": solBalance,
        }
    
    def fetchWalletData(self, wallets, threads, skipWallets, useProxies):
        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = {
                executor.submit(self.getWalletData, wallet.strip(), skipWallets, useProxies): wallet
                for wallet in wallets
            }
            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    self.results.append(result)

        resultDict = {}
        filteredCount = 0
        
        for result in self.results:
            wallet = result.get('wallet')
            if wallet:
                # Check all filters - exclude wallets that don't meet criteria
                winrate_str = result.get('Winrate', '0%')
                usd_profit_str = result.get('USDProfit', '$0.00')
                fast_tx_str = result.get('Fast tx %', '0%')
                no_buy_hold_str = result.get('No buy hold ratio', '0%')
                sol_balance_str = result.get('SOL balance', '0')
                traded_str = result.get('Traded', '0')
                
                try:
                    # Extract numeric value from winrate string (e.g., "45.23%" -> 45.23)
                    winrate_value = float(winrate_str.replace('%', ''))
                    
                    # Extract numeric value from USDProfit string (e.g., "$123.45" -> 123.45)
                    usd_profit_value = float(usd_profit_str.replace('$', '').replace(',', ''))
                    
                    # Extract numeric value from Fast tx % string (e.g., "25.50%" -> 25.50)
                    fast_tx_value = float(fast_tx_str.replace('%', ''))
                    
                    # Extract numeric value from No buy hold ratio string (e.g., "15.30%" -> 15.30)
                    no_buy_hold_value = float(no_buy_hold_str.replace('%', ''))

                    # Extract numeric value for SOL balance
                    sol_balance_value = float(str(sol_balance_str).replace(',', ''))

                    # Extract numeric value for Traded
                    traded_value = float(str(traded_str).replace(',', ''))

                    if (winrate_value >= 40.0 and 
                        usd_profit_value >= 0.001 and 
                        fast_tx_value <= 30.0 and 
                        no_buy_hold_value <= 30.0 and 
                        sol_balance_value > 0.0 and
                        traded_value >= 70.0):
                        resultDict[wallet] = result
                        result.pop('wallet', None)
                    else:
                        filteredCount += 1
                        # Collect all failed criteria for a single log message
                        failed_criteria = []
                        if winrate_value < 40.0:
                            failed_criteria.append(f"winrate {winrate_str} (< 40%)")
                        if usd_profit_value < 0.001:
                            failed_criteria.append(f"USDProfit {usd_profit_str} (< $0.001)")
                        if fast_tx_value > 30.0:
                            failed_criteria.append(f"Fast tx % {fast_tx_str} (> 30%)")
                        if no_buy_hold_value > 30.0:
                            failed_criteria.append(f"No buy hold ratio {no_buy_hold_str} (> 30%)")
                        if sol_balance_value <= 0.0:
                            failed_criteria.append(f"SOL balance {sol_balance_str} (= 0)")
                        if traded_value < 70.0:
                            failed_criteria.append(f"Traded {traded_str} (< 70)")
                        
                        # Show single log message with all failed criteria
                        criteria_text = ", ".join(failed_criteria)
                        if self.debug and criteria_text:
                            print(f"[🐲] Filtered wallet {wallet}: {criteria_text}")
                except (ValueError, TypeError):
                    # If values cannot be parsed, include the wallet (safer approach)
                    resultDict[wallet] = result
                    result.pop('wallet', None)
            else:
                print(f"[🐲] Missing 'wallet' key in result: {result}")

        if not resultDict:
            print("[🐲] No wallets meet the filtering criteria (winrate >= 40%, USDProfit >= $0.001, Fast tx % <= 30%, No buy hold ratio <= 30%, SOL balance > 0, and Traded >= 70). No CSV file created.")
            return

        identifier = self.shorten(list(resultDict)[0])
        filename = f"1.csv"
        path = f"Dragon/data/Solana/BulkWallet/wallets_{filename}"

        # Check if file exists to determine if we need to write headers
        file_exists = os.path.exists(path)
        
        with open(path, 'a', newline='') as outfile:
            writer = csv.writer(outfile)
            
            # Only write header if file doesn't exist
            if not file_exists:
                header = ['Identifier'] + list(next(iter(resultDict.values())).keys())
                writer.writerow(header)
            else:
                # Get header from existing file to ensure consistency
                header = ['Identifier'] + list(next(iter(resultDict.values())).keys())

            for key, value in resultDict.items():
                row = [key]
                for h in header[1:]:
                    row.append(value.get(h))
                writer.writerow(row)

        if file_exists:
            print(f"[🐲] Appended data for {len(resultDict.items())} wallets to existing {filename}")
        else:
            print(f"[🐲] Created new file and saved data for {len(resultDict.items())} wallets to {filename}")
        if filteredCount > 0:
            print(f"[🐲] Filtered out {filteredCount} wallets with winrate < 40%, USDProfit < $0.001, Fast tx % > 30%, No buy hold ratio > 30%, SOL balance = 0, or Traded < 70")

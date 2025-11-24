import random
import tls_client

import concurrent.futures
from fake_useragent import UserAgent
from threading import Lock
import time
import base64
import json
import os

ua = UserAgent(os='linux', browsers=['firefox'])

class ScanAllTx:

    def __init__(self):
        self.sendRequest = tls_client.Session(client_identifier='chrome_103')
        
        self.shorten = lambda s: f"{s[:4]}...{s[-5:]}" if len(s) >= 9 else s
        self.lock = Lock()
        self.proxyPosition = 0
        self._cached_proxies = None

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
            self.userAgent = UserAgent(os=[osType]).random
        except Exception:
            self.userAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:82.0) Gecko/20100101 Firefox/82.0"

        self.headers = {
            'Host': 'gmgn.ai',
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
            'dnt': '1',
            'priority': 'u=1, i',
            'referer': 'https://gmgn.ai/?chain=sol',
            'user-agent': self.userAgent
        }

    def loadProxies(self):
        if self._cached_proxies is not None:
            return self._cached_proxies

        proxy_path = "Dragon/data/Proxies/proxies.txt"
        if not os.path.exists(proxy_path):
            self._cached_proxies = []
            return self._cached_proxies

        with open(proxy_path, "r", encoding="utf-8") as file:
            proxies = file.read().splitlines()

        formatted_proxies = []
        for proxy in proxies:
            if ":" in proxy:
                parts = proxy.split(":")
                if len(parts) == 4:
                    ip, port, username, password = parts
                    formatted_proxies.append({
                        "http": f"http://{username}:{password}@{ip}:{port}",
                        "https": f"http://{username}:{password}@{ip}:{port}"
                    })
                else:
                    formatted_proxies.append({
                        "http": f"http://{proxy}",
                        "https": f"http://{proxy}"
                    })
            else:
                formatted_proxies.append(f"http://{proxy}")

        self._cached_proxies = formatted_proxies
        return self._cached_proxies
    
    def configureProxy(self, proxy):
        if isinstance(proxy, dict):
            self.sendRequest.proxies = {
                "http": proxy.get("http"),
                "https": proxy.get("https")
            }
        elif isinstance(proxy, str):
            self.sendRequest.proxies = {
                "http": proxy,
                "https": proxy
            }
        else:
            self.sendRequest.proxies = None
        return proxy
    
    def getNextProxy(self):
        proxies = self.loadProxies()
        if not proxies:
            return None
        proxy = proxies[self.proxyPosition % len(proxies)]
        self.proxyPosition += 1
        return proxy


    def request(self, url: str, useProxies):
        retries = 3
        
        for attempt in range(retries):
            try:
                proxy = self.getNextProxy() if useProxies else None
                self.configureProxy(proxy)
                response = self.sendRequest.get(url, headers=self.headers, allow_redirects=True)
                if response.status_code == 200:
                    data = response.json()["data"]["history"]
                    paginator = response.json()["data"].get("next")
                    return data, paginator
            except Exception:
                print(f"[🐲] Error fetching data, trying backup...")
            
            time.sleep(1)

        print(f"[🐲] Failed after {retries} attempts: {url}")
        return [], None

    def getAllTxMakers(self, contractAddress: str, threads: int, useProxies):
        base_url = f"http://172.86.110.62:1337/vas/api/v1/token_trades/sol/{contractAddress}?limit=100"
        paginator = None
        
        folder = "Dragon/data/Solana/ScanAllTx"
        os.makedirs(folder, exist_ok=True)
        walletFilename = f"wallets_{self.shorten(contractAddress)}__{random.randint(1111, 9999)}.txt"
        walletFilePath = f"{folder}/{walletFilename}"
        jsonFilePath = f"{folder}/{self.shorten(contractAddress)}_pages.json"
        print("[🐲] Starting incremental mode... No data loss possible.\n")
        pageNumber = 1
        while True:
            self.randomise()
            url = f"{base_url}&cursor={paginator}" if paginator else base_url
            try:
                proxy = self.getNextProxy() if useProxies else None
                self.configureProxy(proxy)
                response = self.sendRequest.get(url, headers=self.headers, allow_redirects=True)
                if response.status_code != 200:
                    raise Exception("Error on request")
            except Exception:
                print(f"[🐲] Error fetching page {pageNumber}, retrying...")
                time.sleep(1)
                continue
            data = response.json()
            with open(jsonFilePath, "a", encoding="utf-8") as jf:
                jf.write(json.dumps(data) + "\n")
            history = data["data"].get("history", [])
            paginator = data["data"].get("next")
            with open(walletFilePath, "a", encoding="utf-8") as wf:
                for entry in history:
                    if entry["event"] == "buy":
                        wf.write(entry["maker"] + "\n")
            print(f"[🐲] Saved page {pageNumber} ({len(history)} tx).")

            if paginator:
                try:
                    decoded = base64.b64decode(paginator).decode("utf-8")
                    print(f"[🐲] Next cursor: {decoded}")
                except:
                    print("[🐲] Next cursor unreadable, continuing.")
            else:
                print("[🐲] No more pages. Finished")
                break
            pageNumber += 1
            time.sleep(1)

        print("\n[🐲] Completed. Incremental output saved.")
        
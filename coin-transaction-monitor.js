import WebSocket from 'ws';
import fs from 'fs';
import path from 'path';
import readline from 'readline';

class CoinTransactionMonitor {
    constructor() {
        this.ws = null;
        this.trackedTokens = new Set();
        this.trackedAccounts = new Set();
        this.isRunning = false;
        this.apiKey = "a58qjga19nupyw1pddw6ywbfa4vmcybh8cu58hjte1up8mu88t738t1gecupan2d8nw74gk784qprykb9dp7ehj7ehv6my3d8rwpccu1f9mmpt39e1u5cvj1f9p4evbu85c3ev3ua4ykuamv4yhvfan94uh2h5d2nau2n6g8xapjk2k9duqcau6ehcpwwk9at96eda8an0kuf8";
        this.uri = "wss://pumpportal.fun/api/data";
        this.connectionAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 5000;
        this.debugMode = true;
        this.tokenActivityTimers = new Map(); // Track last activity time for each token
        this.inactiveTimeout = 3 * 60 * 1000; // 3 minutes in milliseconds
        
        // Clear .txt files when code is initiated
        this.clearTxtFiles();
        
        // Setup readline for key press detection
        this.rl = readline.createInterface({
            input: process.stdin,
            output: process.stdout
        });
        
        this.setupKeyListener();
    }

    clearTxtFiles() {
        try {
            // Clear Coin.txt file
            const coinFilePath = path.join(process.cwd(), 'Coin.txt');
            if (fs.existsSync(coinFilePath)) {
                fs.writeFileSync(coinFilePath, '', 'utf8');
                console.log('🧹 Cleared Coin.txt file');
            } else {
                console.log('ℹ️  Coin.txt file does not exist, skipping clear');
            }
            
            // Clear wallets.txt file
            const walletFilePath = path.join(process.cwd(), 'Dragon', 'data', 'Solana', 'BulkWallet', 'wallets.txt');
            if (fs.existsSync(walletFilePath)) {
                fs.writeFileSync(walletFilePath, '', 'utf8');
                console.log('🧹 Cleared wallets.txt file');
            } else {
                console.log('ℹ️  wallets.txt file does not exist, skipping clear');
            }
            
        } catch (error) {
            console.log('❌ Error clearing .txt files:', error.message);
        }
    }

    setupKeyListener() {
        // Enable raw mode to capture individual key presses
        if (process.stdin.isTTY) {
            process.stdin.setRawMode(true);
        }
        
        process.stdin.on('data', (key) => {
            // Check for 'q' or 'Q' to quit
            if (key.toString().toLowerCase() === 'q') {
                console.log('\n🛑 Shutting down gracefully...');
                this.stop();
            }
            // Check for 's' or 'S' to show status
            else if (key.toString().toLowerCase() === 's') {
                this.showStatus();
            }
            // Check for 'r' or 'R' to reconnect
            else if (key.toString().toLowerCase() === 'r') {
                console.log('\n🔄 Reconnecting...');
                this.reconnect();
            }
            // Check for 'h' or 'H' to show help
            else if (key.toString().toLowerCase() === 'h') {
                this.showHelp();
            }
            // Check for 'd' or 'D' to toggle debug mode
            else if (key.toString().toLowerCase() === 'd') {
                this.toggleDebugMode();
            }
            // Check for 'u' or 'U' to manually unsubscribe from inactive tokens
            else if (key.toString().toLowerCase() === 'u') {
                this.cleanupInactiveTokens();
            }
        });
    }

    readTokenAddressesFromFile() {
        try {
            const coinFilePath = path.join(process.cwd(), 'Coin.txt');
            
            if (!fs.existsSync(coinFilePath)) {
                console.log('❌ Coin.txt file not found. Please create the file and add token addresses.');
                return [];
            }

            const fileContent = fs.readFileSync(coinFilePath, 'utf8');
            const lines = fileContent.split('\n')
                .map(line => line.trim())
                .filter(line => line && !line.startsWith('#'));

            if (lines.length === 0) {
                console.log('❌ Coin.txt file is empty or contains no valid token addresses.');
                return [];
            }

            console.log(`✅ Loaded ${lines.length} token address(es) from Coin.txt`);
            return lines;
            
        } catch (error) {
            console.log('❌ Error reading Coin.txt file.');
            console.log(`Error: ${error.message}`);
            return [];
        }
    }

    readAccountAddressesFromFile() {
        try {
            const walletFilePath = path.join(process.cwd(), 'Dragon', 'data', 'Solana', 'BulkWallet', 'wallets.txt');
            
            if (!fs.existsSync(walletFilePath)) {
                console.log('⚠️  wallets.txt file not found. Account monitoring will be skipped.');
                return [];
            }

            const fileContent = fs.readFileSync(walletFilePath, 'utf8');
            const lines = fileContent.split('\n')
                .map(line => line.trim())
                .filter(line => line && !line.startsWith('#'));

            if (lines.length === 0) {
                console.log('⚠️  wallets.txt file is empty. Account monitoring will be skipped.');
                return [];
            }

            console.log(`✅ Loaded ${lines.length} account address(es) from wallets.txt`);
            return lines;
            
        } catch (error) {
            console.log('⚠️  Error reading wallets.txt file.');
            console.log(`Error: ${error.message}`);
            return [];
        }
    }

    saveTraderWalletToFile(walletAddress) {
        try {
            const walletFilePath = path.join(process.cwd(), 'Dragon', 'data', 'Solana', 'BulkWallet', 'wallets.txt');
            
            // Read existing wallets to avoid duplicates
            let existingWallets = new Set();
            if (fs.existsSync(walletFilePath)) {
                const fileContent = fs.readFileSync(walletFilePath, 'utf8');
                const lines = fileContent.split('\n')
                    .map(line => line.trim())
                    .filter(line => line && !line.startsWith('#'));
                lines.forEach(line => existingWallets.add(line));
            }
            
            // Check if wallet already exists
            if (existingWallets.has(walletAddress)) {
                return false; // Wallet already exists
            }
            
            // Add new wallet to the set
            existingWallets.add(walletAddress);
            
            // Convert set back to array and write to file
            const walletsArray = Array.from(existingWallets);
            const fileContent = walletsArray.join('\n') + '\n';
            
            fs.writeFileSync(walletFilePath, fileContent, 'utf8');
            console.log(`💾 Saved new trader wallet: ${walletAddress}`);
            return true; // Wallet was saved
            
        } catch (error) {
            console.log('❌ Error saving wallet to wallets.txt file.');
            console.log(`Error: ${error.message}`);
            return false;
        }
    }

    extractAndSaveTraderPublicKeys(message) {
        // Recursively search for traderPublicKey in the message object
        const extractKeys = (obj, path = '') => {
            if (typeof obj !== 'object' || obj === null) return;
            
            for (const [key, value] of Object.entries(obj)) {
                const currentPath = path ? `${path}.${key}` : key;
                
                if (key === 'traderPublicKey' && typeof value === 'string' && value !== 'Unknown') {
                    console.log(`🔑 Found traderPublicKey at ${currentPath}: ${value}`);
                    this.saveTraderWalletToFile(value);
                } else if (typeof value === 'object' && value !== null) {
                    extractKeys(value, currentPath);
                }
            }
        };
        
        extractKeys(message);
    }

    async connect() {
        return new Promise((resolve, reject) => {
            console.log('🔌 Connecting to PumpPortal WebSocket...');
            
            this.ws = new WebSocket(this.uri);
            
            this.ws.on('open', () => {
                console.log('✅ Connected to PumpPortal WebSocket');
                this.isRunning = true;
                this.connectionAttempts = 0;
                this.setupSubscriptions();
                resolve();
            });
            
            this.ws.on('error', (error) => {
                console.error('❌ WebSocket error:', error);
                reject(error);
            });
            
            this.ws.on('close', (code, reason) => {
                console.log(`🔌 WebSocket connection closed. Code: ${code}, Reason: ${reason}`);
                this.isRunning = false;
                
                // Attempt to reconnect if not manually closed
                if (this.connectionAttempts < this.maxReconnectAttempts) {
                    this.connectionAttempts++;
                    console.log(`🔄 Attempting to reconnect (${this.connectionAttempts}/${this.maxReconnectAttempts}) in ${this.reconnectDelay/1000} seconds...`);
                    setTimeout(() => {
                        this.connect().catch(console.error);
                    }, this.reconnectDelay);
                } else {
                    console.log('❌ Max reconnection attempts reached. Please restart the application.');
                }
            });
            
            this.ws.on('message', (data) => {
                this.handleMessage(data);
            });
        });
    }

    setupSubscriptions() {
        console.log('📡 Setting up subscriptions...');
        
        // Subscribe to new token creation events
        this.subscribeToNewTokens();
        
        // Subscribe to migration events
        this.subscribeToMigrations();
        
        // Subscribe to token trades for coins in Coin.txt
        const tokenAddresses = this.readTokenAddressesFromFile();
        if (tokenAddresses.length > 0) {
            this.subscribeToTokenTrades(tokenAddresses);
        }
        
        // Subscribe to account trades for wallets in wallets.txt
        const accountAddresses = this.readAccountAddressesFromFile();
        if (accountAddresses.length > 0) {
            this.subscribeToAccountTrades(accountAddresses);
        }
    }

    subscribeToNewTokens() {
        const payload = {
            method: "subscribeNewToken"
        };
        
        console.log('📡 Subscribing to new token creation events...');
        this.ws.send(JSON.stringify(payload));
    }

    subscribeToMigrations() {
        const payload = {
            method: "subscribeMigration"
        };
        
        console.log('📡 Subscribing to migration events...');
        this.ws.send(JSON.stringify(payload));
    }

    subscribeToTokenTrades(tokenAddresses) {
        // Filter out tokens we're already tracking
        const newTokens = tokenAddresses.filter(address => !this.trackedTokens.has(address));
        
        if (newTokens.length === 0) {
            console.log('ℹ️  All provided tokens are already being tracked');
            return;
        }
        
        const payload = {
            method: "subscribeTokenTrade",
            keys: newTokens
        };
        
        console.log(`📊 Subscribing to trades for ${newTokens.length} new token(s):`);
        newTokens.forEach((address, index) => {
            console.log(`  ${index + 1}. ${address}`);
            this.trackedTokens.add(address);
        });
        
        this.ws.send(JSON.stringify(payload));
        console.log(`✅ Successfully subscribed to ${newTokens.length} token(s). Total tracked: ${this.trackedTokens.size}`);
        
        // Set up activity tracking and auto-unsubscribe timers for new tokens
        newTokens.forEach(tokenAddress => {
            this.setupTokenActivityTracking(tokenAddress);
        });
        
        // Log the subscription payload for debugging
        if (this.debugMode) {
            console.log('📤 Subscription payload sent:', JSON.stringify(payload, null, 2));
        }
    }

    subscribeToAccountTrades(accountAddresses) {
        const payload = {
            method: "subscribeAccountTrade",
            keys: accountAddresses
        };
        
        console.log(`👤 Subscribing to trades for ${accountAddresses.length} account(s):`);
        accountAddresses.forEach((address, index) => {
            console.log(`  ${index + 1}. ${address}`);
            this.trackedAccounts.add(address);
        });
        
        this.ws.send(JSON.stringify(payload));
    }

    setupTokenActivityTracking(tokenAddress) {
        // Record the current time as the last activity
        this.tokenActivityTimers.set(tokenAddress, Date.now());
        
        // Set up a timer to check for inactivity
        const checkInactivity = () => {
            const lastActivity = this.tokenActivityTimers.get(tokenAddress);
            const now = Date.now();
            
            if (lastActivity && (now - lastActivity) >= this.inactiveTimeout) {
                console.log(`⏰ Token ${tokenAddress} has been inactive for 3+ minutes. Unsubscribing...`);
                this.unsubscribeFromTokenTrades([tokenAddress]);
            } else if (this.trackedTokens.has(tokenAddress)) {
                // Continue checking every 30 seconds
                setTimeout(checkInactivity, 30000);
            }
        };
        
        // Start the inactivity check
        setTimeout(checkInactivity, this.inactiveTimeout);
    }

    updateTokenActivity(tokenAddress) {
        // Update the last activity time for a token
        if (this.trackedTokens.has(tokenAddress)) {
            this.tokenActivityTimers.set(tokenAddress, Date.now());
        }
    }

    unsubscribeFromTokenTrades(tokenAddresses) {
        const payload = {
            method: "unsubscribeTokenTrade",
            keys: tokenAddresses
        };
        
        console.log(`📤 Unsubscribing from ${tokenAddresses.length} token(s):`);
        tokenAddresses.forEach((address, index) => {
            console.log(`  ${index + 1}. ${address}`);
            this.trackedTokens.delete(address);
            this.tokenActivityTimers.delete(address);
        });
        
        this.ws.send(JSON.stringify(payload));
        console.log(`✅ Successfully unsubscribed from ${tokenAddresses.length} token(s). Total tracked: ${this.trackedTokens.size}`);
        
        // Log the unsubscription payload for debugging
        if (this.debugMode) {
            console.log('📤 Unsubscription payload sent:', JSON.stringify(payload, null, 2));
        }
    }

    unsubscribeFromAllTokens() {
        if (this.trackedTokens.size === 0) {
            console.log('ℹ️  No tokens to unsubscribe from');
            return;
        }

        const tokenAddresses = Array.from(this.trackedTokens);
        const payload = {
            method: "unsubscribeTokenTrade",
            keys: tokenAddresses
        };
        
        console.log(`📤 Unsubscribing from all ${tokenAddresses.length} tracked token(s)...`);
        tokenAddresses.forEach((address, index) => {
            console.log(`  ${index + 1}. ${address}`);
        });
        
        this.ws.send(JSON.stringify(payload));
        this.trackedTokens.clear();
        this.tokenActivityTimers.clear();
        console.log(`✅ Successfully unsubscribed from all tokens`);
        
        // Log the unsubscription payload for debugging
        if (this.debugMode) {
            console.log('📤 Unsubscription payload sent:', JSON.stringify(payload, null, 2));
        }
    }

    unsubscribeFromAllAccounts() {
        if (this.trackedAccounts.size === 0) {
            console.log('ℹ️  No accounts to unsubscribe from');
            return;
        }

        const accountAddresses = Array.from(this.trackedAccounts);
        const payload = {
            method: "unsubscribeAccountTrade",
            keys: accountAddresses
        };
        
        console.log(`📤 Unsubscribing from all ${accountAddresses.length} tracked account(s)...`);
        accountAddresses.forEach((address, index) => {
            console.log(`  ${index + 1}. ${address}`);
        });
        
        this.ws.send(JSON.stringify(payload));
        this.trackedAccounts.clear();
        console.log(`✅ Successfully unsubscribed from all accounts`);
        
        // Log the unsubscription payload for debugging
        if (this.debugMode) {
            console.log('📤 Unsubscription payload sent:', JSON.stringify(payload, null, 2));
        }
    }

    handleMessage(data) {
        try {
            const message = JSON.parse(data.toString());
            
            // Extract and save all traderPublicKey values from the message
            this.extractAndSaveTraderPublicKeys(message);
            
            // Debug mode: log all messages
            if (this.debugMode) {
                console.log('\n🔍 DEBUG - Raw message received:');
                console.log(JSON.stringify(message, null, 2));
            }
            
            // Handle different message types
            if (message.method === 'subscribeNewToken') {
                this.handleNewToken(message);
            }
            else if (message.method === 'subscribeMigration') {
                this.handleMigration(message);
            }
            else if (message.method === 'subscribeTokenTrade') {
                this.handleTokenTrade(message);
            }
            else if (message.method === 'subscribeAccountTrade') {
                this.handleAccountTrade(message);
            }
            // Handle actual trade data messages (these don't have a method field)
            else if (this.isTokenTradeMessage(message)) {
                this.handleTokenTrade(message);
            }
            else if (this.isAccountTradeMessage(message)) {
                this.handleAccountTrade(message);
            }
            else if (this.isNewTokenMessage(message)) {
                this.handleNewToken(message);
            }
            else if (this.isMigrationMessage(message)) {
                this.handleMigration(message);
            }
            else {
                console.log('\n📨 UNHANDLED MESSAGE TYPE');
                console.log('-'.repeat(40));
                console.log('Timestamp:', new Date().toISOString());
                console.log('Message Type:', message.method || 'Unknown');
                console.log('Message ID:', message.id || 'No ID');
                
                // Try to extract any useful information
                if (message.data) {
                    console.log('Data Keys:', Object.keys(message.data).join(', '));
                }
                if (message.result) {
                    console.log('Result Keys:', Object.keys(message.result).join(', '));
                }
                
                if (this.debugMode) {
                    console.log('\n🔍 DEBUG - Full Message:');
                    console.log(JSON.stringify(message, null, 2));
                } else {
                    console.log('(Use "d" to enable debug mode for full message details)');
                }
                console.log('-'.repeat(40));
            }
        } catch (error) {
            console.error('❌ Error parsing message:', error);
            console.log('Raw message:', data.toString());
        }
    }

    // Helper methods to identify message types
    isTokenTradeMessage(message) {
        // Check if this looks like a token trade message
        return (message.token || message.mint) && 
               (message.type || message.side || message.amount || message.price || message.trader);
    }

    isAccountTradeMessage(message) {
        // Check if this looks like an account trade message
        return (message.account || message.user) && 
               (message.token || message.mint) && 
               (message.type || message.side || message.amount);
    }

    isNewTokenMessage(message) {
        // Check if this looks like a new token creation message
        return (message.token || message.mint) && 
               (message.name || message.symbol || message.description || message.creator);
    }

    isMigrationMessage(message) {
        // Check if this looks like a migration message
        return message.migration || message.fromToken || message.toToken;
    }

    handleNewToken(message) {
        console.log('\n🆕 NEW TOKEN CREATED!');
        console.log('='.repeat(60));
        console.log('Timestamp:', new Date().toISOString());
        
        // Display formatted information instead of raw JSON
        const tokenInfo = message.data || message.result || message;
        console.log('Token Name:', tokenInfo.name || 'Unknown');
        console.log('Token Symbol:', tokenInfo.symbol || 'Unknown');
        console.log('Token Address:', tokenInfo.token || tokenInfo.mint || tokenInfo.address || 'Unknown');
        console.log('Creator:', tokenInfo.creator || tokenInfo.traderPublicKey || 'Unknown');
        console.log('Description:', tokenInfo.description || 'No description');
        
        if (this.debugMode) {
            console.log('\n🔍 DEBUG - Full Message:');
            console.log(JSON.stringify(message, null, 2));
        }
        console.log('='.repeat(60));
        
        // Extract token address from the message if available (try multiple possible fields)
        const tokenAddress = message.token || 
                           message.data?.token || 
                           message.result?.token || 
                           message.mint || 
                           message.address ||
                           message.tokenAddress ||
                           message.contractAddress;
        
        // Extract trader public key from the message
        const traderPublicKey = message.traderPublicKey || 
                               message.data?.traderPublicKey || 
                               message.result?.traderPublicKey ||
                               message.trader ||
                               message.user ||
                               message.creator;
        
        // Save trader public key to wallets.txt if available
        if (traderPublicKey && traderPublicKey !== 'Unknown') {
            console.log(`👤 Detected trader: ${traderPublicKey}`);
            this.saveTraderWalletToFile(traderPublicKey);
        }
        
        // Also check for traderPublicKey in the message data
        const messageTraderPublicKey = message.traderPublicKey || message.data?.traderPublicKey || message.result?.traderPublicKey;
        if (messageTraderPublicKey && messageTraderPublicKey !== 'Unknown' && messageTraderPublicKey !== traderPublicKey) {
            console.log(`🔑 Detected additional trader public key: ${messageTraderPublicKey}`);
            this.saveTraderWalletToFile(messageTraderPublicKey);
        }
        
        if (tokenAddress) {
            console.log(`🔍 Detected new token: ${tokenAddress}`);
            
            // Check if we're not already tracking this token
            if (!this.trackedTokens.has(tokenAddress)) {
                console.log(`📊 Auto-subscribing to trades for new token: ${tokenAddress}`);
                this.subscribeToTokenTrades([tokenAddress]);
            } else {
                console.log(`ℹ️  Already tracking trades for token: ${tokenAddress}`);
            }
        } else {
            console.log('⚠️  Could not extract token address from new token message');
            console.log('Available fields:', Object.keys(message));
            
            // Try to find any field that looks like a token address (44 characters, base58-like)
            const possibleAddresses = Object.values(message).filter(value => 
                typeof value === 'string' && 
                value.length >= 32 && 
                value.length <= 44 &&
                /^[A-Za-z0-9]+$/.test(value)
            );
            
            if (possibleAddresses.length > 0) {
                console.log('🔍 Found possible token addresses:', possibleAddresses);
                // Try the first one that looks like a token address
                const possibleToken = possibleAddresses[0];
                console.log(`📊 Attempting to subscribe to possible token: ${possibleToken}`);
                this.subscribeToTokenTrades([possibleToken]);
            }
        }
    }

    handleMigration(message) {
        console.log('\n🔄 MIGRATION EVENT!');
        console.log('-'.repeat(40));
        console.log('Timestamp:', new Date().toISOString());
        
        // Display formatted information instead of raw JSON
        const migrationInfo = message.data || message.result || message;
        console.log('From Token:', migrationInfo.fromToken || migrationInfo.oldToken || 'Unknown');
        console.log('To Token:', migrationInfo.toToken || migrationInfo.newToken || 'Unknown');
        console.log('Migration Type:', migrationInfo.migrationType || 'Unknown');
        console.log('Amount:', migrationInfo.amount || 'Unknown');
        console.log('Trader:', migrationInfo.trader || migrationInfo.traderPublicKey || 'Unknown');
        
        // Save trader public key to wallets.txt if available
        const migrationTrader = migrationInfo.trader || migrationInfo.traderPublicKey || message.traderPublicKey;
        if (migrationTrader && migrationTrader !== 'Unknown') {
            console.log(`🔑 Detected trader in migration: ${migrationTrader}`);
            this.saveTraderWalletToFile(migrationTrader);
        }
        
        if (this.debugMode) {
            console.log('\n🔍 DEBUG - Full Message:');
            console.log(JSON.stringify(message, null, 2));
        }
        console.log('-'.repeat(40));
    }

    handleTokenTrade(message) {
        console.log('\n💰 TOKEN TRADE DETECTED!');
        console.log('-'.repeat(40));
        console.log('Timestamp:', new Date().toISOString());
        
        // Extract key information from the trade
        const tradeData = message.data || message.result || message;
        const tokenAddress = tradeData.token || tradeData.mint || message.token || message.mint;
        const traderAddress = tradeData.trader || 
                             tradeData.user || 
                             tradeData.traderPublicKey ||
                             message.trader || 
                             message.user || 
                             message.traderPublicKey;
        
        if (tradeData) {
            console.log('Token Address:', tokenAddress || 'Unknown');
            console.log('Trader:', traderAddress || 'Unknown');
            console.log('Type:', tradeData.type || tradeData.side || 'Unknown');
            console.log('Amount:', tradeData.amount || tradeData.tokenAmount || 'Unknown');
            console.log('Price:', tradeData.price || tradeData.solAmount || 'Unknown');
            console.log('Market Cap:', tradeData.marketCap || 'Unknown');
        }
        
        // Save trader wallet address to wallets.txt if available
        if (traderAddress && traderAddress !== 'Unknown') {
            console.log(`👤 Detected trader in trade: ${traderAddress}`);
            this.saveTraderWalletToFile(traderAddress);
        }
        
        // Also save traderPublicKey if it's different from traderAddress
        const traderPublicKey = tradeData.traderPublicKey || message.traderPublicKey;
        if (traderPublicKey && traderPublicKey !== 'Unknown' && traderPublicKey !== traderAddress) {
            console.log(`🔑 Detected trader public key: ${traderPublicKey}`);
            this.saveTraderWalletToFile(traderPublicKey);
        }
        
        // Update activity timer for this token
        if (tokenAddress) {
            this.updateTokenActivity(tokenAddress);
        }
        
        if (this.debugMode) {
            console.log('\n🔍 DEBUG - Full Message:');
            console.log(JSON.stringify(message, null, 2));
        }
        console.log('-'.repeat(40));
    }

    handleAccountTrade(message) {
        console.log('\n👤 ACCOUNT TRADE DETECTED!');
        console.log('-'.repeat(40));
        console.log('Timestamp:', new Date().toISOString());
        
        // Extract key information from the trade
        const tradeData = message.data || message.result || message;
        const accountAddress = tradeData.account || tradeData.user || message.account || message.user;
        
        if (tradeData) {
            console.log('Account:', accountAddress || 'Unknown');
            console.log('Token:', tradeData.token || tradeData.mint || 'Unknown');
            console.log('Type:', tradeData.type || tradeData.side || 'Unknown');
            console.log('Amount:', tradeData.amount || tradeData.tokenAmount || 'Unknown');
            console.log('Price:', tradeData.price || tradeData.solAmount || 'Unknown');
        }
        
        // Save account wallet address to wallets.txt if available
        if (accountAddress && accountAddress !== 'Unknown') {
            this.saveTraderWalletToFile(accountAddress);
        }
        
        // Also save traderPublicKey if available and different from accountAddress
        const traderPublicKey = tradeData.traderPublicKey || message.traderPublicKey;
        if (traderPublicKey && traderPublicKey !== 'Unknown' && traderPublicKey !== accountAddress) {
            console.log(`🔑 Detected trader public key in account trade: ${traderPublicKey}`);
            this.saveTraderWalletToFile(traderPublicKey);
        }
        
        if (this.debugMode) {
            console.log('\n🔍 DEBUG - Full Message:');
            console.log(JSON.stringify(message, null, 2));
        }
        console.log('-'.repeat(40));
    }

    showStatus() {
        console.log('\n📊 MONITOR STATUS');
        console.log('='.repeat(50));
        console.log('Connection Status:', this.isRunning ? '🟢 Connected' : '🔴 Disconnected');
        console.log('Connection Attempts:', this.connectionAttempts);
        console.log('Tracked Tokens:', this.trackedTokens.size);
        console.log('Tracked Accounts:', this.trackedAccounts.size);
        console.log('Auto-Subscribe:', '🟢 Enabled (new tokens auto-tracked)');
        console.log('Auto-Unsubscribe:', '🟢 Enabled (3 min inactivity timeout)');
        console.log('Debug Mode:', this.debugMode ? '🟢 Enabled' : '🔴 Disabled');
        
        if (this.trackedTokens.size > 0) {
            console.log('\nTracked Token Addresses:');
            Array.from(this.trackedTokens).forEach((token, index) => {
                console.log(`  ${index + 1}. ${token}`);
            });
        }
        
        if (this.trackedAccounts.size > 0) {
            console.log('\nTracked Account Addresses:');
            Array.from(this.trackedAccounts).forEach((account, index) => {
                console.log(`  ${index + 1}. ${account}`);
            });
        }
        
        console.log('='.repeat(50));
        this.showHelp();
    }

    toggleDebugMode() {
        this.debugMode = !this.debugMode;
        console.log(`\n🔍 Debug mode: ${this.debugMode ? '🟢 ENABLED' : '🔴 DISABLED'}`);
        if (this.debugMode) {
            console.log('   Full JSON messages will be shown for all events');
        } else {
            console.log('   Only formatted information will be shown (no raw JSON)');
        }
    }

    cleanupInactiveTokens() {
        const now = Date.now();
        const inactiveTokens = [];
        
        this.tokenActivityTimers.forEach((lastActivity, tokenAddress) => {
            if ((now - lastActivity) >= this.inactiveTimeout) {
                inactiveTokens.push(tokenAddress);
            }
        });
        
        if (inactiveTokens.length > 0) {
            console.log(`\n🧹 Found ${inactiveTokens.length} inactive token(s). Unsubscribing...`);
            this.unsubscribeFromTokenTrades(inactiveTokens);
        } else {
            console.log('\n✅ All tracked tokens are active (no inactive tokens found)');
        }
    }

    showHelp() {
        console.log('\n🎮 CONTROLS:');
        console.log('  Press "q" to quit');
        console.log('  Press "s" to show status');
        console.log('  Press "r" to reconnect');
        console.log('  Press "d" to toggle debug mode');
        console.log('  Press "u" to manually cleanup inactive tokens');
        console.log('  Press "h" to show this help');
        console.log('');
    }

    reconnect() {
        if (this.ws) {
            this.ws.close();
        }
        this.connectionAttempts = 0;
        this.connect().catch(console.error);
    }

    stop() {
        this.isRunning = false;
        
        // Unsubscribe from all tokens and accounts before closing
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            console.log('\n🛑 Unsubscribing from all active subscriptions...');
            this.unsubscribeFromAllTokens();
            this.unsubscribeFromAllAccounts();
            
            // Give a small delay to ensure unsubscribe messages are sent
            setTimeout(() => {
                if (this.ws) {
                    this.ws.close();
                }
                
                if (process.stdin.isTTY) {
                    process.stdin.setRawMode(false);
                }
                
                this.rl.close();
                process.exit(0);
            }, 100);
        } else {
            // If WebSocket is not open, just clean up and exit
            if (this.ws) {
                this.ws.close();
            }
            
            if (process.stdin.isTTY) {
                process.stdin.setRawMode(false);
            }
            
            this.rl.close();
            process.exit(0);
        }
    }

    async start() {
        try {
            console.log('🚀 Starting Coin Transaction Monitor...');
            console.log('Using Pump Portal API for real-time monitoring');
            console.log('✨ Auto-subscription enabled: New tokens will be automatically tracked');
            console.log('⏰ Auto-unsubscribe enabled: Inactive tokens (3+ min) will be automatically removed');
            console.log('');
            
            // Show initial help
            this.showHelp();
            
            await this.connect();
            
            // Keep the process running
            const keepAlive = setInterval(() => {
                if (!this.isRunning) {
                    clearInterval(keepAlive);
                }
            }, 1000);
            
        } catch (error) {
            console.error('❌ Failed to start monitor:', error);
            this.stop();
        }
    }
}

// Handle process termination gracefully
process.on('SIGINT', () => {
    console.log('\n🛑 Received SIGINT, shutting down gracefully...');
    process.exit(0);
});

process.on('SIGTERM', () => {
    console.log('\n🛑 Received SIGTERM, shutting down gracefully...');
    process.exit(0);
});

// Start the monitor
const monitor = new CoinTransactionMonitor();
monitor.start();

#!/bin/bash

echo "========================================"
echo "   Dragon Automated Cycle Monitor"
echo "========================================"
echo

# Function to count lines in wallets.txt
count_wallets() {
    if [ -f "Dragon/data/Solana/BulkWallet/wallets.txt" ]; then
        wc -l < "Dragon/data/Solana/BulkWallet/wallets.txt"
    else
        echo 0
    fi
}

# Function to start coin monitor
start_coin_monitor() {
    echo "[INFO] Starting Coin Transaction Monitor..."
    node coin-transaction-monitor.js &
    COIN_PID=$!
    echo "[INFO] Coin monitor started with PID: $COIN_PID"
}

# Function to stop coin monitor
stop_coin_monitor() {
    if [ ! -z "$COIN_PID" ]; then
        echo "[INFO] Stopping coin monitor (PID: $COIN_PID)..."
        kill $COIN_PID 2>/dev/null
        wait $COIN_PID 2>/dev/null
    fi
    # Also kill any remaining node processes
    pkill -f "coin-transaction-monitor.js" 2>/dev/null
}

# Function to run Dragon with automated input
run_dragon() {
    echo "[INFO] Starting Dragon Wallet Checker"
    echo "[INFO] Automated sequence: 1 -> 2 -> 2 -> 7 -> n -> n -> 10"
    echo
    
    # Create input file for automated Dragon interaction
    cat > dragon_input.txt << EOF
1
2
2
7
n
n
10
EOF
    
    # Run Dragon with automated input
    python dragon.py < dragon_input.txt
    
    # Clean up input file
    rm -f dragon_input.txt
}

# Main cycle function
start_cycle() {
    echo "[INFO] Starting new cycle..."
    echo "[INFO] Step 1: Starting Coin Transaction Monitor"
    echo
    
    # Clear wallets.txt to start fresh
    echo "" > "Dragon/data/Solana/BulkWallet/wallets.txt"
    
    # Start coin monitor
    start_coin_monitor
    
    echo "[INFO] Monitoring wallets.txt for 4000 lines..."
    echo "[INFO] Current wallet count: 0"
    
    # Monitor wallets
    while true; do
        WALLET_COUNT=$(count_wallets)
        
        # Display progress every 100 wallets
        if [ $((WALLET_COUNT % 100)) -eq 0 ] && [ $WALLET_COUNT -gt 0 ]; then
            echo "[INFO] Current wallet count: $WALLET_COUNT / 40"
        fi
        
        # Check if we have reached 4000 wallets
        if [ $WALLET_COUNT -ge 40 ]; then
            echo "[INFO] Target reached! Stopping coin monitor and starting Dragon..."
            echo
            
            # Stop coin monitor
            stop_coin_monitor
            
            # Wait a moment
            sleep 3
            
            # Run Dragon
            run_dragon
            
            echo
            echo "[INFO] Dragon cycle completed. Restarting in 5 seconds..."
            sleep 5
            
            echo "[INFO] Starting new cycle..."
            echo
            return 0
        else
            # Wait 10 seconds before checking again
            sleep 10
        fi
    done
}

# Trap to handle Ctrl+C gracefully
cleanup() {
    echo
    echo "[INFO] Received interrupt signal. Cleaning up..."
    stop_coin_monitor
    rm -f dragon_input.txt
    echo "[INFO] Cleanup completed. Exiting."
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Main execution loop
while true; do
    start_cycle
done

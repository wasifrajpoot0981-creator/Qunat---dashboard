import math
import numpy as np
import logging
import time
import sys

# Logging configuration for Colab output forcing flush
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s - %(levelname)s: %(message)s")
log = logging.getLogger("BitnodesColabBot")

class BitnodesColabTradingBot:
    def __init__(self):
        log.info("Bitnodes Colab Bot initialized successfully.")
        self.coins = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]

    def calculate_pix(self, indices_sum):
        pix_score = (indices_sum / 14.0) * 10.0
        return max(0.0, min(10.0, pix_score))

    def calculate_nmi(self, current_nodes, historical_nodes_list):
        if len(historical_nodes_list) < 20:
            sma_20 = np.mean(historical_nodes_list) if historical_nodes_list else current_nodes
        else:
            sma_20 = np.mean(historical_nodes_list[-20:])
        if sma_20 == 0:
            return 0.0
        return ((current_nodes - sma_20) / sma_20) * 100

    def calculate_pdm(self, tor_nodes, ipv6_nodes, ipv4_nodes):
        if ipv4_nodes == 0:
            return 0.0
        return (tor_nodes + ipv6_nodes) / ipv4_nodes

    def run_market_prediction_cycle(self):
        log.info("==================================================")
        log.info("🔄 Running 5-Minute Bitnodes Prediction Scan...")
        
        current_nodes = 15350
        node_history = [15000 + i*12 for i in range(25)]
        tor_nodes = 2200
        ipv6_nodes = 4650
        ipv4_nodes = 8500
        peer_sum = 9.5
        
        pix_val = self.calculate_pix(peer_sum)
        nmi_val = self.calculate_nmi(current_nodes, node_history)
        pdm_val = self.calculate_pdm(tor_nodes, ipv6_nodes, ipv4_nodes)
        
        if nmi_val > 0 and pdm_val > 0.15 and pix_val > 6.0:
            signal = "LONG 🟢 (Bullish Network Health & Whale Accumulation)"
        else:
            signal = "SHORT 🔴 (Network Contraction / Distribution)"
            
        log.info(f"📊 Metrics -> PIX: {pix_val:.2f} | NMI: {nmi_val:.2f}% | PDM: {pdm_val:.4f}")
        log.info("--------------------------------------------------")
        log.info("🎯 5-MINUTE COIN PREDICTIONS:")
        for coin in self.coins:
            log.info(f"   -> Coin: {coin:<10} | Prediction: {signal}")
        log.info("==================================================\n")
        sys.stdout.flush()

if __name__ == "__main__":
    bot = BitnodesColabTradingBot()
    
    # Pehli dafa foran run hoga bina wait kiye
    bot.run_market_prediction_cycle()
    
    # Phir har 5 minute baad chalega
    try:
        while True:
            log.info("Waiting for the next 5-minute interval... (Sleeping for 300 seconds)")
            sys.stdout.flush()
            time.sleep(300)
            bot.run_market_prediction_cycle()
    except KeyboardInterrupt:
        log.info("Bot execution stopped by user.")

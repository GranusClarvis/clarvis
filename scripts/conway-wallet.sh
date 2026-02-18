#!/bin/bash
# Conway Wallet CLI — Thin wrapper for Clarvis
# Usage: conway-wallet.sh [balance|info|credits|status]

CMD="${1:-status}"
AUTOMATON_DIR="$HOME/projects/automaton"

case "$CMD" in
  balance)
    cd "$AUTOMATON_DIR" && node --input-type=module -e "
      import { getUsdcBalance } from './dist/conway/x402.js';
      const b = await getUsdcBalance('0x3f788Cf3c685996Dd07B8C04590FB7EeadbBFcAB');
      console.log('USDC Balance: ' + b.toFixed(6) + ' USDC');
      console.log('Network: Base (eip155:8453)');
      console.log('Wallet: 0x3f788Cf3c685996Dd07B8C04590FB7EeadbBFcAB');
    "
    ;;
  info)
    cat ~/.automaton/automaton.json | node -e "
      const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8'));
      console.log('Wallet:  ' + d.walletAddress);
      console.log('Name:    ' + d.name);
      console.log('Creator: ' + d.creatorAddress);
      console.log('API:     ' + d.conwayApiUrl);
      console.log('Model:   ' + d.inferenceModel);
      console.log('Version: ' + d.version);
    "
    ;;
  credits)
    cd "$AUTOMATON_DIR" && node --input-type=module -e "
      import { getUsdcBalance } from './dist/conway/x402.js';
      const b = await getUsdcBalance('0x3f788Cf3c685996Dd07B8C04590FB7EeadbBFcAB');
      console.log('USDC:    ' + b.toFixed(6) + ' USDC on Base');
    "
    ;;
  status)
    cd "$AUTOMATON_DIR" && node --input-type=module -e "
      import { getUsdcBalance } from './dist/conway/x402.js';
      const b = await getUsdcBalance('0x3f788Cf3c685996Dd07B8C04590FB7EeadbBFcAB');
      const tier = b >= 5 ? 'normal' : b >= 1 ? 'low_compute' : b > 0 ? 'critical' : 'dead';
      console.log('=== CLARVIS FINANCIAL STATUS ===');
      console.log('Wallet:     0x3f788Cf3c685996Dd07B8C04590FB7EeadbBFcAB');
      console.log('USDC:       ' + b.toFixed(6) + ' USDC on Base');
      console.log('Network:    Base Mainnet');
      console.log('Tier:       ' + tier);
      console.log('================================');
    "
    ;;
  *)
    echo "Usage: conway-wallet.sh [balance|info|credits|status]"
    ;;
esac

# Crypto Alerts Service

## How It Works

1. **Add alert:** User sends `/watch bitcoin 50000 above` to Telegram bot
2. **Store:** Alert saved to `alerts.json`
3. **Check:** Cron runs `price_checker.py` every 5 minutes
4. **Alert:** If price crosses threshold, sends Telegram

- `/watch  message

## Commands<coin> <price> <above|below>` - Add alert
- `/unwatch <coin>` - Remove all alerts for coin
- `/list` - Show active alerts

## Setup

```bash
# Add to crontab
*/5 * * * * /home/agent/.openclaw/workspace/services/crypto-alerts/price_checker.py
```

## Files

- `price_checker.py` - Main checker script
- `alerts.json` - Alert storage
- `check.log` - Check log

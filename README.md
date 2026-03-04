# cTrader Monitor for Home Assistant

A Home Assistant custom integration for monitoring your cTrader trading account. View-only extension that displays:

- **Current Balance** - Your account balance
- **Equity** - Current account equity
- **Margin Used** - Current margin usage
- **Open Trades** - Count of currently open positions
- **Closed Trades** - Recent closed trades summary

## Features

✅ **View-only monitoring** - No trading capability, read-only data access
✅ **Secure credential input** - Credentials entered through Home Assistant UI, never hardcoded
✅ **Real-time updates** - Fetches data from cTrader API every minute
✅ **HACS compatible** - Easy installation through Home Assistant Community Store

## Installation

### Via HACS (Recommended)

1. Open Home Assistant
2. Go to **Settings → Devices & Services → HACS**
3. Click **Explore & Download Repositories**
4. Search for **cTrader Monitor**
5. Click **Install**
6. Restart Home Assistant

### Manual Installation

1. Download this repository
2. Copy the `custom_components/ctrader_monitor` folder to your Home Assistant `custom_components` directory
3. Restart Home Assistant

## Setup

1. Go to **Settings → Devices & Services → Create Automation**
2. Click **Create Integration**
3. Search for **cTrader Monitor**
4. Enter your:
   - **Access Token** - Get from cTrader OpenAPI portal
   - **Account ID** - Your cTrader account number

## Getting Your Credentials

### Step 1: Register & Approve App

1. Go to [cTrader OpenAPI Portal](https://openapi.ctrader.com)
2. **Create Application:**
   - Name: "Home Assistant cTrader Monitor"
   - Permissions: Read-only (`accounts` scope)
   - Redirect URI: `http://localhost:8123/auth/callback`
3. **Submit for Spotware approval** (24-48 hours)

### Step 2: Get App Credentials

Once approved, grab your:
- **Client ID**
- **Client Secret**

### Step 3: Add to Home Assistant

1. Go to **Settings → Devices & Services**
2. Click **Create Integration**
3. Search for **cTrader Monitor**
4. Enter your app credentials:
   - **Client ID** (from app portal)
   - **Client Secret** (from app portal)
   - **Account ID** (your cTID account number)
5. Click **Submit**

### Step 4: Authorize Account (Automatic!)

The integration will:
1. **Generate an authorization link** for you
2. **Show it in setup** — click it or copy the URL
3. **You'll log in** with your cTID and approve access
4. **You'll be redirected** with an authorization code
5. **Paste the code** back into Home Assistant setup

The integration **automatically exchanges the code for access + refresh tokens** — no manual REST calls needed! 🎯

### Automatic Token Refresh ✅

- ✅ Tokens obtained automatically from auth code
- ✅ Token expiry monitored (tokens last ~30 days)
- ✅ Automatically refreshes 5 minutes before expiry
- ✅ New tokens stored in Home Assistant
- ✅ Infinite renewal (refresh token never expires)

**Security:** All tokens/credentials stored securely in Home Assistant config.

## Sensors

The integration creates the following sensors:

- `sensor.ctrader_balance` - Account balance
- `sensor.ctrader_equity` - Account equity
- `sensor.ctrader_margin_used` - Margin currently in use
- `sensor.ctrader_open_trades` - Number of open positions
- `sensor.ctrader_recent_closed_trades` - Recent closed trades info

## Usage Examples

### Account Summary Card

```yaml
type: entities
title: 💰 Account Summary
entities:
  - sensor.ctrader_balance
  - sensor.ctrader_equity
  - sensor.ctrader_margin_used
  - sensor.ctrader_open_trades
```

### Open Trades Card with Profit

```yaml
type: markdown
title: 📈 Open Trades
content: >
  {% set trades = state_attr('sensor.ctrader_open_trades', 'open_trades') %}
  {% if trades and trades | length > 0 %}
  {% for t in trades %}
  **{{ t.symbol }}** | {{ t.side }} | {{ "%.4f" % t.volume }} lots
  {% if t.unrealized_profit is not none %}
    | {{ '🟢' if t.unrealized_profit >= 0 else '🔴' }} **${{ "%.2f" % t.unrealized_profit }}**
  {% endif %}<br>
  📍 Entry: `{{ "%.5f" % t.entry_price }}`
  {% if t.current_price %} | Current: `{{ "%.5f" % t.current_price }}`{% endif %}<br>
  {% if t.stop_loss or t.take_profit %}
  🛑 SL: {% if t.stop_loss %}`{{ t.stop_loss }}`{% else %}-{% endif %} | 🎯 TP: {% if t.take_profit %}`{{ t.take_profit }}`{% else %}-{% endif %}<br>
  {% endif %}
  <br>
  {% endfor %}
  {% else %}
  ✅ No open positions
  {% endif %}
```

**Formula:** `profit = (current_price - entry_price) × volume_lots × 1,000,000`
- For BUY: profit if current > entry
- For SELL: profit if entry > current

**Example:** EURUSD BUY 0.01 lots, entry 1.16433, current 1.16429
- Profit = (1.16429 - 1.16433) × 0.01 × 1,000,000 = **-$0.40**

### Recent Closed Trades Card

```yaml
type: markdown
title: 📉 Recent Closed Trades
content: >
  {% set trades = state_attr('sensor.ctrader_recent_closed_trades', 'last_closed_trades') %}
  {% if trades and trades | length > 0 %}
  {% for t in trades %}
  **{{ t.symbol }}** · {{ t.side }} · {{ t.volume }} lots<br>
  {% if t.profit is not none %}{{ '🟢' if t.profit >= 0 else '🔴' }} **{{ t.profit }}**<br>{% endif %}
  🕐 {{ (t.close_timestamp / 1000) | timestamp_local | truncate(16, true, '') }}
  <br><br>
  {% endfor %}
  {% else %}
  No recent closed trades 🟢
  {% endif %}
```

### Alert on Low Balance

```yaml
automation:
  - alias: "Alert Low Balance"
    trigger:
      platform: numeric_state
      entity_id: sensor.ctrader_balance
      below: 1000
    action:
      service: notify.notify
      data:
        message: "cTrader balance is below $1000"
```

## Requirements

- Home Assistant 2024.1.0 or later
- Python 3.11 or later
- Valid cTrader API access token with read permissions

## Troubleshooting

### Authentication Failed
- Verify your access token is correct
- Check that token has not expired
- Ensure token has read permissions enabled

### No Data Showing
- Wait 1-2 minutes for first data fetch
- Check Home Assistant logs for errors
- Verify internet connection to cTrader API

### Integration Not Installing
- Ensure HACS is properly installed
- Try clearing browser cache
- Restart Home Assistant

## Support

For issues, feature requests, or contributions:
- GitHub Issues: [max246/hacs-ctrader](https://github.com/max246/hacs-ctrader/issues)

## License

MIT License - See LICENSE file for details

## Disclaimer

This integration is provided as-is for monitoring purposes only. It does not execute any trades. Always verify account status through your official cTrader platform.

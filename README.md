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

Follow the [official cTrader Open API app creation guide](https://help.ctrader.com/open-api/creating-new-app/):

### Step 1: Define Your Application

1. Go to [cTrader OpenAPI Portal](https://openapi.ctrader.com)
2. Create a new application with:
   - **Name:** "Home Assistant cTrader Monitor" (or your choice)
   - **Purpose:** Home automation monitoring of trading account
   - **Permissions:** Read-only access to account data
   - **Redirect URL:** `http://localhost:8123/auth/callback` (for local HA setup)

### Step 2: Submit for Approval

1. Fill in detailed description of how you'll use the integration
2. Specify read-only permissions for:
   - Account balance & equity
   - Open positions
   - Closed trades history
3. Submit for Spotware approval
4. Wait for approval (typically 24-48 hours)

### Step 3: Get Your Credentials

Once approved, you'll receive:

- **Client ID**
- **Client Secret**
- **Access Token** (or ability to generate one)

### Step 4: Find Your Account ID

1. Log into your cTrader platform
2. Go to **Account Settings**
3. Note your account number (e.g., `9882835`)

### Step 5: Configure in Home Assistant

1. In Home Assistant: **Settings → Devices & Services**
2. Search for **cTrader Monitor**
3. Enter:
   - **Access Token** (from cTrader portal)
   - **Account ID** (your account number)

**Security Note:** Keep your access token private. Treat it like a password — it grants read access to your account data.

## Sensors

The integration creates the following sensors:

- `sensor.ctrader_balance` - Account balance
- `sensor.ctrader_equity` - Account equity
- `sensor.ctrader_margin_used` - Margin currently in use
- `sensor.ctrader_open_trades` - Number of open positions
- `sensor.ctrader_recent_closed_trades` - Recent closed trades info

## Usage Examples

### Display in Home Assistant Dashboard

```yaml
type: entities
entities:
  - entity_id: sensor.ctrader_balance
  - entity_id: sensor.ctrader_equity
  - entity_id: sensor.ctrader_margin_used
  - entity_id: sensor.ctrader_open_trades
```

### Create Automations

Example: Send notification if balance drops below certain level

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

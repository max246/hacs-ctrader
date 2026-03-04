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

Follow these steps to set up authentication:

### Step 1: Create Application (Portal)

1. Go to [cTrader OpenAPI Portal](https://openapi.ctrader.com)
2. Create new application:
   - **Name:** "Home Assistant cTrader Monitor"
   - **Permissions:** Read-only (`accounts` scope)
   - **Redirect URI:** `http://localhost:8123/auth/callback`
3. Submit for Spotware approval (24-48 hours)

### Step 2: Get App Credentials

Once approved, grab your:
- **Client ID**
- **Client Secret**

### Step 3: Authenticate Your Account

Follow the [official OAuth 2.0 authentication flow](https://help.ctrader.com/open-api/account-authentication/#authentication-flow):

1. Open this authorization URI in your browser:
```
https://id.ctrader.com/my/settings/openapi/grantingaccess/?client_id={CLIENT_ID}&redirect_uri=http://localhost:8123/auth/callback&scope=accounts&product=web
```

2. Replace `{CLIENT_ID}` with your actual Client ID
3. Log in with your cTID
4. Select account(s) you want to authorize → **Allow access**
5. You'll be redirected with an `code` parameter in the URL

### Step 4: Exchange Code for Access Token

Make this REST API call:

```bash
curl -X GET 'https://openapi.ctrader.com/apps/token?grant_type=authorization_code&code={AUTHORIZATION_CODE}&redirect_uri=http://localhost:8123/auth/callback&client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}'
```

Replace:
- `{AUTHORIZATION_CODE}` - from redirect URL
- `{CLIENT_ID}` - your client ID
- `{CLIENT_SECRET}` - your client secret

**Response will contain:**
```json
{
  "accessToken": "YOUR_ACCESS_TOKEN_HERE",
  "refreshToken": "YOUR_REFRESH_TOKEN",
  "expiresIn": 2628000
}
```

### Step 5: Get Your Account ID

1. Log into your cTrader platform
2. View account number in **Account Settings**

### Step 6: Add to Home Assistant

1. **Settings → Devices & Services**
2. Search for **cTrader Monitor**
3. Enter all OAuth credentials:
   - **Access Token** (from step 4 response)
   - **Refresh Token** (from step 4 response)
   - **Client ID** (from app credentials)
   - **Client Secret** (from app credentials)
   - **Account ID** (from step 5)

### Automatic Token Refresh ✅

The integration automatically handles token refresh! Here's what happens:

- ✅ Monitors token expiry (tokens last ~30 days)
- ✅ Refreshes token automatically 5 minutes before expiry
- ✅ Stores new tokens in Home Assistant config
- ✅ No manual intervention needed

The `refresh_token` is the key — it never expires and allows unlimited refreshes.

**Security Note:** Keep all tokens/credentials private. Store them only in Home Assistant config.

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

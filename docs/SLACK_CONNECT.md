# Connecting Dash to Slack

Slack gives Dash two capabilities:
1. **Receiving messages** — users interact with Dash via DMs, @mentions, and thread replies.
2. **Sending messages** — Dash posts to channels proactively (scheduled task results) or on request.

Each Slack thread maps to a session ID, so every thread gets its own conversation context.

## Prerequisites

- Dash running locally (`docker compose up -d --build`) or deployed to a public URL
- A Slack workspace where you can install apps

## Step 1: Get a Public URL

Slack needs a public URL to send events to Dash.

**Production** — use your deployed URL (e.g., `https://dash-production-xxxx.up.railway.app`).

**Local development** — use [ngrok](https://ngrok.com/download/mac-os):

```sh
# Docker Compose (Quick Start)
ngrok http 8000

# Bare AgentOS (python -m app.main)
ngrok http 7777
```

Copy the `https://` URL (e.g., `https://abc123.ngrok-free.app`). This is your base URL.

## Step 2: Create a Slack App from Manifest

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Click **Create New App → From a manifest**
3. Select your workspace
4. Switch to **JSON** and paste the manifest below
5. Replace `YOUR_URL_HERE` with your base URL from Step 1
6. Click **Create**

```json
{
  "display_information": {
    "name": "Dash",
    "description": "Self-learning data agent that delivers insights, not just SQL results",
    "background_color": "#1a1a2e"
  },
  "features": {
    "app_home": {
      "home_tab_enabled": false,
      "messages_tab_enabled": true,
      "messages_tab_read_only_enabled": false
    },
    "bot_user": {
      "display_name": "Dash",
      "always_online": true
    }
  },
  "oauth_config": {
    "scopes": {
      "bot": [
        "app_mentions:read",
        "assistant:write",
        "channels:history",
        "channels:read",
        "chat:write",
        "chat:write.customize",
        "chat:write.public",
        "files:read",
        "files:write",
        "groups:history",
        "im:history",
        "im:read",
        "im:write",
        "search:read.public",
        "search:read.files",
        "search:read.users",
        "users:read",
        "users:read.email"
      ]
    }
  },
  "settings": {
    "event_subscriptions": {
      "request_url": "YOUR_URL_HERE/slack/events",
      "bot_events": [
        "app_mention",
        "message.channels",
        "message.groups",
        "message.im"
      ]
    },
    "org_deploy_enabled": false,
    "socket_mode_enabled": false,
    "token_rotation_enabled": false
  }
}
```

## Step 3: Install to Workspace

1. Go to **Install App** in the sidebar
2. Click **Install to Workspace**
3. Authorize the requested permissions
4. Copy the **Bot User OAuth Token** (`xoxb-...`)

## Step 4: Add Credentials and Restart

1. Copy the bot token from Step 3 → `SLACK_TOKEN`
2. Go to **Basic Information** in the sidebar, under **App Credentials**, copy **Signing Secret** → `SLACK_SIGNING_SECRET`

**Local development:**

```env
SLACK_TOKEN="xoxb-your-bot-token"
SLACK_SIGNING_SECRET="your-signing-secret"
```

```sh
docker compose up -d --build
```

**Railway:**

Add both variables to `.env.production`, then sync and redeploy:

```sh
./scripts/railway_env.sh
./scripts/railway_redeploy.sh
```

## Step 5: Verify Event Subscriptions

Slack verifies your endpoint with a `challenge` request when the app is created. If Dash wasn't running at that time, the verification fails silently and events won't be delivered.

1. Go to your Dash app settings → **Event Subscriptions**
2. If the Request URL shows "Your URL didn't respond", click **Retry**
3. Confirm it shows **Verified** with a green checkmark
4. Click **Save Changes**

## Verify

- **DM**: Open a direct message to the Dash bot and send a message.
- **Channel**: @mention Dash in any channel (e.g., `@Dash what's our MRR?`).
- **Thread**: Reply in a thread — Dash continues the conversation with full context.

## Updating Permissions

After changing the manifest or scopes, go to **Install App** and click **Reinstall to Workspace** to apply the new permissions.

## Bot Scopes Reference

| Scope | Purpose |
|-------|---------|
| `app_mentions:read` | Respond when @mentioned |
| `assistant:write` | Slack AI assistant features |
| `channels:history` | Read channel message history for context |
| `channels:read` | List and discover public channels |
| `chat:write` | Post messages |
| `chat:write.customize` | Custom message formatting (username, icon) |
| `chat:write.public` | Post to public channels without joining |
| `files:read` | Read files shared in channels |
| `files:write` | Upload files (reports, exports) |
| `groups:history` | Read private channel history |
| `im:history` | Read DM history |
| `im:read` | View DMs |
| `im:write` | Send DMs |
| `search:read.public` | Search public messages |
| `search:read.files` | Search files |
| `search:read.users` | Search users |
| `users:read` | View user profiles |
| `users:read.email` | View user email addresses |

## How It Works

Dash uses [Agno's Slack interface](https://docs.agno.com) which handles:

- **Event verification**: Validates the signing secret on every incoming event.
- **Message routing**: Bot mentions, DMs, channel messages, and group messages all route to the Dash team leader.
- **Thread sessions**: Each Slack thread timestamp becomes a session ID. Thread replies reuse the same session context without needing to @mention again.
- **Streaming**: Responses stream to Slack in real time.
- **User identity**: Dash knows who is asking via `users:read` scope.

The Slack interface is registered conditionally in `app/main.py` — only when both `SLACK_TOKEN` and `SLACK_SIGNING_SECRET` are set.

### SlackTools vs Slack Interface

Two separate things:
- **Slack Interface** (`app/main.py`): Receives incoming events from Slack. Requires both `SLACK_TOKEN` and `SLACK_SIGNING_SECRET`.
- **SlackTools** (`dash/team.py`): Lets the team leader send messages to channels, search messages, and get user info. Requires only `SLACK_TOKEN`. Enabled tools: `send_message`, `list_channels`, `send_message_thread`, `get_channel_info`, `get_thread`, `get_user_info`, `search_messages`.

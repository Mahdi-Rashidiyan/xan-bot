# Telegram Bot Manager

A versatile Telegram bot for managing both groups and channels with powerful moderation and user management capabilities.

## Features

### Group Management
- Ban users from groups with `/ban` command
- Unban users with `/unban` command
- Simple admin-only permissions
- Helpful command responses

### Channel Management
- **Post Moderation**: All posts from admins require approval from the channel creator before being published
- **User Addition**: Add users from groups to channels
- **Media Support**: Handles various content types including text, photos, videos, documents, audio, and more

### User Addition Tools
- `/add` - Interactive wizard to add users from a group to a channel
- `/addgroup` - Directly add users from a specific group link to a channel

## Setup Instructions

1. **Get a Bot Token:**
   - Talk to [@BotFather](https://t.me/BotFather) on Telegram
   - Create a new bot with `/newbot` command
   - Copy the API token provided

2. **Set the Token:**
   Option 1: Environment Variable
   ```
   export TELEGRAM_BOT_TOKEN=your_token_here
   ```
   
   Option 2: Config File
   - Copy `config.txt.example` to `config.txt`
   - Replace the placeholder with your actual token

3. **Install Dependencies:**
   ```
   pip install -r requirements.txt
   ```
   Note: This bot uses python-telegram-bot version 20+.

4. **Run the Bot:**
   ```
   python bot.py
   ```

## Usage

### Group Management
1. Add the bot to your group
2. Make the bot an admin in the group
3. Reply to a user's message with `/ban` to ban them
4. Reply to a message with `/unban` to unban a user
5. You can also just reply with "ban" or "unban" text (without the slash)

### Channel Post Moderation
1. Add the bot to your channel as an administrator
2. When admins post to the channel, the message will be intercepted
3. The channel creator will receive a private message with the post content and approve/reject buttons
4. If approved, the post will be published to the channel
5. If rejected, the post will be discarded
6. The admin who made the post will be notified of the decision

### Adding Users to Channels
#### Method 1: Using the `/add` command
1. Start a private chat with the bot
2. Type `/add`
3. Follow the interactive prompts to:
   - Provide a channel where you want to add users
   - Provide a group link or list of usernames to add

#### Method 2: Using the `/addgroup` command
1. Start a private chat with the bot
2. Type `/addgroup https://t.me/your_group_link`
3. Provide the channel where you want to add users
4. The bot will process and add users automatically

## Bot Permissions

### For Group Management
- Must be an admin in the group
- Requires ban user permission

### For Channel Management
- Must be an admin in the channel
- Requires "add members" permission for user addition
- Requires "post messages" and "delete messages" for post moderation

### For User Addition
- The bot must be an admin in both the source group (to see members) and target channel (to add members)
- Due to Telegram API limitations, the bot can only retrieve admins from groups unless it has special access

## Limitations

- When extracting users from groups, only admins can be retrieved due to Telegram API limitations
- Channel post moderation requires the channel creator to have a private chat with the bot
- The bot must have the necessary permissions in both groups and channels

## Requirements

- Python 3.7+
- python-telegram-bot version 20.0 or higher

## Note

Only users with admin privileges in the group can use the ban/unban commands. 
# Telegram Bot Manager

A simple Telegram bot to help manage groups by providing ban and unban functionality for administrators.

## Features

- Ban users from groups with `/ban` command
- Unban users with `/unban` command
- Simple admin-only permissions
- Helpful command responses

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

1. Add the bot to your group
2. Make the bot an admin in the group
3. Reply to a user's message with `/ban` to ban them
4. Reply to a message with `/unban` to unban a user
5. You can also just reply with "ban" or "unban" text (without the slash)

## Requirements

- Python 3.7+
- python-telegram-bot version 20.0 or higher

## Note

Only users with admin privileges in the group can use the ban/unban commands. 
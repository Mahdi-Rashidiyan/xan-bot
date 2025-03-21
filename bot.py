from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes, 
    CallbackQueryHandler, ConversationHandler, CallbackContext
)
import os
import logging
from datetime import datetime
import re

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Dictionary to store pending posts: {post_id: {'chat_id': chat_id, 'message': message, 'admin_id': admin_id}}
PENDING_POSTS = {}

# Define conversation states
CHANNEL, GROUP_LINK, CHANNEL_FOR_GROUP = range(3)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        "Hi! I'm a management bot for groups and channels.\n\n"
        "Available commands:\n"
        "/ban - Ban a user (reply to their message)\n"
        "/unban - Unban a user (reply to their message)\n"
        "/add - Add users from a group to a channel\n"
        "/addgroup - Add users from a specific group link\n"
        "/help - Show this help message"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        "Available commands:\n"
        "/ban - Ban a user (reply to their message)\n"
        "/unban - Unban a user (reply to their message)\n"
        "/add - Start the user addition wizard\n"
        "/addgroup <group_link> - Add users from a specific group link\n"
        "/help - Show this help message\n\n"
        "Channel Features:\n"
        "• All posts from admins are sent to the channel creator for approval\n"
        "• Channel creator can approve or reject posts before they are published\n"
        "• You can add users from a group to a channel using the /add or /addgroup commands"
    )

async def check_admin_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if the user is an admin or the creator of the group."""
    try:
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        # Get the member status
        member = await context.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        
        # Check if the user is an admin or the creator
        if member.status in ['administrator', 'creator']:
            return True
        else:
            await update.message.reply_text("Only admins can use this command.")
            return False
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
        await update.message.reply_text("An error occurred while checking admin permissions.")
        return False

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ban a user from the group."""
    # Check if user is admin
    if not await check_admin_status(update, context):
        return
    
    # Ensure the message is a reply
    if update.message.reply_to_message is None:
        await update.message.reply_text("Please reply to a user's message to ban them.")
        return
    
    # Get the user to ban
    user_to_ban = update.message.reply_to_message.from_user
    chat_id = update.effective_chat.id
    
    # Don't allow banning yourself
    if user_to_ban.id == update.effective_user.id:
        await update.message.reply_text("You cannot ban yourself.")
        return
    
    try:
        # Ban the user
        await context.bot.ban_chat_member(chat_id=chat_id, user_id=user_to_ban.id)
        await update.message.reply_text(f"User {user_to_ban.first_name} has been banned.")
    except Exception as e:
        logger.error(f"Error banning user: {e}")
        await update.message.reply_text("An error occurred while trying to ban the user.")

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Unban a user from the group."""
    # Check if user is admin
    if not await check_admin_status(update, context):
        return
    
    # Ensure the message is a reply
    if update.message.reply_to_message is None:
        await update.message.reply_text("Please reply to a user's message to unban them.")
        return
    
    # Get the user to unban
    user_to_unban = update.message.reply_to_message.from_user
    chat_id = update.effective_chat.id
    
    try:
        # Unban the user
        await context.bot.unban_chat_member(chat_id=chat_id, user_id=user_to_unban.id)
        await update.message.reply_text(f"User {user_to_unban.first_name} has been unbanned.")
    except Exception as e:
        logger.error(f"Error unbanning user: {e}")
        await update.message.reply_text("An error occurred while trying to unban the user.")

async def handle_text_commands(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text-based 'ban' and 'unban' commands for backward compatibility."""
    text = update.message.text.lower()
    
    if text == "ban":
        await ban_command(update, context)
    elif text == "unban":
        await unban_command(update, context)

async def check_user_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check if the user is an admin, creator, or regular member."""
    try:
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        # Get the member status
        member = await context.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        return member.status
    except Exception as e:
        logger.error(f"Error checking user status: {e}")
        return None

async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle posts in channels - require approval from creator for admin posts."""
    # This is triggered when the bot is added as an admin to a channel
    # and intercepts posts before they are published
    
    # Get the post object (could be either channel_post or edited_channel_post)
    post = update.channel_post or update.edited_channel_post
    if not post:
        return
    
    if not update.effective_user:
        # If we can't determine the user, just ignore this update
        return
        
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Check if the poster is an admin but not the creator
    user_status = await check_user_status(update, context)
    
    if user_status == 'administrator':
        # Find the creator of the channel
        chat = await context.bot.get_chat(chat_id)
        
        # Some channels may not have a primary creator accessible via API
        # In that case, we'll use a designated admin as the approver
        # This would need to be configured separately
        
        try:
            # Try to get chat administrators and find the creator
            admins = await context.bot.get_chat_administrators(chat_id)
            creator = next((admin.user for admin in admins if admin.status == 'creator'), None)
            
            if creator:
                # Store the post for approval
                post_id = f"{chat_id}_{datetime.now().timestamp()}"
                
                # Store message content, possibly handle different message types
                message_content = post.text or "Non-text content"
                
                PENDING_POSTS[post_id] = {
                    'chat_id': chat_id,
                    'message': post,
                    'admin_id': user_id,
                    'admin_name': update.effective_user.full_name
                }
                
                # Create approval buttons
                keyboard = [
                    [
                        InlineKeyboardButton("Approve", callback_data=f"approve_{post_id}"),
                        InlineKeyboardButton("Reject", callback_data=f"reject_{post_id}")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # Send approval request to creator
                await context.bot.send_message(
                    chat_id=creator.id,
                    text=f"New post from admin {update.effective_user.full_name} needs approval for channel {chat.title}:\n\n{message_content}",
                    reply_markup=reply_markup
                )
                
                # Delete the original message to prevent it from being posted
                await context.bot.delete_message(chat_id=chat_id, message_id=post.message_id)
                
                # Notify admin that post is pending approval
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"Your post to {chat.title} has been sent to the channel owner for approval."
                    )
                except Exception as e:
                    logger.error(f"Could not notify admin: {e}")
            else:
                # If we can't find the creator, let the post through
                logger.warning("Could not find channel creator, allowing post without approval")
                
        except Exception as e:
            logger.error(f"Error processing channel post: {e}")
    
    # If it's the creator posting or we had an error, do nothing and let the post go through

async def handle_approval_response(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle creator's response to post approval request."""
    query = update.callback_query
    await query.answer()
    
    # Parse the callback data
    data = query.data.split("_")
    action = data[0]
    post_id = "_".join(data[1:])  # Reconstruct post_id in case it contains underscores
    
    if post_id in PENDING_POSTS:
        post_data = PENDING_POSTS[post_id]
        chat_id = post_data['chat_id']
        admin_id = post_data['admin_id']
        admin_name = post_data['admin_name']
        message = post_data['message']
        
        if action == "approve":
            try:
                # Forward the approved message to the channel based on its type
                if message.text:
                    await context.bot.send_message(chat_id=chat_id, text=message.text)
                
                elif message.photo:
                    # Handle photos
                    photo = message.photo[-1]  # Get the largest photo
                    await context.bot.send_photo(
                        chat_id=chat_id, 
                        photo=photo.file_id, 
                        caption=message.caption
                    )
                
                elif message.video:
                    # Handle videos
                    await context.bot.send_video(
                        chat_id=chat_id,
                        video=message.video.file_id,
                        caption=message.caption
                    )
                
                elif message.document:
                    # Handle documents/files
                    await context.bot.send_document(
                        chat_id=chat_id,
                        document=message.document.file_id,
                        caption=message.caption
                    )
                
                elif message.audio:
                    # Handle audio files
                    await context.bot.send_audio(
                        chat_id=chat_id,
                        audio=message.audio.file_id,
                        caption=message.caption
                    )
                
                elif message.voice:
                    # Handle voice messages
                    await context.bot.send_voice(
                        chat_id=chat_id,
                        voice=message.voice.file_id,
                        caption=message.caption
                    )
                
                elif message.animation:
                    # Handle GIFs/animations
                    await context.bot.send_animation(
                        chat_id=chat_id,
                        animation=message.animation.file_id,
                        caption=message.caption
                    )
                
                elif message.poll:
                    # Handle polls
                    # We need to recreate the poll as polls can't be forwarded by file_id
                    await context.bot.send_poll(
                        chat_id=chat_id,
                        question=message.poll.question,
                        options=[option.text for option in message.poll.options],
                        is_anonymous=message.poll.is_anonymous,
                        allows_multiple_answers=message.poll.allows_multiple_answers,
                        type=message.poll.type
                    )
                
                else:
                    # For any other types we don't handle specifically
                    logger.warning(f"Unhandled message type for post {post_id}")
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text="Content was approved but could not be properly forwarded due to unsupported format."
                    )
                
                await query.edit_message_text(text=f"✅ Post from {admin_name} has been approved and published.")
                
                # Notify the admin
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"Your post to the channel has been approved and published."
                    )
                except Exception as e:
                    logger.error(f"Could not notify admin about approval: {e}")
                    
            except Exception as e:
                logger.error(f"Error publishing approved post: {e}")
                await query.edit_message_text(text=f"⚠️ Error publishing the post: {str(e)}")
        
        elif action == "reject":
            await query.edit_message_text(text=f"❌ Post from {admin_name} has been rejected.")
            
            # Notify the admin
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"Your post to the channel has been rejected by the channel owner."
                )
            except Exception as e:
                logger.error(f"Could not notify admin about rejection: {e}")
        
        # Clean up the pending post
        del PENDING_POSTS[post_id]
    else:
        await query.edit_message_text(text="This approval request is no longer valid.")

# Add Users Conversation Handlers
async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the process of adding users to a channel."""
    await update.message.reply_text(
        "Please send me the channel username or invite link where you want to add users.\n"
        "Make sure I am an admin in the channel with user add permissions."
    )
    return CHANNEL

async def get_channel_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process the channel information and ask for the group link."""
    channel_info = update.message.text
    
    # Save the channel information to context.user_data
    context.user_data['channel'] = channel_info
    
    # Extract the channel ID or username
    if channel_info.startswith('https://t.me/'):
        channel_username = channel_info.split('https://t.me/')[1]
        context.user_data['channel_username'] = channel_username
    else:
        # Assume it's directly a username or ID
        context.user_data['channel_username'] = channel_info.lstrip('@')
    
    # Check if the bot is an admin in the channel
    try:
        # Try to get the chat to validate it exists
        chat = await context.bot.get_chat(context.user_data['channel_username'])
        context.user_data['channel_id'] = chat.id
        
        # Check if the bot is an admin
        bot_member = await context.bot.get_chat_member(chat.id, context.bot.id)
        
        if bot_member.status != 'administrator':
            await update.message.reply_text(
                "I need to be an administrator in the channel to add users. "
                "Please add me as an admin with user add permissions and try again."
            )
            return ConversationHandler.END
        
        # Check if the bot has the right to add users
        if not bot_member.can_invite_users:
            await update.message.reply_text(
                "I am an admin in the channel, but I don't have permission to add users. "
                "Please update my permissions and try again."
            )
            return ConversationHandler.END
        
        await update.message.reply_text(
            f"Great! I'm an admin in the channel {chat.title}.\n\n"
            "Now, please send me the link to the group or a list of usernames (one per line) "
            "from which you want to add users."
        )
        return GROUP_LINK
        
    except Exception as e:
        logger.error(f"Error checking channel: {e}")
        await update.message.reply_text(
            "I couldn't access that channel. Please make sure:\n"
            "1. The channel exists\n"
            "2. I'm a member of the channel\n"
            "3. You provided a valid username or invite link\n\n"
            "Please try again or use /cancel to stop."
        )
        return ConversationHandler.END

async def get_group_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process the group information and start adding users."""
    group_info = update.message.text
    
    await update.message.reply_text("Processing your request. This might take some time...")
    
    try:
        # Check if it's a list of usernames (one per line)
        usernames = []
        if not group_info.startswith('https://'):
            # It's a list of usernames
            usernames = [username.strip(' @') for username in group_info.split('\n') if username.strip()]
        else:
            # It's a group link - try to get members
            # Extract the group username or invite code
            if 'https://t.me/' in group_info:
                group_id = group_info.split('https://t.me/')[1]
                if '+' in group_id:  # It's a private invite
                    await update.message.reply_text(
                        "I can't automatically extract users from private group invites. "
                        "Please provide a list of usernames instead (one per line)."
                    )
                    return ConversationHandler.END
                
                # It's a public group
                try:
                    # Try to get the chat
                    chat = await context.bot.get_chat(group_id)
                    
                    # Try to get some members (limited by Telegram API)
                    # This might not work for large groups due to API limitations
                    chat_admins = await context.bot.get_chat_administrators(chat.id)
                    usernames = [admin.user.username for admin in chat_admins if admin.user.username]
                    
                    await update.message.reply_text(
                        f"I could only retrieve {len(usernames)} users from the group due to Telegram API limitations.\n"
                        "I'll proceed with adding these users to the channel."
                    )
                except Exception as e:
                    logger.error(f"Error getting group members: {e}")
                    await update.message.reply_text(
                        "I couldn't access the group members. Please provide a list of usernames instead (one per line)."
                    )
                    return ConversationHandler.END
            else:
                await update.message.reply_text(
                    "Invalid group link format. Please provide a valid group link or a list of usernames (one per line)."
                )
                return ConversationHandler.END
        
        if not usernames:
            await update.message.reply_text(
                "No valid usernames found. Please provide at least one valid username."
            )
            return ConversationHandler.END
            
        # Use the shared function to add users to the channel
        return await add_users_to_channel(update, context, usernames)
        
    except Exception as e:
        logger.error(f"Error in add users process: {e}")
        await update.message.reply_text(
            f"An error occurred while processing your request: {str(e)}\n"
            "Please try again later."
        )
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation."""
    await update.message.reply_text(
        "Operation cancelled.", 
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

# Direct Group Link Handler
async def addgroup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the direct group link command."""
    # Check if arguments were provided
    if not context.args:
        await update.message.reply_text(
            "Please provide a group link after the command. For example:\n"
            "/addgroup https://t.me/your_group_name"
        )
        return ConversationHandler.END
    
    # Get the group link from arguments
    group_link = context.args[0]
    
    # Store the group link in user_data
    context.user_data['group_link'] = group_link
    
    # Check if it's a valid Telegram link
    if not group_link.startswith('https://t.me/'):
        await update.message.reply_text(
            "That doesn't look like a valid Telegram group link. "
            "Please provide a link in the format: https://t.me/your_group_name"
        )
        return ConversationHandler.END
    
    # Now ask for the channel where to add users
    await update.message.reply_text(
        "Please send me the channel username or invite link where you want to add users.\n"
        "Make sure I am an admin in the channel with user add permissions."
    )
    
    return CHANNEL_FOR_GROUP

async def process_channel_for_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process the channel for the direct group link command."""
    channel_info = update.message.text
    
    # Save the channel information to context.user_data
    context.user_data['channel'] = channel_info
    
    # Extract the channel ID or username
    if channel_info.startswith('https://t.me/'):
        channel_username = channel_info.split('https://t.me/')[1]
        context.user_data['channel_username'] = channel_username
    else:
        # Assume it's directly a username or ID
        context.user_data['channel_username'] = channel_info.lstrip('@')
    
    # Check if the bot is an admin in the channel
    try:
        # Try to get the chat to validate it exists
        chat = await context.bot.get_chat(context.user_data['channel_username'])
        context.user_data['channel_id'] = chat.id
        
        # Check if the bot is an admin
        bot_member = await context.bot.get_chat_member(chat.id, context.bot.id)
        
        if bot_member.status != 'administrator':
            await update.message.reply_text(
                "I need to be an administrator in the channel to add users. "
                "Please add me as an admin with user add permissions and try again."
            )
            return ConversationHandler.END
        
        # Check if the bot has the right to add users
        if not bot_member.can_invite_users:
            await update.message.reply_text(
                "I am an admin in the channel, but I don't have permission to add users. "
                "Please update my permissions and try again."
            )
            return ConversationHandler.END
        
        # Now process the group link
        await update.message.reply_text(
            f"Great! I'm an admin in the channel {chat.title}.\n\n"
            "Now processing the group link you provided. This might take some time..."
        )
        
        # Process the group link
        return await process_group_link(update, context, context.user_data['group_link'])
        
    except Exception as e:
        logger.error(f"Error checking channel: {e}")
        await update.message.reply_text(
            "I couldn't access that channel. Please make sure:\n"
            "1. The channel exists\n"
            "2. I'm a member of the channel\n"
            "3. You provided a valid username or invite link\n\n"
            "Please try again or use /cancel to stop."
        )
        return ConversationHandler.END

async def process_group_link(update: Update, context: ContextTypes.DEFAULT_TYPE, group_link: str) -> int:
    """Process the group link and add users to the channel."""
    try:
        # Check if it's a valid group link
        if 'https://t.me/' in group_link:
            group_id = group_link.split('https://t.me/')[1]
            
            if '+' in group_id:  # It's a private invite
                await update.message.reply_text(
                    "I can't automatically extract users from private group invites. "
                    "Please use /add command and provide a list of usernames instead (one per line)."
                )
                return ConversationHandler.END
            
            # It's a public group
            try:
                # Try to get the chat
                chat = await context.bot.get_chat(group_id)
                
                # Try to get some members (limited by Telegram API)
                chat_admins = await context.bot.get_chat_administrators(chat.id)
                usernames = [admin.user.username for admin in chat_admins if admin.user.username]
                
                if not usernames:
                    await update.message.reply_text(
                        "I couldn't retrieve any users from the group. The group might be empty or I don't have permission to see its members."
                    )
                    return ConversationHandler.END
                
                await update.message.reply_text(
                    f"I found {len(usernames)} users from the group due to Telegram API limitations.\n"
                    "I'll proceed with adding these users to the channel."
                )
                
                # Add the users to the channel
                return await add_users_to_channel(update, context, usernames)
                
            except Exception as e:
                logger.error(f"Error getting group members: {e}")
                await update.message.reply_text(
                    "I couldn't access the group members. Please make sure:\n"
                    "1. The group exists\n"
                    "2. It's a public group\n"
                    "3. I have permission to access its members\n\n"
                    "Please try again with /add command and provide usernames manually."
                )
                return ConversationHandler.END
        else:
            await update.message.reply_text(
                "Invalid group link format. Please provide a valid Telegram group link starting with https://t.me/"
            )
            return ConversationHandler.END
            
    except Exception as e:
        logger.error(f"Error processing group link: {e}")
        await update.message.reply_text(
            f"An error occurred while processing the group link: {str(e)}\n"
            "Please try again later."
        )
        return ConversationHandler.END

async def add_users_to_channel(update: Update, context: ContextTypes.DEFAULT_TYPE, usernames: list) -> int:
    """Add the provided list of usernames to the channel."""
    channel_id = context.user_data['channel_id']
    added_count = 0
    failed_count = 0
    failed_users = []
    
    # Create a progress message
    progress_message = await update.message.reply_text(f"Starting to add users to the channel...")
    
    for i, username in enumerate(usernames):
        try:
            # Try to get the user by username
            if not username:
                continue
            
            user = None
            try:
                user = await context.bot.get_chat(username)
            except Exception as e:
                failed_count += 1
                failed_users.append(username)
                logger.error(f"Error getting user {username}: {e}")
                continue
            
            # Try to add the user to the channel
            try:
                # Use invite_chat_member to add user to channel
                await context.bot.invite_chat_member(
                    chat_id=channel_id,
                    user_id=user.id
                )
                added_count += 1
            except Exception as e:
                # User might already be in the channel or can't be added for other reasons
                error_message = str(e).lower()
                if "already a member" in error_message:
                    # User is already in the channel, consider this a success
                    added_count += 1
                else:
                    failed_count += 1
                    failed_users.append(username)
                    logger.error(f"Error adding user {username} to channel: {e}")
            
            # Update progress every 5 users or at the end
            if (i + 1) % 5 == 0 or i == len(usernames) - 1:
                await progress_message.edit_text(
                    f"Progress: {i + 1}/{len(usernames)} users processed.\n"
                    f"Added: {added_count}, Failed: {failed_count}"
                )
            
        except Exception as e:
            failed_count += 1
            failed_users.append(username)
            logger.error(f"Error processing user {username}: {e}")
            continue
    
    # Final report
    if failed_users:
        failed_list = '\n'.join(failed_users[:10])
        additional_failed = len(failed_users) - 10 if len(failed_users) > 10 else 0
        
        await update.message.reply_text(
            f"User addition complete!\n\n"
            f"✅ Successfully added: {added_count} users\n"
            f"❌ Failed to add: {failed_count} users\n\n"
            f"Some users that couldn't be added (first 10):\n{failed_list}"
            f"{f'... and {additional_failed} more' if additional_failed else ''}"
        )
    else:
        await update.message.reply_text(
            f"User addition complete!\n\n"
            f"✅ Successfully added: {added_count} users\n"
            f"All users were added successfully!"
        )
    
    return ConversationHandler.END

def main() -> None:
    """Set up and run the Telegram bot."""
    # Get the token from environment variable
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    
    # Fallback to a config file if not in environment
    if not token:
        try:
            # Try to read from a config file
            with open("config.txt", "r") as file:
                token = file.read().strip()
        except FileNotFoundError:
            logger.error("No token found. Please set the TELEGRAM_BOT_TOKEN environment variable or create a config.txt file.")
            return
    
    # Replace with placeholder if still not set (for development only)
    if not token or token == "YOUR_TOKEN":
        logger.warning("Using placeholder token. Please set a real token for production.")
        token = "YOUR_TOKEN"  # This should be replaced with a real token
    
    # Create the Application and pass it the bot's token
    application = Application.builder().token(token).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("unban", unban_command))
    
    # Add conversation handler for the regular add command
    add_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("add", add_command)],
        states={
            CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_channel_info)],
            GROUP_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_group_info)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(add_conv_handler)
    
    # Add conversation handler for the direct group link command
    addgroup_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("addgroup", addgroup_command)],
        states={
            CHANNEL_FOR_GROUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_channel_for_group)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(addgroup_conv_handler)
    
    # Channel post handler
    application.add_handler(MessageHandler(filters.ChatType.CHANNEL, handle_channel_post))
    
    # Callback query handler for approval buttons
    application.add_handler(CallbackQueryHandler(handle_approval_response))
    
    # Keep the old text-command functionality for backward compatibility
    application.add_handler(MessageHandler(filters.TEXT & filters.REPLY & filters.ChatType.GROUPS, handle_text_commands))
    
    # Start the Bot
    application.run_polling()
    logger.info("Bot is running...")

if __name__ == "__main__":
    main()
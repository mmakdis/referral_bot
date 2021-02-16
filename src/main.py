#!/usr/bin/env python
# pylint: disable=W0613, C0116
# type: ignore[union-attr]
# This program is dedicated to the public domain under the CC0 license.

"""
Referall Bot
"""

import logging
import sys
import base64
import random
import string
import json
import pprint
from telegram import Update
from telegram import MessageEntity
from telegram import ParseMode
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, error
from telegram.bot import Bot
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from telegram.ext import CallbackQueryHandler, MessageHandler, Filters
from telegram.message import Message
from telegram.update import Update
from configparser import ConfigParser
from captcha.image import ImageCaptcha
from tinydb import TinyDB, Query
from tinydb.storages import JSONStorage
from tinydb.middlewares import CachingMiddleware
from uuid import uuid4

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

config = ConfigParser()

if not config.read("config.ini"):
    print("The script couldn't find config.ini. sure it's in the right directory?")
    sys.exit(1)

logger = logging.getLogger(__name__)
#db = TinyDB('../db/db.json', storage=CachingMiddleware(JSONStorage))
db = TinyDB('../db/db.json')
User = Query()

def is_digit(digit: str) -> bool:
    """
    Checks if the given digit is, well, a digit lol.
    The difference between this and str.isdigit() is that this
    actually checks if the given str is an ASCII or not, to avoid
    non-ASCII digits like arabic numbers.

    returns True or False
    """
    return digit.isascii() and digit.isdigit()

def image_captcha() -> dict:
    """
    Generate a random string and make a captcha for it.

    returns a dictionary with two keys, "text" and "image".
    "text" is the captcha text as str, "image" is the image
    as BytesIO.
    """
    image = ImageCaptcha()
    length = random.randint(4, 5)
    text = ''.join(
        random.choice(string.ascii_uppercase + string.digits + string.ascii_lowercase) 
        for _ in range(length))
    data = image.generate(text)
    print(text)
    return {"text": text, "image": data}


# Check for group admins
def is_admin(bot: Bot, update: Update, user_id: int) -> bool:
    """
    This function checks if the given user_id is an admin
    
    returns True or False.
    """
    admins: list = [admin.user.id for admin in
                    bot.get_chat_administrators(update.message.chat.id)]
    return user_id in admins

# Check for local admins in config.ini
def is_local_admin(user_id: int) -> bool:
    """
    Check if the given user_id is a local admin.
    Local admins are admins whom IDs are saved in the config.ini file.
    So basically check if the user_id is in [admin][admins] (config.ini)

    returns True or False
    """
    admins: list = [int(user_id) for 
        user_id in config.get("admin", "admins").split(",")]
    return user_id in admins

def check_user(update: Update, context: CallbackContext) -> int:
    """
    This functions makes it less pain in the ass to check if /user @user
    is correct.

    returns the user_id
    """
    from_id = update.message.from_user.id
    args = context.args
    if not is_local_admin(from_id): 
        return None
    if not args:
        update.message.reply_text(text="Please provide a username or an ID.", quote=True)
        return None
    elif len(args) >= 1:
        user_id = 0
        entities = update.message.parse_entities(
            [MessageEntity.TEXT_MENTION, MessageEntity.MENTION])
        if update.message.entities and entities:
            for ent in entities:
                if ent.type == MessageEntity.TEXT_MENTION:
                    user_id = ent.user.id
                    if args[0] != user_id:
                        update.message.reply_text(text="Usage: /command username/ID", quote=True)
                        return None
                elif ent.type == MessageEntity.MENTION:
                    from_username = update.message.text[ent.offset:ent.offset + ent.length]
                    if args[0] != from_username:
                        update.message.reply_text(text="Usage: /command username/ID", quote=True)
                        return None
                    db_check = db.search(User.username == from_username)
                    if not db_check:
                        update.message.reply_text(text="❓ Username unknown", quote=True)
                        return None
                    else:
                        user_id = db_check[0]["id"]
        elif is_digit(args[0]):
            db_check = db.search(User.id == int(args[0]))
            if not db_check:
                update.message.reply_text(text="❓ Username unknown (not in db)")
                return None
            else:
                user_id = int(args[0])
        else:
            update.message.reply_text(text="Usage: /command username/ID", quote=True)
        return user_id

def users(update: Update, context: CallbackContext) -> None:
    """
    Sends a message saying how many users are in the databse.

    returns None
    """
    from_id = update.message.from_user.id
    if is_local_admin(from_id):
        update.message.reply_text(f"Total users: {len(db.all())}")

def save(update: Update, context: CallbackContext) -> None:
    """
    Placeholder until otherwise.
    """
    from_id = update.message.from_user.id
    if is_local_admin(from_id):
        pass

def diverter(update: Update, context: CallbackContext) -> None:
    """
    This is the callback query handler. It's called diverter because it's
    supposed to redirect the query message (query.data) to the needed function.
    Maybe I should have called it redirector? Forwarder? Whatever.

    returns None
    """
    query = update.callback_query
    user_id = query.from_user.id
    print(is_local_admin(user_id))
    if query is None or not is_local_admin(user_id):
        pass
    elif query.data == "reset_yes":
        print(db.all())
        db.update({"points": 0}, User.captcha == True)
        context.bot.edit_message_text(chat_id=query.message.chat.id, message_id=query.message.message_id, text="Resetted successfully.")
    elif query.data == "reset_no":
        context.bot.edit_message_text(chat_id=query.message.chat.id, message_id=query.message.message_id, text="Cancelled.")
    else:
        pass
    context.bot.answer_callback_query(callback_query_id=query.id)

def user(update: Update, context: CallbackContext) -> None:
    user_id = check_user(update, context)
    if not user_id:
        return
    user_data = context.bot.get_chat_member(chat_id=update.message.chat.id, user_id=user_id)
    db_user_data = db.search(User.id == user_id)
    keyboard = [[InlineKeyboardButton("OK", callback_data="ok_cool")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    user_name = user_data["user"]["first_name"]
    string_about = f"{'⭐️ Admin: ' if is_local_admin(user_id) else '👤 User '} <a href=\"tg://user?id={user_id}\">{user_name}</a> [<code>{user_id}</code>]"
    string_points = f"🚀 Points: {db_user_data[0]['points']}"
    string_captcha = f"🤖 Passed captcha (yet): {'yes' if db_user_data[0]['captcha'] else 'no'}"
    string_complete = f"{string_about}\n{string_points}\n{string_captcha}"
    update.message.reply_text(text=string_complete, 
                        reply_markup=reply_markup, 
                        parse_mode=ParseMode.HTML)

def set_channel(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if not is_local_admin(user_id):
        return
    keyboard = [[InlineKeyboardButton("Yes", callback_data="setchannel_yes"),
                InlineKeyboardButton("No", callback_data="setchannel_no")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    # just for fun.
    update.message.reply_text(text=f"Are you sure you want set",
                            reply_markup=reply_markup)

def get_channel_id(update: Update, context: CallbackContext) -> None:
    channel_id = update.channel_post.chat.id
    message_id = update.channel_post.message_id
    message = f"Hi! Forward the next message to the bot to set up this channel.\n"
    command = f"/setchannel {channel_id}"
    context.bot.send_message(chat_id=channel_id, text=message, reply_to_message_id=message_id)
    context.bot.send_message(chat_id=channel_id, text=command, parse_mode=ParseMode.HTML)

def channel_commands(update: Update, context: CallbackContext) -> None:
    pass

def points(update: Update, context: CallbackContext) -> None:
    user_id = check_user(update, context)
    if not user_id:
        return
    user_data = context.bot.get_chat_member(chat_id=update.message.chat.id, user_id=user_id)
    db_user_data = db.search(User.id == user_id)
    user_name = user_data["user"]["first_name"]
    if len(context.args) != 2:
        update.message.reply_text("Usage: /points username/ID n")
        return
    if is_digit(context.args[1]):
        db.update({"points": int(context.args[1])}, User.id == user_id)
        update.message.reply_text(f"Updated <a href=\"tg://user?id={user_id}\">{user_name}</a>'s points from <i>{db_user_data[0]['points']}</i> to <i>{context.args[1]}</i>",
                            parse_mode=ParseMode.HTML)
    else:
        update.message.reply_text("Please provide a number!")

def reset(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if not is_local_admin(user_id):
        return
    db_size = len(db.all())
    keyboard = [[InlineKeyboardButton("Yes", callback_data="reset_yes"),
                InlineKeyboardButton("No", callback_data="reset_no")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    # just for fun.
    detail_user = ""
    if db_size < 1:
        update.message.reply_text("There are no users in the database")
        return
    elif db_size == 1:
        detail_user = "user's"
    else:
        detail_user = "users'"
    update.message.reply_text(text=f"Are you sure you want to reset {len(db.all())} {detail_user} points?",
                            reply_markup=reply_markup)

# Define a few command handlers. These usually take the two arguments update and
# context. Error handlers also receive the raised TelegramError object in error.
def start(update: Update, context: CallbackContext) -> None:
    """
    Start the bot. This is the command the user first sends to the bot to
    solve the captcha, or not. Add the user to the database and do stuff.
    
    returns None
    """
    from_id = update.message.from_user.id
    from_username = update.message.from_user.username
    db_user = db.search(User.id == from_id)
    if db_user:
        if db_user[0]["re"]:
            db.update({"re": False}, User.id == from_id)
            data = image_captcha()
            context.user_data["captcha_text"] = data["text"]
            update.message.reply_photo(photo=data["image"], caption="Solve the captcha 👆")
        elif not db_user[0]["captcha"]:
            update.message.reply_text("Please solve the captcha first.")
        else:
            update.message.reply_text("Referall code: []")
    else:
        db.insert({"id": from_id,
                "username": f"@{from_username}", 
                "captcha": False, 
                "re": False, 
                "points": 0})
        data = image_captcha()
        context.user_data["captcha_text"] = data["text"]
        update.message.reply_photo(photo=data["image"], caption="Solve the captcha 👆")


def help_command(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /help is issued."""
    from_id = update.message.from_user.id
    if is_local_admin(from_id) or is_admin(from_id):
        update.message.reply_text("Admin help")
    else:
        update.message.reply_text('User help')


def echo(update: Update, context: CallbackContext) -> None:
    """
    Check if the sent message solves the captcha or not.

    returns None
    """
    from_id = update.message.from_user.id
    db_user = db.search(User.id == from_id)
    if not db_user:
        update.message.reply_text("Please send /start first.")
    elif db_user[0]["captcha"]:
        update.message.reply_text("Start message")
    else:
        value = context.user_data.get("captcha_text", 'Not found')
        if update.message.text == value:
            db.update({"captcha": True, "re": False}, User.id == from_id)
            context.user_data.clear()   
            update.message.reply_text("Start message.")
        elif value == "Not found":
            # todo: make it send another captcha?
            print("Captcha text not found? Weird.")
        else:
            db.update({"re": True}, User.id == from_id)
            update.message.reply_text("Incorrect, please try again.")
            start(update, context)

def channel_chat(update: Update, context: CallbackContext) -> None:
    #print(update.channel_post.chat.type)
    print(update)
    # print(update.message.chat.type)

def new_status(update: Update, context: CallbackContext) -> None:
    print("status")

def main():
    """
    Start the bot and add the commands.
    """
    # Create the Updater and pass it your bot's token.
    updater = Updater(config.get("main", "token"))

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # on different commands - answer in Telegram
    # private commands.
    dispatcher.add_handler(CommandHandler(["reset", "r"], reset))
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("save", save))
    dispatcher.add_handler(CommandHandler(["help", "h"], help_command))
    dispatcher.add_handler(CommandHandler("users", users))
    dispatcher.add_handler(CommandHandler(["user", "u"], user))
    dispatcher.add_handler(CommandHandler(["points", "p"], points))
    dispatcher.add_handler(CommandHandler(["setchannel", "sc"], set_channel, Filters.chat_type.private))

    # Channel commands.
    #dispatcher.add_handler(MessageHandler(Filters.command & Filters.chat_type.channel, channel_commands))
    # todo: make it accept args?
    dispatcher.add_handler(MessageHandler(Filters.text(["/id"]) & Filters.chat_type.channel, get_channel_id))
    
    # on noncommand i.e message - echo the message on Telegram
    dispatcher.add_handler(MessageHandler(Filters.text & Filters.chat_type.private & ~Filters.command, echo))
    dispatcher.add_handler(MessageHandler(Filters.text & Filters.chat_type.channel & ~Filters.command, channel_chat))
    dispatcher.add_handler(MessageHandler(Filters.status_update.new_chat_members & Filters.chat_type, new_status))
    # Callback query handler.
    dispatcher.add_handler(CallbackQueryHandler(diverter))

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
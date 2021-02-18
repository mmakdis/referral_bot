#!/usr/bin/env python
# pylint: disable=W0613, C0116
# type: ignore[union-attr]

"""
Referall Bot

This bot is written to work in one file, to make it easier and less of a pain
when needing to switch paths or automatically downloading the bot from somewhere.

 ______   _______ _______ _______ ______   ______   _______ ___     
|    _ | |       |       |       |    _ | |    _ | |   _   |   |    
|   | || |    ___|    ___|    ___|   | || |   | || |  |_|  |   |    
|   |_||_|   |___|   |___|   |___|   |_||_|   |_||_|       |   |    
|    __  |    ___|    ___|    ___|    __  |    __  |       |   |___ 
|   |  | |   |___|   |   |   |___|   |  | |   |  | |   _   |       |
|___|  |_|_______|___|   |_______|___|  |_|___|  |_|__| |__|_______|
 _______ _______ _______                                            
|  _    |       |       |                                           
| |_|   |   _   |_     _|                                           
|       |  | |  | |   |                                             
|  _   ||  |_|  | |   |                                             
| |_|   |       | |   |                                             
|_______|_______| |___|                                             

Send /start to the bot.
"""

import logging
import sys
import base64
import random
import string
import json
import pprint
import time
import inspect
from datetime import datetime
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
    return digit.isascii() and digit.lstrip('-').isdigit()

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
    letters = "COPSUVWXZ"
    # todo check the opposite when user inputs the captcha text
    # these letters are pretty hard to tell whether they're in caps
    # or not, so replace all caps by lowercase.
    # better than using a custom font.
    text = text.translate({ord(x): y for (x, y) in zip(letters, letters.lower())})
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
    return user_id in get_local_admins()

def is_local_channel(channel_id: int) -> bool:
    """
    Just a quicker way / cleaner (?) to check if channel_id is 
    in get_local_channels()
    """
    return channel_id in get_local_channels()

def get_local_admins() -> list:
    data: list = config.get("admin", "admins").split(",")
    return [int(user_id) for user_id in data if is_digit(user_id)]

def get_local_channels() -> list:
    data = config.get("chats", "channels").split(",")
    return [int(channel) for channel in data if is_digit(channel)]

def passed_captcha(user_id: int) -> bool:
    """
    Checks whether the user has passed the captcha or not. Add

    returns True or False
    """
    data = db.get((User.id == user_id) & (User.captcha == True))
    return True if data else False

def has_address(user_id: int) -> bool:
    data = db.get((User.id == user_id) & (User.address.exists()))
    return True if data else False

def in_channel(context: CallbackContext, user_id: int) -> bool:
    """
    Checks whether the given user ID is in at least one of the channels.

    returns True or False
    """
    for channel in get_local_channels():
        try:
            data = context.bot.get_chat_member(chat_id=channel, user_id=user_id)
            return False if data.status == "left" else True
        except error.BadRequest:
            continue
    return False

def now_ns() -> int:
    return time.time_ns()

def utc_ts(time_ns: int) -> datetime:
    return datetime.utcfromtimestamp(time_ns / 1E9)

def utc_date(datetime: datetime) -> str:
    return datetime.strftime("%Y-%m-%d %H:%M:%S")

def uniqueid():
    seed = random.getrandbits(12)

def referral(user_id: int) -> str:
    user_data = db.get(User.id == user_id)
    if not user_data:
        return
    if "referral_link" not in user_data:
        link = f"r{random.getrandbits(16)}{user_id}"
        db.update({"referral_link": link, 
                    "referrals": []}, 
                User.id == user_id)
        return link
    else:
        return user_data["referral_link"]

def referral_link(context: CallbackContext, user_id: int) -> str:
    """
    Wrapper function around referral()

    returns str, the actual (formatted) link in HTML, not _only_ the referral code.
    """
    return f"https://t.me/{context.bot.get_me().username}?start={referral(user_id)}"

def referral_valid(referral) -> bool:
    """
    Check if the referral link is valid.

    returns the referral link's user if it's valid and it exists
    otherwise returns `False`
    """
    if not referral.startswith("r"):
        return False
    if not is_digit(referral.lstrip("r")):
        return False
    user_data = db.get(User.referral_link == referral)
    return user_data if user_data else False

def link(user_id: int, user_name: str) -> str:
    return f"<a href=\"tg://user?id={user_id}\">{user_name}</a>"

def get_channels_data(context: CallbackContext) -> list:
    """
    Get all channels data in one list[].

    returns list[telegram.chat.Chat]
    """
    data = []
    for channel in get_local_channels():
        try:
            data.append(context.bot.get_chat(chat_id=channel))
        except Error.BadRequest:
            continue
    return data

def write(section: str, option: str, value: str):
    try:
        config.set(section, option, value)
        with open('config.ini', 'w') as configfile:
            config.write(configfile)
    except Exception as e:
        print(e)

def calc_top_list(n: int):
    sorted_db = sorted(db.search((User.captcha == True) & (User.address.exists())),
                            key=lambda k: k['points'],
                            reverse=True)
    filtered_db = []
    last_points = 0
    last_date = 0
    for user_data in sorted_db:
        if user_data["points"] != last_points:
            last_points = user_data["points"]
        

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
                    from_username = from_username.lower()
                    if args[0] != from_username:
                        update.message.reply_text(text="Usage: /command username/ID", quote=True)
                        return None
                    db_check = db.get(User.username == from_username)
                    if not db_check:
                        update.message.reply_text(text="❓ Username unknown", quote=True)
                        return None
                    else:
                        user_id = db_check["id"]
        elif is_digit(args[0]):
            db_check = db.get(User.id == int(args[0]))
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

def test(update: Update, context: CallbackContext) -> None:
    # testing function
    from_id = update.message.from_user.id
    if not is_local_admin(from_id):
        return
    print(referral(from_id))
    print(referral_link(context, from_id))

def diverter(update: Update, context: CallbackContext) -> None:
    """
    This is the callback query handler. It's called diverter because it's
    supposed to redirect the query message (query.data) to the needed function.
    Maybe I should have called it redirector? Forwarder? Whatever.

    returns None
    """
    query = update.callback_query
    user_id = query.from_user.id
    if query is None or not is_local_admin(user_id):
        pass
    # data comes in like
    # setchannel_yes:data for the channel:something else maybe?
    args = query.data.split(":")
    if args[0] == "reset_yes":
        db.update({"points": 0}, User.captcha == True)
        context.bot.edit_message_text(chat_id=query.message.chat.id, message_id=query.message.message_id, text="Resetted successfully.")
    elif args[0] == "reset_no":
        context.bot.edit_message_text(chat_id=query.message.chat.id, message_id=query.message.message_id, text="Cancelled.")
    elif args[0] == "setchannel_yes" and len(args) == 3:
        # to avoid checking the channel name by ID again
        # it just gets passed in the data.
        channel_name = args[1]
        channel_id = int(args[2])
        channel_ids = get_local_channels()
        channel_ids.append(channel_id)
        write("chats", "channels", 
            ", ".join([str(channel_id) for channel_id in channel_ids]))
        context.bot.edit_message_text(chat_id=query.message.chat.id, 
                    message_id=query.message.message_id, 
                    text=f"Channel <i>{args[1]}</i> set.",
                    parse_mode=ParseMode.HTML)
    elif args[0] == "joinchannel_done":
        # check if the user has actually joined
        if in_channel(context, user_id):
            # echo(update, context)
            #keyboard = [[InlineKeyboardButton("Done ✅", callback_data="joinchannel_done")]]
            #reply_markup = InlineKeyboardMarkup(keyboard)
            message = "".join([f"* <a href=\"{channel.invite_link}\">{channel.title}</a>\n"
                        for channel in get_channels_data(context)])
            context.bot.edit_message_text(chat_id=query.message.chat.id, 
                            message_id=query.message.message_id,
                            parse_mode=ParseMode.HTML,
                            disable_web_page_preview=True,
                            text=f"Join the channel(s) to continue:\n{message}\nJoined!")
            referral = context.user_data.get("referred_by", False)
            if referral:
                referral_data = referral_valid(referral)
                referrals = referral_data["referrals"]
                # mark
                referrals.append(user_id)
                referral_id = referral_data["id"]
                referral_name = referral_data["first_name"]
                db.update({"referrals": referrals}, User.referral_link == referral)
                context.user_data.pop("referred_by", None)
                context.bot.send_message(chat_id=query.message.chat.id,
                            text=f"Referred by {link(referral_id, referral_name)}",
                            parse_mode=ParseMode.HTML)
            if has_address(user_id):
                get_referral_link = referral_link(context, user_id)
                context.bot.send_message(chat_id=query.message.chat.id,
                        text=f"Your referral link is: {get_referral_link}")
            else:
                context.bot.send_message(chat_id=query.message.chat.id,
                        text=f"Send your ERC-20 USDT address 👇")
                context.user_data["get_address"] = True
        else:
            context.bot.answer_callback_query(callback_query_id=query.id, 
                            text="You haven't joined yet.",
                            show_alert=True)
            return
    elif args[0] == "setchannel_no":
        context.bot.edit_message_text(chat_id=query.message.chat.id, message_id=query.message.message_id, text="Cancelled.")
    else:
        pass
    context.bot.answer_callback_query(callback_query_id=query.id)

def user(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    is_admin = is_local_admin(user_id)
    if is_local_admin(user_id) and context.args:
        user_id = check_user(update, context)
        if not user_id: return
    try:
        chat_id = get_local_channels()
        if not chat_id and is_admin:
            update.message.reply_text("Set up a channel first with /setchannel and have that user in the channel.")
            return
        if user_id != update.message.from_user.id:
            pass
            #update.message.reply_text("❓ Username unknown.\nSet up a channel first with /setchannel")
        user_data = context.bot.get_chat_member(chat_id=chat_id[0], user_id=user_id)
    except error.BadRequest:
        update.message.reply_text("❓ Username unknown, not in channel")
        return
    db_user_data = db.get(User.id == user_id)
    if not db_user_data or not user_data:
        update.message.reply_text("❓ Username unknown (not in db)\nHave you sent /start?")
        return
    keyboard = [[InlineKeyboardButton("OK", callback_data="ok_cool")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    user_name = user_data["user"]["first_name"]
    message = f"""
    {'⭐️ Admin: ' if is_local_admin(user_id) else '👤 User '} <a href=\"tg://user?id={user_id}\">{user_name}</a> [<code>{user_id}</code>]
    🚀 Points: {db_user_data['points']}
    👀 First seen: {utc_date(utc_ts(db_user_data['first_seen']))} 
    💳 ERC-20 USDT: {f"<code>{db_user_data['address']}</code>" if 'address' in db_user_data else "not set! send /a"}
    🤖 Passed captcha: {'yes' if db_user_data['captcha'] else 'no'}
    """
    update.message.reply_text(text=inspect.cleandoc(message), 
                        parse_mode=ParseMode.HTML)

def set_channel(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    channel_id = -1
    if not is_local_admin(user_id):
        return
    if update.message.forward_from_chat:
        channel_id = update.message.forward_from_chat.id
    else:
        if len(context.args) < 1:
            update.message.reply_text("Please provide a chat ID or forward a message from a channel.\nTo forward: send /sc to the channel")
            return
        elif not is_digit(context.args[0]):
            update.message.reply_text("Please provide an actual number.")
            return
        channel_id = int(context.args[0])
    chat_data = context.bot.get_chat(chat_id=channel_id)
    keyboard = [[InlineKeyboardButton("Yes", callback_data=f"setchannel_yes:{chat_data['title']}:{channel_id}"),
                InlineKeyboardButton("No", callback_data="setchannel_no")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    # just for fun.
    update.message.reply_text(text=f"Are you sure you want set \"{chat_data['title']}\" as the main channel?",
                            reply_markup=reply_markup)

def get_channel_id(update: Update, context: CallbackContext) -> None:
    channel_id = update.channel_post.chat.id
    message_id = update.channel_post.message_id
    message = f"Now, forward this (your <code>{update.channel_post.text}</code> message) command to the bot to set up this channel.\n"
    context.bot.send_message(chat_id=channel_id, text=message, reply_to_message_id=message_id, parse_mode=ParseMode.HTML)

def channel_commands(update: Update, context: CallbackContext) -> None:
    pass

def points(update: Update, context: CallbackContext) -> None:
    user_id = check_user(update, context)
    if not user_id:
        return
    chat_id = get_local_channels()
    if not chat_id:
        update.message.reply_text("Set up a channel first with /setchannel")
        return
    user_data = context.bot.get_chat_member(chat_id=chat_id[0], user_id=user_id)
    db_user_data = db.search(User.id == user_id)
    user_name = user_data["user"]["first_name"]
    if len(context.args) != 2:
        update.message.reply_text("Usage: <code>/p @username 10</code> (10 is an example)")
        return
    if is_digit(context.args[1]):
        db.update({"points": int(context.args[1])}, User.id == user_id)
        update.message.reply_text(f"Updated <a href=\"tg://user?id={user_id}\">{user_name}</a>'s points from <i>{db_user_data[0]['points']}</i> to <i>{context.args[1]}</i>",
                            parse_mode=ParseMode.HTML)
    else:
        update.message.reply_text("Please provide a number!")

def address(update: Update, context: CallbackContext) -> None:
    #user_id = check_user(update, context)
    from_id = update.message.from_user.id    
    db_user = db.get(User.id == from_id)
    if db_user:
        if not context.args:
            update.message.reply_text("Provide an address, like so: <code>/a insert_address_here</code>",
                        parse_mode=ParseMode.HTML)
            return
        db.update({"address": context.args[0]}, User.id == from_id)
        message = ""
        if "address" in db_user:
            message = f"Your address has been changed from '<i>{db_user['address']}</i>' to '<i>{context.args[0]}</i>'"
        else:
            message = f"Your address has been set to: '<i>{context.args[0]}</i>'"
        update.message.reply_text(message, parse_mode=ParseMode.HTML)
    else:
        update.message.reply_text("Please send /start first")

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
    from_firstname = update.message.from_user.first_name
    referred = False
    db_user = db.get(User.id == from_id)
    if context.args:
        referral_data = referral_valid(context.args[0])
        if not referral_data:
            update.message.reply_text("The referral link is invalid or does not exist.")
            return
        if not db_user:
            # referral_data = db.get(User.referral_link == context.args[0])
            referrals = referral_data["referrals"]
            referrals.append(from_id)
            referral_id = referral_data["id"]
            referral_name = referral_data["first_name"]
            # db.update({"referrals": referrals}, User.referral_link == context.args[0])
            referred = True
            context.user_data["referred_by"] = context.args[0]
            update.message.reply_text(f"You were sent by {link(referral_id, referral_name)}.",
                            parse_mode=ParseMode.HTML)
        else:
            if referral_data["id"] == from_id:
                update.message.reply_text("You can't use your own referral link.")
            elif from_id in referral_data["referrals"]:
                update.message.reply_text(f"You've already used {referral_data['first_name']}'s referral link")
            else:
                update.message.reply_text("You can't use referral links after starting the bot.")
    if db_user:
        if db_user["re"]:
            db.update({"re": False}, User.id == from_id)
            data = image_captcha()
            context.user_data["captcha_text"] = data["text"]
            update.message.reply_photo(photo=data["image"], caption="Solve the captcha 👆")
        elif not db_user["captcha"]:
            update.message.reply_text("Please solve the captcha first.")
        elif not in_channel(context, from_id) or not has_address(from_id):
            context.user_data["get_address"] = False
            echo(update, context)
        else:
            #todo check if the username and name are changed and update them.
            update.message.reply_text(f"Your referral link is: {referral_link(context, from_id)}")
    else:
        current_time = now_ns()
        db_insertion = {
            "id": from_id,
            "first_name": from_firstname,
            "captcha": False,
            "re": False,
            "referred": referred,
            "points": 0,
            "first_seen": current_time
            }
        if from_username:
            db_insertion["username"] = "@" + from_username.lower()
        db.insert(db_insertion)
        data = image_captcha()
        context.user_data["captcha_text"] = data["text"]
        update.message.reply_photo(photo=data["image"], caption="Solve the captcha 👆")

def help_command(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /help is issued."""
    from_id = update.message.from_user.id
    #todo not hardcode it lol
    if is_local_admin(from_id):
        help_message = """
        <code>/start</code>: start the bot and identify yourself.
        <code>/address</code> or <code>/a</code>: change your ERC-20 address.
        <b>[admin|user]</b> <code>/user</code> or <code>/u</code>: check your user data or other user's data.
        <b>[admin]</b> <code>/users</code>: check the total users.
        <b>[admin]</b> <code>/points</code> or <code>p</code>: change a user's points.
        <b>[admin]</b> <code>/reset</code> or <code>r</code>: reset all users' points.
        <b>[admin]</b> <code>/setchannel</code> or <code>sc</code>: set a channel as the main channel.

        Users have different usage of commands. For an example, a user is allowed to use <code>/user</code> but only to check their own data, not other's data.
        Users don't see some commands they don't need to see.
        """
        update.message.reply_text(inspect.cleandoc(help_message), parse_mode=ParseMode.HTML)
    else:
        help_message = """
        <code>/start</code>: start the bot and identify yourself.
        <code>/address</code> or <code>/a</code>: change your ERC-20 address.
        <code>/user</code> or <code>/u</code>: check your user data.
        """
        update.message.reply_text(inspect.cleandoc(help_message), parse_mode=ParseMode.HTML)

def echo(update: Update, context: CallbackContext) -> None:
    """
    Check if the sent message solves the captcha or not.
    Handles other stuff.

    returns None
    """
    from_id = update.message.from_user.id
    from_firstname = update.message.from_user.first_name
    db_user = db.get(User.id == from_id)    
    passed = passed_captcha(from_id)
    channel = in_channel(context, from_id)
    address = has_address(from_id)
    if not db_user:
        update.message.reply_text("Please send /start first.")
    elif passed:
        if not channel:
            keyboard = [[InlineKeyboardButton("Done ✅", callback_data="joinchannel_done")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            message = "".join([f"* <a href=\"{channel.invite_link}\">{channel.title}</a>\n"
                        for channel in get_channels_data(context)])
            update.message.reply_text(f"Join the channel(s) to continue:\n{message}\nTick 'Done' once you're done.", 
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True,
                        reply_markup=reply_markup)
            return
        referral = context.user_data.get("referred_by", False)
        if referral:
            referral_data = referral_valid(referral)
            referrals = referral_data["referrals"]
            referrals.append(from_id)
            referral_id = referral_data["id"]
            referral_name = referral_data["first_name"]
            db.update({"referrals": referrals}, User.referral_link == referral)
            context.user_data.pop("referred_by", None)
            update.message.reply_text(f"Referred by {link(referral_id, referral_name)}",
                        parse_mode=ParseMode.HTML)
            try:
                context.bot.send_message(chat_id=referral_data["id"],
                        text=f"You referred {link(from_id, from_firstname)}.",
                        parse_mode=ParseMode.HTML)
            except error.BadRequest:
                print(f"Tried sending a message to {referral_data['id']} that they referred someone but failed.")
        if not address:
            value = context.user_data.get("address", 'Not found')
            if value == "Not found":
                get_address = context.user_data.get("get_address", False)
                if get_address:
                    context.user_data["address"] = update.message.text
                    echo(update, context)
                else:
                    update.message.reply_text("Send your ERC-20 USDT address 👇")
                    context.user_data["get_address"] = True
            else:
                db.update({"address": value}, User.id == from_id)
                context.user_data.pop("address", None)
                echo(update, context)
            #update.message.reply_text("Send your address with /a, like:\n<code>/a YOUR_ADDRESS_HERE</code>",
            #                parse_mode=ParseMode.HTML)
        else:
            # todo: get referral_link
            get_referral_link = referral_link(context, from_id)
            update.message.reply_text(f"Your referral link is: {get_referral_link}")
    else:
        value = context.user_data.get("captcha_text", 'Not found')
        # todo add the pop function here
        if update.message.text == value:
            db.update({"captcha": True, "re": False}, User.id == from_id)
            context.user_data.pop("captcha_text", None)   
            echo(update, context)
        elif value == "Not found":
            # todo: make it send another captcha?
            db.update({"re": True}, User.id == from_id)
            context.user_data.pop("captcha_text", None)
            update.message.reply_text("Issue occured, regenerating captcha.")
            start(update, context)
        else:
            db.update({"re": True}, User.id == from_id)
            context.user_data.pop("captcha_text", None)
            update.message.reply_text("Incorrect, please try again.")
            start(update, context)

def channel_chat(update: Update, context: CallbackContext) -> None:
    #print(update.channel_post.chat.type)
    pass
    #print(update)
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
    dispatcher.add_handler(CommandHandler("start", start, Filters.chat_type.private))
    dispatcher.add_handler(CommandHandler("save", save))
    dispatcher.add_handler(CommandHandler(["help", "h"], help_command, Filters.chat_type.private))
    dispatcher.add_handler(CommandHandler("users", users))
    dispatcher.add_handler(CommandHandler(["user", "u"], user, Filters.chat_type.private))
    dispatcher.add_handler(CommandHandler(["points", "p"], points, Filters.chat_type.private))
    dispatcher.add_handler(CommandHandler(["address", "a"], address, Filters.chat_type.private))
    dispatcher.add_handler(CommandHandler(["setchannel", "sc"], set_channel, Filters.chat_type.private))
    dispatcher.add_handler(CommandHandler(["test"], test))

    # Channel commands.
    #dispatcher.add_handler(MessageHandler(Filters.command & Filters.chat_type.channel, channel_commands))
    # todo: make it accept args?
    dispatcher.add_handler(MessageHandler(Filters.text(["/sc", "/setchannel"]) & Filters.chat_type.channel, get_channel_id))
    
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
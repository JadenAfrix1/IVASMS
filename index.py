import requests
import re
import json
import time
import logging
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import os
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler
import asyncio
import urllib.parse
from flask import Flask
import threading

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/')
def home():
    return "IVASMS Bot is running!"

@app.route('/health')
def health():
    return "OK", 200

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

BANNER_URL = "https://files.catbox.moe/koc535.jpg"

def get_inline_keyboard():
    """Return inline keyboard with channel/group buttons."""
    keyboard = [
        [
            InlineKeyboardButton("𝐍ᴜᴍʙᴇʀ 𝐂ʜᴀɴɴᴇʟ", url="https://t.me/mrafrixtech"),
            InlineKeyboardButton("𝐎ᴛᴘ 𝐆𝐫𝐨𝐮𝐩", url="https://t.me/afrixotpgc"),
        ],
        [
            InlineKeyboardButton("𝐑ᴇɴᴛ sᴄʀɪᴘᴛ", url="https://t.me/jaden_afrix"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_powered_by_caption():
    """Return the powered by caption with auto-updated year."""
    current_year = datetime.now().year
    return f"©ᴘᴏᴡᴇʀᴇᴅ ʙʏ 𝐀ᴜʀᴏʀᴀ𝐈ɪɴᴄ {current_year}"

# Common headers
BASE_HEADERS = {
    "Host": "www.ivasms.com",
    "Cache-Control": "max-age=0",
    "Sec-Ch-Ua": '"Not)A;Brand";v="8", "Chromium";v="138"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-User": "?1",
    "Sec-Fetch-Dest": "document",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-GB,en;q=0.9",
    "Priority": "u=0, i",
    "Connection": "keep-alive"
}

async def send_to_telegram(sms):
    """Send SMS details to Telegram group with banner, buttons, and powered by caption."""
    bot = Bot(token=os.getenv("BOT_TOKEN"))
    
    # Build message with powered by caption as quoted reply header
    message = (
        f"📨 *New SMS Received*\n\n"
        f"📞 *Number*: `+{sms['number']}`\n\n"
        f"💬 *Message*: {sms['message']}\n\n"
        f"🕒 *Time*: {sms['timestamp']}\n\n"
        f"_{get_powered_by_caption()}_"
    )

    try:
        # Send banner image with caption and inline keyboard
        await bot.send_photo(
            chat_id=os.getenv("CHAT_ID"),
            photo=BANNER_URL,
            caption=message,
            parse_mode="Markdown",
            reply_markup=get_inline_keyboard()
        )
        logger.info(f"Sent SMS to Telegram: {sms['message'][:50]}...")
    except Exception as e:
        logger.error(f"Failed to send to Telegram: {str(e)}")
        # Fallback to text message if image fails
        try:
            await bot.send_message(
                chat_id=os.getenv("CHAT_ID"),
                text=message,
                parse_mode="Markdown",
                reply_markup=get_inline_keyboard()
            )
        except Exception as e2:
            logger.error(f"Fallback text message also failed: {str(e2)}")

def payload_1(session):
    """Send GET request to /login to retrieve initial tokens."""
    url = "https://www.ivasms.com/login"
    headers = BASE_HEADERS.copy()
    try:
        response = session.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        token_match = re.search(r'<input type="hidden" name="_token" value="([^"]+)"', response.text)
        if not token_match:
            raise ValueError("Could not find _token in response")
        return {"_token": token_match.group(1)}
    except Exception as e:
        logger.error(f"Payload 1 failed: {str(e)}")
        raise

def payload_2(session, _token):
    """Send POST request to /login with credentials."""
    url = "https://www.ivasms.com/login"
    headers = BASE_HEADERS.copy()
    headers.update({
        "Content-Type": "application/x-www-form-urlencoded",
        "Sec-Fetch-Site": "same-origin",
        "Referer": "https://www.ivasms.com/login"
    })
    
    data = {
        "_token": _token,
        "email": os.getenv("IVASMS_EMAIL"),
        "password": os.getenv("IVASMS_PASSWORD"),
        "remember": "on",
        "g-recaptcha-response": "",
        "submit": "Login"
    }
    
    try:
        response = session.post(url, headers=headers, data=data, timeout=30)
        response.raise_for_status()
        if response.url.endswith("/login"):
            raise ValueError("Login failed, redirected back to /login")
        return response
    except Exception as e:
        logger.error(f"Payload 2 failed: {str(e)}")
        raise

def payload_3(session):
    """Send GET request to /sms/received to get statistics page."""
    url = "https://www.ivasms.com/portal/sms/received"
    headers = BASE_HEADERS.copy()
    headers.update({
        "Sec-Fetch-Site": "same-origin",
        "Referer": "https://www.ivasms.com/portal"
    })
    
    try:
        response = session.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        token_match = re.search(r'<meta name="csrf-token" content="([^"]+)"', response.text)
        if not token_match:
            logger.warning("No CSRF token found in /sms/received response")
            return response, ""
        return response, token_match.group(1)
    except Exception as e:
        logger.error(f"Payload 3 failed: {str(e)}")
        raise

def payload_4(session, csrf_token, from_date, to_date):
    """Send POST request to /sms/received/getsms to fetch SMS statistics."""
    url = "https://www.ivasms.com/portal/sms/received/getsms"
    headers = BASE_HEADERS.copy()
    headers.update({
        "Content-Type": "multipart/form-data; boundary=----WebKitFormBoundaryhkp0qMozYkZV6Ham",
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Referer": "https://www.ivasms.com/portal/sms/received",
        "Origin": "https://www.ivasms.com"
    })
    
    data = (
        "------WebKitFormBoundaryhkp0qMozYkZV6Ham\r\n"
        "Content-Disposition: form-data; name=\"from\"\r\n"
        "\r\n"
        f"{from_date}\r\n"
        f"------WebKitFormBoundaryhkp0qMozYkZV6Ham\r\n"
        "Content-Disposition: form-data; name=\"to\"\r\n"
        "\r\n"
        f"{to_date}\r\n"
        f"------WebKitFormBoundaryhkp0qMozYkZV6Ham\r\n"
        "Content-Disposition: form-data; name=\"_token\"\r\n"
        "\r\n"
        f"{csrf_token}\r\n"
        "------WebKitFormBoundaryhkp0qMozYkZV6Ham--\r\n"
    )
    
    try:
        response = session.post(url, headers=headers, data=data, timeout=30)
        response.raise_for_status()
        return response
    except Exception as e:
        logger.error(f"Payload 4 failed: {str(e)}")
        raise

def parse_statistics(response_text):
    """Parse SMS statistics from response and return range data."""
    try:
        soup = BeautifulSoup(response_text, 'html.parser')
        ranges = []
        
        # Check for "no SMS" message
        no_sms = soup.find('p', id='messageFlash')
        if no_sms and "You do not have any SMS" in no_sms.text:
            logger.info("No SMS data found in response")
            return ranges
        
        # Find all range cards
        range_cards = soup.find_all('div', class_='card card-body mb-1 pointer')
        for card in range_cards:
            cols = card.find_all('div', class_=re.compile(r'col-sm-\d+|col-\d+'))
            if len(cols) >= 5:
                range_name = cols[0].text.strip()
                count_text = cols[1].find('p').text.strip()
                paid_text = cols[2].find('p').text.strip()
                unpaid_text = cols[3].find('p').text.strip()
                revenue_span = cols[4].find('span', class_='currency_cdr')
                revenue_text = revenue_span.text.strip() if revenue_span else "0.0"
                
                # Convert to appropriate types, with fallback to 0
                try:
                    count = int(count_text) if count_text else 0
                    paid = int(paid_text) if paid_text else 0
                    unpaid = int(unpaid_text) if unpaid_text else 0
                    revenue = float(revenue_text) if revenue_text else 0.0
                except ValueError as e:
                    logger.warning(f"Error parsing values for {range_name}: {str(e)}")
                    count, paid, unpaid, revenue = 0, 0, 0, 0.0
                
                # Extract range_id from onclick
                onclick = card.get('onclick', '')
                range_id_match = re.search(r"getDetials$$'([^']+)'$$", onclick)
                range_id = range_id_match.group(1) if range_id_match else range_name
                
                ranges.append({
                    "range_name": range_name,
                    "range_id": range_id,
                    "count": count,
                    "paid": paid,
                    "unpaid": unpaid,
                    "revenue": revenue
                })
        return ranges
    except Exception as e:
        logger.error(f"Parse statistics failed: {str(e)}")
        raise

def save_to_json(data, filename="sms_statistics.json"):
    """Save range data to JSON file."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        logger.info("Range saved in memory")
    except Exception as e:
        logger.error(f"Failed to save to JSON: {str(e)}")

def load_from_json(filename="sms_statistics.json"):
    """Load range data from JSON file."""
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    except Exception as e:
        logger.error(f"Failed to load from JSON: {str(e)}")
        return []

def payload_5(session, csrf_token, to_date, range_name):
    """Send POST request to /sms/received/getsms/number to get numbers for a range."""
    url = "https://www.ivasms.com/portal/sms/received/getsms/number"
    headers = BASE_HEADERS.copy()
    headers.update({
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Referer": "https://www.ivasms.com/portal/sms/received",
        "Origin": "https://www.ivasms.com"
    })
    
    data = {
        "_token": csrf_token,
        "start": "",
        "end": to_date,
        "range": range_name
    }
    
    try:
        response = session.post(url, headers=headers, data=data, timeout=30)
        response.raise_for_status()
        return response
    except Exception as e:
        logger.error(f"Payload 5 failed: {str(e)}")
        raise

def parse_numbers(response_text):
    """Parse numbers from the range response."""
    try:
        soup = BeautifulSoup(response_text, 'html.parser')
        numbers = []
        
        number_divs = soup.find_all('div', class_='card card-body border-bottom bg-100 p-2 rounded-0')
        for div in number_divs:
            onclick = div.find('div', class_=re.compile(r'col-sm-\d+|col-\d+')).get('onclick', '')
            match = re.search(r"'([^']+)','([^']+)'", onclick)
            if match:
                number, number_id = match.groups()
                numbers.append({"number": number, "number_id": number_id})
            else:
                logger.warning(f"Failed to parse onclick: {onclick}")
        return numbers
    except Exception as e:
        logger.error(f"Parse numbers failed: {str(e)}")
        raise

def payload_6(session, csrf_token, to_date, number, range_name):
    """Send POST request to /sms/received/getsms/number/sms to get message details."""
    url = "https://www.ivasms.com/portal/sms/received/getsms/number/sms"
    headers = BASE_HEADERS.copy()
    headers.update({
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Referer": "https://www.ivasms.com/portal/sms/received",
        "Origin": "https://www.ivasms.com"
    })
    
    data = {
        "_token": csrf_token,
        "start": "",
        "end": to_date,
        "Number": number,
        "Range": range_name
    }
    
    try:
        response = session.post(url, headers=headers, data=data, timeout=30)
        response.raise_for_status()
        return response
    except Exception as e:
        logger.error(f"Payload 6 failed: {str(e)}")
        raise

def parse_message(response_text):
    """Parse message details from response."""
    try:
        soup = BeautifulSoup(response_text, 'html.parser')
        message_div = soup.find('div', class_='col-9 col-sm-6 text-center text-sm-start')
        revenue_div = soup.find('div', class_='col-3 col-sm-2 text-center text-sm-start')
        
        message = message_div.find('p').text.strip() if message_div else "No message found"
        revenue = revenue_div.find('span', class_='currency_cdr').text.strip() if revenue_div else "0.0"
        return {"message": message, "revenue": revenue}
    except Exception as e:
        logger.error(f"Parse message failed: {str(e)}")
        raise

async def start_command(update, context):
    """Handle /start command in Telegram."""
    try:
        welcome_message = (
            "🚀 *IVASMS Bot Started!*\n\n"
            "Monitoring SMS statistics...\n\n"
            f"_{get_powered_by_caption()}_"
        )
        await update.message.reply_photo(
            photo=BANNER_URL,
            caption=welcome_message,
            parse_mode="Markdown",
            reply_markup=get_inline_keyboard()
        )
        logger.info("Processed /start command")
    except Exception as e:
        logger.error(f"Start command failed: {str(e)}")

async def main():
    """Main function to execute automation and monitor SMS statistics."""
    try:
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        logger.info(f"Flask server started on port {os.environ.get('PORT', 5000)}")
        
        # Set up Telegram bot with polling
        application = Application.builder().token(os.getenv("BOT_TOKEN")).build()
        application.add_handler(CommandHandler("start", start_command))
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        logger.info("Telegram bot started")
        
        # Calculate date range
        today = datetime.now()
        from_date = today.strftime("%m/%d/%Y")
        to_date = (today + timedelta(days=1)).strftime("%m/%d/%Y")
        
        # Initialize in-memory storage
        JSON_FILE = "sms_statistics.json"
        existing_ranges = load_from_json(JSON_FILE)
        existing_ranges_dict = {r["range_name"]: r for r in existing_ranges}
        logger.info("Initialized storage")
        
        # Track last re-authentication time to prevent rapid loops
        last_reauth_time = 0
        min_reauth_interval = 60  # Minimum seconds between re-authentication attempts
        
        while True:
            try:
                with requests.Session() as session:
                    # Initialize session start time
                    session_start = time.time()
                    
                    # Step 1: Login
                    logger.info("Executing Payload 1: GET /login")
                    tokens = payload_1(session)
                    
                    logger.info("Executing Payload 2: POST /login")
                    response = payload_2(session, tokens["_token"])
                    logger.debug(f"Payload 2 response status: {response.status_code}, URL: {response.url}")
                    
                    logger.info("Executing Payload 3: GET /sms/received")
                    response, csrf_token = payload_3(session)
                    logger.debug(f"Payload 3 response status: {response.status_code}")
                    
                    # Step 2: Fetch initial statistics
                    logger.info(f"Executing Payload 4: POST /sms/received/getsms for date range {from_date} to {to_date}")
                    response = payload_4(session, csrf_token, from_date, to_date)
                    logger.debug(f"Payload 4 response status: {response.status_code}")
                    ranges = parse_statistics(response.text)
                    
                    # Save initial statistics if empty
                    if not existing_ranges:
                        existing_ranges = ranges
                        existing_ranges_dict = {r["range_name"]: r for r in ranges}
                        save_to_json(existing_ranges, JSON_FILE)
                    
                    # Step 3: Continuous monitoring
                    while True:
                        # Check session validity before expiry check
                        try:
                            test_response = session.get("https://www.ivasms.com/portal", headers=BASE_HEADERS, timeout=10)
                            if test_response.status_code == 401 or test_response.url.endswith("/login"):
                                logger.info("Session invalid. Re-authenticating...")
                                last_reauth_time = time.time()
                                break
                        except Exception as e:
                            logger.warning(f"Session validation check failed: {str(e)}")
                            last_reauth_time = time.time()
                            break
                        
                        # Check for session expiry (2 hours)
                        elapsed_time = time.time() - session_start
                        logger.debug(f"Session elapsed time: {elapsed_time:.2f} seconds")
                        if elapsed_time > 7200:
                            logger.info("Session nearing expiry. Re-authenticating...")
                            # Ensure minimum interval between re-authentications
                            time_since_last_reauth = time.time() - last_reauth_time
                            if time_since_last_reauth < min_reauth_interval:
                                logger.info(f"Waiting {min_reauth_interval - time_since_last_reauth:.2f} seconds before re-authenticating")
                                await asyncio.sleep(min_reauth_interval - time_since_last_reauth)
                            last_reauth_time = time.time()
                            break
                        
                        # Fetch updated statistics
                        response = payload_4(session, csrf_token, from_date, to_date)
                        logger.debug(f"Payload 4 response status: {response.status_code}")
                        new_ranges = parse_statistics(response.text)
                        new_ranges_dict = {r["range_name"]: r for r in new_ranges}
                        
                        # Compare with existing ranges
                        for range_data in new_ranges:
                            range_name = range_data["range_name"]
                            current_count = range_data["count"]
                            existing_range = existing_ranges_dict.get(range_name)
                            
                            if not existing_range:
                                logger.info(f"New range detected: {range_name}")
                                response = payload_5(session, csrf_token, to_date, range_name)
                                logger.debug(f"Payload 5 response status: {response.status_code}")
                                numbers = parse_numbers(response.text)
                                if numbers:
                                    for number_data in numbers[::-1]:
                                        logger.info(f"Fetching message for number: {number_data['number']}")
                                        response = payload_6(session, csrf_token, to_date, number_data["number"], range_name)
                                        logger.debug(f"Payload 6 response status vp6: {response.status_code}")
                                        message_data = parse_message(response.text)
                                        
                                        sms = {
                                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                            "number": number_data["number"],
                                            "message": message_data["message"],
                                            "range": range_name,
                                            "revenue": message_data["revenue"]
                                        }
                                        logger.info(f"New SMS: {sms}")
                                        await send_to_telegram(sms)
                                    
                                    existing_ranges.append(range_data)
                                    existing_ranges_dict[range_name] = range_data
                            
                            elif current_count > existing_range["count"]:
                                count_diff = current_count - existing_range["count"]
                                logger.info(f"Count increased for {range_name}: {existing_range['count']} -> {current_count} (+{count_diff})")
                                response = payload_5(session, csrf_token, to_date, range_name)
                                logger.debug(f"Payload 5 response status: {response.status_code}")
                                numbers = parse_numbers(response.text)
                                if numbers:
                                    for number_data in numbers[-count_diff:][::-1]:
                                        logger.info(f"Fetching message for number: {number_data['number']}")
                                        response = payload_6(session, csrf_token, to_date, number_data["number"], range_name)
                                        logger.debug(f"Payload 6 response status vp6: {response.status_code}")
                                        message_data = parse_message(response.text)
                                        
                                        sms = {
                                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                            "number": number_data["number"],
                                            "message": message_data["message"],
                                            "range": range_name,
                                            "revenue": message_data["revenue"]
                                        }
                                        logger.info(f"New SMS: {sms}")
                                        await send_to_telegram(sms)
                                    
                                    for r in existing_ranges:
                                        if r["range_name"] == range_name:
                                            r["count"] = current_count
                                            r["paid"] = range_data["paid"]
                                            r["unpaid"] = range_data["unpaid"]
                                            r["revenue"] = range_data["revenue"]
                                            break
                                    existing_ranges_dict[range_name] = range_data
                        
                        # Update existing ranges
                        existing_ranges = new_ranges
                        existing_ranges_dict = new_ranges_dict
                        save_to_json(existing_ranges, JSON_FILE)
                        
                        # Wait 2-3 seconds
                        await asyncio.sleep(2 + (time.time() % 1))
                    
            except Exception as e:
                logger.error(f"Error in main loop: {str(e)}. Response content: {getattr(e, 'response', 'No response')}")
                # Implement exponential backoff
                retry_delay = min(30 * 2 ** min(3, 1), 300)  # Cap at 300 seconds
                logger.info(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
    
    except Exception as e:
        logger.error(f"Main loop failed: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main())

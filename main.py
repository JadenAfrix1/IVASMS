import requests
import re
import json
import time
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import os
from telegram import Bot
from telegram.ext import Application, CommandHandler
import asyncio
from playsound import playsound
from plyer import notification
import urllib.parse

# Load environment variables
load_dotenv()
IVASMS_EMAIL = os.getenv("IVASMS_EMAIL")
IVASMS_PASSWORD = os.getenv("IVASMS_PASSWORD")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

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
    """Send SMS details to Telegram group with copiable number."""
    bot = Bot(token=BOT_TOKEN)
    message = (
        f"New SMS Received:\n"
        f"Timestamp: {sms['timestamp']}\n"
        f"Number: +{sms['number']}\n"
        f"Message: {sms['message']}\n"
        f"Range: {sms['range']}\n"
        f"Revenue: {sms['revenue']}"
    )
    try:
        await bot.send_message(chat_id=CHAT_ID, text=message)
        print(f"Sent SMS to Telegram: {sms['message'][:50]}...")
    except Exception as e:
        print(f"Failed to send to Telegram: {str(e)}")

def show_notification(number, message):
    """Show desktop notification using plyer."""
    try:
        notification.notify(
            title=f"New SMS on +{number}",
            message=message[:100],  # Limit message length for notification
            app_name="IVASMS Monitor",
            timeout=10
        )
        print(f"Displayed notification for number: +{number}")
    except Exception as e:
        print(f"Failed to show notification: {str(e)}")

def play_notification_sound():
    """Play notification sound."""
    try:
        playsound("notification.mp3")
        print("Played notification sound")
    except Exception as e:
        print(f"Failed to play notification sound: {str(e)}")

def payload_1(session):
    """Send GET request to /login to retrieve initial tokens."""
    url = "https://www.ivasms.com/login"
    headers = BASE_HEADERS.copy()
    response = session.get(url, headers=headers)
    response.raise_for_status()
    
    token_match = re.search(r'<input type="hidden" name="_token" value="([^"]+)"', response.text)
    if not token_match:
        raise ValueError("Could not find _token in response")
    return {"_token": token_match.group(1)}

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
        "email": IVASMS_EMAIL,
        "password": IVASMS_PASSWORD,
        "remember": "on",
        "g-recaptcha-response": "",
        "submit": "register"
    }
    
    response = session.post(url, headers=headers, data=data)
    response.raise_for_status()
    if response.url.endswith("/login"):
        raise ValueError("Login failed, redirected back to /login")
    return response

def payload_3(session):
    """Send GET request to /sms/received to get statistics page."""
    url = "https://www.ivasms.com/portal/sms/received"
    headers = BASE_HEADERS.copy()
    headers.update({
        "Sec-Fetch-Site": "same-origin",
        "Referer": "https://www.ivasms.com/portal"
    })
    
    response = session.get(url, headers=headers)
    response.raise_for_status()
    
    # Extract CSRF token from response
    token_match = re.search(r'<meta name="csrf-token" content="([^"]+)">', response.text)
    if not token_match:
        raise ValueError("Could not find CSRF token in /sms/received response")
    return response, token_match.group(1)

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
    
    response = session.post(url, headers=headers, data=data)
    response.raise_for_status()
    return response

def parse_statistics(response_text):
    """Parse SMS statistics from response and return range data."""
    soup = BeautifulSoup(response_text, 'html.parser')
    ranges = []
    
    # Check for "no SMS" message
    no_sms = soup.find('p', id='messageFlash')
    if no_sms and "You do not have any SMS" in no_sms.text:
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
                count, paid, unpaid, revenue = 0, 0, 0, 0.0
            
            # Extract range_id from onclick
            onclick = card.get('onclick', '')
            range_id_match = re.search(r"getDetials\('([^']+)'\)", onclick)
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

def save_to_json(data, filename="sms_statistics.json"):
    """Save range data to JSON file."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        print("Range saved in file")
    except Exception as e:
        print(f"Failed to save to JSON: {str(e)}")

def load_from_json(filename="sms_statistics.json"):
    """Load range data from JSON file."""
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    except Exception as e:
        print(f"Failed to load from JSON: {str(e)}")
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
    
    response = session.post(url, headers=headers, data=data)
    response.raise_for_status()
    return response

def parse_numbers(response_text):
    """Parse numbers from the range response."""
    soup = BeautifulSoup(response_text, 'html.parser')
    numbers = []
    
    number_divs = soup.find_all('div', class_='card card-body border-bottom bg-100 p-2 rounded-0')
    for div in number_divs:
        onclick = div.find('div', class_=re.compile(r'col-sm-\d+|col-\d+')).get('onclick', '')
        match = re.search(r"'([^']+)','([^']+)'", onclick)
        if match:
            number, number_id = match.groups()
            numbers.append({"number": number, "number_id": number_id})
    
    return numbers

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
    
    response = session.post(url, headers=headers, data=data)
    response.raise_for_status()
    return response

def parse_message(response_text):
    """Parse message details from response."""
    soup = BeautifulSoup(response_text, 'html.parser')
    message_div = soup.find('div', class_='col-9 col-sm-6 text-center text-sm-start')
    revenue_div = soup.find('div', class_='col-3 col-sm-2 text-center text-sm-start')
    
    message = message_div.find('p').text.strip() if message_div else "No message found"
    revenue = revenue_div.find('span', class_='currency_cdr').text.strip() if revenue_div else "0.0"
    return {"message": message, "revenue": revenue}

async def start_command(update, context):
    """Handle /start command in Telegram."""
    await update.message.reply_text("IVASMS Bot started! Monitoring SMS statistics.")

async def main():
    """Main function to execute automation and monitor SMS statistics."""
    # Set up Telegram bot with polling
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start_command))
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    # Calculate date range
    today = datetime.now()
    from_date = today.strftime("%m/%d/%Y")
    to_date = (today + timedelta(days=1)).strftime("%m/%d/%Y")
    
    # Initialize JSON file
    JSON_FILE = "sms_statistics.json"
    session_start = time.time()
    
    while True:
        try:
            with requests.Session() as session:
                # Step 1: Login
                tokens = payload_1(session)
                payload_2(session, tokens["_token"])
                response, csrf_token = payload_3(session)
                
                # Step 2: Fetch initial statistics
                response = payload_4(session, csrf_token, from_date, to_date)
                ranges = parse_statistics(response.text)
                
                # Load existing statistics
                existing_ranges = load_from_json(JSON_FILE)
                existing_ranges_dict = {r["range_name"]: r for r in existing_ranges}
                
                # Save initial statistics if file doesn't exist or is empty
                if not existing_ranges:
                    save_to_json(ranges, JSON_FILE)
                
                # Step 3: Continuous monitoring
                while True:
                    # Check for session expiry (2 hours)
                    if time.time() - session_start > 7200:
                        break
                    
                    # Clear console
                    os.system('cls' if os.name == 'nt' else 'clear')
                    
                    # Fetch updated statistics
                    response = payload_4(session, csrf_token, from_date, to_date)
                    new_ranges = parse_statistics(response.text)
                    new_ranges_dict = {r["range_name"]: r for r in new_ranges}
                    
                    # Compare with existing ranges
                    for range_data in new_ranges:
                        range_name = range_data["range_name"]
                        current_count = range_data["count"]
                        existing_range = existing_ranges_dict.get(range_name)
                        
                        if not existing_range:
                            print(f"New range detected: {range_name}")
                            # Fetch numbers for the new range
                            response = payload_5(session, csrf_token, to_date, range_name)
                            numbers = parse_numbers(response.text)
                            if numbers:
                                # Process all numbers in the new range
                                for number_data in numbers[::-1]:  # Process in reverse to get latest first
                                    print(f"Fetching message for number: {number_data['number']}")
                                    response = payload_6(session, csrf_token, to_date, number_data["number"], range_name)
                                    message_data = parse_message(response.text)
                                    
                                    # Process notifications
                                    sms = {
                                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                        "number": number_data["number"],
                                        "message": message_data["message"],
                                        "range": range_name,
                                        "revenue": message_data["revenue"]
                                    }
                                    print(f"New SMS: {sms}")
                                    play_notification_sound()
                                    show_notification(sms["number"], sms["message"])
                                    await send_to_telegram(sms)
                                
                                # Update JSON with new range
                                existing_ranges.append(range_data)
                                existing_ranges_dict[range_name] = range_data
                        
                        elif current_count > existing_range["count"]:
                            count_diff = current_count - existing_range["count"]
                            print(f"Count increased for {range_name}: {existing_range['count']} -> {current_count} (+{count_diff})")
                            # Fetch numbers for the range
                            response = payload_5(session, csrf_token, to_date, range_name)
                            numbers = parse_numbers(response.text)
                            if numbers:
                                # Process the last N numbers based on count_diff
                                for number_data in numbers[-count_diff:][::-1]:  # Process last N in reverse
                                    print(f"Fetching message for number: {number_data['number']}")
                                    response = payload_6(session, csrf_token, to_date, number_data["number"], range_name)
                                    message_data = parse_message(response.text)
                                    
                                    # Process notifications
                                    sms = {
                                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                        "number": number_data["number"],
                                        "message": message_data["message"],
                                        "range": range_name,
                                        "revenue": message_data["revenue"]
                                    }
                                    print(f"New SMS: {sms}")
                                    play_notification_sound()
                                    show_notification(sms["number"], sms["message"])
                                    await send_to_telegram(sms)
                                
                                # Update count in JSON
                                for r in existing_ranges:
                                    if r["range_name"] == range_name:
                                        r["count"] = current_count
                                        r["paid"] = range_data["paid"]
                                        r["unpaid"] = range_data["unpaid"]
                                        r["revenue"] = range_data["revenue"]
                                        break
                                existing_ranges_dict[range_name] = range_data
                    
                    # Update existing ranges with any new data
                    existing_ranges = new_ranges
                    existing_ranges_dict = new_ranges_dict
                    save_to_json(existing_ranges, JSON_FILE)
                    
                    # Wait 2-3 seconds before next check
                    await asyncio.sleep(2 + (time.time() % 1))
                
        except Exception as e:
            print(f"Error: {str(e)}. Retrying in 30 seconds...")
            await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(main())

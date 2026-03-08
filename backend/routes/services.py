"""
Payment notification services:
  - M-Pesa STK Push  (Safaricom Daraja API)
  - Africa's Talking SMS
  - WhatsApp deep-link builder
"""
import base64
import urllib.parse
import requests
from datetime import datetime


# ─────────────────────────────────────────────────────────
#  M-PESA STK PUSH
# ─────────────────────────────────────────────────────────

def _mpesa_access_token(consumer_key, consumer_secret, env='sandbox'):
    url = (
        'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
        if env == 'sandbox' else
        'https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
    )
    resp = requests.get(url, auth=(consumer_key, consumer_secret), timeout=10)
    resp.raise_for_status()
    return resp.json()['access_token']


def _mpesa_password(shortcode, passkey):
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    raw = f"{shortcode}{passkey}{timestamp}"
    password = base64.b64encode(raw.encode()).decode()
    return password, timestamp


def send_stk_push(phone, amount, account_ref, description, config):
    """
    Initiate an M-Pesa STK Push to the client's phone.
    Returns (success: bool, message: str, data: dict)
    """
    try:
        # Normalise phone to 254XXXXXXXXX
        phone = str(phone).strip().replace(' ', '').replace('-', '')
        if phone.startswith('0'):
            phone = '254' + phone[1:]
        elif phone.startswith('+'):
            phone = phone[1:]

        consumer_key    = config['MPESA_CONSUMER_KEY']
        consumer_secret = config['MPESA_CONSUMER_SECRET']
        shortcode       = config['MPESA_SHORTCODE']
        passkey         = config['MPESA_PASSKEY']
        callback_url    = config['MPESA_CALLBACK_URL']
        env             = config.get('MPESA_ENV', 'sandbox')

        if not all([consumer_key, consumer_secret, passkey, callback_url]):
            return False, 'M-Pesa credentials not configured. Please contact the system admin.', {}

        token = _mpesa_access_token(consumer_key, consumer_secret, env)
        password, timestamp = _mpesa_password(shortcode, passkey)

        stk_url = (
            'https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest'
            if env == 'sandbox' else
            'https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest'
        )

        payload = {
            "BusinessShortCode": shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(amount),
            "PartyA": phone,
            "PartyB": shortcode,
            "PhoneNumber": phone,
            "CallBackURL": callback_url,
            "AccountReference": account_ref[:12],
            "TransactionDesc": description[:13]
        }

        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }

        resp = requests.post(stk_url, json=payload, headers=headers, timeout=30)
        data = resp.json()

        if data.get('ResponseCode') == '0':
            return True, 'STK push sent! The client should see a payment prompt on their phone.', data
        else:
            msg = data.get('errorMessage') or data.get('ResponseDescription', 'STK push failed')
            return False, msg, data

    except requests.exceptions.Timeout:
        return False, 'Request timed out. Please try again.', {}
    except Exception as e:
        return False, f'STK push error: {str(e)}', {}


# ─────────────────────────────────────────────────────────
#  AFRICA'S TALKING SMS
# ─────────────────────────────────────────────────────────

def send_sms(phone, message, config):
    """
    Send SMS via Africa's Talking.
    Returns (success: bool, message: str)
    """
    try:
        api_key   = config.get('AT_API_KEY', '')
        username  = config.get('AT_USERNAME', 'sandbox')
        sender_id = config.get('AT_SENDER_ID', '')

        if not api_key:
            return False, "Africa's Talking API key not configured."

        # Normalise phone
        phone = str(phone).strip().replace(' ', '').replace('-', '')
        if phone.startswith('0'):
            phone = '+254' + phone[1:]
        elif phone.startswith('254'):
            phone = '+' + phone
        elif not phone.startswith('+'):
            phone = '+254' + phone

        url = (
            'https://api.sandbox.africastalking.com/version1/messaging'
            if username == 'sandbox' else
            'https://api.africastalking.com/version1/messaging'
        )

        headers = {
            'apiKey': api_key,
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json'
        }

        payload = {'username': username, 'to': phone, 'message': message}
        if sender_id:
            payload['from'] = sender_id

        resp = requests.post(url, data=payload, headers=headers, timeout=10)
        data = resp.json()

        recipients = data.get('SMSMessageData', {}).get('Recipients', [])
        if recipients and recipients[0].get('status') == 'Success':
            return True, 'SMS sent successfully!'
        else:
            reason = recipients[0].get('status', 'Unknown error') if recipients else 'No response from API'
            return False, f'SMS failed: {reason}'

    except requests.exceptions.Timeout:
        return False, 'SMS request timed out. Please try again.'
    except Exception as e:
        return False, f'SMS error: {str(e)}'


# ─────────────────────────────────────────────────────────
#  WHATSAPP LINK BUILDER
# ─────────────────────────────────────────────────────────

def build_whatsapp_link(phone, message):
    """Build a wa.me deep link with a pre-filled message."""
    phone = str(phone).strip().replace(' ', '').replace('-', '').replace('+', '')
    if phone.startswith('0'):
        phone = '254' + phone[1:]
    encoded = urllib.parse.quote(message)
    return f"https://wa.me/{phone}?text={encoded}"


# ─────────────────────────────────────────────────────────
#  SHARED MESSAGE BUILDER
# ─────────────────────────────────────────────────────────

def build_payment_message(client_name, business_name, balance, due_date, credit_sales):
    """Build the payment reminder message used for both WhatsApp and SMS."""
    lines = [
        f"Dear {client_name},",
        f"",
        f"This is a payment reminder from {business_name}.",
        f"",
        f"Outstanding Balance: KSh {balance:.2f}",
        f"Due Date: {due_date}",
        f"",
    ]

    if credit_sales:
        lines.append("Credit Sales:")
        for sale in credit_sales:
            date_str = sale['date'].strftime('%d %b %Y') if sale.get('date') else 'Unknown'
            lines.append(f"  {date_str}: KSh {sale.get('total_amount', 0):.2f}")
        lines.append("")

    lines.append("Please settle your balance at your earliest convenience.")
    lines.append("Thank you for your business.")

    return "\n".join(lines)
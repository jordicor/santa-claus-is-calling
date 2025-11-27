import re
import sys
import pytz
import atexit
import random
import bcrypt
import sqlite3
import smtplib
import requests
import traceback
import subprocess
import os, json, uuid, time 
import paypal_sandbox as paypal
from dateutil import tz
from pytz import timezone
from openai import OpenAI
from functools import wraps
from markupsafe import Markup
from twilio.rest import Client
from dotenv import load_dotenv
from flask import abort, jsonify
from datetime import datetime, timedelta
from itsdangerous import URLSafeTimedSerializer
from flask import Flask, flash, get_flashed_messages, request, render_template,render_template_string, redirect, url_for, session, g, has_request_context
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

app = Flask(__name__)

if 'cloudflare' in sys.argv:
    @app.before_request
    def require_cloudflare_origin():
        if 'X-Origin' not in request.headers or request.headers['X-Origin'] != 'CloudFlare-SantaClausApp':
            abort(401)  # Access only allowed via Cloudflare

load_dotenv()
timezones = pytz.all_timezones
# Configure the app to use secure sessions
app.config['SESSION_COOKIE_SECURE'] = True  # Ensures that cookies are only transmitted over HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Ensures that cookies are not accessible via JS
app.config['REMEMBER_COOKIE_HTTPONLY'] = True  # Specific to Flask-Login, makes the "remember me" cookie also HttpOnly
app.config['REMEMBER_COOKIE_SECURE'] = True  # Ensures that the "remember me" cookie is only transmitted over HTTPS

# Declaring global variables for platforms
account_sid = os.getenv('TWILIO_SID')
auth_token = os.getenv('TWILIO_AUTH') 
client = Client(account_sid, auth_token)
clientAI = os.getenv("OPENAI_KEY")
service_sid = os.getenv('SERVICE_SID')
app.secret_key = os.getenv('APP_SECRET_KEY')
app.salt = os.getenv('SECURITY_PASSWORD_SALT')
twilio_number = os.getenv('TWILIO_NUMBER')
paypal_client_id_sandbox = os.getenv('PAYPAL_CLIENT_ID_SANDBOX')
paypal_client_secret_sandbox = os.getenv('PAYPAL_CLIENT_SECRET_SANDBOX')
postmark_server_token = os.getenv('POSTMARK_SERVER_TOKEN')
pepper = os.getenv('PEPPER')
dbname = os.getenv('DATABASE')
# Internal communication with austin-to-santa.py via HTTP (faster than HTTPS for localhost)
fastapi_schedule_url = "http://localhost:7778/schedule-call"
fastapi_cancel_url = "http://localhost:7778/cancel-call"
default_lang = "en"
qr_data = f"tel:{twilio_number}"  


def handle_language(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if has_request_context():
            lang = request.args.get('lang', session.get('lang', default_lang))
            session['lang'] = lang
        else:
            lang = default_lang

        strings_data = load_strings_data(lang)
        return f(strings_data, *args, **kwargs)
    return decorated_function


def load_strings_data(lang):
    try:
        with open(f'templates/lang/{lang}.json', 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {} 
        
        
def generate_token(user_id):
    serializer = URLSafeTimedSerializer(app.secret_key)
    return serializer.dumps(user_id, salt=app.salt)

def verify_token(token, expiration=3600):
    serializer = URLSafeTimedSerializer(app.secret_key)
    try:
        user_id = serializer.loads(
            token,
            salt=app.salt,
            max_age=expiration
        )
    except:
        return False
    return user_id

def get_db_connection():
    conn = sqlite3.connect(dbname, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

@app.teardown_appcontext
def close_connection(exception):
    pass

def hash_code(verify_code):
    code_peppered = verify_code + pepper
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(code_peppered.encode(), salt)

def hash_password(user_password):
    if isinstance(user_password, bytes):
        user_password = user_password.decode('utf-8')
    user_password_peppered = user_password + pepper
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(user_password_peppered.encode('utf-8'), salt)
    return hashed_password

def check_password(provided_password, stored_password):
    provided_password_peppered = provided_password + pepper
    provided_password_peppered_encoded = provided_password_peppered.encode('utf-8')
    
    return bcrypt.checkpw(provided_password_peppered_encoded, stored_password)

@app.errorhandler(404)
@handle_language
def not_found_error(strings_data, error):
    return render_template('error.html',**strings_data, error_code = 404, error_message=strings_data['error404']), 404

@app.errorhandler(403)
@handle_language
def forbidden_error(strings_data, error):
    return render_template('error.html',**strings_data,error_code = 403, error_message=strings_data['error403']), 403

@app.errorhandler(500)
@handle_language
def internal_error(strings_data, error):
    return render_template('error.html',**strings_data,error_code = 500, error_message=strings_data['error500']), 500
@app.context_processor
def inject_strings_data():
    lang = session.get('lang', 'en')  
    strings_data = load_strings_data(lang) 
    return dict(strings_data=strings_data)

@app.route('/')
@handle_language
def index(strings_data):
    timezones = pytz.all_timezones
    user_details = None
    if 'user_authenticated' in session and session['user_authenticated']:
        user_id = session.get('user_id')
        if user_id:
            try:
                auto_cancel_past_call(user_id)
            except Exception as e:
                app.logger.warning(f"auto_cancel_past_call in index failed: {e}")

            conn = get_db_connection()
            try:
                cursor = conn.cursor()
                query =  '''
                            SELECT ud.child_name, c.call_date, c.call_time, ud.phone_number, c.call_job_id
                            FROM user_details ud
                            JOIN calls c ON ud.user_id = c.user_id
                            WHERE ud.user_id = ?
                            '''
                cursor.execute(query, (user_id,))
                user_details = cursor.fetchone()
                print(user_details)
            finally:
                conn.close()
    return render_template('index.html', timezones=timezones, user_details=user_details, **strings_data)


@app.route('/get_current_time', methods=['GET'])
def get_current_time():
    user_timezone = request.headers.get('X-Timezone')
    if user_timezone:
        try:
            tz = timezone(user_timezone)
            current_time = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            return jsonify({'error': str(e)}), 400
    else:
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return jsonify({'current_time': current_time})

@app.route('/load_next_step')
@handle_language
def load_next_step(strings_data):
    step = request.args.get('step', type=int)
    form_id = request.args.get('formId')
    steps_content = {
        'formulario1': {
            2: '''<div class="campo-formulario" id="campo2" style="display:none;"><div class="input-button-container"><button type="button" class="boton-anterior" onclick="showPreviousField(2, 1)">{{ btn_back}}</button><div class="input-container"><div class="input-group"><textarea id="gifts" name="regalos" required placeholder="{{ placeholder_gifts }}" class="textarea-formulario form-control"></textarea><button type="button" class="boton-ayuda" onclick="toggleModal()">?</button></div></div><div class="next-back"><button type="button" class="boton-siguiente" onclick="showNextField(2, 'formulario1')">{{ btn_next }}</button></div></div><span class="mensaje-error" id="error-gifts"></span></div>''',
            3: '''<div class="campo-formulario" id="campo3" style="display:none;"><div class="input-button-container"><button type="button" class="boton-anterior" onclick="showPreviousField(3, 1)">{{ btn_back}}</button><div class="input-group"><select id="time_zone" name="time_zone" required class="select-formulario form-control"><option value="">{{ select_timezone_option }}</option>{% for timezone in timezones %}<option value="{{ timezone }}">{{ timezone }}</option>{% endfor %}</select><!-- Botón de Ayuda --><button type="button" class="boton-ayuda-raros" onclick="toggleModal()">?</button></div><div class="next-back"><button type="button" class="boton-siguiente" onclick="showNextField(3, 'formulario1')">{{ btn_next }}</button></div></div><span class="mensaje-error" id="error-time_zone"></span></div><script src="/static/js/updateTimeDate.js"></script>''',
            4: '''<div class="campo-formulario" id="campo4" style="display:none;"><div class="input-button-container"><button type="button" class="boton-anterior" onclick="showPreviousField(4, 1)">{{ btn_back}}</button><div class="input-container"><div class="input-group"><input type="date" id="call_date" name="call_date" required class="input-formulario"><!-- Botón de Ayuda --><button type="button" class="boton-ayuda-raros" onclick="toggleModal()">?</button></div></div><div class="next-back"><button type="button" class="boton-siguiente" onclick="showNextField(4, 'formulario1')">{{ btn_next }}</button></div></div><span class="mensaje-error" id="error-call_date"></span></div>''',
            5: '''<div class="campo-formulario" id="campo5" style="display:none;"><div class="input-button-container"><button type="button" class="boton-anterior" onclick="showPreviousField(5, 1)">{{ btn_back}}</button><div class="input-container"><div class="input-group"><input type="time" id="call_time" name="call_time" required class="input-formulario"><!-- Botón de Ayuda --><button type="button" class="boton-ayuda-raros" onclick="toggleModal()">?</button></div></div><div class="next-back"><button type="button" class="boton-siguiente" onclick="showNextField(5, 'formulario1')">{{ btn_next }}</button></div></div><span class="mensaje-error" id="error-call_time"></span></div>''',
            6: '''<div class="campo-formulario" id="campo6" style="display:none;"><div class="input-button-container"><button type="button" class="boton-anterior" onclick="showPreviousField(6, 1)">{{ btn_back}}</button><div class="input-container"><div class="input-group"><select id="lang" name="lang" required class="select-formulario"><option value="">{{ select_language_option }}</option><option value="es">{{ option_spanish }}</option><option value="en">{{ option_english }}</option><option value="fr">{{ option_french }}</option><option value="bg">{{ option_bulgarian }}</option><option value="cs">{{ option_czech }}</option><option value="da">{{ option_danish }}</option><option value="nl">{{ option_dutch }}</option><option value="tl">{{ option_filipino }}</option><option value="hr">{{ option_croatian }}</option><option value="it">{{ option_italian }}</option><option value="ja">{{ option_japanese }}</option><option value="ko">{{ option_korean }}</option><option value="de">{{ option_german }}</option><option value="pl">{{ option_polish }}</option><option value="pt">{{ option_portuguese }}</option><option value="ro">{{ option_romanian }}</option><option value="ru">{{ option_russian }}</option><option value="sk">{{ option_slovak }}</option><option value="sv">{{ option_swedish }}</option><option value="el">{{ option_greek }}</option><option value="uk">{{ option_ukrainian }}</option><option value="fi">{{ option_finnish }}</option></select><!-- Botón de Ayuda --><button type="button" class="boton-ayuda-raros" onclick="toggleModal()">?</button></div></div><div class="next-back"><button type="button" class="boton-siguiente" onclick="showNextField(6, 'formulario1')">{{ btn_next }}</button></div></div><span class="mensaje-error" id="error-lang"></span></div>''',
            7: '''<div class="campo-formulario" id="campo7" style="display:none;"><div class="input-button-container"><button type="button" class="boton-anterior" onclick="showPreviousField(7, 1)">{{ btn_back}}</button><div class="input-container"><div class="input-group"><input type="text" id="email" name="email" required placeholder="{{ mail_placeholder }}" class="input-formulario"><!-- Botón de Ayuda --><button type="button" class="boton-ayuda" onclick="toggleModal()">?</button></div></div><div class="next-back"><button type="submit" id="boton-enviar" class="boton-enviar">{{ btn_send }}</button></div></div><span class="mensaje-error" id="error-email"></span></div><script>initializeEmailForm();</script>''',
        },
        'formulario2': {
            2: '''<div class="campo-formulario" id="campo2" style="display:none;">
                <div class="input-button-container">
                    <button type="button" class="boton-anterior" onclick="showPreviousField(2, 2)">{{ btn_back}}</button>
                    <div class="input-container"> 
                        <div class="input-group">  
                            <input type="tel" id="phone_number" name="phone_number" required placeholder="{{ phone_number_placeholder }}" class="input-formulario">
                            <button type="button" class="boton-ayuda" onclick="toggleModal()">?</button>
                        </div>
                    </div>
                    <div class="next-back">
                        <button type="button" class="boton-siguiente" onclick="showNextField(2, 'formulario2')">{{ btn_next }}</button>
                        </div>>
                </div>
                <span class="mensaje-error" id="error-phone_number"></span>
            </div>''',
            3: '''<div class="campo-formulario" id="campo3" style="display:none;">
                <div class="input-button-container">
                    <button type="button" class="boton-anterior" onclick="showPreviousField(3, 2)">{{ btn_back}}</button>
                    <div class="input-container">
                        <div class="input-group">  
                            <input type="text" id="father_name" name="father_name" required placeholder="{{ placeholder_father_name }}" class="input-formulario">
                            <button type="button" class="boton-ayuda" onclick="toggleModal()">?</button>
                        </div>
                    </div>
                    <div class="next-back">
                    <button type="button" class="boton-siguiente" onclick="showNextField(3, 'formulario2')">{{ btn_next }}</button>
                    </div>
                </div>
                <span class="mensaje-error" id="error-father_name"></span>
            </div>''',
            4: ''' <div class="campo-formulario" id="campo4" style="display:none;">
                <div class="input-button-container">
                    <button type="button" class="boton-anterior" onclick="showPreviousField(4, 2)">{{ btn_back}}</button>
                    <div class="input-container">
                        <div class="input-group">  
                            <input type="text" id="mother_name" name="mother_name" required placeholder="{{ mother_name_placeholder }}" class="input-formulario">
                            <button type="button" class="boton-ayuda" onclick="toggleModal()">?</button>
                        </div>
                    </div>
                    <div class="next-back">
                        <button type="button" class="boton-siguiente" onclick="showNextField(4, 'formulario2')">{{ btn_next }}</button>
                        </div>
                </div>
                <span class="mensaje-error" id="error-mother_name"></span>
                </div>''',
            5: '''<div class="campo-formulario" id="campo5" style="display:none;">
                    <div class="input-button-container">
                        <button type="button" class="boton-anterior" onclick="showPreviousField(5, 2)">{{ btn_back}}</button>
                        
                        <div class="input-container">
                            <div class="input-group">  
                                <textarea id="context" name="contexto" placeholder="{{ textarea_placeholder }}" class="textarea-formulario"></textarea>
                                <button type="button" class="boton-ayuda" onclick="toggleModal()">?</button>
                            </div>
                        </div>
                        <div class="next-back">
                            <button type="button" class="boton-siguiente" onclick="showNextField(5, 'formulario2')">{{ btn_next }}</button>
                        </div>
                    </div>
                    <span class="mensaje-error" id="error-context"></span>
                </div>''',
            6: '''<div class="campo-formulario" id="campo6" style="display:none;">
                    <div class="input-button-container">
                        <button type="button" class="boton-anterior" onclick="showPreviousField(6, 2)">{{ btn_back}}</button>
                        <div class="input-group">  
                            <select id="time" name="time" required class="select-formulario">
                                <option value="">{{ select_call_duration }}</option>
                                <option value="300">{{ option_5_dollars }}</option>
                                <option value="600">{{ option_8_dollars }}</option>
                                <option value="1800">{{ option_30_min }}</option>
                            </select>
                            <button type="button" class="boton-ayuda-raros" onclick="toggleModal()">?</button>
                        </div>
                        <div class="next-back">
                            <button type="submit" class="boton-enviar">{{ btn_send }}</button>
                            </div>
                    </div>
                    <span class="mensaje-error" id="error-time_zone"></span>
                </div>''',
        }
    }

    html_content = steps_content.get(form_id, {}).get(step, '')
    rendered_html = render_template_string(html_content, timezones=timezones, **strings_data)

    return jsonify({'html': rendered_html})



@app.route('/get-session-data', methods=['GET'])
def get_session_data():
    print("SESSION_DATA")
    data = {}
    data['time'] = session.get('time', 'n/a')
    print(f"time: {data['time']}")    
    
    data['call_date'] = session.get('call_date', 'n/a')
    data['call_time'] = session.get('call_time', 'n/a')
    data['time_zone'] = session.get('time_zone', 'n/a')
    return jsonify(data)    
   
@app.route('/check-email')
def check_email():
    email = request.args.get('email').lower()
    if email: 
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("Select * FROM users WHERE email = ?", (email,))
        usuario_existente = cursor.fetchone()
        conn.close()
        if usuario_existente:
            return jsonify({'exists': True})
        else:
            return jsonify({'exists': False})

@app.route('/get-payment-data', methods=['GET'])
@handle_language
def get_payment_data(strings_data):
    user_id = session.get('user_id')
    data = {
        'time': session.get('time', 'n/a')
    }
    if not user_id:
        return strings_data['user_not_found'], 404

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute('''
        SELECT call_date, call_time, time_zone
        FROM calls
        WHERE user_id = ?
        ''', (user_id,)).fetchone()
        if row:
            
            data.update({
                'call_date': row['call_date'],
                'call_time': row['call_time'],
                'time_zone': row['time_zone']
            })
            return jsonify(data)
        else:
            return {'error': 'Payment details not found'}, 404
    finally:
        conn.close()

@app.route('/payment', methods=['GET', 'POST'])
@handle_language
def payment(strings_data):
    lang = request.args.get('lang')
    time = request.args.get('time')
    print(session, "Payment")
    allowed_values = [300, 600, 1800]

    if time:
        try:
            session['time'] = time
            timer_value = int(time)
        except ValueError:

            return render_template('error.html', error_code=400, error_message=strings_data['time_to_buy_error']), 400

        if timer_value not in allowed_values:
            return render_template('error.html', error_code=400, error_message=strings_data['time_to_buy_error']), 400

        session['time'] = timer_value

    return render_template('payment.html', paypal_client_id=paypal_client_id_sandbox, **strings_data)

@app.route('/payment-success', methods=['POST'])
@handle_language
def payment_success(strings_data):
    print("Entering payment-success")
    data = request.get_json()
    order_id = data['orderID']
    timer_value = int(session.get('time', '0')) 
    allowed_values = [300, 600, 1800]
    print(f"timer_value from session: '{timer_value}'")
    if timer_value not in allowed_values:
        print("Timer value not allowed")
        return render_template('error.html', error_code=400, error_message=strings_data['time_to_buy_error']), 400
    else:
        timer_value = int(timer_value)
        access_token = paypal.get_paypal_access_token(paypal_client_id_sandbox, paypal_client_secret_sandbox)
        transaction_details = paypal.verify_paypal_transaction(access_token, order_id)

        if transaction_details.get('status') == 'COMPLETED':
            session['payment_verified'] = True
            discount_code = session.get('discount_code')
            if discount_code:
                conn = get_db_connection()
                cur = conn.cursor()
                
                cur.execute("SELECT usage_count, unlimited_usage FROM discounts WHERE code = ?", (discount_code,))
                discount_info = cur.fetchone()
                
                if discount_info and not discount_info[1]:
                    if discount_info[0] and discount_info[0] > 0:
                        new_uses = discount_info[0] - 1
                        cur.execute("UPDATE discounts SET usage_count = ? WHERE code = ?", (new_uses, discount_code))
                        conn.commit()
                    elif discount_info[0] == 0:
                        pass
                
            phone_number = session.get('phone_number')
            user_id = session.get('user_id')
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT verification_code, timer FROM calls WHERE user_id = ?", (user_id,))
            user_data = cursor.fetchone()
            if user_data:
                verify_code, timer = user_data
                if verify_code:
                    new_timer = int(timer) + timer_value
                    cursor.execute("UPDATE calls SET timer = ? WHERE user_id = ?", (new_timer, user_id))
                    conn.commit()
                    conn.close()
                    flash(strings_data["added_balance"], 'success')
                    return url_for('get_user')
                else:
                    cursor.execute("UPDATE calls SET timer = ? WHERE user_id = ?", (timer_value, user_id))
                    conn.commit()
                    conn.close()
                    print(f"add {timer_value} seconds after registration")
                    flash(strings_data["added_balance_sms"], 'success')
                    if phone_number:
                        client.verify.v2.services(service_sid).verifications.create(to=phone_number, channel='sms')
                    return url_for('verify')
            else:
                conn.close()
                return render_template('error.html', error_code=404, error_message=strings_data['user_not_found']), 404
        else:
            return render_template('error.html', error_code=400, error_message=strings_data['payment_failed']), 400

@app.route('/payment-success-simulated', methods=['POST'])
@handle_language
def payment_success_simulated(strings_data):
    print("Entering simulated")
    session['payment_verified'] = True
    user_id = session.get('user_id')
    phone_number = session.get('phone_number')
    timer_value = session.get('time', '0')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT verification_code, timer FROM calls WHERE user_id = ?", (user_id,))
    user_data = cursor.fetchone()
    print(f"timer_value: {timer_value}")
    if user_data:
        verify_code, timer = user_data
        print("user data", user_data)
        if verify_code:
            new_timer = int(timer) + timer_value
            cursor.execute("UPDATE calls SET timer = ? WHERE user_id = ?", (new_timer, user_id))
            conn.commit()
            conn.close()
            flash(strings_data["added_balance"], 'success')
            return jsonify({'redirectUrl': url_for('get_user')}) 
        else:
            cursor.execute("UPDATE calls SET timer = ? WHERE user_id = ?", (timer_value, user_id))
            conn.commit()
            conn.close()
            print(f"Added {timer_value} seconds after registration")
            flash(strings_data["added_balance_sms"], 'success')
            if phone_number:
                client.verify.v2.services(service_sid).verifications.create(to=phone_number, channel='sms')
            return jsonify({'redirectUrl': url_for('verify')})
    else:
        conn.close()
        return render_template('error.html', error_code=404, error_message=strings_data['user_not_found']), 404
 
def determinate_base_price(timer_value):
    price = {
        '300': 5.00,
        '600': 8.00,
        '1800': 15.00,
    }
    return price.get(str(timer_value), 15.00)

@app.route('/apply-discount', methods=['POST'])
@handle_language
def apply_discount(strings_data):
    timer_value = session.get('time', '0')
    user_id = session.get('user_id')
    data = {}
    print(timer_value)
    code = request.form.get('discount_code')
    conn = get_db_connection()
    cur = conn.cursor()
    print(code) 
    cur.execute("SELECT discount_value, active, usage_count, validity_date, unlimited_usage, unlimited_validity FROM discounts WHERE code = ?", (code,))
    discount = cur.fetchone()
    conn.row_factory = sqlite3.Row
    row = conn.execute('''
        SELECT call_date, call_time, time_zone
        FROM calls
        WHERE user_id = ?
        ''', (user_id,)).fetchone()
    if row:
        data.update({
            'call_date': row['call_date'],
            'call_time': row['call_time'],
            'time_zone': row['time_zone']
        })
    conn.close()
    base_price = determinate_base_price(timer_value)
    print(base_price)
    if discount and discount[1]:
        current_date = datetime.now().date()
        
        if not discount[5]:  # If it does not have unlimited validity
            expiration_date = datetime.strptime(discount[3], '%Y-%m-%d').date()
            if current_date > expiration_date:
                return jsonify({'success': False, 'message': strings_data['discount_code_expired']}), 400

        if not discount[4] and discount[2] <= 0:  # If it does not have unlimited uses and the number of uses is 0 or less
            return jsonify({'success': False, 'message': strings_data['discount_code_depleted']}), 400
        else:
            session['discount_code'] = code
            discount_percent = discount[0] / 100.0
            apply_discount = base_price * discount_percent
            new_price = max(base_price - apply_discount, 0)
            session['discount_price'] = new_price
            data.update({
                'success': True, 
                'newPrice': new_price, 
                'timer': timer_value,
            })
            return jsonify(data)
    else:
        return jsonify({'success': False, 'message': strings_data['invalid_discount_code']}), 400

@app.route('/confirm', methods=['GET', 'POST'])
@handle_language
def confirm(strings_data):
    return render_template('confirm.html', **strings_data)

@app.route('/verify', methods=['GET', 'POST'])
@handle_language
def verify(strings_data):
    return render_template('verify.html', **strings_data)

def text_moderation(text):
    response = requests.post(
            "https://api.openai.com/v1/moderations",
            headers={
                "Authorization": f"Bearer {clientAI}",
                "Content-Type": "application/json",
            },
            data=json.dumps({
                "input": text
            })
        )

    moderation_response = response.json()
    #print(f"Moderation response: {moderation_response}")
    if 'results' in moderation_response and isinstance(moderation_response['results'], list):
        return moderation_response
    else:
        print("Error receiving moderation results")
        return render_template('error.html', error_code=500, error_message=strings_data['error500']), 500
        

@app.route('/start-verification', methods=['POST'])
@handle_language
def start_verification(strings_data):
    session['form_data'] = request.form.to_dict()

    print("START VERIFICATION")

    session['call_date'] = request.form['call_date']
    print(f"call_date: {session['call_date']}")

    session['call_time'] = request.form['call_time']
    print(f"call_time: {session['call_time']}")

    session['time_zone'] = request.form['time_zone']
    print(f"time_zone: {session['time_zone']}")

    session['lang'] = request.form['lang']
    print(f"lang: {session['lang']}")
    
    child_name = request.form['child_name']
    gifts = request.form['regalos']
    call_date = request.form['call_date']
    call_time = request.form['call_time']
    time_zone = request.form['time_zone']
    lang = request.form['lang']
    email = request.form['email'].lower()
    moderate_text = f"{child_name} , {gifts} , {email} , {call_date} , {call_time} , {time_zone} , {lang}"
    moderation_response = text_moderation(moderate_text)
    first_result = moderation_response['results'][0]
    if first_result['flagged'] == False:
        try:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute('''
            INSERT INTO users (email, lang, password, role_id)
            VALUES (?, ?, NULL, 2)
            ''', (email, lang))
            user_id = c.lastrowid
            
            c.execute('''
            INSERT INTO user_details (user_id, child_name, gifts)
            VALUES (?, ?, ?)
            ''', (user_id, child_name, gifts))
            
            c.execute('''
            INSERT INTO calls (user_id, call_date, call_time, time_zone)
            VALUES (?, ?, ?, ?)
            ''', (user_id, call_date, call_time, time_zone))
            
            conn.commit()
            session['user_id'] = user_id
            print("Successful registration")
            confirmation_link = create_user_token(user_id, "register")

            #send_confirmation_email(email, confirmation_link)
            print(confirmation_link)
            conn.close()
            return render_template('mail.html', **strings_data)
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            if conn:
                conn.close()
            return render_template('error.html', error_code=500, error_message=strings_data['error500']), 500
    else:
        print(f"Potentially malicious content detected: {moderate_text}")
        return render_template('error.html', error_code=400, error_message=strings_data['malicious_text']), 400
    

def create_user_token(user_id, url_path):
    token = generate_token(user_id)

    # Get the scheme (http or https) and host from the request
    scheme = request.scheme
    host = request.headers['Host']
    return f'{scheme}://{host}/{url_path}/{token}' # Returns http/s + domain + path + token


def send_confirmation_email(user_email, confirmation_link):
    url = "https://api.postmarkapp.com/email"
    postmark_token = os.getenv("POSTMARK_SERVER_TOKEN")
    from_email = os.getenv("EMAIL_FROM", "noreply@yourdomain.com")

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Postmark-Server-Token": postmark_token
    }
    data = {
        "From": from_email,
        "To": user_email,
        "Subject": "Verify your email",
        "HtmlBody": f"<html><body>Hello,<br><br>Thank you for registering. Please confirm your registration by visiting the following link:<br><a href='{confirmation_link}'>{confirmation_link}</a><br><br>If you have not requested this registration, please ignore this email.<br><br>Greetings,<br>SantaClaus App</body></html>",
        "MessageStream": "outbound"
    }

    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 200:
        print("Email send successfully")
        return True
    else:
        print(f"Error sending email: {response.status_code} - {response.text}")
        return False


@app.route('/register/<token>')
@handle_language
def complete_registration(strings_data, token):
    user_id = verify_token(token, 86400)
    if user_id:
        return render_template('complete_user.html', token=token, **strings_data)
    else:
        return render_template('error.html', error_code=400, error_message=strings_data['invalid_token']), 400

@app.route('/process-register', methods=['POST'])
@handle_language
def process_register(strings_data):
    token = request.form['token']
    password = request.form['password']
    confirm_password = request.form['confirm_password']
    father_name = request.form['father_name']
    mother_name = request.form['mother_name']
    phone_number = request.form['phone_number']
    context = request.form['contexto']
    time = request.form['time']
    timer_value = request.form['time']

    # Verify token and get the user_id
    user_id = verify_token(token, 86400)
    session['user_id'] = user_id
    print(user_id)
    if not user_id:
        return render_template('error.html', error_code=400, error_message=strings_data['invalid_token']), 400

    if timer_value not in ['300', '600', '1800']:
        return render_template('error.html', error_code=400, error_message=strings_data['time_to_buy_error']), 400

    if password != confirm_password:
        return render_template('error.html', error_code=400, error_message=strings_data['password_mismatch']), 400
    moderate_text = f"{father_name} , {mother_name} , {phone_number} , {context} , {time} , {timer_value}"
    moderation_response = text_moderation(moderate_text)
    first_result = moderation_response['results'][0]
    if first_result['flagged'] == False:
        try:
            password= hash_password(password)
            conn = get_db_connection()
            c = conn.cursor()

            c.execute('''
            UPDATE users
            SET password = ?
            WHERE id = ?
            ''', (password, user_id))

            c.execute('''
            UPDATE user_details
            SET father_name = ?, mother_name = ?, phone_number = ?, context = ?
            WHERE user_id = ?
            ''', (father_name, mother_name, phone_number, context, user_id))
            
            session['time'] = time
            session['phone_number'] = phone_number
            conn.commit()
            conn.close()
            print(session,"Registration completed")
            return redirect(url_for('payment'))
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            if conn:
                conn.close()
            return render_template('error.html', error_code=500, error_message=strings_data['error500']), 500

    else:
        print(f"Potentially malicious content detected: {moderate_text}")
        return render_template('error.html', error_code=400, error_message="Inappropriate content detected"), 400

@app.route('/verify-code', methods=['POST'])
@handle_language
def verify_code(strings_data):
    global fastapi_url
    phone_number = session['phone_number']
    print(phone_number)
    verification_code = request.form['verification_code']
    verification_check = client.verify.v2.services(service_sid).verification_checks.create(to=phone_number, code=verification_code)

    if verification_check.status == 'approved':
        session['user_authenticated'] = True            
        user_id = session.get('user_id')
        try:
            conn = get_db_connection()
            c = conn.cursor()
            
            c.execute('''
            UPDATE calls
            SET verification_code = ?
            WHERE user_id = ?
            ''', (verification_code, user_id))
            conn.commit()
            data = {
                'user_id': user_id,
            }
            headers = {'Content-Type': 'application/json'}
            response = requests.post(fastapi_schedule_url, json=data, headers=headers, verify=False)
            if response.status_code == 200:
                print("Call scheduled successfully")
            else:
                print("Error scheduling the call", response.text)
            user_url = f"/user"
            conn.close()
            session["verify_code"]= verification_code
            return render_template('confirm.html', 
                                    verified=True, 
                                    verify_code=verification_code, 
                                    user_url=user_url, 
                                    **strings_data
                                    )

        except Exception as e:
            traceback.print_exc()
            print(f"Error inserting data into database: {e}")
            return render_template('error.html', error_code=500, error_message=strings_data['error500']), 500

    else:
        session.pop('user_authenticated', None)  # Remove the variable if authentication fails
        return render_template('confirm.html', verified=False, **strings_data)
        
        
@app.route('/logout')
def logout():
    session.pop('user_authenticated', None)
    session.pop('user_id', None)
    return redirect(url_for('index'))

@app.route('/user', methods=['GET', 'POST'])
@handle_language
def get_user(strings_data):
    if request.method == 'POST':
        mail = request.form['mail'].lower()
        password = request.form['password']
        conn = get_db_connection()
        try:
            c = conn.cursor()
            c.execute("SELECT id, password FROM users WHERE email=?", (mail,))
            user = c.fetchone()
            
            if user and check_password(password, user[1]):
                session['user_authenticated'] = True
                session['user_id'] = user[0]
                session['user_mail'] = mail
                return redirect(url_for('get_user'))
            else:
                time.sleep(2)
                flash(strings_data["auth_failed"], 'warning')
                return render_template('login.html', error=strings_data["auth_failed"], **strings_data)
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return render_template('error.html', error_code=500, error_message=strings_data['error500']), 500
        finally:
            conn.close()
    
    if 'user_authenticated' in session and session['user_authenticated']:
        user_id = session.get('user_id')
        if user_id:
            return load_and_display_user_info(user_id, strings_data)
    
    return render_template('login.html', **strings_data)

def load_and_display_user_info(user_id, strings_data):
    try:
        auto_cancel_past_call(user_id)
    except Exception as e:
        app.logger.warning(f"auto_cancel_past_call in user page failed: {e}")

    conn = get_db_connection()
    try:
        c = conn.cursor()
        
        c.execute("SELECT lang FROM users WHERE id=?", (user_id,))
        user_data = c.fetchone()
        columns_user = [column[0] for column in c.description]
        c.execute("SELECT * FROM user_details WHERE user_id=?", (user_id,))
        details_data = c.fetchone()
        columns_details = [column[0] for column in c.description] 
        c.execute("SELECT * FROM calls WHERE user_id=?", (user_id,))

        call_data = c.fetchone()
        columns_call = [column[0] for column in c.description]
        user = {}

        if user_data:
            user = dict(zip(columns_user, user_data))
        if details_data:
            details = dict(zip(columns_details, details_data))
            user.update(details)  
        if call_data:
            call = dict(zip(columns_call, call_data))
            user.update(call)  

        if user:
            timezones = pytz.all_timezones
            return render_template('user.html', user=user, timezones=timezones, **strings_data)
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return render_template('error.html', error_code=500, error_message=strings_data['error500']), 500
    finally:
        conn.close()
    return render_template('default_template.html', **strings_data)    

@app.route('/update-user', methods=['POST'])
@handle_language
def update_user(strings_data):
    global fastapi_url
    if 'user_authenticated' not in session or 'user_id' not in session:
        return render_template('error.html', error_code=403, error_message=strings_data['error403']), 403
    
    child_name = request.form['child_name']
    father_name = request.form['father_name']
    mother_name = request.form['mother_name']
    phone_number = request.form['phone_number']
    gifts = request.form['gifts']
    call_date = request.form.get('call_date', '')
    call_time = request.form.get('call_time', '')
    time_zone = request.form.get('time_zone', '')
    context = request.form['context']
    lang = request.form['lang']

    moderate_text = f"{child_name} , {gifts} , {call_date} , {call_time} , {time_zone} , {lang} , {context}"
    response_moderation = text_moderation(moderate_text)
    first_result = response_moderation['results'][0]
    if first_result['flagged'] == False:

        user_id = session['user_id']
        
        conn = get_db_connection()  
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute("SELECT call_date, call_time, time_zone, call_job_id FROM calls WHERE user_id = ?", (user_id,))
        current_call = c.fetchone()

        date_time_changed = (current_call and (call_date != current_call['call_date'] or
                                               call_time != current_call['call_time'] or
                                               time_zone != current_call['time_zone']))
        if date_time_changed:
            old_job_id = current_call['call_job_id']
            if old_job_id:
                try:
                    cancel_call(user_id)
                except JobLookupError:
                    c.execute('UPDATE calls SET call_job_id = NULL WHERE user_id = ?', (user_id,))
                    conn.commit()

        call_datetime_str = f"{call_date} {call_time}"
        try:
            call_datetime = datetime.strptime(call_datetime_str, "%Y-%m-%d %H:%M")
            user_tz = pytz.timezone(time_zone)
            user_datetime = user_tz.localize(call_datetime)
            current_datetime = datetime.now(pytz.utc).astimezone(user_tz)
            is_future_datetime = user_datetime > current_datetime
        except ValueError:
            is_future_datetime = False

        try:
            c.execute('UPDATE users SET lang = ? WHERE id = ?', (lang, user_id))
            c.execute(
                'UPDATE user_details SET child_name = ?, father_name = ?, mother_name = ?, phone_number = ?, gifts = ?, context = ? WHERE user_id = ?',
                (child_name, father_name, mother_name, phone_number, gifts, context, user_id)
            )
            c.execute(
                'UPDATE calls SET call_date = ?, call_time = ?, time_zone = ? WHERE user_id = ?',
                (call_date, call_time, time_zone, user_id)
            )
            conn.commit()

            if is_future_datetime and date_time_changed and phone_number:
                data = {'user_id': user_id}
                headers = {'Content-Type': 'application/json'}
                response = requests.post(fastapi_schedule_url, json=data, headers=headers, verify=True)
                if response.status_code == 200:
                    print("Call scheduled successfully")
                else:
                    print("Error scheduling the call", response.text)
                    return response.text
        except sqlite3.Error as e:
            app.logger.error(f"Database error: {e}")
            return render_template('error.html', error_code=500, error_message=strings_data['error500']), 500
        finally:
            conn.close()

        flash(strings_data["profile_updated_success_msg"], 'success')
        return redirect(url_for('get_user'))

    else:
        print(f"Potentially malicious content detected: {moderate_text}")
        return render_template('error.html', error_code=400, error_message=strings_data['malicious_text']), 400
    
@app.route('/delete-user', methods=['DELETE'])
@handle_language
def delete_user(strings_data):
    if 'user_authenticated' not in session or 'user_id' not in session:
        return jsonify({'error_code': 403, 'error_message': strings_data['error403']}), 403

    user_id = session['user_id']        
        
    try:
        conn = get_db_connection()
        conn.execute('DELETE FROM user_details WHERE user_id = ?', (user_id,))
        conn.execute('DELETE FROM calls WHERE user_id = ?', (user_id,))
        conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
    except sqlite3.Error as e:
        app.logger.error(f"Database error: {e}")
        return render_template('error.html', error_code=500, error_message=strings_data['error500']), 500
    finally:
        conn.close()

    session.pop('user_authenticated', None)

    return jsonify({'success': True, 'message': strings_data['user_deleted']})


@app.route('/cancel-call', methods = ['POST'])
@handle_language
def cancel_call(strings_data, user_id = None):
    # If user_id is not provided, try to get it from the session
    if user_id is None:
        user_id = session.get('user_id')
    
    if not user_id:
        return jsonify({'error': strings_data['user_not_found']}), 404
    
    data = {'user_id': user_id}
    headers = {'Content-Type': 'application/json'}
    
    try:
        response = requests.post(fastapi_cancel_url, json=data, headers=headers, verify=True)
        if response.status_code == 200:
            # Also cleans the job_id locally
            conn = get_db_connection()
            conn.execute('UPDATE calls SET call_job_id = NULL WHERE user_id = ?', (user_id,))
            conn.commit()
            conn.close()
            return jsonify(response.json()), 200
        else:
            return jsonify({'error': 'Error canceling the call', 'details': response.text}), response.status_code
    except requests.exceptions.RequestException as e:
        print(f"Error making request to FastAPI: {e}")
        return jsonify({'error': 'Internal server error'}), 500



def auto_cancel_past_call(user_id: int) -> bool:
    """
    If the user's call is in the past according to their time_zone,
    it attempts to cancel it in FastAPI and cleans call_job_id from the database.
    Returns True if cleanup/cancellation was performed, False if there was nothing to do.
    """
    conn = sqlite3.connect(dbname, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        c = conn.cursor()
        row = c.execute(
            "SELECT call_date, call_time, time_zone, call_job_id FROM calls WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        if not row:
            return False

        call_date = row['call_date']
        call_time = row['call_time']
        tz_name   = row['time_zone']
        job_id    = row['call_job_id']
        if not call_date or not call_time or not tz_name:
            return False

        try:
            dt_naive = datetime.strptime(f"{call_date} {call_time}", "%Y-%m-%d %H:%M")
        except ValueError:
            return False

        user_tz = pytz.timezone(tz_name)
        call_dt = user_tz.localize(dt_naive)
        now_local = datetime.now(pytz.utc).astimezone(user_tz)

        if call_dt <= now_local:
            # Cancel in FastAPI if job_id exists
            if job_id and fastapi_cancel_url:
                try:
                    requests.post(
                        fastapi_cancel_url,
                        json={'user_id': user_id},
                        headers={'Content-Type': 'application/json'},
                        timeout=10,
                        verify=True
                    )
                except Exception as e:
                    app.logger.warning(f"Cancel API failed for user {user_id}: {e}")

            # Clean job_id locally
            c.execute("UPDATE calls SET call_job_id = NULL WHERE user_id = ?", (user_id,))
            conn.commit()
            return True

        return False
    finally:
        conn.close()
        

@app.route('/confirmation')
@handle_language
def confirmation(strings_data):
    phone_number = session['phone_number']
    verify_code = session['verify_code']

    user_url = f"/user"  # Format the URL with the phone number from the session

    return render_template('confirm.html', 
                            phone_number=phone_number,
                            verify_code=verify_code, 
                            user_url=user_url,
                            **strings_data)
        
def run_austin_to_santa():
    try:
        # Run the script as a separate process
        subprocess.Popen(["python", "austin-to-santa.py"])
        print("Successfully started austin-to-santa.py")
    except Exception as e:
        print(f"Error starting austin-to-santa.py: {e}")


@app.route('/remember-user', methods=['GET', 'POST'])
@handle_language
def remember_user(strings_data):
    if 'user_authenticated' in session and session['user_authenticated']:
        return redirect(url_for('get_user'))
    else:    
        if request.method == 'POST':
            email = request.form['mail'].lower()
            
            try:
                conn = get_db_connection()
                c = conn.cursor()
                c.execute('SELECT id, password FROM users WHERE email = ?', (email,))
                user_data = c.fetchone()
                if user_data:
                    user_id, user_password = user_data
                    if user_password:
                        confirmation_link = create_user_token(user_id, "new-password")

                        #send_confirmation_email(email, confirmation_link)  # Uncomment and adjust as needed
                        print(confirmation_link)
                        flash(strings_data['email_pass_sent'], 'success')
                    else:
                        confirmation_link = create_user_token(user_id, "register")
                        #send_confirmation_email(email, confirmation_link)
                        print(confirmation_link)
                        conn.close()
                        return render_template('mail.html', **strings_data)
                else:
                    flash(strings_data['user_not_found'], 'warning')
            except Exception as e:
                print(f"Error accessing database: {e}")
                return render_template('error.html', error_code=500, error_message=strings_data['error500']), 500
            finally:
                conn.close() 
        return render_template('remember_user.html', **strings_data)

@app.route('/change-password', methods=['POST'])
@handle_language
def change_password(strings_data):
    if 'user_id' not in session:
        flash(strings_data['login_for_password'], 'warning')
        return redirect(url_for('get_user'))

    user_id = session['user_id']
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT email FROM users WHERE id = ?', (user_id,))
        user_info = c.fetchone()

        if user_info:
            email = user_info[0]
            confirmation_link = create_user_token(user_id, "new-password")
            # send_confirmation_email(email, confirmation_link)
            print(confirmation_link)
            flash(strings_data['email_pass_sent'], 'success')
        else:
            return render_template('error.html', error_code=404, error_message=strings_data['user_not_found']), 404
    except Exception as e:
        print(f"Error accessing database: {e}")
        return render_template('error.html', error_code=500, error_message=strings_data['error500']), 500
    finally:
        try:
            conn.close()
        except:
            pass

    return render_template('mail.html', **strings_data)
   

@app.route('/new-password', defaults={'token': None}, methods=['GET', 'POST'])
@app.route('/new-password/<token>', methods=['GET', 'POST'])
@handle_language
def new_password(strings_data, token):
    if token:
        user_id = verify_token(token, 900)
        if user_id:
            return render_template('new_password.html', token=token, **strings_data)
        else:
            return render_template('error.html', error_code=400, error_message=strings_data['invalid_token']), 400
    else:
        return render_template('error.html', error_code=403, error_message=strings_data['error403']), 403
    
    
@app.route('/process-new-password', methods=['POST'])
@handle_language
def process_new_password(strings_data):
    token = request.form['token']
    password = request.form['password']
    confirm_password = request.form['confirm_password']
    user_id = verify_token(token, 900)

    if not user_id:
        flash(strings_data['invalid_token'], 'error')
        # Do not redirect to /new-password without token (would give 403)
        return render_template('error.html', error_code=400, error_message=strings_data['invalid_token']), 400

    if password != confirm_password:
        flash(strings_data['password_mismatch'], 'error')
        # Return to the same view with the token so the user can correct
        return render_template('new_password.html', token=token, **strings_data)

    try:
        hashed_password = hash_password(password)
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('UPDATE users SET password = ? WHERE id = ?', (hashed_password, user_id))
        conn.commit()
        conn.close()
        flash(strings_data["password_changed_ok"], 'success')
        return render_template('login.html', **strings_data)
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        try:
            conn.close()
        except:
            pass
        flash(strings_data['error500'], 'error')
        return render_template('new_password.html', token=token, **strings_data)
    
@app.route('/create-discount', methods=['GET'])
@handle_language
def create_discount(strings_data):
    return render_template('discount.html', **strings_data)

@app.route('/process-discount', methods=['POST'])
def process_discount():
    code_name = request.form['nombre_codigo']
    discount = request.form['descuento']
    validity_date = request.form.get('fecha_validez') or None
    number_uses = request.form.get('cantidad_usos') or None
    unlimited_uses = 'usos_ilimitados' in request.form
    unlimited_date = 'validez_ilimitada' in request.form

    active = True
    unlimited_uses = True if unlimited_uses else False
    unlimited_date = True if unlimited_date else False

    # Adjust values according to unlimited logic
    if unlimited_uses:
        number_uses = None
    if unlimited_date:
        validity_date = None

    # Insert into database
    conn = get_db_connection()
    conn.execute('INSERT INTO discounts (code, discount_value, active, validity_date, usage_count, unlimited_usage, unlimited_validity) VALUES (?, ?, ?, ?, ?, ?, ?)',
                 (code_name, discount, active, validity_date, number_uses, unlimited_uses, unlimited_date))
    conn.commit()
    conn.close()

    return 'Discount code created successfully'

@app.route('/donation')
@handle_language
def donation(strings_data):
    return render_template('donation.html', **strings_data)

@app.route('/privacy_policy')
@handle_language
def privacy_policy(strings_data):
    return render_template('privacy_policy.html', **strings_data)

if __name__ == '__main__':
    #run_austin_to_santa()

    if 'dev' in sys.argv:
        # Start the application in development mode (HTTP)
        app.config['SESSION_COOKIE_SECURE'] = False
        app.run(host='0.0.0.0', port=6789, debug=True)
    else:
        app.run(
            host='0.0.0.0',
            port=6789,
            debug=True,
            use_reloader=False,
            ssl_context=('static/sec/cert.pem', 'static/sec/privkey.pem')
        )

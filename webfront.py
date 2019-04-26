from flask import Flask, render_template, jsonify, request
from threading import Lock
from werkzeug.serving import run_simple
from datetime import datetime
from text_hash import text_hash

from pywebpush import webpush, WebPushException

import sqlite3

from twilio.rest import Client

app = Flask(__name__)

thread = None
thread_lock = Lock()

#### Public / private keys for push notifications
publicKey = 'BFU1O8aegR7BDQ2HQ5XaCe0L8itsFL6XJyuz7goH1Dj9Y6todufGqL8_LYlqkAUGaTLM7VpK9XDE4t-3IDDet0I'

with open('push_key.pem') as f:
    privateKey = f.read()
# Read adds a newline at the end, lets strip that out
privateKey = privateKey.strip('\n')

with open('account_sid.pem') as f:
    account_sid = f.read()

account_sid = account_sid.strip('\n')

with open('auth_token.pem') as f:
    auth_token = f.read()

auth_token = auth_token.strip('\n')


### Secret Carl Url Readin
with open('secret_carl_url.pem') as f:
    secret_url = f.read()
secret_url = secret_url.strip('\n')


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def average_temp(temp_score):
    if temp_score <= 1.3:
        return "mostly too-cold"
    elif temp_score > 1.3 and temp_score <= 1.7:
        return "between too-cold and cold"
    elif temp_score > 1.7 and temp_score <= 2.3:
        return "mostly cold"
    elif temp_score > 2.3 and temp_score <= 2.7:
        return "between cold and perfect"
    elif temp_score > 2.7 and temp_score <= 3.3:
        return "mostly perfect"
    elif temp_score > 3.3 and temp_score <= 3.7:
        return "between perfect and lukewarm"
    elif temp_score > 3.7 and temp_score <= 4.3:
        return "mostly lukewarm"
    elif temp_score > 4.3 and temp_score <= 4.7:
        return "between lukewarm and hot"
    elif temp_score > 4.7:
        return "mostly hot"
    else:
        return "broken"

@app.route('/')
def home():
    with sqlite3.connect('watertemp.db') as conn:
        cget = conn.cursor()
        cget.row_factory = dict_factory
        cget.execute("""SELECT watertemp, datetime(sqltime, 'localtime', '-1 hour') as updatedt FROM watertemp ORDER BY sqltime DESC LIMIT 50""")
        x = cget.fetchall()
        precise_update = x[0]['updatedt']
        current_update_dt = datetime.strptime(x[0]['updatedt'], '%Y-%m-%d %H:%M:%S').strftime('%A %b %d %I:%M %p')
        cget.execute("""SELECT SUM(CASE WHEN watertemp = 'too-cold' then 1 WHEN watertemp = 'cold' then 2 WHEN watertemp = 'perfect' then 3
        WHEN watertemp = 'lukewarm' then 4 WHEN watertemp = 'hot' then 5 ELSE 0 END) as score, COUNT(*) as theCount FROM watertemp;""")
        agg = cget.fetchone()
        total_updates = agg['theCount']
        total_temp_string =  average_temp(agg['score'] / agg['theCount'])
        cget.execute("""SELECT SUM(CASE WHEN watertemp = 'too-cold' then 1 WHEN watertemp = 'cold' then 2 WHEN watertemp = 'perfect' then 3
        WHEN watertemp = 'lukewarm' then 4 WHEN watertemp = 'hot' then 5 ELSE 0 END) as score, COUNT(*) as theCount FROM watertemp
        WHERE sqltime > datetime(CURRENT_TIMESTAMP, '-1 day');""")
        today_agg = cget.fetchone()
        if today_agg['score'] == None:
            today_updates = 0
            today_temp_string = "not available"
        else:
            today_updates = today_agg['theCount']
            today_temp_string =  average_temp(today_agg['score'] / today_agg['theCount'])
        cget.execute("""SELECT watertemp, datetime(sqltime, 'localtime', '-1 hour') as updatedt FROM watertemp ORDER BY sqltime DESC LIMIT 5""")
        y = cget.fetchall()
        # Get current feedback:
        current_feedback = dict()
        for feedback in ["like", "dislike", "fu", "heart", "sad"]:
            cget.execute("SELECT count(*) as votes FROM water_ratings WHERE update_sqltime = ? AND feedback = ?",(precise_update, feedback,))
            current_feedback[feedback] = cget.fetchone()['votes']
    return render_template('home.html',
        temp=x[0]['watertemp'],
        update=current_update_dt,
        history=x,
        total_updates=total_updates,
        total_temp_string=total_temp_string,
        today_updates=today_updates,
        today_temp_string=today_temp_string,
        last_five=y,
        precise_update=precise_update,
        likes=current_feedback['like'],
        dislikes=current_feedback['dislike'],
        fus=current_feedback['fu'],
        hearts=current_feedback['heart'],
        sads=current_feedback['sad']
        )

@app.route('/water-feedback')
def water_feedback():
    feedback = request.args.get('feedback')
    update_time = request.args.get('update')
    if feedback not in ["like", "dislike", "fu", "heart", "sad"]:
        print("feedback value not valid")
        return jsonify(results = "temp must be too-cold, cold, perfect, lukewarm or hot"), 400
    else:
        with sqlite3.connect('watertemp.db') as conn:
            cput = conn.cursor()
            cput.execute("INSERT INTO water_ratings (update_sqltime, feedback, sqltime) VALUES (?, ?, CURRENT_TIMESTAMP)", (update_time, feedback,))
            cput.close()
        return jsonify(results = "submitted {} feedback".format(feedback)), 200

@app.route('/{}'.format(secret_url))
def test_switch():
    return render_template('index.html', secret=secret_url)

@app.route('/{}/update-water'.format(secret_url))
def update_water():
    temp_update = request.args.get('temp')
    if temp_update is None:
        print("No temp parameter in update-water call.")
        return jsonify(results = "parameter temp is required"), 400
    elif temp_update not in ["too-cold", "cold", "perfect", "lukewarm", "hot"]:
        print("temp value not valid")
        return jsonify(results = "temp must be too-cold, cold, perfect, lukewarm or hot"), 400
    else:
        print("Updating temp to %s".format(temp_update))
        with sqlite3.connect('watertemp.db') as conn:
            cput = conn.cursor()
            cput.execute("INSERT INTO watertemp (sqltime, watertemp) VALUES (CURRENT_TIMESTAMP, ?)", (temp_update,))
            cput.close()
        # Send push notifications
        with sqlite3.connect('watertemp.db') as conn:
            cget = conn.cursor()
            cget.row_factory = dict_factory
            cget.execute("SELECT DISTINCT phone_number FROM text_subscriptions")
            subscribers = cget.fetchall()
            cget.close()
        client = Client(account_sid, auth_token)
        text_body ="Carl's water is {}".format(temp_update)
        for sub in subscribers:
            message = client.messages \
                .create(
                     body=text_body,
                     from_='+16129792194',
                     to='+1' + str(sub['phone_number'])
                 )
        return jsonify(result="updated to %s".format(temp_update))

@app.route('/privacy_policy')
def config_phone():
    return render_template('privacy_policy.html')

@app.route('/text_subscribe')
def config_phone():
    return render_template('text_subscribe.html')

@app.route('/subscribe')
def attempt_subscription():
    # Get inputted phone number
    temp_phone = request.args.get('phone')
    # Phone number should be ten digit string, strip out spaces, hypthens, dots
    clean_phone = temp_phone.replace('-', '').replace(' ', '').replace('.', '')
    # Error check phone numbner: Needs to be numbers
    if not clean_phone.isnumeric():
        return jsonify(result="Phone numbers should only be digits, non-numeric detected.")
    elif clean_phone[0] == '1':
        # should not start with 1.
        return jsonify(result="No country code, phone should be nine digits")
    elif len(clean_phone) != 10:
        # should only be US number, ten digits
        return jsonify(result="Phone number should be nine digits, enter in form xxx-xxx-xxxx")
    else:
        # Check if we've tried this number repeatedly:
        with sqlite3.connect('watertemp.db') as conn:
            cget = conn.cursor()
            cget.row_factory = dict_factory
            cget.execute("""SELECT phone_number, sqltime, julianday(CURRENT_TIMESTAMP) - julianday(sqltime) as diff
                FROM subscribe_attempts WHERE phone_number = ? AND
                julianday(CURRENT_TIMESTAMP) - julianday(sqltime) < .416 ORDER BY sqltime DESC LIMIT 5""", (clean_phone,))
            prev_attempts = cget.fetchall()
            cget.close()
        if len(prev_attempts) > 3:
            return jsonify(result="Max three attempts to subscribe an hour")
        else:
            # check if subscribed
            with sqlite3.connect('watertemp.db') as conn:
                cget = conn.cursor()
                cget.row_factory = dict_factory
                cget.execute("""SELECT phone_number FROM text_subscriptions WHERE phone_number = ?""", (clean_phone,))
                new_attempt = cget.fetchall()
                cget.close()
            if len(new_attempt) > 0:
                return jsonify(result="Already subscribed!")
            else:
                # insert into subscription attempts:
                with sqlite3.connect('watertemp.db') as conn:
                    cput = conn.cursor()
                    cput.execute("INSERT INTO subscribe_attempts (phone_number, sqltime) VALUES (?, CURRENT_TIMESTAMP)", (clean_phone,))
                    cput.close()
                # get exact time of subscription attempt:
                with sqlite3.connect('watertemp.db') as conn:
                    cget = conn.cursor()
                    cget.row_factory = dict_factory
                    cget.execute("""SELECT phone_number, sqltime FROM subscribe_attempts
                        WHERE phone_number = ? ORDER BY sqltime DESC LIMIT 1""", (clean_phone,))
                    latest_text_attempt = cget.fetchall()
                    cget.close()
                # Calculate 6 digit code for text confirmation
                text_code = text_hash(str(latest_text_attempt[0]['phone_number']), latest_text_attempt[0]['sqltime'])
                # send confirmation
                client = Client(account_sid, auth_token)
                message = client.messages.create(
                    body="Subscribing to Carl Water Updates, your code is " + str(text_code) + ". Go to https://cwaas.copeland.bz/text_confirm to finish.",
                    from_='+16129792194',
                    to='+1' + str(latest_text_attempt[0]['phone_number'])
                    )
                return jsonify(result="subscription attempt initiated")


@app.route('/unsubscribe')
def attempt_desubscription():
    # Get inputted phone number
    temp_phone = request.args.get('phone')
    # Phone number should be ten digit string, strip out spaces, hypthens, dots
    clean_phone = temp_phone.replace('-', '').replace(' ', '').replace('.', '')
    # Error check phone numbner: Needs to be numbers
    if not clean_phone.isnumeric():
        return jsonify(result="Phone numbers should only be digits, non-numeric detected.")
    elif clean_phone[0] == '1':
        # should not start with 1.
        return jsonify(result="No country code, phone should be nine digits")
    elif len(clean_phone) != 10:
        # should only be US number, ten digits
        return jsonify(result="Phone number should be nine digits, enter in form xxx-xxx-xxxx")
    else:
        # check that phone number is subscribed:
        with sqlite3.connect('watertemp.db') as conn:
            cget = conn.cursor()
            cget.row_factory = dict_factory
            cget.execute("""SELECT phone_number, sqltime FROM text_subscriptions
                WHERE phone_number = ? ORDER BY sqltime DESC LIMIT 1""", (clean_phone,))
            desubscribe_attempt = cget.fetchall()
            cget.close()
        if len(desubscribe_attempt) != 1:
            return jsonify(result="Error, number not recognized")
        else:
            # Calculate 6 digit code for text confirmation
            text_code = text_hash(str(desubscribe_attempt[0]['phone_number']), desubscribe_attempt[0]['sqltime'])
            # send confirmation
            client = Client(account_sid, auth_token)
            message = client.messages.create(
                body="Unsubscribe to Carl Water Updates, your code is " + str(text_code) + ". Go to https://cwaas.copeland.bz/text_unsubscribe to finish.",
                from_='+16129792194',
                to='+1' + str(desubscribe_attempt[0]['phone_number'])
                )
            return jsonify(result="unsubscribe attempt initiated")


@app.route('/text_confirm')
def confirm_phone():
    return render_template('text_confirm.html')


@app.route('/confirm')
def confirm_subscription():
    # Get inputted phone number
    temp_phone = request.args.get('phone')
    # Phone number should be ten digit string, strip out spaces, hypthens, dots
    clean_phone = temp_phone.replace('-', '').replace(' ', '').replace('.', '')
    temp_confirm = request.args.get('confirm')
    clean_confirm = temp_confirm.replace(' ', '')
    # get exact time of subscription attempt:
    with sqlite3.connect('watertemp.db') as conn:
        cget = conn.cursor()
        cget.row_factory = dict_factory
        cget.execute("""SELECT phone_number, sqltime FROM subscribe_attempts
            WHERE phone_number = ? ORDER BY sqltime DESC LIMIT 1""", (clean_phone,))
        subscribe_attempt = cget.fetchall()
        cget.close()
    # Calculate 6 digit code for text confirmation
    text_code = text_hash(str(subscribe_attempt[0]['phone_number']), subscribe_attempt[0]['sqltime'])
    if text_code == int(clean_confirm):
        with sqlite3.connect('watertemp.db') as conn:
            cput = conn.cursor()
            cput.execute("INSERT INTO text_subscriptions (phone_number, verification_time) VALUES (?, ?)",
                (str(subscribe_attempt[0]['phone_number']), subscribe_attempt[0]['sqltime']))
            cput.close()
        client = Client(account_sid, auth_token)
        message = client.messages.create(
            body="Your subscription to Carl's water temperature updates is confirmed. You'll get updates as they happen.",
            from_='+16129792194',
            to='+1' + str(subscribe_attempt[0]['phone_number'])
            )
        return jsonify(result="Subscribed!")

    else:
        return jsonify(result="Subscription failed, try again. Max 3 times an hour.")

@app.route('/text_unsubscribe')
def text_unsubscribe():
    return render_template('text_unsubscribe.html')

@app.route('/confirm_unsubscribe')
def confirm_unsubscription():
    # Get inputted phone number
    temp_phone = request.args.get('phone')
    # Phone number should be ten digit string, strip out spaces, hypthens, dots
    clean_phone = str(temp_phone.replace('-', '').replace(' ', '').replace('.', ''))
    temp_confirm = request.args.get('confirm')
    clean_confirm = str(temp_confirm.replace(' ', ''))
    # get exact time of subscription attempt:
    with sqlite3.connect('watertemp.db') as conn:
        cget = conn.cursor()
        cget.row_factory = dict_factory
        sql_text = "SELECT phone_number, verification_time FROM text_subscriptions where phone_number = '{}' order by verification_time desc limit 1".format(clean_phone)
        cget.execute(sql_text)
        unsubscribe_attempt = cget.fetchall()
        cget.close()
    if len(text_code) > 0:
        # Calculate 6 digit code for text confirmation
        text_code = text_hash(str(unsubscribe_attempt[0]['phone_number']), unsubscribe_attempt[0]['verification_time'])
        if text_code == int(clean_confirm):
            with sqlite3.connect('watertemp.db') as conn:
                cput = conn.cursor()
                cput.execute("DELETE FROM text_subscriptions WHERE phone_number = '{}'".format(str(unsubscribe_attempt[0]['phone_number'])))
                cput.close()
            return jsonify(result="Unsubscribed! You'll no longer receive text updates.")
        else:
            return jsonify(result="Your unsubscribe attempt failed.")
    else:
        return jsonify(result="Unsubscribe failed, try again.")


application = app

if __name__ == '__main__':
    app.run(threaded=True)

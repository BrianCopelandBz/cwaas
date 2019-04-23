from flask import Flask, render_template, jsonify, request
from threading import Lock
from werkzeug.serving import run_simple
from datetime import datetime

from pywebpush import webpush, WebPushException

import sqlite3

app = Flask(__name__)

thread = None
thread_lock = Lock()

#### Public / private keys for push notifications
publicKey = 'BFU1O8aegR7BDQ2HQ5XaCe0L8itsFL6XJyuz7goH1Dj9Y6todufGqL8_LYlqkAUGaTLM7VpK9XDE4t-3IDDet0I'

with open('push_key.pem') as f:
    privateKey = f.read()
# Read adds a newline at the end, lets strip that out
privateKey = privateKey.strip('\n')

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

def send_push(new_temp):
    with sqlite3.connect('watertemp.db') as conn:
        cget = conn.cursor()
        cget.row_factory = dict_factory
        cget.execute("""SELECT endpoint, p256dh, auth FROM subscriptions""")
        x = cget.fetchall()
    for i in x:
        keys = dict({"p256dh": i["p256dh"], "auth": i["auth"]})
        subscription_info = dict({'endpoint': i["endpoint"], 'keys': keys})
        try:
            webpush(
                subscription_info,
                data="Carl's water is " + new_temp + ".",
                vapid_private_key=privateKey,
                vapid_claims={"sub": "mailto:brian@copeland.bz"}
            )
        except WebPushException as ex:
            print("I'm sorry, Dave, but I can't do that: {}", repr(ex))
            # Mozilla returns additional information in the body of the response.
            if ex.response and ex.response.json():
                extra = ex.response.json()
                print("Remote service replied with a {}:{}, {}",
                      extra.code,
                      extra.errno,
                      extra.message
                      )
    return("Push sent")


@app.route('/')
def home():
    with sqlite3.connect('watertemp.db') as conn:
        cget = conn.cursor()
        cget.row_factory = dict_factory
        cget.execute("""SELECT watertemp, datetime(sqltime, 'localtime', '-1 hour') as updatedt FROM watertemp ORDER BY sqltime DESC LIMIT 50""")
        x = cget.fetchall()
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
    return render_template('home.html',
        temp=x[0]['watertemp'],
        update=current_update_dt,
        history=x,
        total_updates=total_updates,
        total_temp_string=total_temp_string,
        today_updates=today_updates,
        today_temp_string=today_temp_string
        )

@app.route('/{}'.format(secret_url))
def test_switch():
    return render_template('index.html')

@app.route('/update-water')
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
        send_push(temp_update)
        return jsonify(result="updated to too cold")


@app.route('/note')
def note():
    return render_template('note.html')

@app.route('/save-subscription', methods=['POST'])
def add_subscription():
    content=request.json
    with sqlite3.connect('watertemp.db') as conn:
        cput = conn.cursor()
        cput.execute("INSERT INTO subscriptions (endpoint, p256dh, auth) VALUES (?, ?, ?)", (content['endpoint'],
        content['keys']['p256dh'],
        content['keys']['auth'],
        ))
        cput.close()
    data = {'response': 'Subscription created'}
    return jsonify(data), 200
    #return 200

application = app

if __name__ == '__main__':
    app.run(threaded=True)

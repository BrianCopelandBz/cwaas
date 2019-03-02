from flask import Flask, render_template, jsonify, request
from threading import Lock
from werkzeug.serving import run_simple
from datetime import datetime

import sqlite3

app = Flask(__name__)

thread = None
thread_lock = Lock()

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
        if today_agg[0] == None:
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

@app.route('/secret_carl_url')
def test_switch():
    return render_template('index.html')

@app.route('/_new_too_cold')
def new_too_cold():
    with sqlite3.connect('watertemp.db') as conn:
        cput = conn.cursor()
        cput.execute("INSERT INTO watertemp (sqltime, watertemp) VALUES (CURRENT_TIMESTAMP, ?)", ("too-cold",))
        cput.close()
    return jsonify(result="updated to too cold")

@app.route('/_new_cold')
def new_cold():
    with sqlite3.connect('watertemp.db') as conn:
        cput = conn.cursor()
        cput.execute("INSERT INTO watertemp (sqltime, watertemp) VALUES (CURRENT_TIMESTAMP, ?)", ("cold",))
        cput.close()
    return jsonify(result="updated to cold")


@app.route('/_new_perfect')
def new_perfect():
    with sqlite3.connect('watertemp.db') as conn:
        cput = conn.cursor()
        cput.execute("INSERT INTO watertemp (sqltime, watertemp) VALUES (CURRENT_TIMESTAMP, ?)", ("perfect",))
        cput.close()
    return jsonify(result="updated to perfect")


@app.route('/_new_lukewarm')
def new_lukewarm():
    with sqlite3.connect('watertemp.db') as conn:
        cput = conn.cursor()
        cput.execute("INSERT INTO watertemp (sqltime, watertemp) VALUES (CURRENT_TIMESTAMP, ?)", ("lukewarm",))
        cput.close()
    return jsonify(result="updated to lukewarm")

@app.route('/_new_hot')
def new_hot():
    with sqlite3.connect('watertemp.db') as conn:
        cput = conn.cursor()
        cput.execute("INSERT INTO watertemp (sqltime, watertemp) VALUES (CURRENT_TIMESTAMP, ?)", ("hot",))
        cput.close()
    return jsonify(result="updated to hot")

application = app

if __name__ == '__main__':
    app.run(threaded=True)

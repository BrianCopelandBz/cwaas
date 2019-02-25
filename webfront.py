from flask import Flask, render_template, jsonify, request
from threading import Lock
from werkzeug.serving import run_simple

import sqlite3

app = Flask(__name__)

thread = None
thread_lock = Lock()

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

@app.route('/')
def home():
    with sqlite3.connect('watertemp.db') as conn:
        cget = conn.cursor()
        cget.row_factory = dict_factory
        cget.execute("""SELECT watertemp, datetime(sqltime, 'localtime') as updatedt FROM watertemp ORDER BY sqltime DESC LIMIT 10""")
        x = cget.fetchone()
        y = cget.fetchall()
    return render_template('home.html', temp=x['watertemp'], update=x['updatedt'], history=y)

@app.route('/test')
def test_site():
    return render_template('test.html')

@app.route('/test2')
def test2_site():
    return render_template('test2.html')

@app.route('/test3')
def test3_site():
    return render_template('test3.html')

@app.route('/secret_carl_url')
def test_switch():
    return render_template('index.html')

@app.route('/_new_too_cold')
def new_too_cold():
    with sqlite3.connect('watertemp.db') as conn:
        cput = conn.cursor()
        cput.execute("INSERT INTO watertemp (sqltime, watertemp) VALUES (CURRENT_TIMESTAMP, ?)", ("too-cold",))

    return jsonify(result="updated to too cold")

@app.route('/_new_cold')
def new_cold():
    with sqlite3.connect('watertemp.db') as conn:
        cput = conn.cursor()
        cput.execute("INSERT INTO watertemp (sqltime, watertemp) VALUES (CURRENT_TIMESTAMP, ?)", ("cold",))

    return jsonify(result="updated to cold")


@app.route('/_new_perfect')
def new_perfect():
    with sqlite3.connect('watertemp.db') as conn:
        cput = conn.cursor()
        cput.execute("INSERT INTO watertemp (sqltime, watertemp) VALUES (CURRENT_TIMESTAMP, ?)", ("perfect",))
    return jsonify(result="updated to perfect")


@app.route('/_new_lukewarm')
def new_lukewarm():
    with sqlite3.connect('watertemp.db') as conn:
        cput = conn.cursor()
        cput.execute("INSERT INTO watertemp (sqltime, watertemp) VALUES (CURRENT_TIMESTAMP, ?)", ("lukewarm",))

    return jsonify(result="updated to lukewarm")

@app.route('/_new_hot')
def new_hot():
    with sqlite3.connect('watertemp.db') as conn:
        cput = conn.cursor()
        cput.execute("INSERT INTO watertemp (sqltime, watertemp) VALUES (CURRENT_TIMESTAMP, ?)", ("hot",))

    return jsonify(result="updated to hot")

application = app

if __name__ == '__main__':
    app.run(threaded=True)

from flask import Flask, render_template, jsonify, request
from threading import Lock
from werkzeug.serving import run_simple

import sqlite3

app = Flask(__name__)

thread = None
thread_lock = Lock()

@app.route('/')
def home():
    with sqlite3.connect('watertemp.db') as conn:
        cget = conn.cursor()
        cget.execute("""SELECT watertemp, datetime(sqltime, 'localtime') FROM watertemp ORDER BY sqltime DESC LIMIT 1""")
        x = cget.fetchone()
    return render_template('home.html', temp=x[0], update=x[1])

@app.route('/[secret_carl_url]')
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


if __name__ == '__main__':
    app.run(threaded=True)

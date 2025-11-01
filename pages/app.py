from flask import Flask, request, render_template, redirect
import psycopg2
from psycopg2 import sql

app = Flask(__name__)

conn = psycopg2.connect(
    dbname="",
    user="",
    password="",
    host="localhost",
    port="5432"
)

@app.route('/')
def home():
    return render_template('login.html')

@app.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password_hash = request.form['password']

        cur = conn.cursor()

        cur.execute(
            sql.SQL("SELECT * FROM users WHERE username = %s AND password_hash = %s"),
            (username, password_hash)
        )

        user = cur.fetchone()
        cur.close()

        if (user):
            return redirect('/index')
        else:
            return render_template('login.html', error="Invalid username or password.")
    return render_template('login.html')

@app.route('/create_account', methods=['POST', 'GET'])
def create_account():
    if request.method == 'POST':
        email = request.form['email']
        username = request.form['username']
        password = request.form['password']

        cur = conn.cursor()

        cur.execute(
            sql.SQL("INSERT INTO users (email, username, password_hash) VALUES (%s, %s, %s)"),
            [email, username, password]
        )

        conn.commit()
        cur.close()
    return render_template('create_acc.html')

@app.route('/map-view')
def view_map():
    return render_template('selection.html')

@app.route('/index')
def select_location():
    return render_template('index.html')

@app.route('/route-view')
def route_view():
    return render_template('routeview.html')

if __name__ == '__main__':
    app.run(debug=True)

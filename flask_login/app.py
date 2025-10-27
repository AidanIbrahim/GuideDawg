from flask import Flask, request, render_template, redirect
import psycopg2
from psycopg2 import sql

app = Flask(__name__)

conn = psycopg2.connect(
    dbname="insert_your_db_name",
    user="insert_username",
    password="insert_pw",
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
        password = request.form['password']

        cur = conn.cursor()

        cur.execute(
            sql.SQL("SELECT * FROM users WHERE username = %s AND password = %s"),
            (username, password)
        )

        user = cur.fetchone()
        cur.close()

        if (user):
            return redirect('/home')
        else:
            return "Invalid username or password", 401
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

if __name__ == '__main__':
    app.run(debug=True)

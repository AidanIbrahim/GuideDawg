from flask import Flask, request, render_template, redirect
import psycopg2
from psycopg2 import sql

app = Flask(__name__)

user_conn = psycopg2.connect(
    dbname="",
    user="",
    password="!",
    host="",
    port=""
)

map_conn = psycopg2.connect(
    dbname="",
    user="",
    password="!",
    host="",
    port=""
)

@app.route('/')
def home():
    return render_template('login.html')

@app.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password_hash = request.form['password']

        cur = user_conn.cursor()

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

        cur = user_conn.cursor()

        cur.execute(
            sql.SQL("INSERT INTO users (email, username, password_hash) VALUES (%s, %s, %s)"),
            [email, username, password]
        )

        user_conn.commit()
        cur.close()
    return render_template('create_acc.html')

@app.route('/map-view', methods=['POST', 'GET'])
def view_map():
    if request.method == 'POST':
        start = request.form['startLocation']
        end = request.form['endLocation']

        cur = map_conn.cursor()

        query = """
        WITH source_nodes AS (
            SELECT id
            FROM nodes
            WHERE building = %s
        ),
        target_nodes AS (
            SELECT id
            FROM nodes
            WHERE building = %s
        ),
        all_paths AS (
            SELECT 
                s.id AS source_id,
                t.id AS target_id,
                (pgr_dijkstra(
                    'SELECT id, source, target, cost FROM edges',
                    s.id,
                    t.id,
                    directed := false
                )).*
            FROM source_nodes s
            CROSS JOIN target_nodes t
        ),
        agg_costs AS (
            SELECT source_id, target_id, MAX(agg_cost) AS total_cost
            FROM all_paths
            GROUP BY source_id, target_id
        ),
        best_pair AS (
            SELECT source_id, target_id, total_cost
            FROM agg_costs
            ORDER BY total_cost
            LIMIT 1
        )
        SELECT ST_AsGeoJSON(n.geom) AS geom
        FROM all_paths p
        JOIN best_pair bp
        ON p.source_id = bp.source_id AND p.target_id = bp.target_id
        JOIN nodes n
        ON p.node = n.id
        ORDER BY p.seq;
        """

        cur.execute(query, (start, end))
        rows = cur.fetchall()
        cur.close()

        path = [row[-1] for row in rows]
        return render_template('selection.html', path=path, start=start, end=end)
    return render_template('selection.html', path=None)

@app.route('/index')
def select_location():
    cur = map_conn.cursor()
    cur.execute("SELECT DISTINCT building from nodes ORDER BY building")
    buildings = [row[0] for row in cur.fetchall()]
    cur.close()

    return render_template('index.html', buildings=buildings)

@app.route('/route-view')
def route_view():
    return render_template('routeview.html')

if __name__ == '__main__':
    app.run(debug=True)

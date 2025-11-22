from flask import Flask, request, render_template, redirect, session
import psycopg2
from psycopg2 import sql
from flask import jsonify
from psycopg2.extras import Json
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# connect to user database
user_conn = psycopg2.connect(
    dbname="",
    user="",
    password="",
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

# connect to map database
map_conn = psycopg2.connect(
    dbname="",
    user="",
    password="",
    host="",
    port=""
)

@app.before_request
def require_login():
    # pages that do not require login
    allowed = {'home', 'login', 'create_account', 'static'}

    if request.endpoint not in allowed and 'user_id' not in session:
        return redirect('/')

@app.route('/')
def home():
    return render_template('login.html')

# login page
@app.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == 'POST':
        # get user input from login.html
        username = request.form['username']
        password_hash = request.form['password']

        cur = user_conn.cursor()

        # query database to validate user credentials
        cur.execute(
            sql.SQL("SELECT user_id, username FROM users WHERE username = %s AND password_hash = %s"),
            (username, password_hash)
        )

        user = cur.fetchone()
        cur.close()

        # store user_id in session
        if user:
            session['user_id'] = user[0]
            
            return redirect('/index')
        else:
            # return error if invalid
            return render_template('login.html', error="Invalid username or password.")
        
    return render_template('login.html')

# create account page
@app.route('/create_account', methods=['POST', 'GET'])
def create_account():
    if request.method == 'POST':
        # get user input from create_acc.html
        email = request.form['email']
        username = request.form['username']
        password = request.form['password']

        cur = user_conn.cursor()

        cur.execute(
            sql.SQL("INSERT INTO users (email, username, password_hash) VALUES (%s, %s, %s)"),
            [email, username, password]
        )

        # need to add some check that username/email doesn't already exist

        user_conn.commit()
        cur.close()
    return render_template('create_acc.html')

# map view page
@app.route('/map-view', methods=['POST', 'GET'])
def view_map():
    if request.method == 'POST':
        # get start and end location from index.html
@app.route('/map-view', methods=['POST', 'GET'])
def view_map():
    if request.method == 'POST':
        start = request.form['startLocation']
        end = request.form['endLocation']

        cur = map_conn.cursor()

        # get shortest path from database:
        # essentially creates a list of source building entrances and target building entrances,
        # generates all possible path combinations, calculates the cost of each and returns the
        # three shortest ones
        # in the future, this query will be much simpler since instead of using entrances, will 
        # use elevators (may be more complex if buildings have multiple) 
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
        best_pairs AS (
            SELECT source_id, target_id, total_cost,
                ROW_NUMBER() OVER (ORDER BY total_cost) AS route_rank
            FROM agg_costs
            ORDER BY total_cost
            LIMIT 3
        )
        SELECT p.seq, bp.route_rank, ST_AsGeoJSON(e.geom) AS geom, p.agg_cost
        FROM all_paths p
        JOIN best_pairs bp
            ON p.source_id = bp.source_id
            AND p.target_id = bp.target_id
        JOIN edges e
            ON p.edge = e.id
        WHERE p.edge IS NOT NULL
        ORDER BY bp.route_rank, p.seq;
        """

        # run SQL query and fetch all rows returned
        cur.execute(query, (start, end))
        rows = cur.fetchall()

        # organize rows by route
        routes = {}
        for seq, route_rank, geom, agg_cost in rows:
            # append geometry to correct route list
            routes.setdefault(route_rank, []).append(geom)

        return render_template('selection.html', routes=routes)

    return render_template('selection.html', path=None)

# update database when user stars a route
@app.route("/star-route", methods=["POST"])
def star_route():
    # read JSON request sent from JS
    data = request.json
    user_id = session.get('user_id')
    rank = data.get("rank")
    geometry = data.get("geometry")
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

    if geometry is None:
        return jsonify({"error": "No geometry provided"}), 400

    cur = user_conn.cursor()

    # add route to user's starred routes, ensure no duplicates
    try:
        cur.execute("""
            INSERT INTO starred_routes (user_id, route_rank, route_geometry)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, route_rank) DO NOTHING
        """, (user_id, rank, Json(geometry)))

        user_conn.commit()

        # return success
        return jsonify({"status": "saved", "rank": rank})

    # protect database in case of error
    except Exception as e:
        user_conn.rollback()
        return jsonify({"error": str(e)}), 500

# update database when user unstars a route
@app.route("/unstar-route", methods=["POST"])
def unstar_route():
    data = request.json
    user_id = session.get('user_id')
    rank = data.get("rank")

    cur = user_conn.cursor()
    cur.execute("DELETE FROM starred_routes WHERE user_id = %s AND route_rank = %s", (user_id, rank))

    user_conn.commit()
    # tell browser than route was successfully unstarred
    return jsonify({"status": "removed"})

# user can see all of their starred routes (max 5)
# need to add functionality for this, probably some popup window
@app.route("/my-stars")
def my_stars():
    user_id = session.get('user_id')
    cur = user_conn.cursor()
    cur.execute("""
        SELECT route_rank, route_geometry, created_at
        FROM starred_routes
        WHERE user_id = %s
        ORDER BY created_at DESC
    """, (user_id,))

    rows = cur.fetchall()
    saved = [{"rank": r[0], "geometry": r[1], "created_at": r[2]} for r in rows]

    return render_template("starred_routes.html", saved=saved)

# show if a route generated from a query is a starred route
@app.route("/check-star", methods=["POST"])
def check_star():
    data = request.json
    rank = data.get("rank")
    user_id = session.get('user_id')

    cur = user_conn.cursor()
    cur.execute("SELECT 1 FROM starred_routes WHERE user_id = %s AND route_rank = %s", (user_id, rank))

    result = cur.fetchone()
    # tell browser whether route is a starred route
    return jsonify({"starred": bool(result)})

# page where user inputs their start and end location
# will eventually combine with /map-view page
@app.route('/index')
def select_location():
    cur = map_conn.cursor()
    cur.execute("SELECT DISTINCT building from nodes ORDER BY building")
    buildings = [row[0] for row in cur.fetchall()]
    cur.close()

    return render_template('index.html', buildings=buildings)

# directions page (currently not functional)
@app.route('/route-view')
def route_view():
    return render_template('routeview.html')

if __name__ == '__main__':
    app.run(debug=True)

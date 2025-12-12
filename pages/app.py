from flask import Flask, request, render_template, redirect, session, abort
import psycopg2
from psycopg2 import sql
from flask import jsonify
from psycopg2.extras import Json
import secrets
import json
from geopy.distance import distance
from functools import wraps
import hashlib

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)


map_conn = psycopg2.connect(
    host="localhost",
    dbname="map_db",
    user="postgres",
    password="thebestpassword",
    port="5432"
)


# get length of route in meters
def compute_route_length_meters(geoms):
    total = 0
    for g in geoms:
        coords = json.loads(g["geom"])["coordinates"]
        for i in range(len(coords)-1):
            total += distance((coords[i][1], coords[i][0]), (coords[i+1][1], coords[i+1][0])).meters
    return round(total)


# pages that require login
@app.before_request
def require_login():
    allowed = {'home', 'login', 'create_account', 'static'}

    if request.endpoint not in allowed and 'user_id' not in session:
        return redirect('/')


@app.route('/')
def home():
    return render_template('login.html')


# login page where user must enter valid username and password
@app.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password_hash = request.form['password']

        cur = map_conn.cursor()

        cur.execute(
            sql.SQL("SELECT user_id, email, is_admin FROM users WHERE username = %s AND password_hash = %s"),
            (username, password_hash)
        )

        user = cur.fetchone()
        cur.close()

        if user:
            session['user_id'] = user[0]
            session['email'] = user[1]
            session["is_admin"] = user[2]
            
            return redirect('/map')
        else:
            return render_template('login.html', error="Invalid username or password.")
        
    return render_template('login.html')


# create account page where user enters username, password, and email
@app.route('/create_account', methods=['POST', 'GET'])
def create_account():
    if request.method == 'POST':
        email = request.form['email']
        username = request.form['username']
        password = request.form['password']

        cur = map_conn.cursor()

        cur.execute("SELECT 1 FROM users WHERE email = %s OR username = %s", (email, username))
        exists = cur.fetchone()

        if exists:
            cur.close()
            return render_template('create_acc.html',
                 error="That email or username is already taken. Please choose another.")

        cur.execute(
            sql.SQL("INSERT INTO users (email, username, password_hash) VALUES (%s, %s, %s)"),
            [email, username, password]
        )

        map_conn.commit()
        cur.close()

        return render_template('create_acc.html', success="Account created successfully!")

    return render_template('create_acc.html')


# main map page, includes sql queries to get shortest path(s), reported nodes, etc.
@app.route('/map', methods=['POST', 'GET'])
def view_map():
    cur = map_conn.cursor()
    cur.execute("SELECT DISTINCT building FROM nodes ORDER BY building")
    buildings = [row[0] for row in cur.fetchall()]

    routes = {}
    report_nodes = []

    if request.method == 'POST':
        start = request.form['startLocation']
        end = request.form['endLocation']

        session['start'] = start
        session['end'] = end

        cur = map_conn.cursor()

        query = """
        WITH source_nodes AS (
            SELECT id
            FROM nodes
            WHERE building = %s AND type = 'elevator'
            UNION ALL
            SELECT id
            FROM nodes
            WHERE building = %s AND type = 'classroom'
            AND NOT EXISTS (SELECT 1 FROM nodes WHERE building = %s AND type = 'elevator')
            UNION ALL
            SELECT id
            FROM nodes
            WHERE building = %s AND type = 'entrance'
            AND NOT EXISTS (SELECT 1 FROM nodes WHERE building = %s AND type IN ('elevator','classroom'))
        ),
        target_nodes AS (
            SELECT id
            FROM nodes
            WHERE building = %s AND type = 'elevator'
            UNION ALL
            SELECT id
            FROM nodes
            WHERE building = %s AND type = 'classroom'
            AND NOT EXISTS (SELECT 1 FROM nodes WHERE building = %s AND type = 'elevator')
            UNION ALL
            SELECT id
            FROM nodes
            WHERE building = %s AND type = 'entrance'
            AND NOT EXISTS (SELECT 1 FROM nodes WHERE building = %s AND type IN ('elevator','classroom'))
        ),
        pairs AS (
            -- Compute all pairs and pick the shortest path among them
            SELECT s.id AS source_id, t.id AS target_id
            FROM source_nodes s
            CROSS JOIN target_nodes t
            ORDER BY (
                SELECT agg_cost
                FROM pgr_dijkstra(
                    'SELECT id, source, target, cost FROM edges',
                    s.id, t.id, false
                )
                ORDER BY agg_cost DESC
                LIMIT 1
            )
            LIMIT 1
        ),
        raw_paths AS (
            SELECT *
            FROM pgr_ksp(
                'SELECT id, source, target, cost FROM edges',
                (SELECT source_id FROM pairs),
                (SELECT target_id FROM pairs),
                10,   -- generate 10 paths
                false, false
            )
        ),
        shortest_edges AS (
            SELECT edge FROM raw_paths WHERE path_id = 1 AND edge IS NOT NULL
        ),
        overlap AS (
            SELECT path_id,
                COUNT(*) FILTER (WHERE edge IN (SELECT edge FROM shortest_edges))::float
                / NULLIF(COUNT(*),0) AS overlap_ratio
            FROM raw_paths
            WHERE edge IS NOT NULL
            GROUP BY path_id
        ),
        filtered AS (
            SELECT p.path_id, p.seq, p.agg_cost, ST_AsGeoJSON(e.geom) AS geom
            FROM raw_paths p
            JOIN overlap o ON p.path_id = o.path_id
            JOIN edges e ON p.edge = e.id
            WHERE (p.path_id = 1 OR o.overlap_ratio <= 0.6)
        ),
        total_cost AS (
            SELECT path_id,
                MAX(agg_cost) AS total_cost
            FROM filtered
            GROUP BY path_id
        ),
        ranked AS (
            SELECT path_id,
                ROW_NUMBER() OVER (ORDER BY total_cost) AS cost_rank
            FROM total_cost
        )
        SELECT f.path_id AS pgr_path_id,
            ROW_NUMBER() OVER (PARTITION BY f.path_id ORDER BY f.seq) AS seq,
            r.cost_rank AS route_rank,
            f.agg_cost,
            f.geom
        FROM filtered f
        JOIN ranked r ON f.path_id = r.path_id
        WHERE (f.path_id = 1 OR (r.cost_rank <= 3 AND f.path_id <> 1))
        ORDER BY route_rank, seq;
        """

        cur.execute(query, (start, start, start, start, start, end, end, end, end, end))
        rows = cur.fetchall()

        for pgr_path_id, seq, route_rank, agg_cost, geom in rows:
            route_key = str(route_rank)
            entry = {"seq": seq, "geom": geom, "pgr_path_id": pgr_path_id}
            routes.setdefault(route_key, []).append(entry)

        routes_final = {}
        for rank, items in routes.items():
            geoms = [{"seq": it["seq"], "geom": it["geom"]} for it in items]
            pgr_id = items[0]["pgr_path_id"]
            total_meters = compute_route_length_meters(geoms)
            routes_final[rank] = {
                "geoms": geoms,
                "meters": total_meters,
                "time_min": round(total_meters / 50),
                "pgr_path_id": pgr_id,
                "start_building": start,
                "end_building": end
            }

        routes = {k: routes_final[k] for k in sorted(routes_final.keys())[:3]}

    cur.execute("""
        SELECT id, type, name, building, ST_X(geom) AS lng, ST_Y(geom) AS lat
        FROM nodes
        WHERE can_report = TRUE
    """)
    report_nodes_rows = cur.fetchall()
    report_nodes = [
        {"id": r[0], "type": r[1], "name": r[2], "building": r[3], "lng": r[4], "lat": r[5]} 
        for r in report_nodes_rows
    ]

    cur.execute("""
        SELECT id, type, name, building, ST_X(geom) AS lng, ST_Y(geom) AS lat
        FROM removed_nodes
        WHERE can_report = TRUE
    """)
    removed_nodes_rows = cur.fetchall()
    removed_nodes = [
        {"id": r[0], "type": r[1], "name": r[2], "building": r[3], "lng": r[4], "lat": r[5]} 
        for r in removed_nodes_rows
    ]

    user_settings = {"mode": "light", "live_updates": False, "voice_over": False}
    user_id = session.get("user_id")
    if user_id:
        cur.execute("""
            SELECT mode, live_updates, voice_over
            FROM users
            WHERE user_id = %s
        """, (user_id,))
        row = cur.fetchone()
        if row:
            user_settings = {
                "mode": row[0],
                "live_updates": row[1],
                "voice_over": row[2]
            }

    cur.close()

    return render_template(
        'selection.html',
        buildings=buildings,
        routes=routes,
        report_nodes=report_nodes,
        is_admin=session.get("is_admin"),
        mode=user_settings["mode"],
        live_updates=user_settings["live_updates"],
        voice_over=user_settings["voice_over"],
        removed_nodes=removed_nodes
    )


# given the path id, returns a list of nodes and their attributes
@app.route('/directions/<int:pgr_path_id>')
def get_directions(pgr_path_id):
    start_building = session.get('start')
    end_building = session.get('end')

    if not start_building or not end_building:
        return jsonify({"error": "Start/end not set"}), 400

    cur = map_conn.cursor()

    query = """
    WITH source_nodes AS (
        SELECT id
        FROM nodes
        WHERE building = %s AND type = 'elevator'
        UNION ALL
        SELECT id
        FROM nodes
        WHERE building = %s AND type = 'classroom'
          AND NOT EXISTS (SELECT 1 FROM nodes WHERE building = %s AND type = 'elevator')
        UNION ALL
        SELECT id
        FROM nodes
        WHERE building = %s AND type = 'entrance'
          AND NOT EXISTS (SELECT 1 FROM nodes WHERE building = %s AND type IN ('elevator','classroom'))
    ),
    target_nodes AS (
        SELECT id
        FROM nodes
        WHERE building = %s AND type = 'elevator'
        UNION ALL
        SELECT id
        FROM nodes
        WHERE building = %s AND type = 'classroom'
          AND NOT EXISTS (SELECT 1 FROM nodes WHERE building = %s AND type = 'elevator')
        UNION ALL
        SELECT id
        FROM nodes
        WHERE building = %s AND type = 'entrance'
          AND NOT EXISTS (SELECT 1 FROM nodes WHERE building = %s AND type IN ('elevator','classroom'))
    ),
    pairs AS (
        SELECT s.id AS source_id, t.id AS target_id
        FROM source_nodes s
        CROSS JOIN target_nodes t
        ORDER BY (
            SELECT agg_cost
            FROM pgr_dijkstra(
                'SELECT id, source, target, cost FROM edges',
                s.id, t.id, false
            )
            ORDER BY agg_cost DESC
            LIMIT 1
        )
        LIMIT 1
    ),
    raw_paths AS (
        SELECT *
        FROM pgr_ksp(
            'SELECT id, source, target, cost FROM edges',
            (SELECT source_id FROM pairs),
            (SELECT target_id FROM pairs),
            10,
            false, false
        )
    )
    SELECT p.seq,
           n.id, n.type, n.building, n.floor, n.angle,
           ST_X(n.geom) AS lng, ST_Y(n.geom) AS lat
    FROM raw_paths p
    JOIN nodes n ON p.node = n.id
    WHERE p.path_id = %s
    ORDER BY p.seq;
    """

    cur.execute(query, (
    start_building, start_building, start_building, start_building, start_building,
    end_building, end_building, end_building, end_building, end_building,
    pgr_path_id
    ))
    rows = cur.fetchall()
    cur.close()

    nodes = [
        {
            "seq": r[0], "id": r[1], "type": r[2], "building": r[3],
            "floor": r[4], "angle": r[5], "lng": r[6], "lat": r[7]
        }
        for r in rows
    ]
    return jsonify(nodes)


# adds the selected route to the starred_routes table
@app.route("/star-route", methods=["POST"])
def star_route():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 403

    data = request.json
    route_json = data.get("route_json")
    star_name = data.get("name")
    directions = data.get("directions")

    if route_json is None:
        return jsonify({"error": "Missing route_json"}), 400

    try:
        geoms = route_json.get("geoms", [])
        feature_collection = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": g["geom"],
                    "properties": {"seq": g.get("seq")}
                }
                for g in geoms
                if "geom" in g
            ]
        }

        route_geometry_str = json.dumps(feature_collection, sort_keys=True)
        hashed_geometry = hashlib.sha256(route_geometry_str.encode("utf-8")).hexdigest()
    except Exception as e:
        return jsonify({"error": f"Invalid route_json: {e}"}), 400

    cur = map_conn.cursor()
    try:
        cur.execute("""
            SELECT 1 FROM starred_routes
            WHERE user_id = %s AND hashed_geometry = %s
        """, (user_id, hashed_geometry))

        if cur.fetchone():
            return jsonify({"error": "Route already starred"}), 409

        cur.execute("""
            INSERT INTO starred_routes (user_id, custom_name, hashed_geometry, route_json, directions)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            user_id,
            star_name,
            hashed_geometry,
            json.dumps(feature_collection),
            json.dumps(directions) if directions else None
        ))
        map_conn.commit()
    except Exception as e:
        map_conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()

    return jsonify({"success": True})


# admin user report to reports table
@app.route('/submit-report', methods=['POST'])
def submit_report():
    data = request.json
    node_id = data.get("node_id")
    description = data.get("description").strip()
    node_name = data.get("node_name")
    building = data.get("building")

    if len(description) > 255:
        description = description[:255]

    user_id = session.get("user_id")
    user_email = session.get("email")

    cur = map_conn.cursor()
    cur.execute("""
        INSERT INTO reports (user_id, user_email, node_id, node_name, building, description)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (user_id, user_email, node_id, node_name, building, description))
    map_conn.commit()
    return jsonify({"status": "success"})


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("is_admin"):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


# returns a list of user submitted reports in the last month
@app.route("/admin/report-summary")
@admin_required
def admin_report_summary():
    cur = map_conn.cursor()
    try:
        query = """
        SELECT r.node_id,
               COALESCE(n.name, rn.name) AS name,
               COALESCE(n.building, rn.building) AS building,
               COALESCE(ST_Y(n.geom), ST_Y(rn.geom)) AS lat,
               COALESCE(ST_X(n.geom), ST_X(rn.geom)) AS lng,
               COALESCE(n.type, rn.type) AS type,
               COUNT(*) AS report_count,
               JSON_AGG(
                   JSON_BUILD_OBJECT(
                       'email', r.user_email,
                       'reported_at', r.created_at,
                       'description', r.description
                   )
               ) AS reports,
               CASE WHEN n.id IS NOT NULL THEN TRUE ELSE FALSE END AS in_use
        FROM reports r
        LEFT JOIN nodes n ON r.node_id = n.id
        LEFT JOIN removed_nodes rn ON r.node_id = rn.id
        WHERE r.created_at >= NOW() - INTERVAL '1 month'
        GROUP BY r.node_id, n.id, rn.id, n.name, rn.name, n.building, rn.building, n.geom, rn.geom, n.type, rn.type
        ORDER BY report_count DESC, building ASC, name ASC;
        """
        cur.execute(query)
        results = cur.fetchall()
        
        data = [
            {
                "node_id": r[0],
                "name": r[1],
                "building": r[2],
                "lat": r[3],
                "lng": r[4],
                "type": r[5],
                "report_count": r[6],
                "reports": r[7],
                "in_use": r[8]
            }
            for r in results
        ]
        return jsonify(data)
    except Exception as e:
        print("Error in /admin/report-summary:", e)
        return jsonify([])
    finally:
        cur.close()


# temporarily moves node to removed nodes table and does the same for adjacent edges
@app.route("/admin/remove-node/<int:node_id>", methods=["POST"])
@admin_required
def remove_node(node_id):
    cur = map_conn.cursor()
    try:
        cur.execute("SELECT e_group_id FROM nodes WHERE id = %s", (node_id,))
        row = cur.fetchone()

        if not row:
            raise Exception("Node not found")

        e_group_id = row[0]

        if e_group_id is None:
            group_nodes = [node_id]

        else:
            cur.execute("SELECT id FROM nodes WHERE e_group_id = %s", (e_group_id,))
            group_nodes = [r[0] for r in cur.fetchall()]

        cur.execute("""
            INSERT INTO removed_nodes (id, name, building, type, floor, angle, can_report, geom, e_group_id)
            SELECT id, name, building, type, floor, angle, can_report, geom, e_group_id
            FROM nodes
            WHERE id = ANY(%s)
        """, (group_nodes,))

        cur.execute("""
            INSERT INTO removed_edges (id, source, target, cost, geom)
            SELECT id, source, target, cost, geom
            FROM edges
            WHERE source = ANY(%s) OR target = ANY(%s)
        """, (group_nodes, group_nodes))

        cur.execute("DELETE FROM nodes WHERE id = ANY(%s)", (group_nodes,))

        cur.execute("""
            DELETE FROM edges
            WHERE source = ANY(%s) OR target = ANY(%s)
        """, (group_nodes, group_nodes))

        map_conn.commit()

        cur.execute("""
            SELECT id, name, building, type, floor, angle, can_report,
                   ST_X(geom) AS lat, ST_Y(geom) AS lng, e_group_id
            FROM removed_nodes
            WHERE id = %s
        """, (node_id,))

        node_row = cur.fetchone()

        node_data = {
            "id": node_row[0],
            "name": node_row[1],
            "building": node_row[2],
            "type": node_row[3],
            "lat": node_row[7],
            "lng": node_row[8]
        }

    except Exception as e:
        print("REMOVE NODE ERROR:", e)
        map_conn.rollback()
        cur.close()
        return jsonify({"error": str(e)}), 500

    cur.close()
    return jsonify({"success": True, "node": node_data})


# moves node/edges back to main nodes and edges table
@app.route("/admin/restore-node/<int:node_id>", methods=["POST"])
@admin_required
def restore_node(node_id):
    cur = map_conn.cursor()
    try:
        cur.execute("SELECT e_group_id FROM removed_nodes WHERE id = %s", (node_id,))
        row = cur.fetchone()

        if not row:
            raise Exception("Node not found in removed_nodes")

        e_group_id = row[0]

        if e_group_id is None:
            group_nodes = [node_id]

        else:
            cur.execute("SELECT id FROM removed_nodes WHERE e_group_id = %s", (e_group_id,))
            group_nodes = [r[0] for r in cur.fetchall()]

        cur.execute("""
            INSERT INTO nodes (id, name, building, type, floor, angle, can_report, geom, e_group_id)
            SELECT id, name, building, type, floor, angle, can_report, geom, e_group_id
            FROM removed_nodes
            WHERE id = ANY(%s)
        """, (group_nodes,))

        cur.execute("""
            INSERT INTO edges (id, source, target, cost, geom)
            SELECT id, source, target, cost, geom
            FROM removed_edges
            WHERE source = ANY(%s) OR target = ANY(%s)
        """, (group_nodes, group_nodes))

        cur.execute("DELETE FROM removed_nodes WHERE id = ANY(%s)", (group_nodes,))

        cur.execute("""
            DELETE FROM removed_edges
            WHERE source = ANY(%s) OR target = ANY(%s)
        """, (group_nodes, group_nodes))

        cur.execute("""
            DELETE FROM reports
            WHERE node_id = ANY(%s)
        """, (group_nodes,))

        map_conn.commit()

        cur.execute("""
            SELECT id, name, building, type, floor, angle, can_report,
                   ST_X(geom) AS lat, ST_Y(geom) AS lng, e_group_id
            FROM nodes
            WHERE id = %s
        """, (node_id,))

        node_row = cur.fetchone()

        node_data = {
            "id": node_row[0],
            "name": node_row[1],
            "building": node_row[2],
            "type": node_row[3],
            "lat": node_row[7],
            "lng": node_row[8],
            "in_use": True
        }

    except Exception as e:
        map_conn.rollback()
        cur.close()
        return jsonify({"error": str(e)}), 500

    cur.close()
    return jsonify({"success": True, "node": node_data})


# returns list of starred routes
@app.route("/get-starred-routes")
def get_starred_routes():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify([])

    cur = map_conn.cursor()
    cur.execute("""
        SELECT id, custom_name, created_at
        FROM starred_routes
        WHERE user_id = %s
        ORDER BY created_at DESC
    """, (user_id,))
    rows = cur.fetchall()
    cur.close()

    result = []
    for r in rows:
        result.append({
            "id": r[0],
            "custom_name": r[1],
            "created_at": r[2].isoformat()
        })

    return jsonify(result)


# returns geometry of a starred route
@app.route("/get-starred-route/<int:route_id>")
def get_starred_route(route_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 403

    cur = map_conn.cursor()
    cur.execute("""
        SELECT route_json, directions
        FROM starred_routes
        WHERE id = %s AND user_id = %s
    """, (route_id, user_id))

    row = cur.fetchone()
    cur.close()

    if not row:
        return jsonify({"error": "Route not found"}), 404

    route_json, directions = row

    if isinstance(route_json, str):
        route_json = json.loads(route_json)
    if isinstance(directions, str):
        directions = json.loads(directions)

    return jsonify({
        "route_json": route_json,
        "directions": directions
    })


# deletes a starred route
@app.route("/delete_starred_route", methods=["POST"])
def delete_starred_route():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 403

    data = request.json
    route_id = data.get("id")

    if not route_id:
        return jsonify({"error": "Missing route id"}), 400

    cur = map_conn.cursor()
    try:
        cur.execute("""
            DELETE FROM starred_routes
            WHERE id = %s AND user_id = %s
        """, (route_id, user_id))

        if cur.rowcount == 0:
            map_conn.rollback()
            return jsonify({"error": "Route not found"}), 404

        map_conn.commit()

    except Exception as e:
        map_conn.rollback()
        print("Error deleting starred route:", e)
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()

    return jsonify({"success": True})


# returns a list of alerts from alerts table
@app.route("/alerts", methods=["GET"])
def get_alerts():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 403

    cur = map_conn.cursor()
    cur.execute("""
        SELECT id, user_id, alert_text, created_at
        FROM alerts
        ORDER BY created_at DESC
    """)
    rows = cur.fetchall()
    cur.close()

    alerts = [
        {
            "id": row[0],
            "user_id": row[1],
            "alert_text": row[2],
            "created_at": row[3].isoformat()
        }
        for row in rows
    ]

    return jsonify(alerts)


# add alert to alerts table
@app.route("/create-alert", methods=["POST"])
def create_alert():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 403

    data = request.json
    alert_text = data.get("alert_text")

    if not alert_text or not alert_text.strip():
        return jsonify({"error": "Missing alert text"}), 400

    cur = map_conn.cursor()
    try:
        cur.execute("""
            INSERT INTO alerts (user_id, alert_text)
            VALUES (%s, %s)
        """, (user_id, alert_text.strip()))
        map_conn.commit()
    except Exception as e:
        map_conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()

    return jsonify({"success": True})


# deletes alert from alerts table
@app.route("/delete-alert/<int:alert_id>", methods=["DELETE"])
def delete_alert(alert_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 403

    if not session.get("is_admin"):
        return jsonify({"error": "Not authorized"}), 403

    cur = map_conn.cursor()
    try:
        cur.execute("DELETE FROM alerts WHERE id = %s", (alert_id,))
        if cur.rowcount == 0:
            return jsonify({"error": "Alert not found"}), 404
        map_conn.commit()
    except Exception as e:
        map_conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()

    return jsonify({"success": True})


# update user's settings in users table
@app.route("/update-settings", methods=["POST"])
def update_settings():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 403

    data = request.json
    mode = data.get("mode")
    live_updates = data.get("live_updates")
    voice_over = data.get("voice_over")

    if mode not in ("light", "dark"):
        return jsonify({"error": "Invalid mode"}), 400

    cur = map_conn.cursor()
    try:
        cur.execute("""
            UPDATE users
            SET mode = %s,
                live_updates = %s,
                voice_over = %s
            WHERE user_id = %s
        """, (mode, live_updates, voice_over, user_id))
        map_conn.commit()
    except Exception as e:
        map_conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()

    return jsonify({"success": True})


if __name__ == '__main__':
    app.run(debug=True)

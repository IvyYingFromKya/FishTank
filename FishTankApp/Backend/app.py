# backend/app.py

from datetime import datetime, timedelta
import sqlite3

from flask import Flask, render_template, redirect, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError

from models import db, User, Node, Sensor, NodeStatus, Location  # keep Sensor imported if you need it elsewhere
from auth import auth_bp, login_manager
from nodes import nodes_bp
from sensors import sensors_bp
from ingest import ingest_bp
from config import config_bp

# ---------------------------------------------------------------------
# Flask setup
# ---------------------------------------------------------------------
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sensor_data.db'
app.config['SECRET_KEY'] = 'supersecretkey'

db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

# Blueprints
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(nodes_bp, url_prefix='/nodes')
app.register_blueprint(sensors_bp, url_prefix='/sensors')
app.register_blueprint(ingest_bp, url_prefix='/ingest')
app.register_blueprint(config_bp, url_prefix='/config')

with app.app_context():
    db.create_all()


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# =====================================================================
# DASHBOARD
# =====================================================================
# ===== Dashboard API =====
from datetime import datetime, timedelta
import sqlite3
from flask import jsonify, request
from flask_login import login_required

SENSOR_DB_PATH = 'instance/sensor_data.db'

def _sensor_conn():
    conn = sqlite3.connect(SENSOR_DB_PATH)
    conn.row_factory = sqlite3.Row
    # keep foreign keys sane if we ever write
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def _range_to_start(ts_range: str) -> datetime | None:
    now = datetime.now()
    ts_range = (ts_range or '24H').upper()
    if ts_range == 'ALL':
        return None
    if ts_range == '7D':
        return now - timedelta(days=7)
    if ts_range == '1M':
        return now - timedelta(days=30)
    return now - timedelta(hours=24)

# ---------------------------------------------------------------------
# Cards: totals & quick stats
# ---------------------------------------------------------------------
@app.route('/api/dashboard/summary')
@login_required
def api_dashboard_summary():
    # Nodes (SQLAlchemy)
    total_nodes = Node.query.count()
    # assuming NodeStatus.code == 'ACTIVE' means active
    active_status = NodeStatus.query.filter_by(code='ACTIVE').first()
    active_nodes = (
        Node.query.filter_by(node_status_id=active_status.node_status_id).count()
        if active_status else 0
    )

    # Sensors (sqlite)
    conn = _sensor_conn()
    cur = conn.cursor()

    # total sensors
    cur.execute("SELECT COUNT(*) AS c FROM sensors")
    total_sensors = cur.fetchone()['c']

    # active sensors (via latest status log)
    cur.execute("""
        WITH latest AS (
          SELECT sensor_id, MAX(timestamp) AS max_ts
          FROM sensor_status_log
          GROUP BY sensor_id
        )
        SELECT COUNT(*) AS c
        FROM sensors s
        LEFT JOIN latest l ON l.sensor_id = s.sensor_id
        LEFT JOIN sensor_status_log st
          ON st.sensor_id = s.sensor_id AND st.timestamp = l.max_ts
        LEFT JOIN sensor_status ss
          ON ss.sensor_status_id = st.sensor_status_id
        WHERE COALESCE(LOWER(ss.sensor_status_code),'') = 'active'
    """)
    active_sensors = cur.fetchone()['c']

    # alerts: treat non-active statuses as alerts; “critical” == 'faulty'
    cur.execute("""
        WITH latest AS (
          SELECT sensor_id, MAX(timestamp) AS max_ts
          FROM sensor_status_log
          GROUP BY sensor_id
        )
        SELECT
          SUM(CASE WHEN COALESCE(LOWER(ss.sensor_status_code),'') <> 'active' THEN 1 ELSE 0 END) AS alerts,
          SUM(CASE WHEN COALESCE(LOWER(ss.sensor_status_code),'') = 'faulty' THEN 1 ELSE 0 END) AS critical
        FROM sensors s
        LEFT JOIN latest l ON l.sensor_id = s.sensor_id
        LEFT JOIN sensor_status_log st
          ON st.sensor_id = s.sensor_id AND st.timestamp = l.max_ts
        LEFT JOIN sensor_status ss
          ON ss.sensor_status_id = st.sensor_status_id
    """)
    row = cur.fetchone()
    total_alerts = row['alerts'] or 0
    critical_alerts = row['critical'] or 0

    # data points today (readings since midnight)
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    cur.execute("""
        SELECT COUNT(*) AS c
        FROM readings
        WHERE timestamp >= ?
    """, (today_start.strftime('%Y-%m-%d %H:%M:%S'),))
    data_points_today = cur.fetchone()['c']

    conn.close()

    return jsonify({
        "total_nodes": total_nodes,
        "active_nodes": active_nodes,
        "total_sensors": total_sensors,
        "active_sensors": active_sensors,
        "total_alerts": total_alerts,
        "critical_alerts": critical_alerts,
        "data_points_today": data_points_today
    })


# ---------------------------------------------------------------------
# Charts: temperature / humidity time series
#   - type: temperature | humidity
#   - range: 24H | 7D | 1M
# Returns: { labels: [...ISO...], series: [float,...] }
# ---------------------------------------------------------------------
@app.route('/api/dashboard/chart')
@login_required
def api_dashboard_chart():
    """
    Return multi-series chart data grouped by sensor so the dashboard can draw
    one line per sensor.

    Response shape:
    {
      "datasets": [
        {"sensor_id": 1, "label": "Tank A Temp", "data": [{"x": "...", "y": 24.5}, ...]},
        ...
      ]
    }
    """
    series_type = (request.args.get('type') or 'temperature').lower()
    ts_range = request.args.get('range') or '24H'

    if series_type not in ('temperature', 'humidity'):
        return jsonify({"error": "type must be 'temperature' or 'humidity'"}), 400

    start_dt = _range_to_start(ts_range)
    value_col = 'temperature' if series_type == 'temperature' else 'humidity'

    conn = _sensor_conn()
    cur = conn.cursor()

    try:
        if start_dt is None:
            cur.execute(f"""
                SELECT
                  r.sensor_id,
                  COALESCE(s.name, 'Sensor ' || r.sensor_id) AS sensor_name,
                  r.timestamp,
                  r.{value_col} AS val
                FROM readings r
                LEFT JOIN sensors s
                  ON s.sensor_id = r.sensor_id
                ORDER BY r.sensor_id ASC, r.timestamp ASC
            """)
        else:
            start_str = start_dt.strftime('%Y-%m-%d %H:%M:%S')
            cur.execute(f"""
                SELECT
                  r.sensor_id,
                  COALESCE(s.name, 'Sensor ' || r.sensor_id) AS sensor_name,
                  r.timestamp,
                  r.{value_col} AS val
                FROM readings r
                LEFT JOIN sensors s
                  ON s.sensor_id = r.sensor_id
                WHERE r.timestamp >= ?
                ORDER BY r.sensor_id ASC, r.timestamp ASC
            """, (start_str,))

        rows = cur.fetchall()

        # Fallback to all-time data when selected range has no records.
        if not rows and start_dt is not None:
            cur.execute(f"""
                SELECT
                  r.sensor_id,
                  COALESCE(s.name, 'Sensor ' || r.sensor_id) AS sensor_name,
                  r.timestamp,
                  r.{value_col} AS val
                FROM readings r
                LEFT JOIN sensors s
                  ON s.sensor_id = r.sensor_id
                ORDER BY r.sensor_id ASC, r.timestamp ASC
            """)
            rows = cur.fetchall()
    except sqlite3.OperationalError:
        # e.g., no humidity column yet
        rows = []

    conn.close()

    grouped = {}
    for row in rows:
        sid = row['sensor_id']
        if sid not in grouped:
            grouped[sid] = {
                "sensor_id": sid,
                "label": row['sensor_name'] or f"Sensor {sid}",
                "data": []
            }

        try:
            y_val = float(row['val']) if row['val'] is not None else None
        except (TypeError, ValueError):
            y_val = None

        grouped[sid]["data"].append({"x": row['timestamp'], "y": y_val})

    return jsonify({"datasets": list(grouped.values())})


# ---------------------------------------------------------------------
# Latest readings table (joins sensor & node names and most recent reading)
# Returns: [{sensor_id, name, node, value, timestamp, status}]
# ---------------------------------------------------------------------
@app.route('/api/dashboard/latest')
@login_required
def api_dashboard_latest():
    conn = _sensor_conn()
    cur = conn.cursor()

    # latest reading per sensor (temperature shown; add humidity if you prefer)
    cur.execute("""
        WITH last_r AS (
          SELECT sensor_id, MAX(timestamp) AS max_ts
          FROM readings
          GROUP BY sensor_id
        ),
        last_s AS (
          SELECT sensor_id, MAX(timestamp) AS max_ts
          FROM sensor_status_log
          GROUP BY sensor_id
        )
        SELECT
          s.sensor_id,
          s.name,
          COALESCE(n.node_name, '') AS node_name,
          r.temperature AS value,
          r.timestamp,
          COALESCE(ss.sensor_status_code, 'UNKNOWN') AS status_code
        FROM sensors s
        LEFT JOIN last_r lr
          ON lr.sensor_id = s.sensor_id
        LEFT JOIN readings r
          ON r.sensor_id = s.sensor_id AND r.timestamp = lr.max_ts
        LEFT JOIN nodes n
          ON n.node_id = s.node_id
        LEFT JOIN last_s ls
          ON ls.sensor_id = s.sensor_id
        LEFT JOIN sensor_status_log st
          ON st.sensor_id = s.sensor_id AND st.timestamp = ls.max_ts
        LEFT JOIN sensor_status ss
          ON ss.sensor_status_id = st.sensor_status_id
        ORDER BY (r.timestamp IS NULL), r.timestamp DESC, s.sensor_id ASC
        LIMIT 50
    """)
    rows = cur.fetchall()
    conn.close()

    data = [{
        "sensor_id": row["sensor_id"],
        "name": row["name"],
        "node": row["node_name"],
        "value": row["value"],
        "timestamp": row["timestamp"],
        "status": row["status_code"]
    } for row in rows]

    return jsonify({"items": data})







@app.route('/ui/dashboard')
@login_required
def dashboard():
    return render_template(
        'main.html',
        active_page='dashboard',
        content_template='includes/dashboard_content.html'
    )


# =====================================================================
# NODES (UI)
# =====================================================================
def serialize_node(node):
    """Accepts either a SQLAlchemy Node or a pre-serialized dict and returns a dict."""
    if isinstance(node, dict):
       	# already serialized
       	return node
    return {
        "node_id": node.node_id,
        "hostname": node.hostname or "",
        "ip_address": node.ip_address or "",
        "location_id": node.location_id,
        "location_name": node.location.name if getattr(node, "location", None) else "N/A",
        "node_status_id": node.node_status_id,
        "status_code": node.status.code if getattr(node, "status", None) else "N/A",
        "shared_folder_alias": node.shared_folder_alias or "",
        "shared_folder_path": node.shared_folder_path or "",
        "local_drive_name": node.local_drive_name or "",
        "local_drive_path": node.local_drive_path or "",
        "description": node.description or "",
        "registered_on": (
            node.registered_on.strftime("%Y-%m-%d %H:%M:%S")
            if getattr(node, "registered_on", None) else ""
        ),
    }


@app.route("/ui/nodes")
@login_required
def nodes():
    page = request.args.get("page", 1, type=int)
    per_page = 10

    # Query with eager loading
    node_query = (
        Node.query
        .options(joinedload(Node.location), joinedload(Node.status))
        .order_by(Node.node_id)
    )

    # Pagination
    pagination = node_query.paginate(page=page, per_page=per_page, error_out=False)
    paginated_nodes = [serialize_node(n) for n in pagination.items]

    # Dropdown sources
    locations = Location.query.order_by(Location.name).all()
    statuses = NodeStatus.query.order_by(NodeStatus.code).all()

    location_filters = [loc.name for loc in locations]
    status_filters = [st.code for st in statuses]

    # Stats
    stats = {
        "total": Node.query.count(),
        "active": Node.query.filter_by(node_status_id=1).count(),
        "inactive": Node.query.filter_by(node_status_id=2).count(),
        "maintenance": Node.query.filter_by(node_status_id=3).count(),
    }

    raw_nodes = paginated_nodes  # Only the nodes on current page
    serialized_nodes = [serialize_node(node) for node in pagination.items]  # ONLY ONCE

    return render_template(
        "main.html",
        active_page='nodes',
        content_template="includes/nodes_content.html",
        nodes=serialized_nodes,
	pagination=pagination,
        total_pages=pagination.pages,
        current_page=page,
        has_next=pagination.has_next,
        has_prev=pagination.has_prev,
        next_num=pagination.next_num,
        prev_num=pagination.prev_num,
        status_list=statuses,          	# for modals
        status_options=status_filters,  # for filter dropdown
        location_list=locations,	# for modals
        location_options=location_filters,  # for filter dropdown
        stats=stats
    )

@app.route('/ui/nodes/add', methods=['POST'])
@login_required
def add_node():
    try:
        node = Node(
            hostname=request.form.get('hostname'),
            ip_address=request.form.get('ip_address'),
            location_id=request.form.get('location_id') or None,
            node_status_id=request.form.get('node_status_id') or None,
            shared_folder_alias=request.form.get('shared_folder_alias'),
            shared_folder_path=request.form.get('shared_folder_path'),
            local_drive_name=request.form.get('local_drive_name'),
            local_drive_path=request.form.get('local_drive_path'),
            description=request.form.get('description')
        )
        db.session.add(node)
        db.session.commit()
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e))

@app.route('/ui/nodes/edit', methods=['POST'])
@login_required
def edit_node():
    node_id = request.form.get('node_id')
    node = db.session.get(Node, node_id)
    if not node:
        return jsonify({'success': False, 'error': 'Node not found'}), 404

    node.hostname = request.form.get('hostname')
    node.ip_address = request.form.get('ip_address')
    node.location_id = request.form.get('location_id')
    node.node_status_id = request.form.get('node_status_id')
    node.shared_folder_alias = request.form.get('shared_folder_alias')
    node.shared_folder_path = request.form.get('shared_folder_path')
    node.local_drive_name = request.form.get('local_drive_name')
    node.local_drive_path = request.form.get('local_drive_path')
    node.description = request.form.get('description')

    db.session.commit()
    return jsonify({'success': True})


# --- SINGLE DELETE (id in URL) ---
@app.route("/ui/nodes/<int:node_id>/delete", methods=["POST"])
@login_required
def delete_node(node_id):
    node = db.session.get(Node, node_id)
    if not node:
        return jsonify({"success": False, "error": "Node not found"}), 404
    try:
        db.session.delete(node)
        db.session.commit()
        return jsonify({"success": True})
    except IntegrityError as e:
        db.session.rollback()
        return jsonify({"success": False, "error": "Delete failed (FK constraint?)"}), 409
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

# --- BULK DELETE (ids array in JSON) ---
@app.route("/ui/nodes/delete", methods=["POST"])
@login_required
def delete_nodes_bulk():
    data = request.get_json(silent=True) or {}
    ids = data.get("ids", [])
    if not ids:
        return jsonify({"success": False, "error": "No ids provided"}), 400

    try:
        # Load only existing ids to avoid errors
        existing = Node.query.filter(Node.node_id.in_(ids)).all()
        if not existing:
            return jsonify({"success": False, "error": "No matching nodes found"}), 404

        for n in existing:
            db.session.delete(n)
        db.session.commit()
        return jsonify({"success": True, "deleted": [n.node_id for n in existing]})
    except IntegrityError:
        db.session.rollback()
        return jsonify({"success": False, "error": "Delete failed (FK constraint?)"}), 409
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

# =====================================================================
# SENSORS (UI)
# =====================================================================
@app.route('/ui/sensors')
@login_required
def sensors_ui():
    """
    Render the Sensors management page.
    Uses raw sqlite3 because your sensors tables live in instance/sensor_data.db.
    Adjust DB path if you actually store everything in the same DB file.
    """
    # ---- Connect to the SQLite where the sensors tables live ----
    DB_PATH = 'instance/sensor_data.db'
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # ---- Fetch sensors with latest status and node name ----
    # sensor_status_log columns: sensor_status_log_id, sensor_id, status_id, timestamp, status_message
    # sensor_status columns: status_id, sensor_status_code, status_description
    # nodes table has node_id, node_name (we show node_name)
    cur.execute("""
    SELECT 
        s.sensor_id, s.node_id, s.sensor_device_id, s.sensor_device_path,
        s.sensor_brand, s.sensor_model, s.sensor_specification, s.sensor_pin,
        s.sensor_description, s.name, s.registered_on,
        ss.sensor_status_code AS status_code,
        ss.status_description AS status_description,
        t.sensor_type AS type_name,
        l.name AS location_name,
        n.node_name AS node_name
    FROM sensors s
    LEFT JOIN (
        SELECT sensor_id, MAX(timestamp) AS max_time
        FROM sensor_status_log
        GROUP BY sensor_id
    ) latest_status ON s.sensor_id = latest_status.sensor_id
    LEFT JOIN sensor_status_log st 
        ON s.sensor_id = st.sensor_id AND latest_status.max_time = st.timestamp
    LEFT JOIN sensor_status ss ON st.sensor_status_id = ss.sensor_status_id
    LEFT JOIN sensor_type t ON s.sensor_type_id = t.sensor_type_id
    LEFT JOIN locations l ON s.location_id = l.location_id
    LEFT JOIN nodes n ON s.node_id = n.node_id
    """)


    sensors = cur.fetchall()

    # ---- Dropdown data ----
    cur.execute("SELECT name FROM locations ORDER BY name")
    location_options = [row['name'] for row in cur.fetchall()]

    cur.execute("SELECT sensor_status_code FROM sensor_status ORDER BY sensor_status_code")
    status_options = [row['sensor_status_code'] for row in cur.fetchall()]

    # ---- Stats ----
    total = len(sensors)
    active = sum(1 for s in sensors if (s['status_code'] or '').lower() == 'active')
    inactive = sum(1 for s in sensors if (s['status_code'] or '').lower() == 'inactive')
    faulty = sum(1 for s in sensors if (s['status_code'] or '').lower() == 'faulty')
    stats = {
        "total": total,
        "active": active,
        "inactive": inactive,
        "faulty": faulty
    }

    conn.close()

    return render_template(
        'main.html',
        active_page='sensors',
        content_template='includes/sensors_content.html',
        sensors=sensors,
        stats=stats,
        location_options=location_options,
        status_options=status_options
    )


# =====================================================================
# (OPTIONAL) Sensors data API (unchanged logic, but made safer)
# =====================================================================
@app.route('/api/sensors')
@login_required
def sensors_api():
    conn = None
    try:
        time_range = request.args.get('range', '24H')
        now = datetime.now()

        ranges = {
            '24H': timedelta(hours=24),
            '7D': timedelta(days=7),
            '1M': timedelta(days=30)
        }
        delta = ranges.get(time_range.upper(), timedelta(hours=24))
        start_time = now - delta

        conn = sqlite3.connect('instance/sensor_data.db')
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # NOTE: Adjust this query to your exact schema if needed
        cur.execute("""
            SELECT sensors.sensor_id, readings.timestamp, readings.temperature
            FROM readings
            JOIN sensors ON sensors.sensor_id = readings.sensor_id
            WHERE readings.timestamp >= ?
            ORDER BY readings.timestamp ASC
        """, (start_time.strftime('%Y-%m-%d %H:%M:%S'),))

        rows = cur.fetchall()

        data = {
            "temperature": [],
            "humidity": []
        }
        # If your schema doesn't have 'type' or 'value', adapt here
        for row in rows:
            record = {
                "timestamp": row["timestamp"],
                # "value": row["value"]   # If you have different column, replace
                "value": row["temperature"]
            }
            # Adjust this logic to your schema (removed 'type' for simplicity)
            data["temperature"].append(record)

        return jsonify(data)

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()
#======================================================================
# DELETE FEATURES
#======================================================================

# --- SENSORS: Single delete ---
@app.route("/ui/sensors/<int:sensor_id>/delete", methods=["POST"])
@login_required
def delete_sensor(sensor_id):
    DB_PATH = 'instance/sensor_data.db'
    import sqlite3
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA foreign_keys = ON")
        cur = conn.cursor()

        cur.execute("DELETE FROM sensors WHERE sensor_id = ?", (sensor_id,))
        conn.commit()
        deleted = cur.rowcount
        cur.close(); conn.close()

        if deleted == 0:
            return jsonify({"success": False, "error": "Sensor not found"}), 404
        return jsonify({"success": True})
    except sqlite3.IntegrityError:
        # likely blocked by child rows (e.g., readings or status logs)
        try:
            conn.rollback()
        except Exception:
            pass
        return jsonify({"success": False, "error": "Delete blocked by foreign key constraints"}), 409
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return jsonify({"success": False, "error": str(e)}), 500


# --- SENSORS: Bulk delete ---
@app.route("/ui/sensors/delete", methods=["POST"])
@login_required
def delete_sensors_bulk():
    DB_PATH = 'instance/sensor_data.db'
    import sqlite3, json
    data = request.get_json(silent=True) or {}
    ids = data.get("ids", [])
    if not ids:
        return jsonify({"success": False, "error": "No ids provided"}), 400

    # Ensure integers only
    try:
        ids = [int(x) for x in ids]
    except Exception:
        return jsonify({"success": False, "error": "Invalid id list"}), 400

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA foreign_keys = ON")
        cur = conn.cursor()

        qmarks = ",".join("?" for _ in ids)
        cur.execute(f"DELETE FROM sensors WHERE sensor_id IN ({qmarks})", ids)
        conn.commit()
        deleted = cur.rowcount
        cur.close(); conn.close()

        if deleted == 0:
            return jsonify({"success": False, "error": "No matching sensors found"}), 404
        return jsonify({"success": True, "deleted": deleted})
    except sqlite3.IntegrityError:
        try:
            conn.rollback()
        except Exception:
            pass
        return jsonify({"success": False, "error": "Delete blocked by foreign key constraints"}), 409
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return jsonify({"success": False, "error": str(e)}), 500



# =====================================================================
# CONFIG
# =====================================================================
@app.route('/ui/config')
@login_required
def config():
    return render_template(
        'main.html',
        active_page='config',
        content_template='includes/config_content.html'
    )


# =====================================================================
# HOME / WELCOME
# =====================================================================
@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect('/ui/dashboard')
    return redirect('/auth/login')


# =====================================================================
# MAIN
# =====================================================================
if __name__ == '__main__':
    app.run(debug=True)

# backend/app.py

from datetime import datetime, timedelta
import sqlite3

from flask import Flask, render_template, redirect, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload

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
    return {
        'node_id': node.node_id,
        'hostname': node.hostname,
        'ip_address': node.ip_address,
        'location_id': node.location_id,
        'location_name': node.location.name if node.location else "N/A",
        'node_status_id': node.node_status_id,
        'status_code': node.status.code if node.status else "N/A",
        'shared_folder_alias': node.shared_folder_alias,
        'shared_folder_path': node.shared_folder_path,
        'local_drive_name': node.local_drive_name,
        'local_drive_path': node.local_drive_path,
        'description': node.description,
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
    paginated_nodes = pagination.items

    # Convert each SQLAlchemy object into a dictionary for JSON safety
    serializable_nodes = []
    for node in paginated_nodes:
        serializable_nodes.append({
            'node_id': node.node_id,
            'hostname': node.hostname,
            'ip_address': node.ip_address,
            'location': node.location.name if node.location else 'N/A',
            'location_id': node.location_id,
            'node_status': node.status.code if node.status else 'N/A',
            'node_status_id': node.node_status_id,
            'shared_folder_alias': node.shared_folder_alias,
            'shared_folder_path': node.shared_folder_path,
            'local_drive_name': node.local_drive_name,
            'local_drive_path': node.local_drive_path,
            'description': node.description,
        })


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
    serializable_nodes = [serialize_node(n) for n in raw_nodes]

    return render_template(
        "main.html",
        active_page='nodes',
        content_template="includes/nodes_content.html",
        nodes=serializable_nodes,
	pagination=pagination,
        total_pages=pagination.pages,
        current_page=page,
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
    return redirect('./login')


# =====================================================================
# MAIN
# =====================================================================
if __name__ == '__main__':
    app.run(debug=True)

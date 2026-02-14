from app import app, db
from sqlalchemy import inspect, text

def inspect_all_tables():
    with app.app_context():
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()

        if not tables:
            print("No tables found in the database.")
            return

        print(f"Found {len(tables)} tables: {tables}\n")

        for table in tables:
            print(f"🔍 Contents of table '{table}':")
            try:
                query = db.session.execute(text(f"SELECT * FROM {table}"))
                rows = query.mappings().all()

                if not rows:
                    print("  🚫 No records found.")
                else:
                    for row in rows:
                        print("  ", dict(row))

            except Exception as e:
                print(f"  ❌ Error reading table '{table}': {e}")

            print()

if __name__ == "__main__":
    inspect_all_tables()

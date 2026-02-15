import mysql.connector

# --- CONFIG DATABASE XAMPP ---
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'shopping_list'
}

def migrate():
    print("Starting database migration...")
    try:
        conn = mysql.connector.connect(**db_config)
        c = conn.cursor()

        # 1. Add 'category' to 'items' table
        try:
            print("Attempting to add 'category' column to 'items'...")
            c.execute("ALTER TABLE items ADD COLUMN category VARCHAR(50) DEFAULT 'General'")
            print("SUCCESS: 'category' column added.")
        except mysql.connector.Error as err:
            if err.errno == 1060: # Dulplicate column name
                print("INFO: 'category' column already exists.")
            else:
                print(f"ERROR: {err}")

        # 2. Add 'is_archived' to 'lists' table
        try:
            print("Attempting to add 'is_archived' column to 'lists'...")
            c.execute("ALTER TABLE lists ADD COLUMN is_archived BOOLEAN DEFAULT 0")
            print("SUCCESS: 'is_archived' column added.")
        except mysql.connector.Error as err:
            if err.errno == 1060:
                print("INFO: 'is_archived' column already exists.")
            else:
                print(f"ERROR: {err}")
                
        # 3. Add 'created_at' to 'lists' table
        try:
            print("Attempting to add 'created_at' column to 'lists'...")
            c.execute("ALTER TABLE lists ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            print("SUCCESS: 'created_at' column added.")
        except mysql.connector.Error as err:
            if err.errno == 1060:
                print("INFO: 'created_at' column already exists.")
            else:
                print(f"ERROR: {err}")

        conn.commit()
        conn.close()
        print("Migration completed successfully!")

    except mysql.connector.Error as err:
        print(f"CRITICAL DATABASE ERROR: {err}")
        print("Pastikan XAMPP service MySQL sedang RUNNING.")

if __name__ == "__main__":
    migrate()

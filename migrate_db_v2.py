import mysql.connector

# --- CONFIG DATABASE XAMPP ---
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'shopping_list'
}

def migrate():
    print("Starting database migration Phase 2...")
    try:
        conn = mysql.connector.connect(**db_config)
        c = conn.cursor()

        # 1. Add 'budget' to 'lists' table
        try:
            print("Attempting to add 'budget' column to 'lists' table...")
            c.execute("ALTER TABLE lists ADD COLUMN budget DECIMAL(10,2) DEFAULT 0.00")
            print("SUCCESS: 'budget' column added to 'lists' table.")
        except mysql.connector.Error as err:
            if err.errno == 1060: # Duplicate column code
                print("INFO: 'budget' column already exists in 'lists' table.")
            else:
                print(f"ERROR adding budget column: {err}")

        conn.commit()
        conn.close()
        print("Migration Phase 2 completed successfully!")

    except mysql.connector.Error as err:
        print(f"CRITICAL DATABASE ERROR: {err}")
        print("Ensure XAMPP MySQL service is RUNNING.")

if __name__ == "__main__":
    migrate()

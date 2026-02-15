
import mysql.connector

db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'shopping_list'
}

def migrate():
    try:
        conn = mysql.connector.connect(**db_config)
        c = conn.cursor()
        
        # Check if column exists first
        c.execute("SHOW COLUMNS FROM items LIKE 'is_bought'")
        result = c.fetchone()
        
        if not result:
            print("Adding 'is_bought' column to 'items' table...")
            c.execute("ALTER TABLE items ADD COLUMN is_bought BOOLEAN DEFAULT 0")
            conn.commit()
            print("Migration successful: 'is_bought' column added.")
        else:
            print("Column 'is_bought' already exists. Skipping.")
            
        conn.close()
    except Exception as e:
        print(f"Migration Error: {e}")

if __name__ == "__main__":
    migrate()

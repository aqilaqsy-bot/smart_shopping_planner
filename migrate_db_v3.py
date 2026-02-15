import mysql.connector

# --- CONFIG DATABASE XAMPP ---
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'shopping_list'
}

def migrate():
    print("Starting database migration Phase 3 (Knowledge Base)...")
    
    try:
        conn = mysql.connector.connect(**db_config)
        c = conn.cursor()
        
        # Create product_knowledge table
        print("Creating 'product_knowledge' table...")
        c.execute('''CREATE TABLE IF NOT EXISTS product_knowledge (
                     id INT AUTO_INCREMENT PRIMARY KEY, 
                     user_id INT, 
                     item_name VARCHAR(255),
                     price DECIMAL(10,2),
                     location VARCHAR(255),
                     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                     FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                     )''')
        print("SUCCESS: 'product_knowledge' table created/verified.")
        
        conn.commit()
        conn.close()
        print("Migration Phase 3 completed successfully!")
        
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    migrate()

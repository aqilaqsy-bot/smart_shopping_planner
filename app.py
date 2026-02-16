import mysql.connector
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from groq import Groq 
import datetime
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'default_secret_key_change_me')

# --- DEBUG ERROR HANDLER ---
@app.errorhandler(500)
def internal_error(error):
    import traceback
    return f"<pre>{traceback.format_exc()}</pre>", 500

# --- DATABASE CONFIG ---
# This checks both manual (DB_) and Railway auto-provided (MYSQL) variable names
db_config = {
    'host': os.getenv('DB_HOST') or os.getenv('MYSQLHOST', 'localhost'),
    'user': os.getenv('DB_USER') or os.getenv('MYSQLUSER', 'root'),      
    'password': os.getenv('DB_PASSWORD') or os.getenv('MYSQLPASSWORD', ''),      
    'database': os.getenv('DB_NAME') or os.getenv('MYSQLDATABASE', 'shopping_list'),
    'port': int(os.getenv('DB_PORT') or os.getenv('MYSQLPORT', 3306))
}

# Smart Port Logic: If host is internal, force port 3306 (internal port)
if db_config['host'] == 'mysql.railway.internal':
    db_config['port'] = 3306

print("--- STARTUP DIAGNOSTICS ---")
print(f"Connecting to DB: {db_config['host']}:{db_config['port']}")
print(f"User: {db_config['user']}")
print(f"Database: {db_config['database']}")
if db_config['password']:
    print("Password: [PROVIDED]")
else:
    print("Password: [MISSING/EMPTY]")
print("---------------------------")

# --- DATABASE CONNECTION FUNCTION ---
def get_db_connection():
    conn = mysql.connector.connect(**db_config)
    return conn

# --- TABLE SETUP (AUTO-RUN) ---
def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Table Users
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                 id INT AUTO_INCREMENT PRIMARY KEY, 
                 username VARCHAR(255) UNIQUE, 
                 password VARCHAR(255)
                 )''')
    
    # Table Lists (Updated with budget)
    c.execute('''CREATE TABLE IF NOT EXISTS lists (
                 id INT AUTO_INCREMENT PRIMARY KEY, 
                 user_id INT, 
                 name VARCHAR(255),
                 budget DECIMAL(10,2) DEFAULT 0.00,
                 is_archived BOOLEAN DEFAULT 0,
                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                 FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                 )''')

    # Table Items
    c.execute('''CREATE TABLE IF NOT EXISTS items (
                 id INT AUTO_INCREMENT PRIMARY KEY, 
                 list_id INT, 
                 name VARCHAR(255), 
                 price DECIMAL(10,2), 
                 quantity INT,
                 category VARCHAR(50) DEFAULT 'General',
                 is_bought BOOLEAN DEFAULT 0,
                 FOREIGN KEY(list_id) REFERENCES lists(id) ON DELETE CASCADE
                 )''')
    
    # Table Knowledge Base (AI Training)
    c.execute('''CREATE TABLE IF NOT EXISTS product_knowledge (
                 id INT AUTO_INCREMENT PRIMARY KEY, 
                 user_id INT, 
                 item_name VARCHAR(255),
                 price DECIMAL(10,2),
                 location VARCHAR(255),
                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                 FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                 )''')

    conn.commit()
    conn.close()

# ... (COMMON ROUTES) ...

# ... (OTHER ROUTES) ...



# Run DB setup
try:
    init_db()
    print("MySQL Database successfully connected!")
except Exception as e:
    print(f"Database Error: {e}")
    print("Ensure MySQL is ON and the 'shopping_list' database exists.")

# --- AUTH ROUTES ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_pw = generate_password_hash(password)
        
        conn = get_db_connection()
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed_pw))
            conn.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except mysql.connector.IntegrityError:
            flash('Username already taken.', 'danger')
        except Exception as e:
            flash(f'Error: {e}', 'danger')
        finally:
            conn.close()
            
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        c = conn.cursor(dictionary=True)
        c.execute("SELECT * FROM users WHERE username=%s", (username,))
        user = c.fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


# --- DEBUG ROUTES ---
@app.route('/debug_env')
def debug_env():
    # Return ONLY the keys of environment variables for security
    keys = sorted(list(os.environ.keys()))
    return jsonify({
        'environment_keys': keys,
        'has_db_host': 'DB_HOST' in os.environ,
        'has_db_port': 'DB_PORT' in os.environ,
        'current_time': datetime.datetime.now().isoformat()
    })

# --- DASHBOARD ROUTES ---
@app.route('/')
def home():
    if 'user_id' in session: return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    user_id = session['user_id']
    query = request.args.get('q', '') # Search Query
    
    conn = get_db_connection()
    c = conn.cursor(dictionary=True)

    # 1. Fetch User Lists (Only non-archived)
    c.execute("SELECT * FROM lists WHERE user_id=%s AND is_archived=0 ORDER BY created_at DESC", (user_id,))
    user_lists = c.fetchall()

    if not user_lists:
        # Create default list if none exists
        c.execute("INSERT INTO lists (user_id, name) VALUES (%s, %s)", (user_id, "Main List"))
        conn.commit()
        c.execute("SELECT * FROM lists WHERE user_id=%s AND is_archived=0", (user_id,))
        user_lists = c.fetchall()

    # 2. Determine Active List
    active_list_id = request.args.get('list_id')
    active_list = None
    
    if active_list_id:
        c.execute("SELECT * FROM lists WHERE id=%s AND user_id=%s", (active_list_id, user_id))
        active_list = c.fetchone()
    
    if not active_list and user_lists: 
        active_list = user_lists[0]
    
    items_db = []
    budget = 0.0

    if active_list:
        # Get budget from the list
        budget = float(active_list['budget']) if active_list['budget'] else 0.0

        # 3. Ambil Items (Filter search by NAME or CATEGORY)
        sql_items = "SELECT * FROM items WHERE list_id=%s"
        params = [active_list['id']]
        
        c.execute(sql_items, tuple(params))
        items_db = c.fetchall()
    
    conn.close()

    formatted_items = []
    total_spent = 0.0
    for item in items_db:
        price = float(item['price'])
        qty = int(item['quantity'])
        t = price * qty
        total_spent += t
        formatted_items.append({
            'id': item['id'], 
            'name': item['name'], 
            'qty': qty, 
            'price': price, 
            'total': t,
            'category': item.get('category', 'General'),
            'is_bought': item.get('is_bought', 0)
        })

    return render_template('index.html', 
                           username=session['username'],
                           lists=user_lists,       
                           active_list=active_list, 
                           items=formatted_items,
                           total=total_spent,
                           budget=budget,
                           baki=budget - total_spent,
                           search_query=query)

# --- HISTORY ROUTES ---
@app.route('/history')
def history():
    if 'user_id' not in session: return redirect(url_for('login'))
    user_id = session['user_id']
    
    conn = get_db_connection()
    c = conn.cursor(dictionary=True)
    
    # Fetch archived lists
    c.execute("SELECT * FROM lists WHERE user_id=%s AND is_archived=1 ORDER BY created_at DESC", (user_id,))
    archived_lists = c.fetchall()
    
    # Calculate total for each list for display
    history_data = []
    for lst in archived_lists:
        # 1. Calculate Total
        c.execute("SELECT SUM(price * quantity) as total FROM items WHERE list_id=%s", (lst['id'],))
        total_row = c.fetchone()
        total = total_row['total'] if total_row else 0.0
        
        # 2. Fetch Items in List & Format
        c.execute("SELECT * FROM items WHERE list_id=%s", (lst['id'],))
        items_db = c.fetchall()
        
        formatted_items = []
        for item in items_db:
            price = float(item['price'])
            qty = int(item['quantity'])
            formatted_items.append({
                'name': item['name'],
                'category': item.get('category', 'General'),
                'price': price,
                'quantity': qty,
                'total_price': price * qty
            })

        history_data.append({
            'list': lst,
            'total': float(total) if total else 0.0,
            'purchased_items': formatted_items
        })
        
    conn.close()
    return render_template('history.html', archives=history_data, username=session['username'])

@app.route('/archive_list/<int:list_id>')
def archive_list(list_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE lists SET is_archived=1 WHERE id=%s AND user_id=%s", (list_id, session['user_id']))
    conn.commit()
    conn.close()
    flash('List archived successfully.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/restore_list/<int:list_id>')
def restore_list(list_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE lists SET is_archived=0 WHERE id=%s AND user_id=%s", (list_id, session['user_id']))
    conn.commit()
    conn.close()
    flash('List restored to dashboard.', 'success')
    return redirect(url_for('dashboard', list_id=list_id))

@app.route('/delete_list_permanent/<int:list_id>')
def delete_list_permanent(list_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM lists WHERE id=%s AND user_id=%s", (list_id, session['user_id']))
    conn.commit()
    conn.close()
    flash('List deleted permanently.', 'success')
    return redirect(url_for('history'))

# --- CRUD ROUTES ---
@app.route('/create_list', methods=['POST'])
def create_list():
    if 'user_id' not in session: return redirect(url_for('login'))
    list_name = request.form.get('list_name')
    if list_name:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("INSERT INTO lists (user_id, name) VALUES (%s, %s)", (session['user_id'], list_name))
        conn.commit()
        conn.close()
    return redirect(url_for('dashboard'))

@app.route('/add_item', methods=['POST'])
def add_item():
    if 'user_id' not in session: return redirect(url_for('login'))
    list_id = request.form.get('list_id') 
    name = request.form.get('item_name')
    qty = request.form.get('item_qty')
    price = request.form.get('item_price')
    category = request.form.get('item_category', 'General') # Get category
    
    if name and qty and price and list_id:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("INSERT INTO items (list_id, name, price, quantity, category) VALUES (%s, %s, %s, %s, %s)", 
                     (list_id, name, float(price), int(qty), category))
        conn.commit()
        conn.close()
    return redirect(url_for('dashboard', list_id=list_id))

@app.route('/edit_item', methods=['POST'])
def edit_item():
    if 'user_id' not in session: return redirect(url_for('login'))
    item_id = request.form.get('item_id')
    list_id = request.form.get('list_id') 
    name = request.form.get('item_name')
    qty = request.form.get('item_qty')
    price = request.form.get('item_price')
    category = request.form.get('item_category') # Get category update

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE items SET name=%s, quantity=%s, price=%s, category=%s WHERE id=%s", (name, int(qty), float(price), category, item_id))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard', list_id=list_id))

@app.route('/delete/<int:item_id>')
def delete_item(item_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT list_id FROM items WHERE id=%s", (item_id,))
    item = c.fetchone()
    
    if item:
        list_id = item['list_id']
        c.execute("DELETE FROM items WHERE id=%s", (item_id,))
        conn.commit()
        conn.close()
        return redirect(url_for('dashboard', list_id=list_id))
    
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/toggle_bought/<int:item_id>')
def toggle_bought(item_id):
    if 'user_id' not in session: return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    c = conn.cursor(dictionary=True)
    
    # Check item status first
    c.execute("SELECT list_id, is_bought FROM items WHERE id=%s", (item_id,))
    item = c.fetchone()
    
    new_status = 0
    if item:
        new_status = 0 if item['is_bought'] else 1
        c.execute("UPDATE items SET is_bought=%s WHERE id=%s", (new_status, item_id))
        conn.commit()
        success = True
    else:
        success = False
        
    conn.close()
    
    return jsonify({'success': success, 'new_status': new_status})

# --- NEW ROUTES: RENAME & BUDGET ---

@app.route('/rename_list', methods=['POST'])
def rename_list():
    if 'user_id' not in session: return redirect(url_for('login'))
    list_id = request.form.get('list_id')
    new_name = request.form.get('new_name')
    
    if list_id and new_name:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("UPDATE lists SET name=%s WHERE id=%s AND user_id=%s", (new_name, list_id, session['user_id']))
        conn.commit()
        conn.close()
    return redirect(url_for('dashboard', list_id=list_id))

@app.route('/update_budget', methods=['POST'])
def update_budget():
    if 'user_id' not in session: return redirect(url_for('login'))
    amount = request.form.get('budget_amount')
    list_id = request.form.get('list_id')

    if list_id and amount:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("UPDATE lists SET budget=%s WHERE id=%s AND user_id=%s", (amount, list_id, session['user_id']))
        conn.commit()
        conn.close()
        
    return redirect(url_for('dashboard', list_id=list_id))




# --- TOOLS & AI ROUTES ---
@app.route('/tools')
def tools():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('tools.html', username=session['username'])

@app.route('/ai_assistant')
def ai_assistant(): 
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('ai_assistant.html', username=session['username'])

# --- AI ROUTE (CONTEXT AWARE & GROQ) ---
@app.route('/ask_ai', methods=['POST'])
def ask_ai():
    if 'user_id' not in session:
        return jsonify({'answer': "Please login first."})

    data = request.json
    question = data.get('question')
    user_id = session['user_id']

    # ⚠️⚠️⚠️ API KEY FROM ENV ⚠️⚠️⚠️
    GROQ_API_KEY = os.getenv('GROQ_API_KEY') 

    # 1. FETCH DATA FROM DATABASE (MySQL Version)
    conn = get_db_connection()
    c = conn.cursor(dictionary=True)
    
    # Get total budget from all lists
    c.execute("SELECT SUM(budget) as total_budget FROM lists WHERE user_id=%s", (user_id,))
    budget_row = c.fetchone()
    budget = float(budget_row['total_budget']) if budget_row and budget_row['total_budget'] else 0.0
    
    # Fetch All Items (Join with list name)
    c.execute('''
        SELECT items.name, items.price, items.quantity, lists.name as list_name
        FROM items 
        JOIN lists ON items.list_id = lists.id 
        WHERE items.list_id IN (SELECT id FROM lists WHERE user_id=%s)
    ''', (user_id,))
    items = c.fetchall()
    conn.close()

    # 2. FORMAT DATA FOR AI
    data_text = f"User Information:\n- Total Budget: RM {budget:.2f}\n- Item List:\n"
    
    total_spent = 0
    if items:
        for item in items:
            total = float(item['price']) * int(item['quantity'])
            total_spent += total
            data_text += f"  * {item['name']} (RM {item['price']} x {item['quantity']}) in list '{item['list_name']}'\n"
    else:
        data_text += "  (No items yet)\n"

    balance = budget - total_spent
    data_text += f"\n- Total Spent: RM {total_spent:.2f}\n- Remaining Balance: RM {balance:.2f}"

    # 3. SEND TO GROQ
    try:
        client = Groq(api_key=GROQ_API_KEY)
        
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": f"""
                    You are the SmartPlanner financial assistant. 
                    Answer user questions based on the following data:
                    
                    {data_text}
                    
                    IMPORTANT:
                    - Answer in English.
                    - If balance is negative, give a warning.
                    """
                },
                {
                    "role": "user",
                    "content": question,
                }
            ],
            model="llama-3.3-70b-versatile",
        )

        answer = chat_completion.choices[0].message.content
        return jsonify({'answer': answer})

    except Exception as e:
        print(f"Error AI: {e}")
        return jsonify({'answer': f"AI Error: {str(e)}"})

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
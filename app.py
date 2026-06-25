from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime
import sqlite3
import uuid

app = Flask(__name__)
app.secret_key = "super_secret_yls_key"

# Define the designated Staff Email
STAFF_EMAIL = "admin@yls.com"

# ==========================================
# MODELS (Assignment 2 Design Implementation)
# ==========================================

class Person:
    def __init__(self, name, email, password):
        self.name = name
        self.email = email
        self.password = password

class Customer(Person):
    def __init__(self, name, email, password, address):
        super().__init__(name, email, password)
        self.address = address

class Product:
    def __init__(self, product_id, name, price, stock_level, category, icon="📦"):
        self.product_id = product_id
        self.name = name
        self.price = price
        self.stock_level = stock_level
        self.category = category
        self.icon = icon

    def is_in_stock(self, quantity):
        return self.stock_level >= quantity

class CartItem:
    def __init__(self, product, quantity):
        self.product = product
        self.quantity = quantity

    def get_subtotal(self):
        return self.product.price * self.quantity

class Invoice:
    def __init__(self, customer, items, total):
        self.invoice_id = str(uuid.uuid4())[:8]
        self.date = datetime.now()
        self.customer = customer
        self.items = items 
        self.total = total
        self.status = "PENDING"

class PaymentGateway:
    def process_transaction(self, amount):
        return True

# ==========================================
# SQLITE DATABASE CONTROLLER (Singleton)
# ==========================================

class Database:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            cls._instance.db_name = "yls_store.db"
            cls._instance._initialize_data()
        return cls._instance

    def get_connection(self):
        # Open a connection to the SQLite database
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row # Returns rows as dictionaries
        return conn

    def _initialize_data(self):
        # Create tables if they don't exist yet
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS customers (
                                email TEXT PRIMARY KEY,
                                name TEXT,
                                password TEXT,
                                address TEXT)''')
            
            cursor.execute('''CREATE TABLE IF NOT EXISTS products (
                                product_id TEXT PRIMARY KEY,
                                name TEXT,
                                price REAL,
                                stock_level INTEGER,
                                category TEXT,
                                icon TEXT)''')
            
            cursor.execute('''CREATE TABLE IF NOT EXISTS invoices (
                                invoice_id TEXT PRIMARY KEY,
                                customer_email TEXT,
                                date TEXT,
                                total REAL,
                                status TEXT)''')
            
            # Seed the default Admin account
            cursor.execute("SELECT email FROM customers WHERE email = ?", (STAFF_EMAIL,))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO customers VALUES (?, ?, ?, ?)",
                               (STAFF_EMAIL, "Store Manager", "admin123", "YLS Headquarters"))
            
            # Seed the default Products
            cursor.execute("SELECT COUNT(*) FROM products")
            if cursor.fetchone()[0] == 0:
                default_products = [
                    ("P001", "Fresh Milk 1L", 3.50, 20, "Daily Need", "🥛"),
                    ("P002", "Toilet Paper (12 Rolls)", 8.00, 15, "Household", "🧻"),
                    ("P003", "Chocolate Chip Cookies", 4.00, 25, "Snacks", "🍪"),
                    ("P004", "Organic Shampoo", 12.50, 10, "Personal Care", "🧴"),
                    ("P005", "Potato Chips", 3.00, 30, "Snacks", "🥔"),
                    ("P006", "Sourdough Loaf", 6.00, 8, "Bakery", "🥖")
                ]
                cursor.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?)", default_products)
            conn.commit()

    # --- Database Methods ---
    def get_all_products(self):
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM products").fetchall()
            return [Product(r['product_id'], r['name'], r['price'], r['stock_level'], r['category'], r['icon']) for r in rows]

    def get_product(self, product_id):
        with self.get_connection() as conn:
            r = conn.execute("SELECT * FROM products WHERE product_id = ?", (product_id,)).fetchone()
            if r: return Product(r['product_id'], r['name'], r['price'], r['stock_level'], r['category'], r['icon'])
            return None

    def add_product(self, p):
        with self.get_connection() as conn:
            conn.execute("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?)",
                         (p.product_id, p.name, p.price, p.stock_level, p.category, p.icon))
            conn.commit()

    def update_product_stock(self, product_id, new_stock):
        with self.get_connection() as conn:
            conn.execute("UPDATE products SET stock_level = ? WHERE product_id = ?", (new_stock, product_id))
            conn.commit()

    def delete_product(self, product_id):
        with self.get_connection() as conn:
            conn.execute("DELETE FROM products WHERE product_id = ?", (product_id,))
            conn.commit()

    def get_customer(self, email):
        with self.get_connection() as conn:
            r = conn.execute("SELECT * FROM customers WHERE email = ?", (email,)).fetchone()
            if r: return Customer(r['name'], r['email'], r['password'], r['address'])
            return None

    def add_customer(self, c):
        with self.get_connection() as conn:
            conn.execute("INSERT INTO customers VALUES (?, ?, ?, ?)",
                         (c.email, c.name, c.password, c.address))
            conn.commit()

    def add_invoice(self, i):
        with self.get_connection() as conn:
            conn.execute("INSERT INTO invoices VALUES (?, ?, ?, ?, ?)",
                         (i.invoice_id, i.customer.email, i.date.strftime('%Y-%m-%d %H:%M:%S'), i.total, i.status))
            conn.commit()

db = Database()

# ==========================================
# CUSTOMER CONTROLLERS (Flask Routes)
# ==========================================

@app.route('/')
def catalogue():
    if session.get('user') == STAFF_EMAIL:
        return redirect(url_for('staff_dashboard'))
    products = db.get_all_products()
    return render_template('catalogue.html', products=products)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        address = request.form['address']
        
        if db.get_customer(email):
            flash("Email already registered!")
            return redirect(url_for('register'))
            
        new_customer = Customer(name, email, password, address)
        db.add_customer(new_customer)
        flash("Account created successfully. Please login.")
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        customer = db.get_customer(email)
        if customer and customer.password == password:
            session['user'] = email
            session['cart'] = {}
            if email == STAFF_EMAIL:
                return redirect(url_for('staff_dashboard'))
            return redirect(url_for('catalogue'))
            
        flash("Invalid Credentials")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/add_to_cart/<product_id>', methods=['POST'])
def add_to_cart(product_id):
    if 'user' not in session:
        flash("Please login to add items to cart.")
        return redirect(url_for('login'))
        
    qty = int(request.form['quantity'])
    product = db.get_product(product_id)
    
    if not product or not product.is_in_stock(qty):
        flash(f"Only {product.stock_level} items left for {product.name}!")
        return redirect(url_for('catalogue'))
        
    cart = session.get('cart', {})
    cart[product_id] = cart.get(product_id, 0) + qty
    session['cart'] = cart
    flash(f"Added {qty} x {product.name} to cart.")
    return redirect(url_for('catalogue'))

@app.route('/cart')
def view_cart():
    if 'user' not in session or session.get('user') == STAFF_EMAIL:
        return redirect(url_for('login'))
        
    cart_items = []
    total = 0
    for pid, qty in session.get('cart', {}).items():
        product = db.get_product(pid)
        item = CartItem(product, qty)
        cart_items.append(item)
        total += item.get_subtotal()
        
    return render_template('cart.html', cart_items=cart_items, total=total)

@app.route('/checkout', methods=['POST'])
def checkout():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    customer = db.get_customer(session['user'])
    cart_items = []
    total = 0
    
    for pid, qty in session['cart'].items():
        product = db.get_product(pid)
        if not product or not product.is_in_stock(qty):
            flash(f"Sorry, {product.name} is now out of stock.")
            return redirect(url_for('view_cart'))
            
        item = CartItem(product, qty)
        cart_items.append(item)
        total += item.get_subtotal()
        
        # Deduct stock permanently in SQLite
        db.update_product_stock(pid, product.stock_level - qty)

    invoice = Invoice(customer, cart_items, total)
    gateway = PaymentGateway()
    
    if gateway.process_transaction(total):
        invoice.status = "PAID"
        db.add_invoice(invoice)
        session['cart'] = {}
        return render_template('invoice.html', invoice=invoice)
    else:
        flash("Payment failed.")
        return redirect(url_for('view_cart'))

# ==========================================
# STAFF CONTROLLERS (Protected Routes)
# ==========================================

@app.route('/staff')
def staff_dashboard():
    if session.get('user') != STAFF_EMAIL:
        flash("Unauthorized access. Staff only.")
        return redirect(url_for('login'))
        
    products = db.get_all_products()
    return render_template('staff_dashboard.html', products=products)

@app.route('/staff/add_product', methods=['POST'])
def add_product():
    if session.get('user') != STAFF_EMAIL:
        return redirect(url_for('login'))
        
    p_id = request.form['product_id']
    name = request.form['name']
    price = float(request.form['price'])
    stock = int(request.form['stock'])
    category = request.form['category']
    icon = request.form['icon'] 
    
    if db.get_product(p_id):
        flash(f"Error: Product ID '{p_id}' already exists!")
    else:
        new_prod = Product(p_id, name, price, stock, category, icon)
        db.add_product(new_prod)
        flash(f"Success: {name} was added to the catalogue.")
        
    return redirect(url_for('staff_dashboard'))

@app.route('/staff/add_stock/<product_id>', methods=['POST'])
def add_stock(product_id):
    if session.get('user') != STAFF_EMAIL:
        return redirect(url_for('login'))
        
    product = db.get_product(product_id)
    if product:
        try:
            added_qty = int(request.form['added_stock'])
            db.update_product_stock(product_id, product.stock_level + added_qty)
            flash(f"Success: Added {added_qty} units to {product.name}.")
        except ValueError:
            flash("Error: Invalid quantity entered.")
            
    return redirect(url_for('staff_dashboard'))

@app.route('/staff/delete_product/<product_id>', methods=['POST'])
def delete_product(product_id):
    if session.get('user') != STAFF_EMAIL:
        return redirect(url_for('login'))
        
    product = db.get_product(product_id)
    if product:
        db.delete_product(product_id)
        flash(f"Success: {product.name} was removed from the catalogue.")
    return redirect(url_for('staff_dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
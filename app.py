from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime
import uuid

app = Flask(__name__)
app.secret_key = "super_secret_yls_key"

# Define the designated Staff Email
STAFF_EMAIL = "admin@yls.com"

# ==========================================
# MODELS (Assignment 2 Design Implementation)
# ==========================================

class Database:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            cls._instance._initialize_data()
        return cls._instance

    def _initialize_data(self):
        self.customers = {} 
        # Inject the default Admin/Staff account into the database
        self.customers[STAFF_EMAIL] = Customer("Store Manager", STAFF_EMAIL, "admin123", "YLS Headquarters")
        
        self.products = {
            "P001": Product("P001", "Fresh Milk 1L", 3.50, 20, "Beverage", "🥛"),
            "P002": Product("P002", "Toilet Paper (12 Rolls)", 8.00, 15, "Household", "🧻"),
            "P003": Product("P003", "Chocolate Chip Cookies", 4.00, 25, "Bakery", "🍪"),
            "P004": Product("P004", "Organic Shampoo", 12.50, 10, "Personal Care", "🧴"),
            "P005": Product("P005", "Potato Chips", 3.00, 30, "Snacks", "🥔"),
            "P006": Product("P006", "Sourdough Loaf", 6.00, 8, "Bakery", "🥖")
        }
        self.invoices = {}

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

# Initialize Singleton Database
db = Database()

# ==========================================
# CUSTOMER CONTROLLERS (Flask Routes)
# ==========================================

@app.route('/')
def catalogue():
    """Task 2: Browse Online Store Catalogue"""
    # Prevent staff from seeing the customer catalogue
    if session.get('user') == STAFF_EMAIL:
        return redirect(url_for('staff_dashboard'))
        
    products = db.products.values()
    return render_template('catalogue.html', products=products)

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Task 1: Create Customer Accounts"""
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        address = request.form['address']
        
        if email in db.customers:
            flash("Email already registered!")
            return redirect(url_for('register'))
            
        db.customers[email] = Customer(name, email, password, address)
        flash("Account created successfully. Please login.")
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        customer = db.customers.get(email)
        if customer and customer.password == password:
            session['user'] = email
            session['cart'] = {}
            
            # RBAC: Route Staff to their dashboard, Customers to catalogue
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
    """Task 3: Manage Shopping Cart"""
    if 'user' not in session:
        flash("Please login to add items to cart.")
        return redirect(url_for('login'))
        
    qty = int(request.form['quantity'])
    product = db.products.get(product_id)
    
    if not product.is_in_stock(qty):
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
        product = db.products[pid]
        item = CartItem(product, qty)
        cart_items.append(item)
        total += item.get_subtotal()
        
    return render_template('cart.html', cart_items=cart_items, total=total)

@app.route('/checkout', methods=['POST'])
def checkout():
    """Task 4 & 5: Create Invoice and Mock Payment"""
    if 'user' not in session:
        return redirect(url_for('login'))
        
    customer = db.customers[session['user']]
    cart_items = []
    total = 0
    
    for pid, qty in session['cart'].items():
        product = db.products[pid]
        if not product.is_in_stock(qty):
            flash(f"Sorry, {product.name} is now out of stock.")
            return redirect(url_for('view_cart'))
            
        item = CartItem(product, qty)
        cart_items.append(item)
        total += item.get_subtotal()
        product.stock_level -= qty

    invoice = Invoice(customer, cart_items, total)
    gateway = PaymentGateway()
    
    if gateway.process_transaction(total):
        invoice.status = "PAID"
        db.invoices[invoice.invoice_id] = invoice
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
    """Task 7: Manage Store Catalogue (View)"""
    # Security check: Ensure only staff can access this page
    if session.get('user') != STAFF_EMAIL:
        flash("Unauthorized access. Staff only.")
        return redirect(url_for('login'))
        
    products = db.products.values()
    return render_template('staff_dashboard.html', products=products)

@app.route('/staff/add_product', methods=['POST'])
def add_product():
    """Task 7: Manage Store Catalogue (Add)"""
    if session.get('user') != STAFF_EMAIL:
        return redirect(url_for('login'))
        
    p_id = request.form['product_id']
    name = request.form['name']
    price = float(request.form['price'])
    stock = int(request.form['stock'])
    category = request.form['category']
    icon = request.form['icon'] 
    
    if p_id in db.products:
        flash(f"Error: Product ID '{p_id}' already exists!")
    else:
        db.products[p_id] = Product(p_id, name, price, stock, category, icon)
        flash(f"Success: {name} was added to the catalogue.")
        
    return redirect(url_for('staff_dashboard'))

@app.route('/staff/add_stock/<product_id>', methods=['POST'])
def add_stock(product_id):
    """Task 7: Manage Store Catalogue (Update Stock)"""
    if session.get('user') != STAFF_EMAIL:
        return redirect(url_for('login'))
        
    if product_id in db.products:
        try:
            added_qty = int(request.form['added_stock'])
            db.products[product_id].stock_level += added_qty
            flash(f"Success: Added {added_qty} units to {db.products[product_id].name}.")
        except ValueError:
            flash("Error: Invalid quantity entered.")
            
    return redirect(url_for('staff_dashboard'))

@app.route('/staff/delete_product/<product_id>', methods=['POST'])
def delete_product(product_id):
    """Task 7: Manage Store Catalogue (Delete)"""
    if session.get('user') != STAFF_EMAIL:
        return redirect(url_for('login'))
        
    if product_id in db.products:
        product_name = db.products[product_id].name
        del db.products[product_id]
        flash(f"Success: {product_name} was removed from the catalogue.")
    return redirect(url_for('staff_dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
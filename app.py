# Streamlit Sales Management App with Authentication (MongoDB-backed)
# File: streamlit_sales_management_app.py
# -----------------------------------------------------------------------------
# Features implemented:
# - Streamlit login using MongoDB stored users (configured via Streamlit secrets)
# - Two roles: admin and user
# - Admin dashboard: view users, create users, manage (CRUD) products/customers/sales
# - User dashboard: record/view sales and simple Input->Output processing demo
# - Sales Management features: Products, Customers, Sales, Reports, Import Sample Data
#
# SECURITY: This demo uses plaintext passwords for clarity. For production, replace with
# secure password hashing (bcrypt/argon2) and secure secrets management.
#
# SECRETS EXAMPLE (.streamlit/secrets.toml):
# [mongo]
# uri = "mongodb+srv://<username>:<password>@cluster0.example.mongodb.net/?retryWrites=true&w=majority"
# database = "sales_db"
# users_collection = "users"
# products_collection = "products"
# customers_collection = "customers"
# sales_collection = "sales"
# -----------------------------------------------------------------------------

import streamlit as st
from pymongo import MongoClient
import pandas as pd
from datetime import datetime
from bson.objectid import ObjectId

st.set_page_config(page_title="Sales Management (Auth)", layout="wide")

# -------------------- Mongo helpers --------------------
@st.cache_resource
def get_mongo_client():
    try:
        conf = st.secrets["mongo"]
    except Exception:
        st.error("Mongo configuration not found in Streamlit secrets. See top of file for example.")
        raise
    uri = conf.get("uri")
    if not uri:
        st.error("MongoDB URI missing in secrets['mongo']['uri']")
        raise ValueError("MongoDB URI missing")
    return MongoClient(uri)


def get_collections():
    client = get_mongo_client()
    conf = st.secrets["mongo"]
    db_name = conf.get("database", "sales_db")
    db = client[db_name]
    users_coll = db[conf.get("users_collection", "users")]
    products_coll = db[conf.get("products_collection", "products")]
    customers_coll = db[conf.get("customers_collection", "customers")]
    sales_coll = db[conf.get("sales_collection", "sales")]
    return users_coll, products_coll, customers_coll, sales_coll

# Utility: convert list of docs to dataframe safe for display
def docs_to_df(docs, id_col_name="id"):
    docs2 = []
    for d in docs:
        d2 = d.copy()
        if "_id" in d2:
            d2[id_col_name] = str(d2["_id"])
            del d2["_id"]
        docs2.append(d2)
    if docs2:
        return pd.DataFrame(docs2)
    else:
        return pd.DataFrame()

# -------------------- Auth functions --------------------

def fetch_user_by_username(username: str):
    users_coll, *_ = get_collections()
    return users_coll.find_one({"username": username})


def verify_credentials(username: str, password: str):
    user = fetch_user_by_username(username)
    if not user:
        return None
    # Demo plaintext compare — replace with hashing in prod
    if user.get("password") == password:
        return user
    return None


def fetch_all_users():
    users_coll, *_ = get_collections()
    docs = list(users_coll.find())
    for d in docs:
        d["id"] = str(d.get("_id"))
        if "_id" in d:
            del d["_id"]
    return docs


def create_user(name, username, password, role="user"):
    users_coll, *_ = get_collections()
    if users_coll.find_one({"username": username}):
        raise ValueError("Username already exists")
    res = users_coll.insert_one({"name": name, "username": username, "password": password, "role": role})
    return res.inserted_id

# -------------------- CRUD functions for Sales App --------------------

def list_products():
    _, products_coll, _, _ = get_collections()
    return list(products_coll.find())

def insert_product(name, sku, price, stock, description=""):
    _, products_coll, _, _ = get_collections()
    doc = {"name": name, "sku": sku, "price": float(price), "stock": int(stock), "description": description}
    res = products_coll.insert_one(doc)
    return res.inserted_id

def update_product(prod_id, updates: dict):
    _, products_coll, _, _ = get_collections()
    products_coll.update_one({"_id": ObjectId(prod_id)}, {"$set": updates})

def delete_product(prod_id):
    _, products_coll, _, _ = get_collections()
    products_coll.delete_one({"_id": ObjectId(prod_id)})

# Customers

def list_customers():
    _, _, customers_coll, _ = get_collections()
    return list(customers_coll.find())

def insert_customer(name, email, phone, notes=""):
    _, _, customers_coll, _ = get_collections()
    doc = {"name": name, "email": email, "phone": phone, "notes": notes}
    res = customers_coll.insert_one(doc)
    return res.inserted_id

def update_customer(cust_id, updates: dict):
    _, _, customers_coll, _ = get_collections()
    customers_coll.update_one({"_id": ObjectId(cust_id)}, {"$set": updates})

def delete_customer(cust_id):
    _, _, customers_coll, _ = get_collections()
    customers_coll.delete_one({"_id": ObjectId(cust_id)})

# Sales

def list_sales():
    _, _, _, sales_coll = get_collections()
    return list(sales_coll.find())

def insert_sale(product_id, customer_id, quantity, unit_price, sale_date=None):
    _, products_coll, customers_coll, sales_coll = get_collections()
    product = products_coll.find_one({"_id": ObjectId(product_id)})
    customer = customers_coll.find_one({"_id": ObjectId(customer_id)})
    if not product or not customer:
        raise ValueError("Invalid product or customer")
    quantity = int(quantity)
    unit_price = float(unit_price)
    total = quantity * unit_price
    sale_date = sale_date or datetime.utcnow()
    doc = {
        "product_id": ObjectId(product_id),
        "product_name": product.get("name"),
        "customer_id": ObjectId(customer_id),
        "customer_name": customer.get("name"),
        "quantity": quantity,
        "unit_price": unit_price,
        "total": total,
        "date": sale_date
    }
    res = sales_coll.insert_one(doc)
    try:
        products_coll.update_one({"_id": ObjectId(product_id)}, {"$inc": {"stock": -quantity}})
    except Exception:
        pass
    return res.inserted_id

# -------------------- Session & UI --------------------
# Session state init
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None

st.title("Sales Management App — Auth Enabled")

# Sidebar: Login / Account
with st.sidebar:
    st.header("Account")
    if not st.session_state.logged_in:
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        role_choice = st.selectbox("Login as", ("user", "admin"), index=0)
        if st.button("Log in"):
            user = verify_credentials(username.strip(), password)
            if not user:
                st.error("Invalid username or password.")
            else:
                if user.get("role") != role_choice:
                    st.error(f"User exists but is not a {role_choice}.")
                else:
                    st.success(f"Welcome, {user.get('name') or user.get('username')}!")
                    st.session_state.logged_in = True
                    st.session_state.user = user
    else:
        st.write(f"Signed in as: **{st.session_state.user.get('username')}** ({st.session_state.user.get('role')})")
        if st.button("Log out"):
            st.session_state.logged_in = False
            st.session_state.user = None
            st.experimental_rerun()

# If not logged in show landing/help
if not st.session_state.logged_in:
    st.info("Please log in from the sidebar. Admins can manage users and system data; users can record/view sales.")
    st.write("Tips:")
    st.write("- Make sure you added a user document in your MongoDB 'users' collection, or use the 'Import Sample Data' option (it creates an admin and regular user).\n- Sample fields for users: name, username, password, role (user/admin).")
    # quick sample import button
    if st.button("Import Minimal Sample Users"):
        users_coll, *_ = get_collections()
        if not users_coll.find_one({"username": "admin"}):
            users_coll.insert_one({"name": "Admin User", "username": "admin", "password": "adminpass", "role": "admin"})
        if not users_coll.find_one({"username": "amit"}):
            users_coll.insert_one({"name": "Amit Pandey", "username": "amit", "password": "pass123", "role": "user"})
        st.success("Inserted sample users (admin / amit). Use those to log in from the sidebar.")

else:
    user = st.session_state.user
    role = user.get("role")

    # COMMON NAV
    menu = st.sidebar.selectbox("Menu", ["Dashboard", "Products", "Customers", "Sales", "Reports", "User Profile", "Admin Panel" if role=="admin" else ""].copy())

    # Dashboard
    if menu == "Dashboard":
        st.header("Dashboard")
        prods = docs_to_df(list_products())
        custs = docs_to_df(list_customers())
        sales = docs_to_df(list_sales())

        col1, col2, col3 = st.columns(3)
        col1.metric("Products", len(prods))
        col2.metric("Customers", len(custs))
        total_sales = sales['total'].astype(float).sum() if not sales.empty and 'total' in sales.columns else 0.0
        col3.metric("Total Sales", f"{total_sales:.2f}")

        st.subheader("Recent Sales")
        if not sales.empty:
            sales['date'] = pd.to_datetime(sales['date'])
            st.dataframe(sales.sort_values(by='date', ascending=False)[['date','product_name','customer_name','quantity','unit_price','total']].head(20))
        else:
            st.info("No sales recorded yet.")

    # PRODUCTS
    elif menu == "Products":
        st.header("Products")
        action = st.selectbox("Action", ["List", "Add", "Edit", "Delete"], index=0)

        if action == "List":
            prods = docs_to_df(list_products())
            if not prods.empty:
                st.dataframe(prods[['id','name','sku','price','stock','description']])
            else:
                st.info("No products found.")

        elif action == "Add":
            st.subheader("Add Product")
            name = st.text_input("Name")
            sku = st.text_input("SKU")
            price = st.number_input("Price", min_value=0.0, format="%.2f")
            stock = st.number_input("Stock", min_value=0, step=1)
            description = st.text_area("Description")
            if st.button("Create Product"):
                if not name or not sku:
                    st.error("Name and SKU are required.")
                else:
                    pid = insert_product(name, sku, price, stock, description)
                    st.success(f"Product created: {pid}")

        elif action == "Edit":
            st.subheader("Edit Product")
            prods = docs_to_df(list_products())
            if prods.empty:
                st.info("No products to edit.")
            else:
                prod_choice = st.selectbox("Select product", prods['id'] + " - " + prods['name'])
                prod_id = prod_choice.split(' - ')[0]
                prod_doc = next((p for p in list_products() if str(p.get('_id')) == prod_id), None)
                if prod_doc:
                    name = st.text_input("Name", value=prod_doc.get('name'))
                    sku = st.text_input("SKU", value=prod_doc.get('sku'))
                    price = st.number_input("Price", value=float(prod_doc.get('price',0.0)), format="%.2f")
                    stock = st.number_input("Stock", value=int(prod_doc.get('stock',0)), step=1)
                    description = st.text_area("Description", value=prod_doc.get('description',''))
                    if st.button("Update Product"):
                        update_product(prod_id, {"name": name, "sku": sku, "price": price, "stock": stock, "description": description})
                        st.success("Product updated.")

        elif action == "Delete":
            st.subheader("Delete Product")
            prods = docs_to_df(list_products())
            if prods.empty:
                st.info("No products to delete.")
            else:
                prod_choice = st.selectbox("Select product", prods['id'] + " - " + prods['name'])
                prod_id = prod_choice.split(' - ')[0]
                if st.button("Delete Product"):
                    delete_product(prod_id)
                    st.success("Product deleted.")

    # CUSTOMERS
    elif menu == "Customers":
        st.header("Customers")
        action = st.selectbox("Action", ["List", "Add", "Edit", "Delete"], index=0)

        if action == "List":
            custs = docs_to_df(list_customers())
            if not custs.empty:
                st.dataframe(custs[['id','name','email','phone','notes']])
            else:
                st.info("No customers found.")

        elif action == "Add":
            st.subheader("Add Customer")
            name = st.text_input("Name")
            email = st.text_input("Email")
            phone = st.text_input("Phone")
            notes = st.text_area("Notes")
            if st.button("Create Customer"):
                if not name:
                    st.error("Name is required.")
                else:
                    cid = insert_customer(name, email, phone, notes)
                    st.success(f"Customer created: {cid}")

        elif action == "Edit":
            st.subheader("Edit Customer")
            custs = docs_to_df(list_customers())
            if custs.empty:
                st.info("No customers to edit.")
            else:
                cust_choice = st.selectbox("Select customer", custs['id'] + " - " + custs['name'])
                cust_id = cust_choice.split(' - ')[0]
                cust_doc = next((c for c in list_customers() if str(c.get('_id')) == cust_id), None)
                if cust_doc:
                    name = st.text_input("Name", value=cust_doc.get('name'))
                    email = st.text_input("Email", value=cust_doc.get('email',''))
                    phone = st.text_input("Phone", value=cust_doc.get('phone',''))
                    notes = st.text_area("Notes", value=cust_doc.get('notes',''))
                    if st.button("Update Customer"):
                        update_customer(cust_id, {"name": name, "email": email, "phone": phone, "notes": notes})
                        st.success("Customer updated.")

        elif action == "Delete":
            st.subheader("Delete Customer")
            custs = docs_to_df(list_customers())
            if custs.empty:
                st.info("No customers to delete.")
            else:
                cust_choice = st.selectbox("Select customer", custs['id'] + " - " + custs['name'])
                cust_id = cust_choice.split(' - ')[0]
                if st.button("Delete Customer"):
                    delete_customer(cust_id)
                    st.success("Customer deleted.")

    # SALES
    elif menu == "Sales":
        st.header("Sales")
        action = st.selectbox("Action", ["List", "Record Sale"], index=0)

        if action == "List":
            sales = docs_to_df(list_sales())
            if not sales.empty:
                sales['date'] = pd.to_datetime(sales['date'])
                st.dataframe(sales.sort_values(by='date', ascending=False)[['date','product_name','customer_name','quantity','unit_price','total']])
            else:
                st.info("No sales recorded yet.")

        elif action == "Record Sale":
            st.subheader("Record a Sale")
            prods = docs_to_df(list_products())
            custs = docs_to_df(list_customers())
            if prods.empty or custs.empty:
                st.warning("You need at least one product and one customer to record a sale.")
            else:
                prod_choice = st.selectbox("Product", prods['id'] + " - " + prods['name'])
                prod_id = prod_choice.split(' - ')[0]
                prod_doc = next((p for p in list_products() if str(p.get('_id')) == prod_id), None)
                qty = st.number_input("Quantity", min_value=1, value=1, step=1)
                default_price = float(prod_doc.get('price', 0.0)) if prod_doc else 0.0
                price = st.number_input("Unit Price", value=default_price, format="%.2f")
                cust_choice = st.selectbox("Customer", custs['id'] + " - " + custs['name'])
                cust_id = cust_choice.split(' - ')[0]
                if st.button("Save Sale"):
                    try:
                        sid = insert_sale(prod_id, cust_id, qty, price, sale_date=datetime.utcnow())
                        st.success(f"Sale recorded: {sid}")
                    except Exception as e:
                        st.error(f"Failed to record sale: {e}")

    # REPORTS
    elif menu == "Reports":
        st.header("Reports")
        sales = docs_to_df(list_sales())
        if sales.empty:
            st.info("No sales data to report on.")
        else:
            sales['date'] = pd.to_datetime(sales['date'])
            st.subheader("Sales Summary")
            total = sales['total'].astype(float).sum()
            st.metric("Total Sales", f"{total:.2f}")
            st.subheader("Sales by Product")
            byprod = sales.groupby('product_name')['total'].sum().reset_index().sort_values(by='total', ascending=False)
            st.bar_chart(byprod.set_index('product_name'))
            st.subheader("Sales by Customer")
            bycust = sales.groupby('customer_name')['total'].sum().reset_index().sort_values(by='total', ascending=False)
            st.bar_chart(bycust.set_index('customer_name'))

    # USER PROFILE
    elif menu == "User Profile":
        st.header("Your Profile")
        st.write({
            "id": str(user.get("_id")) if user.get("_id") else "(no id)",
            "name": user.get("name"),
            "username": user.get("username"),
            "role": user.get("role")
        })
        st.markdown("---")
        st.subheader("Input -> Output Demo")
        input_text = st.text_area("Input", placeholder="Type something to process...", key="user_input")
        if st.button("Process"):
            processed = input_text[::-1]
            st.markdown("**Output (processed):**")
            st.write(processed)
            st.markdown("**Metadata**")
            st.write({"length": len(input_text), "words": len(input_text.split())})

    # ADMIN PANEL
    elif menu == "Admin Panel" and role == "admin":
        st.header("Admin Panel")
        st.subheader("Users")
        users = fetch_all_users()
        if users:
            df = pd.DataFrame(users)
            cols = [c for c in ("id","name","username","password","role") if c in df.columns]
            st.dataframe(df[cols])
        else:
            st.info("No users found.")

        with st.expander("Create new user"):
            new_name = st.text_input("Name", key="admin_new_name")
            new_username = st.text_input("Username", key="admin_new_username")
            new_password = st.text_input("Password", key="admin_new_password")
            new_role = st.selectbox("Role", ("user","admin"), key="admin_new_role")
            if st.button("Create user", key="admin_create_user"):
                try:
                    uid = create_user(new_name, new_username, new_password, new_role)
                    st.success(f"Created user: {uid}")
                except Exception as e:
                    st.error(f"Failed to create user: {e}")

        st.markdown("---")
        st.subheader("System Data (Products / Customers / Sales)")
        st.write("Use the main menu (Products, Customers, Sales) to manage system data — admin has full access.")

    # IMPORT SAMPLE DATA (available to logged in users)
    if st.sidebar.button("Import Sample Data"):
        users_coll, products_coll, customers_coll, sales_coll = get_collections()
        # sample users
        if not users_coll.find_one({"username": "admin"}):
            users_coll.insert_one({"name": "Admin User", "username": "admin", "password": "adminpass", "role": "admin"})
        if not users_coll.find_one({"username": "amit"}):
            users_coll.insert_one({"name": "Amit Pandey", "username": "amit", "password": "pass123", "role": "user"})
        # sample products/customers
        products = [
            {"name": "T-Shirt", "sku": "TSH-001", "price": 299.0, "stock": 100, "description": "Cotton T-Shirt"},
            {"name": "Jeans", "sku": "JNS-001", "price": 1499.0, "stock": 50, "description": "Denim Jeans"},
            {"name": "Sneakers", "sku": "SNK-001", "price": 2599.0, "stock": 30, "description": "Running Shoes"}
        ]
        customers = [
            {"name": "Amit Pandey", "email": "amit@example.com", "phone": "9876543210", "notes": "VIP"},
            {"name": "Riya Sharma", "email": "riya@example.com", "phone": "9123456780", "notes": ""}
        ]
        for p in products:
            if not products_coll.find_one({"sku": p['sku']}):
                products_coll.insert_one(p)
        for c in customers:
            if not customers_coll.find_one({"email": c['email']}):
                customers_coll.insert_one(c)
        # one sale
        p = products_coll.find_one({"sku": "TSH-001"})
        c = customers_coll.find_one({"email": "amit@example.com"})
        if p and c:
            sales_coll.insert_one({
                "product_id": p['_id'],
                "product_name": p['name'],
                "customer_id": c['_id'],
                "customer_name": c['name'],
                "quantity": 2,
                "unit_price": p['price'],
                "total": 2 * p['price'],
                "date": datetime.utcnow()
            })
        st.success("Sample data inserted (users, products, customers, a sale).")

# Footer
st.markdown("---")
st.write("This demo combines the earlier login example with the Sales Management app. Replace plaintext passwords with hashed passwords before production.")

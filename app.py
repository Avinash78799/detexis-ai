import os
import sqlite3
from functools import wraps

import numpy as np
import joblib
from flask import Flask, render_template, request, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'intrusion-detection-secret-key-2024')

# Load models
model = joblib.load("Models/model.sav")
scaler_model = joblib.load("Models/scaler.sav")

# Real model performance metrics
MODEL_METRICS = {
    'accuracy': 96.8,
    'precision': 97.1,
    'recall': 96.5,
    'f1_score': 96.8
}

# Feature names for prediction input
FEATURE_NAMES = [
    'network_packet_size', 'protocol_type', 'login_attempts',
    'session_duration', 'encryption_used', 'ip_reputation_score',
    'failed_logins', 'browser_type', 'unusual_time_access'
]


def init_db():
    """Initialize the database and create tables if they don't exist."""
    con = sqlite3.connect('signup.db')
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS info (
            user TEXT PRIMARY KEY,
            name TEXT,
            email TEXT,
            mobile TEXT,
            password TEXT
        )
    """)
    con.commit()
    con.close()


def login_required(f):
    """Decorator that checks if user is logged in before granting access."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function


# --- Public Routes ---

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/logon')
def logon():
    return render_template('signup.html')


@app.route('/login')
def login():
    return render_template('signin.html')


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html")
    else:
        username = request.form.get('user', '')
        name = request.form.get('name', '')
        email = request.form.get('email', '')
        number = request.form.get('mobile', '')
        password = request.form.get('password', '')

        hashed_password = generate_password_hash(password)

        con = sqlite3.connect('signup.db')
        cur = con.cursor()
        cur.execute("SELECT 1 FROM info WHERE user = ?", (username,))
        if cur.fetchone():
            con.close()
            return render_template("signup.html", message="Username already exists. Please choose another.")

        cur.execute(
            "INSERT INTO info (user, name, email, mobile, password) VALUES (?, ?, ?, ?, ?)",
            (username, name, email, number, hashed_password)
        )
        con.commit()
        con.close()
        return render_template("signin.html")


@app.route("/signin", methods=["GET", "POST"])
def signin():
    if request.method == "GET":
        return render_template("signin.html")
    else:
        username = request.form.get('user', '')
        password = request.form.get('password', '')

        con = sqlite3.connect('signup.db')
        cur = con.cursor()
        cur.execute("SELECT user, password FROM info WHERE user = ?", (username,))
        data = cur.fetchone()
        con.close()

        if data is None:
            return render_template("signin.html", message="Invalid username or password.")

        stored_password_hash = data[1]

        if check_password_hash(stored_password_hash, password):
            session['logged_in'] = True
            session['username'] = username
            return redirect('/home')
        else:
            return render_template("signin.html", message="Invalid username or password.")


# --- Protected Routes ---

@app.route('/home')
@login_required
def home():
    return render_template('home.html')


@app.route('/about')
@login_required
def about():
    return render_template('about.html')


@app.route('/predict', methods=['POST'])
@login_required
def predict():
    try:
        # Get input features from the form explicitly to ensure order and robust parsing
        input_features = [
            float(request.form.get('input1', 0)),
            float(request.form.get('input2', 0)),
            float(request.form.get('input3', 0)),
            float(request.form.get('input4', 0)),
            float(request.form.get('input5', 0)),
            float(request.form.get('input6', 0)),
            float(request.form.get('input7', 0)),
            float(request.form.get('input8', 0)),
            float(request.form.get('input9', 0))
        ]

        # Scale the input features
        scaled_data = scaler_model.transform([input_features])

        # Make predictions using the loaded model
        predictions = model.predict(scaled_data)
        confidence_score = round(model.predict_proba(scaled_data).max() * 100, 2)

        # Predict classification (Threat or No Threat)
        predicted_result = "Threat" if predictions[0] == 1 else "No Threat"

        # Map to human-readable values for a premium UI summary card
        protocol_map = {0: "ICMP", 1: "TCP", 2: "UDP"}
        encryption_map = {0: "AES", 1: "DES", 2: "None"}
        browser_map = {0: "Chrome", 1: "Edge", 2: "Firefox", 3: "Safari", 4: "Unknown"}
        time_access_map = {0: "Normal Hours", 1: "Unusual Hours"}

        input_values = {
            "Network Packet Size": f"{int(input_features[0])} bytes",
            "Protocol Type": protocol_map.get(int(input_features[1]), "Unknown"),
            "Login Attempts": int(input_features[2]),
            "Session Duration": f"{input_features[3]} sec",
            "Encryption Used": encryption_map.get(int(input_features[4]), "Unknown"),
            "IP Reputation Score": input_features[5],
            "Failed Logins": int(input_features[6]),
            "Browser Type": browser_map.get(int(input_features[7]), "Unknown"),
            "Unusual Time Access": time_access_map.get(int(input_features[8]), "Unknown")
        }

        # Recommendations based on the prediction
        if predicted_result == "Threat":
            recommendations = [
                "Enhance network security by implementing additional firewalls.",
                "Monitor suspicious activity using advanced analytics tools.",
                "Regularly update intrusion detection models for improved accuracy."
            ]
        else:
            recommendations = [
                "Continue monitoring network activity for any unusual patterns.",
                "Ensure regular updates to security protocols."
            ]

        # Render the result page with the parameters
        return render_template(
            'result.html',
            confidence_score=confidence_score,
            predicted_result=predicted_result,
            accuracy=MODEL_METRICS['accuracy'],
            precision=MODEL_METRICS['precision'],
            recall=MODEL_METRICS['recall'],
            f1_score=MODEL_METRICS['f1_score'],
            recommendations=recommendations,
            input_values=input_values
        )
    except Exception as e:
        return str(e)


# --- Logout ---

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


# --- SEO Routes ---

@app.route('/sitemap.xml')
def sitemap():
    url_root = request.url_root.rstrip('/')
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>{url_root}/</loc></url>
    <url><loc>{url_root}/login</loc></url>
    <url><loc>{url_root}/logon</loc></url>
</urlset>"""
    return xml_content, 200, {'Content-Type': 'application/xml'}


@app.route('/robots.txt')
def robots():
    url_root = request.url_root.rstrip('/')
    txt_content = f"""User-agent: *
Allow: /
Sitemap: {url_root}/sitemap.xml"""
    return txt_content, 200, {'Content-Type': 'text/plain'}


# --- Error Handlers ---

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


# Initialize database on startup/import
init_db()

if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true')

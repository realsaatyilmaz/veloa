import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'veloa_ge_georgia_secret_key_2026'

# Fotoğraf yükleme ayarları
UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DB_NAME = "veloa.db"

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Kullanıcılar Tablosu
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT NOT NULL,
            city TEXT NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    # İlanlar Tablosu
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            city TEXT NOT NULL,
            price REAL NOT NULL,
            currency TEXT DEFAULT '₾',
            description TEXT NOT NULL,
            image_path TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- ROTALAR ---

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    full_name = data.get('full_name')
    email = data.get('email')
    phone = data.get('phone')
    city = data.get('city')
    password = data.get('password')

    if not all([full_name, email, phone, city, password]):
        return jsonify({'success': False, 'message': 'Lütfen tüm alanları doldurun!'}), 400

    hashed_pw = generate_password_hash(password)

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT INTO users (full_name, email, phone, city, password) VALUES (?, ?, ?, ?, ?)',
            (full_name, email, phone, city, hashed_pw)
        )
        conn.commit()
        user_id = cursor.lastrowid
        session['user_id'] = user_id
        session['full_name'] = full_name
        session['email'] = email
        session['phone'] = phone
        return jsonify({'success': True, 'user': {'id': user_id, 'full_name': full_name, 'email': email, 'phone': phone}})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': 'Bu e-posta adresi zaten kayıtlı!'}), 400
    finally:
        conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    conn.close()

    if user and check_password_hash(user['password'], password):
        session['user_id'] = user['id']
        session['full_name'] = user['full_name']
        session['email'] = user['email']
        session['phone'] = user['phone']
        return jsonify({
            'success': True,
            'user': {
                'id': user['id'],
                'full_name': user['full_name'],
                'email': user['email'],
                'phone': user['phone']
            }
        })
    
    return jsonify({'success': False, 'message': 'Hatalı e-posta veya şifre!'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

@app.route('/api/me', methods=['GET'])
def me():
    if 'user_id' in session:
        return jsonify({
            'logged_in': True,
            'user': {
                'id': session['user_id'],
                'full_name': session['full_name'],
                'email': session['email'],
                'phone': session['phone']
            }
        })
    return jsonify({'logged_in': False})

@app.route('/api/listings', methods=['POST'])
def create_listing():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'İlan vermek için giriş yapmalısınız!'}), 401

    title = request.form.get('title')
    category = request.form.get('category')
    city = request.form.get('city')
    price = request.form.get('price')
    currency = request.form.get('currency', '₾')
    description = request.form.get('description')
    
    file = request.files.get('image')
    image_filename = 'default.jpg'

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_")
        image_filename = timestamp + filename
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))

    created_at = datetime.now().strftime("%d.%m.%Y")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO listings (user_id, title, category, city, price, currency, description, image_path, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (session['user_id'], title, category, city, price, currency, description, image_filename, created_at))
    
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': 'İlan başarıyla yayınlandı!'})

@app.route('/api/listings', methods=['GET'])
def get_listings():
    conn = get_db_connection()
    query = '''
        SELECT l.*, u.full_name as user_name, u.phone as user_phone, u.email as user_email
        FROM listings l
        JOIN users u ON l.user_id = u.id
        ORDER BY l.id DESC
    '''
    listings = conn.execute(query).fetchall()
    conn.close()

    result = []
    for item in listings:
        result.append({
            'id': item['id'],
            'user_id': item['user_id'],
            'title': item['title'],
            'category': item['category'],
            'city': item['city'],
            'price': item['price'],
            'currency': item['currency'],
            'description': item['description'],
            'image_url': f"/static/uploads/{item['image_path']}",
            'date': item['created_at'],
            'user_name': item['user_name'],
            'user_phone': item['user_phone'],
            'user_email': item['user_email']
        })

    return jsonify(result)

@app.route('/api/listings/<int:listing_id>', methods=['DELETE'])
def delete_listing(listing_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Yetkisiz işlem!'}), 403

    conn = get_db_connection()
    listing = conn.execute('SELECT * FROM listings WHERE id = ?', (listing_id,)).fetchone()

    if not listing:
        conn.close()
        return jsonify({'success': False, 'message': 'İlan bulunamadı!'}), 404

    if listing['user_id'] != session['user_id']:
        conn.close()
        return jsonify({'success': False, 'message': 'Bu ilanı silme yetkiniz yok!'}), 403

    if listing['image_path'] and listing['image_path'] != 'default.jpg':
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], listing['image_path'])
        if os.path.exists(filepath):
            os.remove(filepath)

    conn.execute('DELETE FROM listings WHERE id = ?', (listing_id,))
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': 'İlan silindi!'})

if __name__ == '__main__':
    print("Veloa.ge Flask sunucusu çalışıyor: http://127.0.0.1:5000")
    app.run(debug=True, port=5000)
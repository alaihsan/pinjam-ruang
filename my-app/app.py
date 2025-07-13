# app.py
# File utama aplikasi Flask.

import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from extensions import db, bcrypt
from models import User, Room, Booking
from functools import wraps
import random

# --- Konfigurasi Aplikasi ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'ganti-dengan-kunci-rahasia-yang-sangat-aman'
# Menentukan path absolut untuk database di dalam folder 'instance'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance/site.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inisialisasi ekstensi dengan aplikasi
db.init_app(app)
bcrypt.init_app(app)

# --- Decorator untuk Autentikasi ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Silakan login untuk mengakses halaman ini.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash('Anda tidak memiliki izin untuk mengakses halaman ini.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# --- Rute-Rute Aplikasi ---
@app.route('/')
@login_required
def dashboard():
    """Menampilkan halaman utama/dashboard setelah login."""
    rooms = Room.query.all()
    return render_template('dashboard.html', rooms=rooms)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Menangani proses login pengguna."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and bcrypt.check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            flash(f'Selamat datang kembali, {user.username}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Login gagal. Periksa kembali username dan password Anda.', 'danger')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Menangani proses registrasi pengguna baru."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Cek apakah username sudah ada
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username sudah digunakan. Silakan pilih yang lain.', 'warning')
            return redirect(url_for('register'))

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registrasi berhasil! Silakan login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    """Menangani proses logout pengguna."""
    session.clear()
    flash('Anda telah berhasil logout.', 'info')
    return redirect(url_for('login'))

# --- Rute untuk Manajemen Ruangan (CRUD) ---
@app.route('/manage-rooms')
@login_required
@admin_required
def manage_rooms():
    """Menampilkan halaman untuk mengelola ruangan."""
    rooms = Room.query.order_by(Room.name).all()
    return render_template('manage_rooms.html', rooms=rooms)

@app.route('/add-room', methods=['GET', 'POST'])
@login_required
@admin_required
def add_room():
    """Menangani penambahan ruangan baru."""
    if request.method == 'POST':
        name = request.form['name']
        capacity = request.form['capacity']
        location = request.form['location']
        facilities = request.form['facilities']
        
        new_room = Room(name=name, capacity=capacity, location=location, facilities=facilities)
        db.session.add(new_room)
        db.session.commit()
        flash(f'Ruangan "{name}" berhasil ditambahkan.', 'success')
        return redirect(url_for('manage_rooms'))
        
    return render_template('room_form.html', title="Tambah Ruangan Baru", room=None)

@app.route('/edit-room/<int:room_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_room(room_id):
    """Menangani pengeditan data ruangan."""
    room = Room.query.get_or_404(room_id)
    if request.method == 'POST':
        room.name = request.form['name']
        room.capacity = request.form['capacity']
        room.location = request.form['location']
        room.facilities = request.form['facilities']
        db.session.commit()
        flash(f'Data ruangan "{room.name}" berhasil diperbarui.', 'success')
        return redirect(url_for('manage_rooms'))

    return render_template('room_form.html', title="Edit Ruangan", room=room)

@app.route('/delete-room/<int:room_id>', methods=['POST'])
@login_required
@admin_required
def delete_room(room_id):
    """Menangani penghapusan ruangan."""
    room = Room.query.get_or_404(room_id)
    # Di sini kita bisa menambahkan pengecekan apakah ruangan sedang dibooking
    # Untuk saat ini, kita langsung hapus
    db.session.delete(room)
    db.session.commit()
    flash(f'Ruangan "{room.name}" telah berhasil dihapus.', 'success')
    return redirect(url_for('manage_rooms'))


# --- Perintah CLI untuk Setup Database ---
@app.cli.command('init-db')
def init_db_command():
    """Membuat tabel database dan admin default."""
    # Pastikan folder instance ada
    instance_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance')
    if not os.path.exists(instance_path):
        os.makedirs(instance_path)
        print("Folder 'instance' dibuat.")

    with app.app_context():
        db.drop_all()
        db.create_all()

        # Buat user admin jika belum ada
        if not User.query.filter_by(username='admin').first():
            hashed_password = bcrypt.generate_password_hash('admin').decode('utf-8')
            admin_user = User(username='admin', password=hashed_password, is_admin=True)
            db.session.add(admin_user)
            print("User admin default dibuat.")

        # Buat beberapa data ruangan dummy
        if Room.query.count() == 0:
            facilities_list = ["Proyektor, AC, Papan Tulis", "AC, Whiteboard, Sound System", "Proyektor, Meja Bundar"]
            for i in range(1, 8):
                room = Room(
                    name=f"Ruang Rapat {i}",
                    capacity=random.choice([10, 20, 30, 50, 100]),
                    location=f"Lantai {random.randint(1, 5)}",
                    facilities=random.choice(facilities_list)
                )
                db.session.add(room)
            print("Data ruangan dummy dibuat.")
        
        db.session.commit()
        print('Database telah diinisialisasi dan diisi dengan data awal.')

if __name__ == '__main__':
    app.run(debug=True)

import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import click
from datetime import datetime

# --- Konfigurasi Aplikasi ---
app = Flask(__name__)
# Menentukan path absolut untuk direktori aplikasi
basedir = os.path.abspath(os.path.dirname(__file__))

# Konfigurasi kunci rahasia dan database
app.config['SECRET_KEY'] = 'kunci_rahasia_yang_sangat_aman_dan_unik'
# Menggunakan SQLite, file database akan bernama 'project.db' di dalam direktori instance
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'instance', 'project.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Membuat direktori instance jika belum ada
instance_path = os.path.join(basedir, 'instance')
if not os.path.exists(instance_path):
    os.makedirs(instance_path)

# Inisialisasi ekstensi SQLAlchemy
db = SQLAlchemy(app)


# --- Model Database ---
# Sesuai dengan rencana Anda di Poin 2

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    
    # Relasi ke pemesanan yang dibuat oleh user
    bookings = db.relationship('Booking', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    location = db.Column(db.String(100))
    facilities = db.Column(db.Text) # Menggunakan Text untuk daftar fasilitas yang lebih panjang
    
    # Relasi ke pemesanan untuk ruangan ini
    bookings = db.relationship('Booking', backref='room', lazy=True)

    def __repr__(self):
        return f'<Room {self.name}>'

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False) # 'pending', 'disetujui', 'ditolak', 'selesai'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Foreign Keys
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)

    def __repr__(self):
        return f'<Booking {self.id} for Room {self.room_id}>'


# --- Perintah CLI Kustom ---

@app.cli.command('init-db')
def init_db_command():
    """Membuat tabel database baru."""
    with app.app_context():
        db.create_all()
    click.echo('Database telah diinisialisasi.')

@app.cli.command('init-admin')
def init_admin_command():
    """Membuat user admin default."""
    with app.app_context():
        # Cek apakah admin sudah ada
        if User.query.filter_by(username='admin').first():
            click.echo('User admin sudah ada.')
            return
        
        # Buat user admin baru
        admin_user = User(username='admin', is_admin=True)
        admin_user.set_password('admin') # Ganti dengan password yang lebih aman di produksi
        db.session.add(admin_user)
        db.session.commit()
        click.echo('User admin berhasil dibuat dengan username "admin" dan password "admin".')


# --- Rute Aplikasi (Routes) ---
# Rute-rute ini perlu disesuaikan nanti untuk menggunakan data dari database

@app.route('/')
def index():
    # Di masa depan, ini akan menjadi halaman utama atau dashboard
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Mengganti validasi hardcode dengan validasi dari database
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            flash('Login Berhasil!', 'success')
            # Di sini Anda akan menambahkan logika session untuk menyimpan status login
            return redirect(url_for('welcome'))
        else:
            error = 'Username atau Password salah. Silakan coba lagi.'

    return render_template('login.html', error=error)

@app.route('/welcome')
def welcome():
    # Halaman ini nantinya akan menjadi dashboard utama setelah login
    return render_template('welcome.html')

if __name__ == '__main__':
    app.run(debug=True)

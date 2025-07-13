import os
import functools
from flask import Flask, render_template, request, redirect, url_for, flash, session, g
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import click
from datetime import datetime

# --- Konfigurasi Aplikasi ---
app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))

app.config['SECRET_KEY'] = 'kunci_rahasia_yang_sangat_aman_dan_unik'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'instance', 'project.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

instance_path = os.path.join(basedir, 'instance')
if not os.path.exists(instance_path):
    os.makedirs(instance_path)

db = SQLAlchemy(app)

# --- Model Database ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    bookings = db.relationship('Booking', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    location = db.Column(db.String(100))
    facilities = db.Column(db.Text)
    bookings = db.relationship('Booking', backref='room', lazy=True)

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)

# --- Perintah CLI Kustom ---
@app.cli.command('init-db')
def init_db_command():
    with app.app_context():
        db.create_all()
    click.echo('Database telah diinisialisasi.')

@app.cli.command('init-admin')
def init_admin_command():
    with app.app_context():
        if User.query.filter_by(username='admin').first():
            click.echo('User admin sudah ada.')
            return
        admin_user = User(username='admin', is_admin=True)
        admin_user.set_password('admin')
        db.session.add(admin_user)
        db.session.commit()
        click.echo('User admin berhasil dibuat.')

@app.cli.command('add-user')
@click.argument('username')
@click.argument('password')
def add_user_command(username, password):
    """Membuat user biasa baru dengan username dan password tertentu."""
    with app.app_context():
        if User.query.filter_by(username=username).first():
            click.echo(f'User dengan username "{username}" sudah ada.')
            return
        
        new_user = User(username=username, is_admin=False)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        click.echo(f'User biasa "{username}" berhasil dibuat.')

# --- Fungsi Bantuan & Decorator ---
def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            flash('Anda harus login untuk mengakses halaman ini.', 'warning')
            return redirect(url_for('login'))
        return view(**kwargs)
    return wrapped_view

def admin_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if not g.user or not g.user.is_admin:
            flash('Anda tidak memiliki hak akses ke halaman ini.', 'danger')
            return redirect(url_for('dashboard'))
        return view(**kwargs)
    return wrapped_view

@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    g.user = User.query.get(user_id) if user_id else None

@app.context_processor
def inject_current_year():
    return {'current_year': datetime.utcnow().year}

# --- Rute Aplikasi ---
@app.route('/')
def index():
    return redirect(url_for('dashboard') if g.user else url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if g.user: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.check_password(request.form['password']):
            session.clear()
            session['user_id'] = user.id
            flash(f'Selamat datang kembali, {user.username}!', 'success')
            return redirect(url_for('dashboard'))
        flash('Username atau Password salah.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Anda telah berhasil logout.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    rooms = Room.query.order_by(Room.name).all()
    return render_template('dashboard.html', rooms=rooms)

# --- Rute untuk Pemesanan (Booking) ---
@app.route('/book/<int:room_id>', methods=['GET', 'POST'])
@login_required
def book_room(room_id):
    room = Room.query.get_or_404(room_id)
    if request.method == 'POST':
        try:
            start_time_str = request.form['start_time']
            end_time_str = request.form['end_time']
            start_time = datetime.fromisoformat(start_time_str)
            end_time = datetime.fromisoformat(end_time_str)
        except ValueError:
            flash('Format tanggal atau waktu tidak valid.', 'danger')
            return render_template('book_room.html', room=room)

        if start_time >= end_time:
            flash('Waktu selesai harus setelah waktu mulai.', 'danger')
            return render_template('book_room.html', room=room)

        # Pencegahan Konflik Jadwal (Poin 6)
        konflik = Booking.query.filter(
            Booking.room_id == room_id,
            Booking.status == 'disetujui',
            Booking.start_time < end_time,
            Booking.end_time > start_time
        ).first()

        if konflik:
            flash('Jadwal yang Anda pilih bertabrakan dengan pemesanan lain.', 'danger')
        else:
            new_booking = Booking(
                user_id=g.user.id,
                room_id=room.id,
                start_time=start_time,
                end_time=end_time
            )
            db.session.add(new_booking)
            db.session.commit()
            flash('Pemesanan Anda telah diajukan dan menunggu persetujuan admin.', 'success')
            return redirect(url_for('history'))
            
    return render_template('book_room.html', room=room)

@app.route('/history')
@login_required
def history():
    bookings = Booking.query.filter_by(user_id=g.user.id).order_by(Booking.start_time.desc()).all()
    return render_template('history.html', bookings=bookings)

# --- Rute untuk Admin ---
@app.route('/manage-bookings')
@login_required
@admin_required
def manage_bookings():
    bookings = Booking.query.order_by(Booking.created_at.desc()).all()
    return render_template('manage_bookings.html', bookings=bookings)

@app.route('/booking/approve/<int:booking_id>', methods=['POST'])
@login_required
@admin_required
def approve_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    booking.status = 'disetujui'
    db.session.commit()
    flash('Pemesanan telah disetujui.', 'success')
    return redirect(url_for('manage_bookings'))

@app.route('/booking/reject/<int:booking_id>', methods=['POST'])
@login_required
@admin_required
def reject_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    booking.status = 'ditolak'
    db.session.commit()
    flash('Pemesanan telah ditolak.', 'danger')
    return redirect(url_for('manage_bookings'))

@app.route('/manage-rooms')
@login_required
@admin_required
def manage_rooms():
    rooms = Room.query.order_by(Room.id).all()
    return render_template('manage_rooms.html', rooms=rooms)

@app.route('/manage-rooms/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_room():
    if request.method == 'POST':
        name = request.form['name']
        if Room.query.filter_by(name=name).first():
            flash(f'Ruangan dengan nama "{name}" sudah ada.', 'danger')
            return redirect(url_for('add_room'))
        new_room = Room(name=name, capacity=request.form['capacity'], location=request.form['location'], facilities=request.form['facilities'])
        db.session.add(new_room)
        db.session.commit()
        flash(f'Ruangan "{name}" berhasil ditambahkan.', 'success')
        return redirect(url_for('manage_rooms'))
    return render_template('add_edit_room.html', form_title="Tambah Ruangan Baru")

@app.route('/manage-rooms/edit/<int:room_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_room(room_id):
    room = Room.query.get_or_404(room_id)
    if request.method == 'POST':
        room.name = request.form['name']
        room.capacity = request.form['capacity']
        room.location = request.form['location']
        room.facilities = request.form['facilities']
        db.session.commit()
        flash(f'Data ruangan "{room.name}" berhasil diperbarui.', 'success')
        return redirect(url_for('manage_rooms'))
    return render_template('add_edit_room.html', form_title="Edit Ruangan", room=room)

@app.route('/manage-rooms/delete/<int:room_id>', methods=['POST'])
@login_required
@admin_required
def delete_room(room_id):
    room = Room.query.get_or_404(room_id)
    db.session.delete(room)
    db.session.commit()
    flash(f'Ruangan "{room.name}" telah dihapus.', 'success')
    return redirect(url_for('manage_rooms'))

if __name__ == '__main__':
    app.run(debug=True)

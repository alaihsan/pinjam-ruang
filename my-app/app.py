from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = 'kunci_rahasia_untuk_flash_messages' # Diperlukan untuk flash messages

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        # Ambil username dan password dari form
        username = request.form['username']
        password = request.form['password']

        # Cek kredensial
        if username == 'admin' and password == 'admin':
            flash('Login Berhasil!', 'success')
            return redirect(url_for('welcome'))
        else:
            # Jika salah, kirim pesan error
            error = 'Username atau Password salah. Silakan coba lagi.'

    # Jika metodenya GET atau login gagal, tampilkan halaman login
    return render_template('login.html', error=error)

@app.route('/welcome')
def welcome():
    return render_template('welcome.html')

# Redirect halaman utama ke halaman login
@app.route('/')
def index():
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
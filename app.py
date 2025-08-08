# ========================================
# app.py - COMPLETO CON DATABASE SQLITE PERSISTENTE
# ========================================

from flask import Flask, render_template, request, jsonify
import hashlib
import secrets
import time
import json
import os
import sqlite3
from datetime import datetime
from contextlib import contextmanager

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-this'

# ========================================
# CLASSE DATABASE RECENSIONI PERSISTENTE
# ========================================

class ReviewsDatabase:
    def __init__(self, db_path='reviews.db'):
        self.db_path = db_path
        self.init_database()
    
    @contextmanager
    def get_db_connection(self):
        """Context manager per connessioni database sicure"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def init_database(self):
        """Inizializza il database delle recensioni"""
        with self.get_db_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
                    comment TEXT NOT NULL,
                    date TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    ip_hash TEXT DEFAULT NULL
                )
            ''')
            conn.commit()
            print("✅ Database recensioni inizializzato correttamente")
    
    def add_review(self, name, rating, comment, ip_hash=None):
        """Aggiungi una nuova recensione"""
        date_iso = datetime.now().isoformat()
        timestamp_human = datetime.now().strftime('%d/%m/%Y alle %H:%M')
        
        with self.get_db_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO reviews (name, rating, comment, date, timestamp, ip_hash)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (name, rating, comment, date_iso, timestamp_human, ip_hash))
            
            review_id = cursor.lastrowid
            conn.commit()
            
            print(f"✅ Nuova recensione aggiunta: ID {review_id}, Rating {rating}/5")
            
            return {
                'id': review_id,
                'name': name,
                'rating': rating,
                'comment': comment,
                'date': date_iso,
                'timestamp': timestamp_human
            }
    
    def get_reviews(self, limit=50):
        """Ottieni tutte le recensioni"""
        with self.get_db_connection() as conn:
            cursor = conn.execute('''
                SELECT id, name, rating, comment, date, timestamp FROM reviews 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (limit,))
            
            reviews = []
            for row in cursor.fetchall():
                reviews.append({
                    'id': row['id'],
                    'name': row['name'],
                    'rating': row['rating'],
                    'comment': row['comment'],
                    'date': row['date'],
                    'timestamp': row['timestamp']
                })
            
            return reviews
    
    def get_stats(self):
        """Ottieni statistiche recensioni"""
        with self.get_db_connection() as conn:
            # Conteggio totale
            total = conn.execute('SELECT COUNT(*) as count FROM reviews').fetchone()['count']
            
            if total == 0:
                return {
                    'total': 0,
                    'average_rating': 0,
                    'distribution': {i: 0 for i in range(1, 6)}
                }
            
            # Media rating
            avg = conn.execute('SELECT AVG(rating) as avg FROM reviews').fetchone()['avg']
            
            # Distribuzione rating
            distribution = {}
            for i in range(1, 6):
                count = conn.execute('SELECT COUNT(*) as count FROM reviews WHERE rating = ?', (i,)).fetchone()['count']
                distribution[i] = count
            
            return {
                'total': total,
                'average_rating': round(avg, 1),
                'distribution': distribution
            }
    
    def check_recent_review(self, ip_hash, hours=24):
        """Controlla se un IP ha già lasciato recensioni recenti"""
        with self.get_db_connection() as conn:
            count = conn.execute('''
                SELECT COUNT(*) as count FROM reviews 
                WHERE ip_hash = ? AND datetime(created_at) > datetime('now', '-{} hours')
            '''.format(hours), (ip_hash,)).fetchone()['count']
            return count > 0

# ========================================
# CLASSE HASH GENERATOR (INVARIATA)
# ========================================

class FlaskHashGenerator:
    def __init__(self):
        self.algorithms = {
            'md5': hashlib.md5,
            'sha1': hashlib.sha1,
            'sha256': hashlib.sha256,
            'sha384': hashlib.sha384,
            'sha512': hashlib.sha512
        }
        
        self.algorithm_info = {
            'md5': {'bits': 128, 'security': 'Basso', 'color': 'danger'},
            'sha1': {'bits': 160, 'security': 'Deprecato', 'color': 'warning'},
            'sha256': {'bits': 256, 'security': 'Alto', 'color': 'success'},
            'sha384': {'bits': 384, 'security': 'Molto Alto', 'color': 'info'},
            'sha512': {'bits': 512, 'security': 'Massimo', 'color': 'primary'}
        }

    def generate_salt(self, length=32):
        """Genera un salt casuale"""
        return secrets.token_hex(length)

    def create_complex_input(self, data, salt=None, include_timestamp=True):
        """Crea input complesso con salt e timestamp"""
        complex_input = str(data)
        
        if salt:
            # Aggiungi salt all'inizio e alla fine (invertito)
            complex_input = salt + complex_input + salt[::-1]
        
        if include_timestamp:
            timestamp = str(int(time.time() * 1000))  # timestamp in millisecondi
            random_suffix = secrets.token_hex(8)
            complex_input += timestamp + random_suffix
            
        return complex_input

    def generate_iterative_hash(self, algorithm_name, data, iterations=1):
        """Genera hash con iterazioni multiple"""
        if algorithm_name not in self.algorithms:
            raise ValueError(f"Algoritmo {algorithm_name} non supportato")
        
        result = data.encode('utf-8')
        hash_func = self.algorithms[algorithm_name]
        
        for i in range(iterations):
            hasher = hash_func()
            hasher.update(result)
            result = hasher.hexdigest().encode('utf-8')
            
            # Aggiungi entropia extra ad ogni iterazione
            entropy = f"{i}{int(time.time())}"[-3:]
            result += entropy.encode('utf-8')
        
        return result.decode('utf-8')

    def generate_complex_hash(self, data, algorithm='sha256', salt=None, 
                            iterations=5, include_timestamp=True, auto_salt=True):
        """Metodo principale per generare hash complesso"""
        
        # Genera salt automaticamente se richiesto
        final_salt = salt if salt else (self.generate_salt() if auto_salt else None)
        
        # Crea input complesso
        complex_input = self.create_complex_input(data, final_salt, include_timestamp)
        
        # Genera hash iterativo
        hash_result = self.generate_iterative_hash(algorithm, complex_input, iterations)
        
        return {
            'hash': hash_result,
            'algorithm': algorithm.upper(),
            'salt': final_salt,
            'iterations': iterations,
            'original_length': len(data),
            'hash_length': len(hash_result),
            'timestamp': datetime.now().isoformat(),
            'algorithm_info': self.algorithm_info.get(algorithm, {})
        }

    def generate_all_hashes(self, data, salt=None, iterations=5, 
                          include_timestamp=True, auto_salt=True):
        """Genera hash per tutti gli algoritmi"""
        results = {}
        
        # Usa lo stesso salt per tutti gli algoritmi per confronto
        shared_salt = salt if salt else (self.generate_salt() if auto_salt else None)
        
        for algorithm in self.algorithms.keys():
            results[algorithm] = self.generate_complex_hash(
                data, algorithm, shared_salt, iterations, 
                include_timestamp, auto_salt=False  # Non rigenerare salt
            )
        
        return results

# ========================================
# ISTANZE GLOBALI
# ========================================

hash_generator = FlaskHashGenerator()
reviews_db = ReviewsDatabase()

# ========================================
# UTILITY FUNCTIONS
# ========================================

def get_client_ip_hash():
    """Ottieni hash IP del cliente per prevenire spam"""
    ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
    if ip:
        # Hash dell'IP per privacy
        return hashlib.sha256(ip.encode()).hexdigest()[:16]
    return None

# ========================================
# ROUTES PRINCIPALI
# ========================================

@app.route('/')
def index():
    """Pagina principale"""
    return render_template('index.html')

@app.route('/api/generate-hash', methods=['POST'])
def api_generate_hash():
    """API per generare hash"""
    try:
        data = request.get_json()
        
        input_text = data.get('input_text', '')
        salt = data.get('salt', '')
        iterations = int(data.get('iterations', 5))
        use_timestamp = data.get('use_timestamp', False)
        
        if not input_text:
            return jsonify({'error': 'Testo di input richiesto'}), 400
        
        if iterations < 1 or iterations > 10:
            return jsonify({'error': 'Iterazioni devono essere tra 1 e 10'}), 400
        
        # Genera hash per tutti gli algoritmi
        results = hash_generator.generate_all_hashes(
            input_text, 
            salt if salt else None,
            iterations,
            use_timestamp,
            auto_salt=True if not salt else False
        )
        
        return jsonify({
            'success': True,
            'hashes': results,
            'input_info': {
                'text_length': len(input_text),
                'salt_length': len(salt) if salt else 0,
                'iterations': iterations,
                'timestamp_used': use_timestamp
            }
        })
        
    except ValueError as e:
        return jsonify({'error': 'Dati di input non validi'}), 400
    except Exception as e:
        return jsonify({'error': 'Errore interno del server'}), 500

@app.route('/api/generate-salt')
def api_generate_salt():
    """API per generare salt casuale"""
    try:
        length = request.args.get('length', 32, type=int)
        if length < 8 or length > 128:
            return jsonify({'error': 'Lunghezza salt deve essere tra 8 e 128'}), 400
            
        salt = hash_generator.generate_salt(length)
        return jsonify({'salt': salt})
    except Exception as e:
        return jsonify({'error': 'Errore nella generazione salt'}), 500

@app.route('/api/generate-random-text')
def api_generate_random_text():
    """API per generare testo casuale complesso"""
    try:
        import string
        import random
        
        # Caratteri speciali e unicode
        chars = string.ascii_letters + string.digits + '!@#$%^&*()_+-=[]{}|;:,.<>?'
        special_chars = '∑∏∫∂∆∇√∞≠≤≥±×÷∈∉∪∩⊂⊃⊆⊇∧∨¬→←↑↓↔'
        
        result = ''
        for _ in range(50):
            if random.random() > 0.8:
                result += random.choice(special_chars)
            else:
                result += random.choice(chars)
        
        return jsonify({'text': result})
    except Exception as e:
        return jsonify({'error': 'Errore nella generazione testo'}), 500

# ========================================
# ROUTES RECENSIONI - DATABASE PERSISTENTE
# ========================================

@app.route('/api/add-review', methods=['POST'])
def add_review():
    """Aggiungi una nuova recensione - VERSIONE DATABASE PERSISTENTE"""
    try:
        data = request.get_json()
        
        name = data.get('name', '').strip()
        rating = int(data.get('rating', 0))
        comment = data.get('comment', '').strip()
        
        # Validazioni
        if not name or not comment:
            return jsonify({'error': 'Nome e commento sono obbligatori'}), 400
            
        if rating < 1 or rating > 5:
            return jsonify({'error': 'Rating deve essere tra 1 e 5 stelle'}), 400
        
        if len(name) > 50:
            return jsonify({'error': 'Nome troppo lungo (max 50 caratteri)'}), 400
            
        if len(comment) > 500:
            return jsonify({'error': 'Commento troppo lungo (max 500 caratteri)'}), 400
        
        # Prevenzione spam (opzionale)
        ip_hash = get_client_ip_hash()
        if ip_hash and reviews_db.check_recent_review(ip_hash, hours=1):
            return jsonify({'error': 'Hai già lasciato una recensione recentemente. Riprova tra un\'ora.'}), 429
        
        # Salva nel database
        new_review = reviews_db.add_review(name, rating, comment, ip_hash)
        
        return jsonify({
            'success': True, 
            'message': 'Grazie per la recensione! È stata salvata permanentemente.',
            'review': new_review
        })
        
    except ValueError:
        return jsonify({'error': 'Rating deve essere un numero tra 1 e 5'}), 400
    except Exception as e:
        print(f"Errore aggiunta recensione: {e}")
        return jsonify({'error': 'Errore interno del server'}), 500

@app.route('/api/get-reviews')
def get_reviews():
    """Ottieni tutte le recensioni - VERSIONE DATABASE PERSISTENTE"""
    try:
        reviews = reviews_db.get_reviews(50)
        stats = reviews_db.get_stats()
        
        return jsonify({
            'reviews': reviews,
            'stats': stats,
            'message': f'Caricate {len(reviews)} recensioni dal database permanente'
        })
        
    except Exception as e:
        print(f"Errore caricamento recensioni: {e}")
        return jsonify({
            'reviews': [],
            'stats': {'total': 0, 'average_rating': 0, 'distribution': {i: 0 for i in range(1, 6)}},
            'error': 'Errore nel caricamento recensioni'
        }), 500

# ========================================
# ROUTES VARIE
# ========================================

@app.route('/reviews')
def reviews_page():
    """Pagina recensioni dedicata"""
    try:
        return render_template('reviews.html')
    except:
        return jsonify({'error': 'Pagina recensioni non disponibile'}), 404

@app.route('/docs')
def docs():
    """Documentazione API"""
    try:
        return render_template('docs.html')
    except:
        return jsonify({'error': 'Documentazione non disponibile'}), 404

@app.route('/health')
def health():
    """Health check per deployment"""
    try:
        # Test database
        stats = reviews_db.get_stats()
        db_status = "connected"
    except:
        stats = None
        db_status = "error"
    
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'algorithms_available': list(hash_generator.algorithms.keys()),
        'database_status': db_status,
        'reviews_count': stats['total'] if stats else 0,
        'features': [
            'Hash Generation (5 algorithms)',
            'Salt Support', 
            'Multiple Iterations',
            'Persistent Reviews System',
            'Social Sharing',
            'SQLite Database',
            'Anti-Spam Protection'
        ]
    })

@app.route('/api/stats')
def api_stats():
    """Statistiche pubbliche del servizio"""
    try:
        review_stats = reviews_db.get_stats()
        
        return jsonify({
            'total_reviews': review_stats['total'],
            'average_rating': review_stats['average_rating'],
            'algorithms_supported': len(hash_generator.algorithms),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': 'Errore nel caricamento statistiche'}), 500

# ========================================
# ERROR HANDLERS
# ========================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint non trovato', 'available_endpoints': [
        'GET /', 'POST /api/generate-hash', 'GET /api/generate-salt',
        'GET /api/generate-random-text', 'POST /api/add-review', 
        'GET /api/get-reviews', 'GET /health'
    ]}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Errore interno del server'}), 500

@app.errorhandler(429)
def rate_limit_handler(e):
    return jsonify({'error': 'Troppi tentativi. Riprova più tardi.'}), 429

# ========================================
# AVVIO DELL'APP
# ========================================

if __name__ == '__main__':
    # Inizializzazione
    print("🚀 Avvio Hash Generator Pro...")
    print("✅ Database SQLite inizializzato")
    print("✅ Hash Generator caricato")
    print("✅ Sistema recensioni attivo")
    
    # Per sviluppo locale e produzione
    import os
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
    
    print("🎉 Hash Generator Pro avviato con successo!")

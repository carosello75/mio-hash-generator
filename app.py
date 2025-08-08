# ========================================
# app.py - AGGIORNATO CON SISTEMA RECENSIONI
# ========================================

from flask import Flask, render_template, request, jsonify
import hashlib
import secrets
import time
import json
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-this'

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

# Istanza globale del generatore
hash_generator = FlaskHashGenerator()

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
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate-salt')
def api_generate_salt():
    """API per generare salt casuale"""
    length = request.args.get('length', 32, type=int)
    salt = hash_generator.generate_salt(length)
    return jsonify({'salt': salt})

@app.route('/api/generate-random-text')
def api_generate_random_text():
    """API per generare testo casuale complesso"""
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

# ========================================
# ROUTES RECENSIONI E CONDIVISIONE
# ========================================

@app.route('/api/add-review', methods=['POST'])
def add_review():
    """Aggiungi una nuova recensione"""
    try:
        data = request.get_json()
        
        name = data.get('name', '').strip()
        rating = int(data.get('rating', 0))
        comment = data.get('comment', '').strip()
        
        if not name or not comment or rating < 1 or rating > 5:
            return jsonify({'error': 'Dati recensione non validi'}), 400
        
        if len(name) > 50:
            return jsonify({'error': 'Nome troppo lungo (max 50 caratteri)'}), 400
            
        if len(comment) > 500:
            return jsonify({'error': 'Commento troppo lungo (max 500 caratteri)'}), 400
        
        # Carica recensioni esistenti
        reviews_file = 'reviews.json'
        reviews = []
        if os.path.exists(reviews_file):
            try:
                with open(reviews_file, 'r', encoding='utf-8') as f:
                    reviews = json.load(f)
            except:
                reviews = []
        
        # Nuova recensione
        new_review = {
            'id': len(reviews) + 1,
            'name': name,
            'rating': rating,
            'comment': comment,
            'date': datetime.now().isoformat(),
            'timestamp': datetime.now().strftime('%d/%m/%Y alle %H:%M')
        }
        
        reviews.append(new_review)
        
        # Salva recensioni (con gestione errori)
        try:
            with open(reviews_file, 'w', encoding='utf-8') as f:
                json.dump(reviews, f, indent=2, ensure_ascii=False)
        except Exception as e:
            # Se non riesce a salvare su file, torna comunque successo
            # (in produzione potresti usare un database)
            pass
        
        return jsonify({
            'success': True, 
            'message': 'Grazie per la recensione!',
            'review': new_review
        })
        
    except ValueError:
        return jsonify({'error': 'Rating deve essere un numero tra 1 e 5'}), 400
    except Exception as e:
        return jsonify({'error': 'Errore interno del server'}), 500

@app.route('/api/get-reviews')
def get_reviews():
    """Ottieni tutte le recensioni"""
    try:
        reviews_file = 'reviews.json'
        reviews = []
        
        if os.path.exists(reviews_file):
            try:
                with open(reviews_file, 'r', encoding='utf-8') as f:
                    reviews = json.load(f)
            except:
                reviews = []
        
        # Ordina per data (più recenti prima) e limita a 50
        reviews = sorted(reviews, key=lambda x: x['date'], reverse=True)[:50]
        
        # Calcola statistiche
        total_reviews = len(reviews)
        if total_reviews > 0:
            avg_rating = sum(r['rating'] for r in reviews) / total_reviews
            rating_distribution = {i: sum(1 for r in reviews if r['rating'] == i) for i in range(1, 6)}
        else:
            avg_rating = 0
            rating_distribution = {i: 0 for i in range(1, 6)}
        
        return jsonify({
            'reviews': reviews,
            'stats': {
                'total': total_reviews,
                'average_rating': round(avg_rating, 1),
                'distribution': rating_distribution
            }
        })
        
    except Exception as e:
        return jsonify({'error': 'Errore nel caricamento recensioni'}), 500

@app.route('/reviews')
def reviews_page():
    """Pagina recensioni dedicata"""
    return render_template('reviews.html')

# ========================================
# ROUTES VARIE
# ========================================

@app.route('/docs')
def docs():
    """Documentazione API"""
    return render_template('docs.html')

@app.route('/health')
def health():
    """Health check per deployment"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'algorithms_available': list(hash_generator.algorithms.keys()),
        'features': [
            'Hash Generation',
            'Multiple Algorithms',
            'Salt Support', 
            'Multiple Iterations',
            'Reviews System',
            'Social Sharing'
        ]
    })

# ========================================
# ERROR HANDLERS
# ========================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint non trovato'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Errore interno del server'}), 500

# ========================================
# AVVIO DELL'APP
# ========================================

if __name__ == '__main__':
    # Per sviluppo locale
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

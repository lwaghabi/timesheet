import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import mysql.connector
from datetime import datetime, timedelta, date
import traceback
from dotenv import load_dotenv

load_dotenv()  # carrega variáveis do arquivo .env

app = Flask(__name__)
CORS(app, origins='*')

# ============================================
# CONFIGURAÇÃO DO BANCO DE DADOS (via variáveis de ambiente)
# ============================================
db_config = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'sistemaos03'),
    'port': int(os.getenv('DB_PORT', 3306))
}

def get_db():
    try:
        print(f"🔌 Tentando conectar ao banco: {db_config['host']}:{db_config['port']} usuário {db_config['user']}", flush=True)
        conn = mysql.connector.connect(**db_config)
        print("✅ Conexão com banco estabelecida", flush=True)
        return conn
    except mysql.connector.Error as err:
        print(f"❌ Erro de conexão: {err}", flush=True)
        return None

# ============================================
# Funções auxiliares (já testadas)
# ============================================
def horario_para_minutos(horario):
    if not horario:
        return 0
    partes = horario.split(':')
    if len(partes) >= 2:
        try:
            h = int(partes[0])
            m = int(partes[1])
            return h * 60 + m
        except ValueError:
            return 0
    return 0

def calcular_horas_normais(inicio, pausa, retorno, fim):
    if not inicio or not fim:
        return 0.0
    inicio_min = horario_para_minutos(inicio)
    fim_min = horario_para_minutos(fim)
    if fim_min < inicio_min:
        fim_min += 24 * 60
    tem_pausa = pausa and pausa.strip() != ''
    tem_retorno = retorno and retorno.strip() != ''
    if tem_pausa and tem_retorno:
        pausa_min = horario_para_minutos(pausa)
        retorno_min = horario_para_minutos(retorno)
        if retorno_min < pausa_min:
            retorno_min += 24 * 60
        total_min = (fim_min - inicio_min) - (retorno_min - pausa_min)
    elif not tem_pausa and not tem_retorno:
        total_min = fim_min - inicio_min
    else:
        total_min = 0
    total_min = max(total_min, 0)
    return round(total_min / 60.0, 2)

def calcular_minutos_trabalhados(inicio, pausa, retorno, fim):
    if not inicio or not fim:
        return 0
    inicio_min = horario_para_minutos(inicio)
    fim_min = horario_para_minutos(fim)
    if fim_min < inicio_min:
        fim_min += 24 * 60
    tem_pausa = pausa and pausa.strip() != ''
    tem_retorno = retorno and retorno.strip() != ''
    if tem_pausa and tem_retorno:
        pausa_min = horario_para_minutos(pausa)
        retorno_min = horario_para_minutos(retorno)
        if retorno_min < pausa_min:
            retorno_min += 24 * 60
        total_min = (fim_min - inicio_min) - (retorno_min - pausa_min)
    elif not tem_pausa and not tem_retorno:
        total_min = fim_min - inicio_min
    else:
        total_min = 0
    return max(total_min, 0)

def formatar_minutos_para_time(minutos):
    if minutos <= 0:
        return None
    horas = minutos // 60
    mins = minutos % 60
    return f"{horas:02d}:{mins:02d}:00"

# ============================================
# Endpoints
# ============================================
@app.route('/api/health', methods=['GET', 'OPTIONS'])
def health():
    if request.method == 'OPTIONS':
        return '', 200
    return jsonify({'status': 'online', 'timestamp': datetime.now().isoformat()})

@app.route('/api/login', methods=['POST', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.json
        chPessoa = data.get('chPessoa')
        senha = data.get('senha')
        print(f"🔐 Login recebido: chPessoa={chPessoa}, senha={senha}", flush=True)
        
        conn = get_db()
        print(f"📡 Conexão obtida: {conn is not None}", flush=True)
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor(dictionary=True)
        print(f"🔍 Executando consulta para chPessoa={chPessoa}", flush=True)
        cursor.execute("""
            SELECT * FROM timesheet_embarque 
            WHERE chPessoa = %s AND senhaembarque = %s AND status IN (0, 1)
        """, (chPessoa, senha))
        user = cursor.fetchone()
        print(f"👤 Usuário encontrado: {user is not None}", flush=True)
        cursor.close()
        conn.close()
        
        if user:
            response_data = {
                'success': True,
                'chPessoa': user['chPessoa'],
                'senhaembarque': user['senhaembarque'],
                'cliente': user.get('cliente', ''),
                'unidadeoperacional': user.get('unidadeoperacional', ''),
                'supervisor': user.get('supervisor', ''),
                'iniciojornada': str(user.get('iniciojornada', '')) if user.get('iniciojornada') else '',
                'fimjornada': str(user.get('fimjornada', '')) if user.get('fimjornada') else '',
                'qtddias': user.get('qtddias', 0)
            }
            return jsonify(response_data)
        else:
            return jsonify({'success': False}), 401
    except Exception as e:
        print(f"❌ ERRO login: {e}", flush=True)
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/dados-funcionario/<path:chPessoa>', methods=['GET', 'OPTIONS'])
def get_dados_funcionario(chPessoa):
    if request.method == 'OPTIONS':
        return '', 200
    try:
        conn = get_db()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM timesheet_embarque WHERE chPessoa = %s", (chPessoa,))
        dados = cursor.fetchone()
        cursor.close()
        conn.close()
        if dados:
            dados_json = {}
            for key, value in dados.items():
                if hasattr(value, 'strftime'):
                    dados_json[key] = value.strftime('%Y-%m-%d')
                else:
                    dados_json[key] = value
            return jsonify({'success': True, 'dados': dados_json})
        else:
            return jsonify({'success': False, 'error': 'Funcionário não encontrado'}), 404
    except Exception as e:
        print(f"❌ ERRO dados-funcionario: {e}", flush=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/registros/<path:chPessoa>', methods=['GET', 'OPTIONS'])
def get_registros(chPessoa):
    if request.method == 'OPTIONS':
        return '', 200
    try:
        conn = get_db()
        if not conn:
            return jsonify([]), 500
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT * FROM timesheet_registros 
            WHERE chPessoa = %s 
            ORDER BY data DESC, dia_numero ASC
        """, (chPessoa,))
        registros = cursor.fetchall()
        cursor.close()
        conn.close()
        registros_formatados = []
        for reg in registros:
            novo_reg = {}
            for chave, valor in reg.items():
                if isinstance(valor, timedelta):
                    total_segundos = int(valor.total_seconds())
                    horas = total_segundos // 3600
                    minutos = (total_segundos % 3600) // 60
                    segundos = total_segundos % 60
                    novo_reg[chave] = f"{horas:02d}:{minutos:02d}:{segundos:02d}"
                elif isinstance(valor, (datetime, date)):
                    novo_reg[chave] = valor.strftime('%Y-%m-%d')
                else:
                    novo_reg[chave] = valor
            registros_formatados.append(novo_reg)
        return jsonify(registros_formatados)
    except Exception as e:
        print(f"❌ ERRO get_registros: {e}", flush=True)
        traceback.print_exc()
        return jsonify([]), 500

@app.route('/api/registro-diario', methods=['POST', 'OPTIONS'])
def salvar_registro():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.json
        chPessoa = data.get('chPessoa')
        senhaembarque = data.get('senhaembarque')
        data_registro = data.get('data')
        dia_numero = data.get('dia_numero', 1)
        inicio_turno = data.get('inicio_turno')
        parada_refeicao = data.get('parada_refeicao')
        retorno_refeicao = data.get('retorno_refeicao')
        fim_turno = data.get('fim_turno')

        horas_normais = calcular_horas_normais(inicio_turno, parada_refeicao, retorno_refeicao, fim_turno)
        minutos_totais = calcular_minutos_trabalhados(inicio_turno, parada_refeicao, retorno_refeicao, fim_turno)
        totalhoras = formatar_minutos_para_time(minutos_totais)

        print(f"💾 Registro: {chPessoa} - {data_registro} (dia {dia_numero}) -> totalhoras={totalhoras}", flush=True)

        conn = get_db()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500

        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            INSERT INTO timesheet_registros 
            (chPessoa, senhaembarque, data, dia_numero, inicio_turno, parada_refeicao, retorno_refeicao, fim_turno, horas_normais, totalhoras)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
            inicio_turno = VALUES(inicio_turno),
            parada_refeicao = VALUES(parada_refeicao),
            retorno_refeicao = VALUES(retorno_refeicao),
            fim_turno = VALUES(fim_turno),
            horas_normais = VALUES(horas_normais),
            totalhoras = VALUES(totalhoras)
        """, (chPessoa, senhaembarque, data_registro, dia_numero,
              inicio_turno, parada_refeicao, retorno_refeicao,
              fim_turno, horas_normais, totalhoras))

        conn.commit()
        print("✅ Registro salvo.", flush=True)

        # Atualiza status do funcionário se ainda estiver 0
        cursor.execute("""
            UPDATE timesheet_embarque 
            SET status = 1 
            WHERE chPessoa = %s AND senhaembarque = %s AND status = 0
        """, (chPessoa, senhaembarque))
        if cursor.rowcount > 0:
            conn.commit()
            print(f"✅ Status do funcionário {chPessoa} atualizado para 1.", flush=True)

        cursor.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f"❌ ERRO salvar_registro: {e}", flush=True)
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/atualizar-fim-jornada', methods=['POST', 'OPTIONS'])
def atualizar_fim_jornada():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.json
        chPessoa = data.get('chPessoa')
        fimjornada = data.get('fimjornada')
        conn = get_db()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
        cursor = conn.cursor()
        cursor.execute("UPDATE timesheet_embarque SET fimjornada = %s, status = 2 WHERE chPessoa = %s", (fimjornada, chPessoa))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f"❌ ERRO atualizar-fim-jornada: {e}", flush=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/AppMobile/<path:filename>')
def serve_appmobile(filename):
    try:
        return send_from_directory('AppMobile', filename)
    except Exception as e:
        print(f"Erro ao servir arquivo estático: {e}", flush=True)
        return "Arquivo não encontrado", 404

@app.route('/')
def index():
    return "<h1>Timesheet SHB</h1><p>Sistema online</p><a href='/AppMobile/index.html'>Acessar Timesheet</a>"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)

@app.route('/api/test-db', methods=['GET'])
def test_db():
    try:
        import mysql.connector
        import os
        conn = mysql.connector.connect(
            host=os.getenv('mysql.sistemaos.com.br'),
            user=os.getenv('sistemaos03'),
            password=os.getenv('zinholui47'),
            database=os.getenv('sistemaos03'),
            port=int(os.getenv('DB_PORT', 3306))
        )
        conn.close()
        return jsonify({'success': True, 'message': 'Conexão com banco OK'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

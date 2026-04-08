import os
import requests
import gspread
from flask import Flask, request, jsonify
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

app = Flask(__name__)

# ==========================================
# CONFIGURACIÓN DE CREDENCIALES
# ==========================================
# 1. Pega aquí el Token Permanente que generaste en el Business Manager
TOKEN_WA = "EAA7uuBfqZCbsBRMNUZA1aUSqEWtHZAZC0hTU0TST41Rkw1K5tq4m2rWHYdlR2Yho43vWnyhJOJSZC2siKZA5LU2RBLoZBWzFoUC2HvZCi3WTORlEYI6dIQye3RAbeDrba5x7NNt5KNLZCOuqptaxahtgtH5Xc292OhQIZCzFLFnXUFnv97gT0nW1djQs3FpgxETJLKZBAZDZD"

# 2. Pega aquí el ID de teléfono de Meta (el número largo)
ID_TELEFONO = "1040583289144527"

# 3. Nombre exacto de tu archivo en Google Drive
NOMBRE_EXCEL = "Taxi Judit"

# Ruta para encontrar el JSON de Google Cloud
directorio_actual = os.path.dirname(os.path.abspath(__file__))
ruta_creds = os.path.join(directorio_actual, 'creds.json')

# ==========================================
# FUNCIONES DE APOYO
# ==========================================

def conectar_pestaña_mes():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(ruta_creds, scope)
        client = gspread.authorize(creds)
        archivo = client.open(NOMBRE_EXCEL)
        
        # Diccionario para meses en MAYÚSCULAS como tu Excel
        meses = {
            1: "ENERO", 2: "FEBRERO", 3: "MARZO", 4: "ABRIL",
            5: "MAYO", 6: "JUNIO", 7: "JULIO", 8: "AGOSTO",
            9: "SEPTIEMBRE", 10: "OCTUBRE", 11: "NOVIEMBRE", 12: "DICIEMBRE"
        }
        nombre_mes = meses[datetime.now().month]
        
        # Buscar la pestaña ignorando espacios accidentales
        for p in archivo.worksheets():
            if p.title.strip().upper() == nombre_mes:
                return p
        return None
    except Exception as e:
        print(f"❌ Error de conexión a Sheets: {e}")
        return None

def enviar_confirmacion_wa(texto, numero_destino):
    url = f"https://graph.facebook.com/v18.0/{ID_TELEFONO}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": numero_destino,
        "type": "text",
        "text": {"body": texto}
    }
    headers = {
        "Authorization": f"Bearer {TOKEN_WA}",
        "Content-Type": "application/json"
    }
    try:
        requests.post(url, json=payload, headers=headers)
    except Exception as e:
        print(f"❌ No se pudo enviar el mensaje de confirmación: {e}")

# ==========================================
# WEBHOOK PRINCIPAL
# ==========================================

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        # Token de verificación que pusiste en Meta (ej: taxi_secret_2026)
        return request.args.get('hub.challenge')

    if request.method == 'POST':
        data = request.json
        try:
            value = data['entry'][0]['changes'][0]['value']
            if 'messages' in value:
                msg_obj = value['messages'][0]
                mensaje = msg_obj['text']['body']
                telefono_usuario = msg_obj['from']
                
                if "/" in mensaje:
                    partes = mensaje.split("/")
                    if len(partes) == 3:
                        pestaña = conectar_pestaña_mes()
                        
                        if pestaña:
                            # 1. ID Autoincrementable
                            columna_id = pestaña.col_values(1)
                            ids_numericos = [int(i) for i in columna_id if i.isdigit()]
                            nuevo_id = max(ids_numericos) + 1 if ids_numericos else 1
                            
                            # 2. ESTANDARIZACIÓN A PUNTO (.)
                            # Reemplazamos coma por punto para que Python y la API lo entiendan como float
                            costo_raw = partes[2].strip().replace(',', '.') 
                            try:
                                costo_num = float(costo_raw) # Ahora es un número real para el sistema
                            except:
                                costo_num = 0.0
                            
                            fecha = datetime.now().strftime("%d/%m/%Y")
                            origen = partes[0].strip()
                            destino = partes[1].strip()
                            
                            # 3. Insertar fila como NÚMERO
                            fila = [nuevo_id, fecha, origen, destino, costo_num]
                            pestaña.append_row(fila, value_input_option='USER_ENTERED')
                            
                            # 4. Calcular Gasto Acumulado (leyendo puntos)
                            columna_costos = pestaña.col_values(5)
                            total_mes = 0.0
                            for val in columna_costos:
                                try:
                                    # Limpiamos cualquier residuo y sumamos
                                    limpio = val.replace('S/', '').replace(',', '.').strip()
                                    total_mes += float(limpio)
                                except:
                                    continue
                            
                            # 5. Respuesta en WhatsApp (aquí puedes elegir si verlo con punto o coma)
                            # Si quieres ver punto en el cel: total_wa = f"{total_mes:.2f}"
                            total_wa = f"{total_mes:.2f}" 
                            
                            txt = (
                                f"✅ *¡Registro Exitoso!*\n\n"
                                f"🆔 *ID:* {nuevo_id}\n"
                                f"📍 {origen} ➔ {destino}\n"
                                f"💰 *Costo:* S/ {costo_num:.2f}\n"
                                f"---------------------------\n"
                                f"📊 *Acumulado:* {pestaña.title}\n"
                                f"💵 *Total: S/ {total_wa}*"
                            )
                            enviar_confirmacion_wa(txt, telefono_usuario)
                            print(f"✅ Guardado ID {nuevo_id}. Acumulado: S/ {total_wa}")
                        else:
                            enviar_confirmacion_wa("❌ Error: Pestaña del mes no encontrada.", telefono_usuario)
        except Exception as e:
            print(f"⚠️ Error: {e}")

        return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    # Usar puerto 5000 para local y dinámico para producción
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
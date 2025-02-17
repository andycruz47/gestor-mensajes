import streamlit as st
import os, re, hmac
from dotenv import load_dotenv
import sqlalchemy
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
import json
from common.page_style import hide_streamlit_style
from datetime import date, datetime
from zoneinfo import ZoneInfo

load_dotenv()

# Configuración de la página
st.set_page_config(page_title="Gestor de mensajes", page_icon="📩", layout='wide')
hide_streamlit_style()

# Función para comprobar la contraseña
def check_password():
    def password_entered():
        if hmac.compare_digest(st.session_state["password"], st.secrets["password"]["password"]):
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    st.text_input("Ingresa tu contraseña", type="password", on_change=password_entered, key="password")
    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("Contraseña Incorrecta 😕")
    
    return False

if not check_password():
    hide_streamlit_style()
    st.stop()

# Función para conectarse a PostgreSQL en Railway
def get_db_connection():
    """
    Initializes a connection to a PostgreSQL database in Railway using Streamlit's secrets.
    """
    # Leer credenciales desde secrets.toml
    db_user = st.secrets["postgresql"]["user"]
    db_password = st.secrets["postgresql"]["password"]
    db_host = st.secrets["postgresql"]["host"]
    db_port = st.secrets["postgresql"]["port"]
    db_name = st.secrets["postgresql"]["database"]

    # Construcción de la URL de conexión en formato PostgreSQL
    db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

    # Crear la conexión con SQLAlchemy
    engine = sqlalchemy.create_engine(db_url, pool_pre_ping=True)
    return engine


# Función para obtener los mensajes de la tabla
def get_all_messages():
    engine = get_db_connection()  # Obtiene el pool de SQLAlchemy
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        result = session.execute(text("SELECT * FROM public.educapro_chats order by id;"))  # Agregar text()
        rows = result.fetchall()
    except Exception as e:
        st.error(f"Error al obtener mensajes: {e}")
        rows = []
    finally:
        session.close()

    return rows

#Funcion date_convert
def date_convert(fecha_obj: datetime, zona_horaria: str = "America/Lima") -> str:
    """
    Convierte un objeto datetime con zona horaria a 'dd-mm-yy hh:mm AM/PM' en la zona horaria especificada.

    :param fecha_obj: Objeto datetime con información de zona horaria
    :param zona_horaria: Zona horaria destino (str) - Por defecto, "America/Lima"
    :return: Fecha formateada como 'dd-mm-yy hh:mm AM/PM' (str)
    """
    # Convertir a la zona horaria deseada
    fecha_local = fecha_obj.astimezone(ZoneInfo(zona_horaria))

    # Formatear la fecha
    return fecha_local.strftime("%d-%m-%y %I:%M %p")


# Recuperar registros desde PostgreSQL
rows = get_all_messages()

# Construir el historial de chat a partir de los registros
chat_history = []
for row in rows:
    id_db, session_id, message_val, date_creation = row
    try:
        if isinstance(message_val, dict):
            message_data = message_val
        else:
            message_data = json.loads(message_val)
    except Exception as e:
        st.error(f"Error al parsear JSON: {e}")
        continue

    msg_type = message_data.get("type")   # "human" o "ai"
    content = message_data.get("content")
    
    # Si el contenido es una lista, se invierte el orden y se une en una cadena
    if isinstance(content, list):
        content = " ".join(content[::-1])
    
    # Procesar el contenido: quitar prefijos innecesarios
    if isinstance(content, str):
        #content = re.sub(r"Mensaje del usuario:\s*", "", content, flags=re.IGNORECASE)
        #content = re.sub(r"Telefono del usuario:\s*\d+", "", content, flags=re.IGNORECASE).strip()
        content = re.sub(r".*message text or description:\s*", "", content, flags=re.DOTALL)

    chat_history.append({
         "ChatID": session_id,
         "Role": msg_type,
         "Content": content,
         "Date": date_creation
    })

# Agregar un selector de fecha en el sidebar
selected_date = st.sidebar.date_input("Selecciona una fecha", value=date.today())

# Agregar un buscador de chat_id en el sidebar
search_chat_id = st.sidebar.text_input("Buscar chat por ID", "")

# Filtrar los chat_ids basados en la fecha seleccionada y la búsqueda
filtered_chat_ids = set()
for msg in chat_history:
    msg_date = msg["Date"].astimezone(ZoneInfo("America/Lima")).date()  # Extraer solo la fecha (sin la hora), en zona hora de Lima
    matches_date = msg_date == selected_date  # Coincide con la fecha seleccionada
    matches_search = search_chat_id.lower() in str(msg["ChatID"]).lower()  # Coincide con la búsqueda

    # Si no hay búsqueda, ignorar el filtro de búsqueda
    if not search_chat_id:
        matches_search = True

    # Si coincide con ambos filtros, agregar el chat_id
    if matches_date and matches_search:
        filtered_chat_ids.add(msg["ChatID"])

# Convertir el conjunto a una lista
chat_ids = list(filtered_chat_ids)

# Función para generar los botones en el sidebar
def get_button_label(chat_id):
    return f"{chat_id}"

current_chat_id = None
for chat_id in chat_ids:
    button_label = get_button_label(chat_id)
    if st.sidebar.button(button_label, key=chat_id):
        current_chat_id = chat_id

st.title("Gestor de mensajes | EducaPro")

# Mostrar la conversación del chat seleccionado
if current_chat_id:
    selected_chat = [msg for msg in chat_history if msg["ChatID"] == current_chat_id]
    st.subheader(f"Teléfono: {current_chat_id}")
    
    for message in selected_chat:
        # Definir el prefijo según el rol: "humano:" para mensajes human y "ia:" para mensajes AI
        body = message["Content"]
        date = message["Date"]
        if message["Role"] == "ai":
            with st.chat_message("assistant"):
                st.markdown(date_convert(date), unsafe_allow_html=True)
                st.markdown(body, unsafe_allow_html=True)
        else:
            with st.chat_message("user"):
                st.markdown(date_convert(date), unsafe_allow_html=True)
                st.markdown(body, unsafe_allow_html=True)
else:
    st.write("Selecciona una conversación para ver los mensajes.")

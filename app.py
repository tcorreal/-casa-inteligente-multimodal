import streamlit as st
import numpy as np
from PIL import Image
import tensorflow as tf
import paho.mqtt.client as mqtt  # MQTT

# ---------------- CONFIGURACIÓN STREAMLIT ----------------
st.set_page_config(page_title="Casa Inteligente Multimodal", layout="wide")

# ---------------- CONFIGURACIÓN MQTT ----------------
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_BASE_TOPIC = "casa_oscar"  # cambia 'oscar' si quieres algo más único


@st.cache_resource
def get_mqtt_client():
    """Crea un cliente MQTT y lo deja conectado."""
    client = mqtt.Client()
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()  # para que mantenga la conexión en segundo plano
    return client


def publish_room_state(room: str):
    """Publica el estado de un ambiente (sala/habitacion) por MQTT."""
    client = get_mqtt_client()
    dev = st.session_state.devices[room]
    base = f"{MQTT_BASE_TOPIC}/{room}"

    client.publish(f"{base}/luz", "ON" if dev["luz"] else "OFF")
    client.publish(f"{base}/ventilador", str(dev["ventilador"]))
    client.publish(
        f"{base}/puerta", "CERRADA" if dev["puerta_cerrada"] else "ABIERTA"
    )
    client.publish(f"{base}/presencia", "1" if dev["presencia"] else "0")


# ---------------- CARGA DEL MODELO TM ----------------
@st.cache_resource
def load_tm_model():
    """Carga el modelo de Teachable Machine (gestos.h5 en la raíz del repo)."""
    model = tf.keras.models.load_model("gestos.h5", compile=False)
    return model


tm_model = None
try:
    tm_model = load_tm_model()
    TM_AVAILABLE = True
except Exception as e:
    TM_AVAILABLE = False
    tm_error = str(e)

TM_CLASSES = ["luz_on", "luz_off", "ventilador_on", "ventilador_off"]


def predict_gesto(image: Image.Image):
    """Pasa una imagen por el modelo y devuelve clase + probabilidad."""
    image = image.convert("RGB")
    img = image.resize((224, 224))
    arr = np.array(img) / 255.0
    arr = np.expand_dims(arr, axis=0)

    preds = tm_model.predict(arr)[0]
    idx = int(np.argmax(preds))
    return TM_CLASSES[idx], float(preds[idx])


# ---------------- ESTADO INICIAL ----------------
if "devices" not in st.session_state:
    st.session_state.devices = {
        "sala": {
            "luz": False,
            "brillo": 50,
            "ventilador": 1,
            "puerta_cerrada": True,
            "presencia": False,
        },
        "habitacion": {
            "luz": False,
            "brillo": 50,
            "ventilador": 1,
            "puerta_cerrada": True,
            "presencia": False,
        },
    }

devices = st.session_state.devices


# ---------------- COMANDOS DE TEXTO ----------------
def ejecutar_comando(comando: str):
    comando = comando.lower().strip()

    if "sala" in comando:
        room = "sala"
    elif "habitacion" in comando or "habitación" in comando or "cuarto" in comando:
        room = "habitacion"
    else:
        st.warning("👉 Especifica 'sala' u 'habitación' en el comando.")
        return

    dev = devices[room]

    if "encender luz" in comando:
        dev["luz"] = True
    if "apagar luz" in comando:
        dev["luz"] = False

    if "subir ventilador" in comando:
        dev["ventilador"] = min(3, dev["ventilador"] + 1)
    if "bajar ventilador" in comando:
        dev["ventilador"] = max(0, dev["ventilador"] - 1)
    if "apagar ventilador" in comando:
        dev["ventilador"] = 0
    if "encender ventilador" in comando and dev["ventilador"] == 0:
        dev["ventilador"] = 1

    if "abrir puerta" in comando:
        dev["puerta_cerrada"] = False
    if "cerrar puerta" in comando:
        dev["puerta_cerrada"] = True

    publish_room_state(room)
    st.success(f"✅ Comando aplicado en {room.capitalize()} y enviado por MQTT.")


# ---------------- SIDEBAR ----------------
st.sidebar.title("Casa Inteligente")

pagina = st.sidebar.radio(
    "Navegación",
    ["Panel general", "Control por ambiente", "Control por gestos (TM)"],
)

st.sidebar.markdown("### Comando de texto")
texto_cmd = st.sidebar.text_input(
    "Ejemplo: 'encender luz sala', 'cerrar puerta habitación'"
)
if st.sidebar.button("Ejecutar comando"):
    if texto_cmd.strip():
        ejecutar_comando(texto_cmd)
    else:
        st.sidebar.warning("Escribe un comando primero.")


# ---------------- PÁGINA 1: PANEL GENERAL ----------------
if pagina == "Panel general":
    st.title("Panel general de la casa inteligente")

    col1, col2 = st.columns(2)

    for room, col in zip(["sala", "habitacion"], [col1, col2]):
        dev = devices[room]
        with col:
            st.subheader(room.capitalize())
            luz_estado = "Encendida 💡" if dev["luz"] else "Apagada 💡"
            puerta_estado = "Cerrada 🔒" if dev["puerta_cerrada"] else "Abierta 🔓"
            vent_estado = "Apagado 🌀" if dev["ventilador"] == 0 else f"Velocidad {dev['ventilador']} 🌀"
            presencia = "Persona detectada 🧍" if dev["presencia"] else "Sin presencia"

            st.metric("Luz", luz_estado)
            st.metric("Ventilador", vent_estado)
            st.metric("Puerta", puerta_estado)
            st.metric("Sensor", presencia)

            c1, c2 = st.columns(2)
            with c1:
                if st.button(f"Luz ON/OFF {room}", key=f"btn_luz_{room}"):
                    dev["luz"] = not dev["luz"]
                    publish_room_state(room)
            with c2:
                if st.button(f"Abrir/Cerrar puerta {room}", key=f"btn_puerta_{room}"):
                    dev["puerta_cerrada"] = not dev["puerta_cerrada"]
                    publish_room_state(room)

    st.markdown("---")
    st.subheader("Simulación física (WOKWI / MQTT)")
    st.write(
        "Cada cambio en los estados se publica vía MQTT en el broker "
        f"**{MQTT_BROKER}**, en tópicos como `{MQTT_BASE_TOPIC}/sala/luz`."
    )


# ---------------- PÁGINA 2: CONTROL POR AMBIENTE ----------------
elif pagina == "Control por ambiente":
    st.title("Control detallado por ambiente")

    room = st.selectbox("Selecciona el ambiente", ["sala", "habitacion"])
    dev = devices[room]

    st.subheader(f"Configuración de {room.capitalize()}")

    dev["luz"] = st.toggle("Luz encendida", value=dev["luz"])
    dev["brillo"] = st.slider("Brillo de la luz", 0, 100, dev["brillo"])
    dev["ventilador"] = st.slider(
        "Velocidad ventilador (0 = apagado)", 0, 3, dev["ventilador"]
    )

    puerta_label = "Puerta cerrada" if dev["puerta_cerrada"] else "Puerta abierta"
    if st.button(puerta_label, key=f"btn_puerta_detalle_{room}"):
        dev["puerta_cerrada"] = not dev["puerta_cerrada"]

    dev["presencia"] = st.checkbox(
        "Simular persona presente", value=dev["presencia"]
    )

    publish_room_state(room)

    st.markdown("### Vista visual")
    st.write(
        f"💡 Luz: {'Encendida' if dev['luz'] else 'Apagada'} | "
        f"🔒 Puerta: {'Cerrada' if dev['puerta_cerrada'] else 'Abierta'} | "
        f"🌀 Ventilador: {dev['ventilador']} | "
        f"🧍 Presencia: {'Sí' if dev['presencia'] else 'No'}"
    )


# ---------------- PÁGINA 3: CONTROL POR GESTOS (TM) ----------------
else:
    st.title("Control por gestos con Teachable Machine")

    if not TM_AVAILABLE:
        st.error("No se pudo cargar el modelo de Teachable Machine.")
        st.code(tm_error)
    else:
        st.markdown(
            "Usa gestos frente a la cámara para controlar **la sala**:\n"
            "- `luz_on` / `luz_off`\n"
            "- `ventilador_on` / `ventilador_off`\n"
        )

        foto = st.camera_input("Haz tu gesto y toma la foto")

        if foto is not None:
            image = Image.open(foto)
            clase, prob = predict_gesto(image)

            st.write(f"🔍 Modelo detectó: **{clase}** (confianza: {prob:.2f})")

            dev = devices["sala"]

            if clase == "luz_on":
                dev["luz"] = True
            elif clase == "luz_off":
                dev["luz"] = False
            elif clase == "ventilador_on":
                dev["ventilador"] = max(dev["ventilador"], 1)
            elif clase == "ventilador_off":
                dev["ventilador"] = 0

            publish_room_state("sala")

            st.success("Estado de la sala actualizado con el gesto y enviado por MQTT.")
            st.write(
                f"💡 Luz sala: {'Encendida' if dev['luz'] else 'Apagada'} | "
                f"🌀 Ventilador sala: {dev['ventilador']}"
            )

        st.markdown("---")
        st.caption(
            "Este módulo demuestra control multimodal (UI + texto + gestos) "
            "y envía los estados a un dispositivo físico simulado vía MQTT."
        )

import streamlit as st
import numpy as np
from PIL import Image
import tensorflow as tf

# ---------------- CONFIGURACIÓN STREAMLIT ----------------
st.set_page_config(page_title="Casa Inteligente Multimodal", layout="wide")


# ---------------- CARGA DEL MODELO TM ----------------
@st.cache_resource
def load_tm_model():
    """
    Carga el modelo de Teachable Machine una sola vez.
    El archivo debe estar en la raíz del proyecto con el nombre: gestos.h5
    """
    model = tf.keras.models.load_model("gestos.h5", compile=False)
    return model


# Intentamos cargar el modelo. Si falla, la app igual funciona.
tm_model = None
try:
    tm_model = load_tm_model()
    TM_AVAILABLE = True
except Exception as e:
    TM_AVAILABLE = False
    tm_error = str(e)

# Clases en el mismo orden en que se entrenaron en Teachable Machine
TM_CLASSES = ["luz_on", "luz_off", "ventilador_on", "ventilador_off"]


def predict_gesto(image: Image.Image):
    """
    Recibe una imagen PIL, la prepara y devuelve la clase predicha y su probabilidad.
    """
    image = image.convert("RGB")
    img = image.resize((224, 224))  # tamaño típico de TM
    arr = np.array(img) / 255.0
    arr = np.expand_dims(arr, axis=0)  # shape (1, 224, 224, 3)

    preds = tm_model.predict(arr)[0]
    idx = int(np.argmax(preds))
    return TM_CLASSES[idx], float(preds[idx])


# ---------------- ESTADO INICIAL DE DISPOSITIVOS ----------------
if "devices" not in st.session_state:
    st.session_state.devices = {
        "sala": {
            "luz": False,
            "brillo": 50,
            "ventilador": 1,   # 0=apagado, 1-3 velocidad
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


# ---------------- FUNCIÓN PARA COMANDOS DE TEXTO ----------------
def ejecutar_comando(comando: str):
    comando = comando.lower().strip()

    # 1. Detectar ambiente
    if "sala" in comando:
        room = "sala"
    elif "habitacion" in comando or "habitación" in comando or "cuarto" in comando:
        room = "habitacion"
    else:
        st.warning("👉 Especifica 'sala' u 'habitación' en el comando.")
        return

    dev = devices[room]

    # 2. Luz
    if "encender luz" in comando:
        dev["luz"] = True
    if "apagar luz" in comando:
        dev["luz"] = False

    # 3. Ventilador
    if "subir ventilador" in comando:
        dev["ventilador"] = min(3, dev["ventilador"] + 1)
    if "bajar ventilador" in comando:
        dev["ventilador"] = max(0, dev["ventilador"] - 1)
    if "apagar ventilador" in comando:
        dev["ventilador"] = 0
    if "encender ventilador" in comando and dev["ventilador"] == 0:
        dev["ventilador"] = 1

    # 4. Puerta
    if "abrir puerta" in comando:
        dev["puerta_cerrada"] = False
    if "cerrar puerta" in comando:
        dev["puerta_cerrada"] = True

    st.success(f"✅ Comando aplicado en {room.capitalize()}")


# ---------------- SIDEBAR: NAVEGACIÓN Y COMANDOS ----------------
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
            if dev["ventilador"] == 0:
                vent_estado = "Apagado 🌀"
            else:
                vent_estado = f"Velocidad {dev['ventilador']} 🌀"
            presencia = "Persona detectada 🧍" if dev["presencia"] else "Sin presencia"

            st.metric("Luz", luz_estado)
            st.metric("Ventilador", vent_estado)
            st.metric("Puerta", puerta_estado)
            st.metric("Sensor", presencia)

            # Botones rápidos
            c1, c2 = st.columns(2)
            with c1:
                if st.button(f"Luz ON/OFF {room}", key=f"btn_luz_{room}"):
                    dev["luz"] = not dev["luz"]
            with c2:
                if st.button(f"Abrir/Cerrar puerta {room}", key=f"btn_puerta_{room}"):
                    dev["puerta_cerrada"] = not dev["puerta_cerrada"]

    st.markdown("---")
    st.subheader("Simulación física (WOKWI / Arduino)")
    st.write(
        "Los estados de luz y puerta representan el estado de los LEDs y el servo "
        "en un simulador como WOKWI. En el informe puedes explicar cómo estos "
        "estados se enviarían a un microcontrolador real."
    )


# ---------------- PÁGINA 2: CONTROL POR AMBIENTE ----------------
elif pagina == "Control por ambiente":
    st.title("Control detallado por ambiente")

    room = st.selectbox("Selecciona el ambiente", ["sala", "habitacion"])
    dev = devices[room]

    st.subheader(f"Configuración de {room.capitalize()}")

    # Luz
    dev["luz"] = st.toggle("Luz encendida", value=dev["luz"])
    dev["brillo"] = st.slider("Brillo de la luz", 0, 100, dev["brillo"])

    # Ventilador
    dev["ventilador"] = st.slider(
        "Velocidad ventilador (0 = apagado)", 0, 3, dev["ventilador"]
    )

    # Puerta
    puerta_label = "Puerta cerrada" if dev["puerta_cerrada"] else "Puerta abierta"
    if st.button(puerta_label, key=f"btn_puerta_detalle_{room}"):
        dev["puerta_cerrada"] = not dev["puerta_cerrada"]

    # Sensor de presencia (simulado)
    dev["presencia"] = st.checkbox(
        "Simular persona presente", value=dev["presencia"]
    )

    st.markdown("### Vista visual")
    st.write(
        f"💡 Luz: {'Encendida' if dev['luz'] else 'Apagada'} | "
        f"🔒 Puerta: {'Cerrada' if dev['puerta_cerrada'] else 'Abierta'} | "
        f"🌀 Ventilador: {dev['ventilador']} | "
        f"🧍 Presencia: {'Sí' if dev['presencia'] else 'No'}"
    )

    st.info(
        "En la maqueta o en WOKWI puedes asociar: "
        "LED = luz, Servo = puerta, otro LED o display = ventilador."
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
            "- Gesto para `luz_on` o `luz_off`\n"
            "- Gesto para `ventilador_on` o `ventilador_off`\n"
        )

        foto = st.camera_input("Haz tu gesto y toma la foto")

        if foto is not None:
            image = Image.open(foto)
            clase, prob = predict_gesto(image)

            st.write(f"🔍 Modelo detectó: **{clase}** (confianza: {prob:.2f})")

            dev = devices["sala"]  # controlamos la sala con gestos

            if clase == "luz_on":
                dev["luz"] = True
            elif clase == "luz_off":
                dev["luz"] = False
            elif clase == "ventilador_on":
                dev["ventilador"] = max(dev["ventilador"], 1)
            elif clase == "ventilador_off":
                dev["ventilador"] = 0

            st.success("Estado de la sala actualizado con el gesto.")
            st.write(
                f"💡 Luz sala: {'Encendida' if dev['luz'] else 'Apagada'} | "
                f"🌀 Ventilador sala: {dev['ventilador']}"
            )

        st.markdown("---")
        st.caption(
            "Este módulo demuestra una interfaz multimodal visual usando Teachable Machine."
        )


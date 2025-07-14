import streamlit as st

st.set_page_config(page_title="Control de Clima Invernadero", layout="centered")

st.title("🌱 Sistema de Control de Clima para Invernadero")

st.header("Variables Ambientales")

# Temperatura
temp = st.slider('Temperatura (°C)', 10, 40, 22)
# Humedad
hum = st.slider('Humedad (%)', 30, 90, 60)
# Humedad del Suelo
soil = st.progress(0.5)  # Simula 50% (puedes conectar luego a tus sensores)

# Botón de Riego
if st.button('💧 Activar Riego'):
    st.success("¡Riego activado!")

st.write(f"Temperatura: {temp}°C | Humedad: {hum}%")

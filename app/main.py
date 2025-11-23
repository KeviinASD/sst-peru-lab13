import streamlit as st
from app.auth import autenticar_usuario, cerrar_sesion
from app.modules import (
    riesgos, inspecciones, capacitaciones, 
    incidentes, epp, documental, reportes
)

# Configuración de página
st.set_page_config(
    page_title="Sistema SST Perú",
    layout="wide",
    initial_sidebar_state="expanded"
)

def main():
    # Autenticación
    usuario = autenticar_usuario()
    
    if not usuario:
        st.stop()
    
    # Sidebar - Navegación
    st.sidebar.title(f"👤 {usuario['nombre_completo']}")
    st.sidebar.markdown(f"**Rol:** {usuario['rol'].upper()}")

    cerrar_sesion()
    
    modulo = st.sidebar.selectbox(
        "Módulos",
        [
            "🏠 Dashboard",
            "⚠️ Gestión de Riesgos",
            "📋 Inspecciones",
            "🎓 Capacitaciones",
            "🚨 Incidentes",
            "🛡️ Gestión de EPP",
            "📚 Documentos",
            "📊 Reportes"
        ]
    )
    
    # Router de módulos
    if modulo == "🏠 Dashboard":
        from app.modules import dashboard
        dashboard.mostrar(usuario)
    elif "Riesgos" in modulo:
        riesgos.mostrar(usuario)
    elif "Inspecciones" in modulo:
        inspecciones.mostrar(usuario)
    elif "Capacitaciones" in modulo:
        from app.modules import capacitaciones
        capacitaciones.mostrar(usuario)
    elif "Incidentes" in modulo:
        from app.modules import incidentes
        incidentes.mostrar(usuario)
    elif "EPP" in modulo:
        from app.modules import epp
        epp.mostrar(usuario)
    elif "Documentos" in modulo:
        documental.mostrar(usuario)
    elif "Reportes" in modulo:
        from app.modules import reportes
        reportes.mostrar(usuario)


def mostrar_dashboard(usuario):
    st.title("Dashboard SST - Ley 29783")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Riesgos Pendientes", "12", "+3")
    with col2:
        st.metric("Inspecciones Hoy", "5", "0")
    with col3:
        st.metric("Incidentes Mes", "3", "-2")
    with col4:
        st.metric("EPP por Vencer", "8", "+1")
    
    # Gráfico de riesgos por área
    st.subheader("Nivel de Riesgo por Área")
    # (Aquí iría código para generar gráfico con plotly)

if __name__ == "__main__":
    main()

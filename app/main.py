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
    st.sidebar.divider()

    # Inicializar módulo seleccionado en session_state
    if 'modulo_seleccionado' not in st.session_state:
        st.session_state.modulo_seleccionado = "🏠 Dashboard"
    
    # Botones de navegación
    st.sidebar.markdown("### 📑 Módulos")
    
    if st.sidebar.button("🏠 Dashboard", use_container_width=True, 
                        type="primary" if st.session_state.modulo_seleccionado == "🏠 Dashboard" else "secondary"):
        st.session_state.modulo_seleccionado = "🏠 Dashboard"
        st.rerun()
    
    if st.sidebar.button("⚠️ Gestión de Riesgos", use_container_width=True,
                        type="primary" if st.session_state.modulo_seleccionado == "⚠️ Gestión de Riesgos" else "secondary"):
        st.session_state.modulo_seleccionado = "⚠️ Gestión de Riesgos"
        st.rerun()
    
    if st.sidebar.button("📋 Inspecciones", use_container_width=True,
                        type="primary" if st.session_state.modulo_seleccionado == "📋 Inspecciones" else "secondary"):
        st.session_state.modulo_seleccionado = "📋 Inspecciones"
        st.rerun()
    
    if st.sidebar.button("🎓 Capacitaciones", use_container_width=True,
                        type="primary" if st.session_state.modulo_seleccionado == "🎓 Capacitaciones" else "secondary"):
        st.session_state.modulo_seleccionado = "🎓 Capacitaciones"
        st.rerun()
    
    if st.sidebar.button("🚨 Incidentes", use_container_width=True,
                        type="primary" if st.session_state.modulo_seleccionado == "🚨 Incidentes" else "secondary"):
        st.session_state.modulo_seleccionado = "🚨 Incidentes"
        st.rerun()
    
    if st.sidebar.button("🛡️ Gestión de EPP", use_container_width=True,
                        type="primary" if st.session_state.modulo_seleccionado == "🛡️ Gestión de EPP" else "secondary"):
        st.session_state.modulo_seleccionado = "🛡️ Gestión de EPP"
        st.rerun()
    
    if st.sidebar.button("📚 Documentos", use_container_width=True,
                        type="primary" if st.session_state.modulo_seleccionado == "📚 Documentos" else "secondary"):
        st.session_state.modulo_seleccionado = "📚 Documentos"
        st.rerun()
    
    if st.sidebar.button("📊 Reportes", use_container_width=True,
                        type="primary" if st.session_state.modulo_seleccionado == "📊 Reportes" else "secondary"):
        st.session_state.modulo_seleccionado = "📊 Reportes"
        st.rerun()
    
    st.sidebar.divider()
    cerrar_sesion()
    
    # Router de módulos
    modulo = st.session_state.modulo_seleccionado
    
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

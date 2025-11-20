import streamlit as st
import pandas as pd
from app.utils.supabase_client import get_supabase_client
from app.auth import requerir_rol
import plotly.express as px

def mostrar(usuario):
    """Módulo de Gestión de Riesgos (Ley 29783 Art. 26-28)"""
    requerir_rol(['admin', 'sst', 'supervisor'])
    
    st.title("⚠️ Gestión de Riesgos Laborales")
    
    tab1, tab2, tab3 = st.tabs([
        "📝 Registrar Riesgo",
        "📋 Listar Riesgos",
        "📊 Dashboard"
    ])
    
    with tab1:
        registrar_riesgo(usuario)
    
    with tab2:
        listar_riesgos(usuario)
    
    with tab3:
        dashboard_riesgos()

def registrar_riesgo(usuario):
    """Formulario dinámico de evaluación de riesgos"""
    
    with st.form("form_riesgo", clear_on_submit=True):
        st.subheader("Evaluación de Riesgo")
        
        col1, col2 = st.columns(2)
        
        with col1:
            area = st.selectbox("Área", ["Producción", "Almacén", "Oficinas", "Mantenimiento"])
            puesto = st.text_input("Puesto de Trabajo")
            actividad = st.text_area("Actividad")
        
        with col2:
            peligro = st.text_area("Peligro Identificado")
            tipo_peligro = st.selectbox(
                "Tipo de Peligro",
                ["Físico", "Químico", "Biológico", "Ergonómico", "Psicosocial", "Mecánico"]
            )
        
        st.markdown("### Matriz de Riesgo")
        col3, col4 = st.columns(2)
        
        with col3:
            probabilidad = st.slider("Probabilidad (1-5)", 1, 5, 3,
                help="1=Muy baja, 5=Muy alta")
            severidad = st.slider("Severidad (1-5)", 1, 5, 3,
                help="1=Leve, 5=Catastrófico")
        
        nivel_riesgo = probabilidad * severidad
        
        with col4:
            st.metric("NIVEL DE RIESGO", nivel_riesgo)
            if nivel_riesgo >= 15:
                st.error("🚨 RIESGO ALTO - Requiere control inmediato")
            elif nivel_riesgo >= 8:
                st.warning("⚠️ RIESGO MEDIO - Requiere control a corto plazo")
            else:
                st.success("✅ RIESGO BAJO - Control estándar")
        
        controles = st.text_area("Controles Actuales")
        responsable = st.selectbox("Responsable", ["Juan Pérez", "María García", "Carlos Ruiz"])
        
        submitted = st.form_submit_button("💾 Guardar Evaluación")
        
        if submitted:
            guardar_riesgo({
                'area': area,
                'puesto_trabajo': puesto,
                'actividad': actividad,
                'peligro': peligro,
                'tipo_peligro': tipo_peligro,
                'probabilidad': probabilidad,
                'severidad': severidad,
                'controles_actuales': controles,
                'responsable_id': usuario['id']
            })
            st.success("✅ Riesgo registrado exitosamente")

def guardar_riesgo(data):
    """Guarda en Supabase y dispara webhook de n8n"""
    supabase = get_supabase_client()
    
    # Generar código único
    codigo = f"R-{pd.Timestamp.now().strftime('%Y%m%d')}-{hash(data['peligro'])%1000:03d}"
    data['codigo'] = codigo
    
    try:
        # Insertar en BD
        supabase.table('riesgos').insert(data).execute()
        
        # Disparar webhook de n8n
        import requests
        requests.post(
            st.secrets["N8N_WEBHOOK_URL"] + "/riesgo-nuevo",
            json={"codigo": codigo, "nivel_riesgo": data['probabilidad'] * data['severidad']}
        )
        
    except Exception as e:
        st.error(f"Error al guardar: {e}")

def listar_riesgos(usuario):
    """Tabla interactiva de riesgos"""
    
    supabase = get_supabase_client()
    
    # Filtros
    col1, col2 = st.columns([3, 1])
    with col1:
        filtro_area = st.multiselect("Filtrar por Área", 
            ["Producción", "Almacén", "Oficinas", "Mantenimiento"])
    with col2:
        filtro_estado = st.selectbox("Estado", ["todos", "pendiente", "en_mitigacion", "controlado"])
    
    # Consulta
    query = supabase.table('riesgos').select('*, usuarios(nombre_completo)')
    
    if filtro_area:
        query = query.in_('area', filtro_area)
    if filtro_estado != "todos":
        query = query.eq('estado', filtro_estado)
    
    response = query.execute()
    
    if response.data:
        df = pd.DataFrame(response.data)
        
        # Columnas para la tabla
        df_display = df[['codigo', 'area', 'puesto_trabajo', 'peligro', 
                         'nivel_riesgo', 'estado', 'usuarios']].copy()
        
        # Aplicar colores según nivel
        def color_riesgo(val):
            if val >= 15: return 'background-color: #ffcccc'
            elif val >= 8: return 'background-color: #ffff99'
            else: return 'background-color: #ccffcc'
        
        df_display = df_display.style.applymap(color_riesgo, subset=['nivel_riesgo'])
        
        st.dataframe(df_display, use_container_width=True)
        
        # Exportar a Excel
        if st.button("📥 Exportar a Excel"):
            output = df.to_excel("riesgos.xlsx", index=False)
            with open("riesgos.xlsx", "rb") as file:
                st.download_button(
                    label="Descargar Excel",
                    data=file,
                    file_name=f"riesgos_{pd.Timestamp.now().strftime('%Y%m%d')}.xlsx"
                )
    else:
        st.info("No se encontraron riesgos con los filtros seleccionados")

def dashboard_riesgos():
    """Visualización en tiempo real"""
    
    supabase = get_supabase_client()
    data = supabase.table('riesgos').select('*').execute().data
    
    if not data:
        st.warning("No hay datos para mostrar")
        return
    
    df = pd.DataFrame(data)
    
    # Gráfico 1: Riesgos por Área
    fig1 = px.bar(
        df.groupby('area').size().reset_index(name='cantidad'),
        x='area', y='cantidad',
        title="Riesgos por Área",
        color='cantidad'
    )
    st.plotly_chart(fig1, use_container_width=True)
    
    # Gráfico 2: Distribución por Nivel
    df['rango_riesgo'] = pd.cut(df['nivel_riesgo'], 
                                bins=[0, 7, 14, 25], 
                                labels=['Bajo', 'Medio', 'Alto'])
    fig2 = px.pie(
        df['rango_riesgo'].value_counts(),
        names=df['rango_riesgo'].value_counts().index,
        values=df['rango_riesgo'].value_counts().values,
        title="Distribución de Nivel de Riesgo"
    )
    st.plotly_chart(fig2, use_container_width=True)

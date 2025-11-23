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
    supabase = get_supabase_client() # Obtener la conexión a la base de datos

    # Obtener lista de usuarios de la BD
    response = supabase.table('usuarios').select('id, nombre_completo, rol').execute()
    if response.data:
        usuarios_bd = response.data
        opciones_responsable = {u['nombre_completo']: u['id'] for u in usuarios_bd}
    else:
        opciones_responsable = {}


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
            probabilidad = st.slider(
                "Probabilidad (1-5)", 
                1, 5, 3,
                help="1 = Muy baja, 5 = Muy alta"
            )
            severidad = st.slider(
                "Severidad (1-5)", 
                1, 5, 3,
                help="1 = Leve, 5 = Catastrófico"
            )

        # CALCULO REACTIVO AQUÍ, SIN SACARLO DEL BLOQUE
        nivel_riesgo = probabilidad * severidad

        if nivel_riesgo >= 15:
            evaluacion_riesgo = "🚨 RIESGO ALTO - Requiere control inmediato"
        elif nivel_riesgo >= 8:
            evaluacion_riesgo = "⚠️ RIESGO MEDIO - Requiere control a corto plazo"
        else:
            evaluacion_riesgo = "✅ RIESGO BAJO - Control estándar"

        with col4:
            controles = st.text_area("Controles Actuales")
        
        #responsable = st.selectbox("Responsable", ["Juan Pérez", "María García", "Carlos Ruiz"])
        # Selectbox dinámico de responsables
        responsable_nombre = None
        if opciones_responsable:
            responsable_nombre = st.selectbox("Responsable", list(opciones_responsable.keys()))
            responsable_id = opciones_responsable[responsable_nombre]
        else:
            st.warning("No se encontraron usuarios en la base de datos")
            responsable_id = None

        submitted = st.form_submit_button("💾 Guardar Evaluación")
        
        if submitted:
            # Validaciones
            errores = []
            
            if not puesto or puesto.strip() == "":
                errores.append("⚠️ El campo 'Puesto de Trabajo' es obligatorio")
            
            if not actividad or actividad.strip() == "":
                errores.append("⚠️ El campo 'Actividad' es obligatorio")
            
            if not peligro or peligro.strip() == "":
                errores.append("⚠️ El campo 'Peligro Identificado' es obligatorio")
            
            if responsable_id is None:
                errores.append("⚠️ Debe seleccionar un responsable")
            
            if errores:
                for error in errores:
                    st.error(error)
            else:
                # Guardar riesgo
                resultado = guardar_riesgo({
                    'area': area,
                    'puesto_trabajo': puesto,
                    'actividad': actividad,
                    'peligro': peligro,
                    'tipo_peligro': tipo_peligro,
                    'probabilidad': probabilidad,
                    'severidad': severidad,
                    'evaluacion_riesgo': evaluacion_riesgo,
                    'controles_actuales': controles,
                    'responsable_id': responsable_id
                })
                
                if resultado:
                    mostrar_resumen_riesgo(resultado, responsable_nombre if responsable_nombre else "No asignado")

def guardar_riesgo(data):
    """Guarda en Supabase y dispara webhook de n8n"""
    supabase = get_supabase_client()
    
    # Generar código único
    codigo = f"R-{pd.Timestamp.now().strftime('%Y%m%d')}-{hash(data['peligro'])%1000:03d}"
    data['codigo'] = codigo
    
    try:
        # Insertar en BD
        response = supabase.table('riesgos').insert(data).execute()
        
        if response.data:
            return response.data[0]
        return None
        
    except Exception as e:
        st.error(f"Error al guardar: {e}")
        return None

def mostrar_resumen_riesgo(riesgo, responsable_nombre):
    """Muestra un resumen con los principales datos del riesgo guardado"""
    st.success("✅ Riesgo registrado exitosamente")
    
    st.markdown("---")
    st.markdown("### 📋 Resumen del Riesgo Registrado")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"**Código:** `{riesgo.get('codigo', 'N/A')}`")
        st.markdown(f"**Área:** {riesgo.get('area', 'N/A')}")
        st.markdown(f"**Puesto de Trabajo:** {riesgo.get('puesto_trabajo', 'N/A')}")
        st.markdown(f"**Tipo de Peligro:** {riesgo.get('tipo_peligro', 'N/A')}")
    
    with col2:
        st.markdown(f"**Nivel de Riesgo:** {riesgo.get('nivel_riesgo', 'N/A')}")
        st.markdown(f"**Evaluación:** {riesgo.get('evaluacion_riesgo', 'N/A')}")
        st.markdown(f"**Probabilidad:** {riesgo.get('probabilidad', 'N/A')}/5")
        st.markdown(f"**Severidad:** {riesgo.get('severidad', 'N/A')}/5")
        st.markdown(f"**Responsable:** {responsable_nombre}")
    
    st.markdown("---")
    
    with st.expander("📝 Ver Detalles Completos"):
        st.markdown(f"**Actividad:** {riesgo.get('actividad', 'N/A')}")
        st.markdown(f"**Peligro Identificado:** {riesgo.get('peligro', 'N/A')}")
        st.markdown(f"**Controles Actuales:** {riesgo.get('controles_actuales', 'No especificado')}")

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
    query = supabase.table('riesgos').select('*, usuarios(nombre_completo, rol)')
    
    if filtro_area:
        query = query.in_('area', filtro_area)
    if filtro_estado != "todos":
        query = query.eq('estado', filtro_estado)
    
    response = query.execute()
    
    if response.data:
        df = pd.DataFrame(response.data)
        
        # Procesar la columna de usuarios para mostrar nombre y rol
        def formatear_usuario(usuario_data):
            if usuario_data and isinstance(usuario_data, dict):
                nombre = usuario_data.get('nombre_completo', 'N/A')
                rol = usuario_data.get('rol', 'N/A')
                return f"{nombre} ({rol})"
            elif usuario_data and isinstance(usuario_data, list) and len(usuario_data) > 0:
                # Si es una lista, tomar el primer elemento
                usuario = usuario_data[0]
                nombre = usuario.get('nombre_completo', 'N/A')
                rol = usuario.get('rol', 'N/A')
                return f"{nombre} ({rol})"
            return "No asignado"
        
        df['responsable'] = df['usuarios'].apply(formatear_usuario)
        
        # Columnas para la tabla
        df_display = df[['codigo', 'area', 'puesto_trabajo', 'peligro', 
                         'nivel_riesgo', 'estado', 'responsable']].copy()
        
        # Aplicar colores según nivel
        def color_riesgo(val):
            if val >= 15: return 'background-color: #ffcccc ; color: black;'
            elif val >= 8: return 'background-color: #ffff99;color: black;'
            else: return 'background-color: #ccffcc;color: black;'
        
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

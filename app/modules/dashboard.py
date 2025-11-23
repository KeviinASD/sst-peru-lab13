import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from app.utils.supabase_client import get_supabase_client
from app.auth import requerir_rol
import io

def mostrar(usuario):
    """Dashboard Principal de Seguridad y Salud en el Trabajo"""
    requerir_rol(['admin', 'sst', 'supervisor', 'gerente'])
    
    st.title("📊 Dashboard SST - Indicadores Ley 29783")
    
    # Filtros globales en sidebar
    with st.sidebar.expander("🔍 Filtros Avanzados", expanded=True):
        filtros = crear_filtros_dashboard()
    
    # Cargar datos con caching
    data = cargar_datos_dashboard(filtros)
    
    if not data:
        st.warning("No hay datos para mostrar con los filtros seleccionados")
        return
    
    # KPI Cards
    mostrar_kpi_cards(data)
    
    # Tabs de visualización
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📈 Tendencias",
        "⚠️ Riesgos",
        "🚨 Incidentes",
        "📋 Inspecciones",
        "📊 Reportes Legales"
    ])
    
    with tab1:
        mostrar_tendencias(data, filtros)
    
    with tab2:
        mostrar_analisis_riesgos(data)
    
    with tab3:
        mostrar_analisis_incidentes(data)
    
    with tab4:
        mostrar_analisis_inspecciones(data)
    
    with tab5:
        mostrar_reportes_legales(data, filtros)

def crear_filtros_dashboard():
    """Crear filtros interactivos para el dashboard"""
    
    # Rango de fechas
    fecha_inicio = st.date_input(
        "Fecha Inicio",
        value=datetime.now() - timedelta(days=90)
    )
    fecha_fin = st.date_input(
        "Fecha Fin",
        value=datetime.now()
    )
    
    # Áreas
    supabase = get_supabase_client()
    areas = supabase.table('riesgos').select('area').execute().data
    areas_unicas = sorted(list(set([a['area'] for a in areas]))) if areas else []
    
    areas_seleccionadas = st.multiselect(
        "Áreas",
        options=areas_unicas,
        default=areas_unicas
    )
    
    # Tipo de incidente
    tipos_incidente = st.multiselect(
        "Tipos de Incidente",
        options=["incidente", "accidente", "enfermedad_laboral"],
        default=["incidente", "accidente", "enfermedad_laboral"]
    )
    
    # Nivel de riesgo
    nivel_riesgo = st.slider(
        "Nivel de Riesgo Mínimo",
        1, 25, 1
    )
    
    return {
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'areas': areas_seleccionadas,
        'tipos_incidente': tipos_incidente,
        'nivel_riesgo_min': nivel_riesgo
    }

@st.cache_data(ttl=300)
def cargar_datos_dashboard(filtros):
    """Cargar y procesar datos para el dashboard con caching de 5 min"""
    
    supabase = get_supabase_client()

    
    
    try:
        # Cargar riesgos
        query_riesgos = supabase.table('riesgos').select('*')
        if filtros['areas']:
            query_riesgos = query_riesgos.in_('area', filtros['areas'])
        
        riesgos = query_riesgos.execute().data
        
        # Cargar incidentes con filtro de fecha
        query_incidentes = supabase.table('incidentes').select('*').gte(
            'fecha_hora', filtros['fecha_inicio']
        ).lte('fecha_hora', filtros['fecha_fin'])
        
        if filtros['tipos_incidente']:
            query_incidentes = query_incidentes.in_('tipo', filtros['tipos_incidente'])
        if filtros['areas']:
            query_incidentes = query_incidentes.in_('area', filtros['areas'])
        
        incidentes = query_incidentes.execute().data
        
        # Cargar inspecciones
        inspecciones = supabase.table('inspecciones').select('*').gte(
            'fecha_programada', filtros['fecha_inicio']
        ).execute().data
        
        # Cargar hallazgos
        hallazgos = supabase.table('hallazgos').select('*').execute().data
        
        # Cargar EPP
        epp = supabase.table('epp_asignaciones').select('*').execute().data
        
        # Cargar capacitaciones
        capacitaciones = supabase.table('capacitaciones').select('*').execute().data
        
        return {
            'riesgos': pd.DataFrame(riesgos) if riesgos else pd.DataFrame(),
            'incidentes': pd.DataFrame(incidentes) if incidentes else pd.DataFrame(),
            'inspecciones': pd.DataFrame(inspecciones) if inspecciones else pd.DataFrame(),
            'hallazgos': pd.DataFrame(hallazgos) if hallazgos else pd.DataFrame(),
            'epp': pd.DataFrame(epp) if epp else pd.DataFrame(),
            'capacitaciones': pd.DataFrame(capacitaciones) if capacitaciones else pd.DataFrame()
        }
        
    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        return None

def mostrar_kpi_cards(data):
    """Mostrar tarjetas de métricas clave en tiempo real"""
    
    st.markdown("### 📊 Indicadores Clave de Desempeño")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    # KPI 1: Riesgos Pendientes
    with col1:
        if not data['riesgos'].empty and 'estado' in data['riesgos'].columns:
            riesgos_pendientes = len(data['riesgos'][data['riesgos']['estado'] == 'pendiente'])
            st.metric(
                label="⚠️ Riesgos Pendientes",
                value=riesgos_pendientes,
                delta=f"+{riesgos_pendientes - 5}" if riesgos_pendientes > 5 else f"{riesgos_pendientes}",
                delta_color="inverse"
            )
        else:
            st.metric(
                label="⚠️ Riesgos Pendientes",
                value="0",
                delta="Sin datos"
            )
    
    # KPI 2: Incidentes Mes
    with col2:
        incidentes_mes = len(data['incidentes'])
        tasa_frecuencia = calcular_tasa_frecuencia(incidentes_mes, 50000)  # 50k horas hombre
        st.metric(
            label="🚨 Tasa Frecuencia",
            value=f"{tasa_frecuencia:.2f}",
            delta="vs meta: 5.0",
            delta_color="inverse"
        )
    
    # KPI 3: EPP por Vencer
    with col3:
        if not data['epp'].empty and 'fecha_vencimiento' in data['epp'].columns:
            try:
                fecha_limite = datetime.now().date() + timedelta(days=30)
                epp_vencer = len(data['epp'][pd.to_datetime(data['epp']['fecha_vencimiento']).dt.date <= fecha_limite])
                st.metric(
                    label="🛡️ EPP por Vencer",
                    value=epp_vencer,
                    delta=f"{epp_vencer} en 30 días",
                    delta_color="inverse"
                )
            except Exception as e:
                st.metric(
                    label="🛡️ EPP por Vencer",
                    value="N/A",
                    delta="Error al calcular"
                )
        else:
            st.metric(
                label="🛡️ EPP por Vencer",
                value="0",
                delta="Sin datos"
            )
    
    # KPI 4: Hallazgos Abiertos
    with col4:
        if not data['hallazgos'].empty and 'estado' in data['hallazgos'].columns:
            hallazgos_abiertos = len(data['hallazgos'][data['hallazgos']['estado'] == 'abierto'])
            st.metric(
                label="📋 Hallazgos Abiertos",
                value=hallazgos_abiertos,
                delta=f"{hallazgos_abiertos - 3}" if hallazgos_abiertos > 3 else "✅",
                delta_color="inverse"
            )
        else:
            st.metric(
                label="📋 Hallazgos Abiertos",
                value="0",
                delta="Sin datos"
            )
    
    # KPI 5: Cumplimiento Capacitación
    with col5:
        if not data['capacitaciones'].empty and 'estado' in data['capacitaciones'].columns:
            capac_completadas = len(data['capacitaciones'][data['capacitaciones']['estado'] == 'realizada'])
            capac_total = len(data['capacitaciones'])
            cumplimiento = (capac_completadas / capac_total * 100) if capac_total > 0 else 0
            st.metric(
                label="🎓 % Capacitación",
                value=f"{cumplimiento:.1f}%",
                delta=f"{capac_completadas}/{capac_total} completadas"
            )
        else:
            st.metric(label="🎓 % Capacitación", value="N/A")

def calcular_tasa_frecuencia(incidentes, horas_hombre):
    """Tasa de Frecuencia = (N° Accidentes × 1,000,000) / Horas Hombre Trabajadas"""
    return (incidentes * 1_000_000) / horas_hombre if horas_hombre > 0 else 0

def calcular_tasa_severidad(dias_perdidos, horas_hombre):
    """Tasa de Severidad = (Días Perdidos × 1,000,000) / Horas Hombre Trabajadas"""
    return (dias_perdidos * 1_000_000) / horas_hombre if horas_hombre > 0 else 0

def mostrar_tendencias(data, filtros):
    """Análisis de tendencias históricas"""
    
    st.subheader("📈 Tendencias Históricas")
    
    if data['incidentes'].empty:
        st.info("No hay datos de incidentes para mostrar tendencias")
        return
    
    # Preparar datos mensuales
    if 'fecha_hora' not in data['incidentes'].columns or 'tipo' not in data['incidentes'].columns:
        st.info("Los datos de incidentes no tienen las columnas necesarias (fecha_hora, tipo)")
        return
    
    data['incidentes']['mes'] = pd.to_datetime(data['incidentes']['fecha_hora']).dt.to_period('M')
    tendencias = data['incidentes'].groupby(['mes', 'tipo']).size().unstack(fill_value=0)
    tendencias.index = tendencias.index.astype(str)
    
    # Gráfico de líneas
    fig = px.line(
        tendencias,
        title="Tendencia de Incidentes por Mes y Tipo",
        labels={"value": "N° Incidentes", "mes": "Mes", "variable": "Tipo"},
        template="plotly_white"
    )
    fig.update_traces(mode='lines+markers')
    st.plotly_chart(fig, use_container_width=True)
    
    # Gráfico de área apilada
    fig2 = px.area(
        tendencias,
        title="Acumulado de Incidentes (Área)",
        labels={"value": "N° Incidentes", "mes": "Mes"},
        template="plotly_dark"
    )
    st.plotly_chart(fig2, use_container_width=True)

def mostrar_analisis_riesgos(data):
    """Análisis detallado de riesgos"""
    
    st.subheader("⚠️ Análisis de Riesgos Laborales")
    
    if data['riesgos'].empty:
        st.info("No hay datos de riesgos")
        return
    
    # Validar columnas necesarias
    columnas_necesarias = ['area', 'tipo_peligro', 'nivel_riesgo', 'estado', 'codigo', 'peligro']
    columnas_faltantes = [col for col in columnas_necesarias if col not in data['riesgos'].columns]
    if columnas_faltantes:
        st.warning(f"Faltan columnas en los datos de riesgos: {', '.join(columnas_faltantes)}")
        return
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Heatmap de riesgos por área y tipo
        heatmap_data = data['riesgos'].groupby(['area', 'tipo_peligro'])['nivel_riesgo'].mean().unstack()
        
        fig = px.imshow(
            heatmap_data,
            title="Mapa de Calor: Nivel de Riesgo Promedio",
            labels=dict(x="Tipo de Peligro", y="Área", color="Nivel Riesgo"),
            color_continuous_scale="RdYlGn_r"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Distribución por severidad
        fig2 = px.pie(
            data['riesgos'],
            names='estado',
            title="Distribución por Estado",
            hole=0.5
        )
        st.plotly_chart(fig2, use_container_width=True)
    
    # Top 10 riesgos más altos
    st.markdown("#### 🎯 Top 10 Riesgos Críticos")
    top_riesgos = data['riesgos'].nlargest(10, 'nivel_riesgo')[['codigo', 'area', 'peligro', 'nivel_riesgo', 'estado']]
    
    # Colorear según nivel
    def color_riesgo(val):
        if val >= 15: return 'background-color: #ffcccc; color: #d40000'
        elif val >= 8: return 'background-color: #ffff99; color: #cc8800'
        else: return 'background-color: #ccffcc; color: #008800'
    
    styled = top_riesgos.style.applymap(color_riesgo, subset=['nivel_riesgo'])
    st.dataframe(styled, use_container_width=True)

def mostrar_analisis_incidentes(data):
    """Análisis de incidentes y accidentes"""
    
    st.subheader("🚨 Análisis de Incidentes")
    
    if data['incidentes'].empty:
        st.info("No hay datos de incidentes")
        return
    
    # Validar columnas necesarias
    columnas_necesarias = ['area', 'tipo', 'fecha_hora']
    columnas_faltantes = [col for col in columnas_necesarias if col not in data['incidentes'].columns]
    if columnas_faltantes:
        st.warning(f"Faltan columnas en los datos de incidentes: {', '.join(columnas_faltantes)}")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Distribución por área
        fig = px.bar(
            data['incidentes']['area'].value_counts(),
            title="Incidentes por Área",
            labels={'value': 'N° Incidentes', 'index': 'Área'},
            orientation='v'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Distribución por tipo
        fig2 = px.pie(
            data['incidentes'],
            names='tipo',
            title="Proporción por Tipo",
            color_discrete_sequence=px.colors.qualitative.Set2
        )
        st.plotly_chart(fig2, use_container_width=True)
    
    # Análisis temporal
    st.markdown("#### ⏱️ Análisis Temporal")
    data['incidentes']['hora'] = pd.to_datetime(data['incidentes']['fecha_hora']).dt.hour
    incidentes_hora = data['incidentes']['hora'].value_counts().sort_index()
    
    fig3 = px.bar(
        incidentes_hora,
        title="Incidentes por Hora del Día",
        labels={'value': 'N° Incidentes', 'index': 'Hora'},
        color=incidentes_hora.values,
        color_continuous_scale='reds'
    )
    st.plotly_chart(fig3, use_container_width=True)

def mostrar_analisis_inspecciones(data):
    """Análisis de inspecciones y hallazgos"""
    
    st.subheader("📋 Análisis de Inspecciones")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Estado de inspecciones
        if not data['inspecciones'].empty and 'estado' in data['inspecciones'].columns:
            fig = px.histogram(
                data['inspecciones'],
                x='estado',
                title="Estado de Inspecciones Programadas",
                color='estado',
                color_discrete_sequence=px.colors.qualitative.Set1
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Hallazgos por categoría
        if not data['hallazgos'].empty and 'categoria' in data['hallazgos'].columns:
            hallazgos_cat = data['hallazgos']['categoria'].value_counts().head(10)
            fig2 = px.bar(
                hallazgos_cat,
                title="Top 10 Categorías de Hallazgos",
                orientation='h'
            )
            st.plotly_chart(fig2, use_container_width=True)
    
    # Scatter: Hallazgos vs Tiempo de cierre
    if not data['hallazgos'].empty and not data['inspecciones'].empty:
        if 'inspeccion_id' in data['hallazgos'].columns and 'id' in data['inspecciones'].columns and 'fecha_realizada' in data['inspecciones'].columns:
            merged = data['hallazgos'].merge(
                data['inspecciones'][['id', 'fecha_realizada']],
                left_on='inspeccion_id',
                right_on='id'
            )
            if not merged.empty and 'fecha_cierre' in merged.columns and 'categoria' in merged.columns:
                merged['dias_cierre'] = (pd.to_datetime(merged['fecha_cierre']) - pd.to_datetime(merged['fecha_realizada'])).dt.days
                
                fig3 = px.scatter(
                    merged,
                    x='dias_cierre',
                    y='categoria',
                    title="Días para Cierre de Hallazgos",
                    labels={'dias_cierre': 'Días desde inspección', 'categoria': 'Categoría'}
                )
                st.plotly_chart(fig3, use_container_width=True)

def mostrar_reportes_legales(data, filtros):
    """Reportes oficiales para cumplimiento legal"""
    
    st.subheader("📊 Reportes Legales - Ley 29783")
    
    # Cálculo de indicadores legales
    st.markdown("#### 📋 Indicadores Obligatorios")
    
    # Simular datos de horas hombre (en realidad debería venir de sistema de asistencia)
    horas_hombre_mes = st.number_input(
        "Horas Hombre Trabajadas (último mes)",
        min_value=1,
        value=50000,
        help="Obtén este dato de tu sistema de marcación de asistencia"
    )
    
    # Calcular tasas
    if not data['incidentes'].empty and 'tipo' in data['incidentes'].columns:
        accidentes = len(data['incidentes'][data['incidentes']['tipo'] == 'accidente'])
    else:
        accidentes = 0
    
    dias_perdidos = accidentes * 15  # Simulación (en realidad debería ser campo calculado)
    
    tasa_frecuencia = calcular_tasa_frecuencia(accidentes, horas_hombre_mes)
    tasa_severidad = calcular_tasa_severidad(dias_perdidos, horas_hombre_mes)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "🚨 Tasa Frecuencia",
            f"{tasa_frecuencia:.2f}",
            help="N° accidentes × 1,000,000 / Horas Hombre"
        )
    
    with col2:
        st.metric(
            "💀 Tasa Severidad",
            f"{tasa_severidad:.2f}",
            help="Días perdidos × 1,000,000 / Horas Hombre"
        )
    
    with col3:
        indice_inc = (accidentes / (horas_hombre_mes / 2000)) if horas_hombre_mes > 0 else 0
        st.metric(
            "📊 Índice Incidencia",
            f"{indice_inc:.2f}",
            help="Accidentes / N° trabajadores (asumiendo 2000h/año)"
        )
    
    # Tabla de referencia legal
    st.info("""
    **Referencias Ley 29783:**
    - Tasas deben disminuir mes a mes
    - Meta industry: TF < 5.0, TS < 100
    - Reportar a gerencia mensualmente
    """)
    
    # Botón exportar reporte legal
    st.markdown("#### 📤 Exportar Reporte Mensual")
    
    if st.button("Generar Reporte Legal PDF/Excel"):
        reporte = generar_reporte_legal(data, {
            'tasa_frecuencia': tasa_frecuencia,
            'tasa_severidad': tasa_severidad,
            'indice_inc': indice_inc,
            'accidentes': accidentes,
            'dias_perdidos': dias_perdidos
        })
        
        st.download_button(
            "📥 Descargar Reporte Excel",
            data=reporte['excel'],
            file_name=reporte['nombre_excel'],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

def generar_reporte_legal(data, indicadores):
    """Generar reporte legal en formato Excel para SUNAFIL/gerencia"""
    
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Hoja 1: Resumen Ejecutivo
        resumen = pd.DataFrame({
            'Indicador': ['Tasa Frecuencia', 'Tasa Severidad', 'Índice Incidencia', 'N° Accidentes'],
            'Valor': [indicadores['tasa_frecuencia'], indicadores['tasa_severidad'], 
                     indicadores['indice_inc'], indicadores['accidentes']],
            'Meta': [5.0, 100.0, 1.0, 0],
            'Cumple': [indicadores['tasa_frecuencia'] < 5.0, 
                      indicadores['tasa_severidad'] < 100.0,
                      indicadores['indice_inc'] < 1.0,
                      indicadores['accidentes'] == 0]
        })
        resumen.to_excel(writer, sheet_name='Resumen_Legal', index=False)
        
        # Hoja 2: Detalle Incidentes
        if not data['incidentes'].empty:
            data['incidentes'].to_excel(writer, sheet_name='Incidentes', index=False)
        
        # Hoja 3: Riesgos Críticos
        if not data['riesgos'].empty:
            riesgos_criticos = data['riesgos'][data['riesgos']['nivel_riesgo'] >= 15]
            riesgos_criticos.to_excel(writer, sheet_name='Riesgos_Criticos', index=False)
    
    output.seek(0)
    
    return {
        'excel': output.read(),
        'nombre_excel': f"Reporte_SST_{datetime.now().strftime('%Y%m')}.xlsx"
    }

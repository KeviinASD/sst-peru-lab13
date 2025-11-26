import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from app.utils.supabase_client import get_supabase_client
from app.auth import requerir_rol
import io
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
import base64
import json
import requests
from app.utils.storage_helper import subir_archivo_storage

def mostrar(usuario):
    """Módulo de Reportes Legales y Estadísticos (Ley 29783 Art. 24)"""
    requerir_rol(['admin', 'sst', 'gerente', 'supervisor'])
    
    st.title("📊 Reportes SST - Cumplimiento Ley 29783")
    
    # Filtros globales del reporte
    with st.sidebar.expander("🔧 Filtros de Reporte", expanded=True):
        filtros = crear_filtros_reportes()
    
    # Tabs de reportes
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📈 Resumen Ejecutivo",
        "📋 Reporte Legal SUNAFIL",
        "⚠️ Matriz de Riesgos",
        "📉 Análisis Estadístico",
        "📤 Exportar & Enviar"
    ])
    
    data = cargar_datos_reporte(filtros)
    if not data:
        st.error("No se pudieron cargar los datos del reporte")
        return
    
    with tab1:
        mostrar_resumen_ejecutivo(data, filtros)
    
    with tab2:
        mostrar_reporte_legal_sunafil(data, filtros)
    
    with tab3:
        mostrar_matriz_riesgos_interactiva(data, filtros)
    
    with tab4:
        mostrar_analisis_estadistico(data, filtros)
    
    with tab5:
        mostrar_exportar_enviar(data, filtros)

def crear_filtros_reportes():
    """Crear filtros avanzados para personalizar reportes"""
    supabase = get_supabase_client()
    
    # Rango de fechas (últimos 3 meses por defecto)
    col1, col2 = st.columns(2)
    with col1:
        fecha_inicio = st.date_input(
            "Desde",
            value=datetime.now() - timedelta(days=90),
            key="rep_fecha_inicio"
        )
    with col2:
        fecha_fin = st.date_input(
            "Hasta",
            value=datetime.now(),
            key="rep_fecha_fin"
        )
    
    # Áreas
    areas_data = supabase.table('riesgos').select('area').execute().data
    areas = sorted(list(set([a['area'] for a in areas_data]))) if areas_data else []
    areas_seleccionadas = st.multiselect("Áreas", areas, default=areas, key="rep_areas")
    
    # Tipos de incidente
    tipos_incidente = st.multiselect(
        "Tipos de Incidente",
        options=["incidente", "accidente", "enfermedad_laboral"],
        default=["incidente", "accidente", "enfermedad_laboral"],
        key="rep_tipos_incidente"
    )
    
    # Nivel de riesgo mínimo
    nivel_min = st.slider("Nivel de Riesgo Mínimo", 1, 25, 1, key="rep_nivel_min")
    
    # Roles específicos
    mostrar_solo_fechas_limite = st.checkbox("Solo fechas límite próximas (30 días)", value=False)
    
    return {
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'areas': areas_seleccionadas,
        'tipos_incidente': tipos_incidente,
        'nivel_riesgo_min': nivel_min,
        'solo_fechas_limite': mostrar_solo_fechas_limite
    }

@st.cache_data(ttl=600)  # Cache 10 minutos
def cargar_datos_reporte(filtros):
    """Cargar todos los datos necesarios para reportes"""
    try:
        supabase = get_supabase_client()
        
        # Cargar incidentes con filtros
        query_incidentes = supabase.table('incidentes').select('*, usuarios(nombre_completo)').gte(
            'fecha_hora', filtros['fecha_inicio']
        ).lte('fecha_hora', filtros['fecha_fin'])
        
        if filtros['areas']:
            query_incidentes = query_incidentes.in_('area', filtros['areas'])
        if filtros['tipos_incidente']:
            query_incidentes = query_incidentes.in_('tipo', filtros['tipos_incidente'])
        
        incidentes = query_incidentes.execute().data
        
        # Cargar riesgos
        query_riesgos = supabase.table('riesgos').select('*, usuarios(nombre_completo)').gte(
            'nivel_riesgo', filtros['nivel_riesgo_min']
        )
        if filtros['areas']:
            query_riesgos = query_riesgos.in_('area', filtros['areas'])
        riesgos = query_riesgos.execute().data
        
        # Cargar EPP - especificar relación del trabajador para evitar ambigüedad
        epp_raw = supabase.table('epp_asignaciones').select(
            '*, '
            'usuarios!epp_asignaciones_trabajador_id_fkey(nombre_completo), '
            'epp_catalogo(*)'
        ).execute().data
        
        # Procesar datos de EPP para aplanar estructura (compatibilidad con código existente)
        epp = []
        usuarios_col = 'usuarios!epp_asignaciones_trabajador_id_fkey'
        for item in epp_raw:
            # Crear copia completa del item (incluye todos los campos de epp_asignaciones)
            item_processed = dict(item)  # Usar dict() para asegurar copia completa
            # Extraer nombre_completo de la relación de usuarios
            if usuarios_col in item_processed and isinstance(item_processed[usuarios_col], dict):
                item_processed['nombre_completo'] = item_processed[usuarios_col].get('nombre_completo', '')
            # Extraer nombre del catálogo de EPP
            if 'epp_catalogo' in item_processed and isinstance(item_processed['epp_catalogo'], dict):
                item_processed['epp_nombre'] = item_processed['epp_catalogo'].get('nombre', '')
            # Los campos directos de epp_asignaciones (fecha_vencimiento, fecha_entrega, etc.) 
            # ya están en item_processed por la copia
            epp.append(item_processed)
        
        # Cargar capacitaciones
        capacitaciones = supabase.table('capacitaciones').select('*, asistentes_capacitacion(*)').execute().data
        
        # Cargar inspecciones y hallazgos
        inspecciones = supabase.table('inspecciones').select('*, checklists(*)').execute().data
        hallazgos = supabase.table('hallazgos').select('*, usuarios(nombre_completo)').execute().data
        
        # Cargar documentos
        documentos = supabase.table('documentos').select('*, usuarios(nombre_completo)').execute().data
        
        return {
            'incidentes': pd.DataFrame(incidentes) if incidentes else pd.DataFrame(),
            'riesgos': pd.DataFrame(riesgos) if riesgos else pd.DataFrame(),
            'epp': pd.DataFrame(epp) if epp else pd.DataFrame(),
            'capacitaciones': pd.DataFrame(capacitaciones) if capacitaciones else pd.DataFrame(),
            'inspecciones': pd.DataFrame(inspecciones) if inspecciones else pd.DataFrame(),
            'hallazgos': pd.DataFrame(hallazgos) if hallazgos else pd.DataFrame(),
            'documentos': pd.DataFrame(documentos) if documentos else pd.DataFrame()
        }
    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
        return None

def mostrar_resumen_ejecutivo(data, filtros):
    """Generar resumen ejecutivo con KPIs"""
    st.header("📈 Resumen Ejecutivo de SST")
    
    # Métricas clave
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_incidentes = len(data['incidentes'])
        st.metric("🚨 Total Incidentes", total_incidentes, delta=f"vs periodo anterior")
    
    with col2:
        riesgos_criticos = len(data['riesgos'][data['riesgos']['nivel_riesgo'] >= 15])
        st.metric("⚠️ Riesgos Críticos", riesgos_criticos, delta_color="inverse")
    
    with col3:
        if not data['epp'].empty and 'fecha_vencimiento' in data['epp'].columns:
            epp_vencido = len(data['epp'][pd.to_datetime(data['epp']['fecha_vencimiento']) < datetime.now()])
        else:
            epp_vencido = 0
        st.metric("🛡️ EPP Vencidos", epp_vencido, delta_color="inverse")
    
    with col4:
        capac_realizada = len(data['capacitaciones'][data['capacitaciones']['estado'] == 'realizada'])
        capac_total = len(data['capacitaciones'])
        cumplimiento = (capac_realizada / capac_total * 100) if capac_total > 0 else 0
        st.metric("🎯 % Cumplimiento", f"{cumplimiento:.1f}%")
    
    # Gráfico de tendencia de incidentes
    st.subheader("Tendencia de Incidentes")
    if not data['incidentes'].empty:
        # Convertir a período mensual y luego a string para evitar problemas de serialización
        data['incidentes']['mes'] = pd.to_datetime(data['incidentes']['fecha_hora']).dt.to_period('M').astype(str)
        tendencia = data['incidentes'].groupby('mes').size().reset_index(name='cantidad')
        fig = px.line(tendencia, x='mes', y='cantidad', title="Incidentes por Mes", 
                     labels={'mes': 'Mes', 'cantidad': 'N° Incidentes'})
        fig.update_traces(mode='lines+markers')
        fig.update_xaxes(tickangle=45)
        st.plotly_chart(fig, use_container_width=True)

def mostrar_reporte_legal_sunafil(data, filtros):
    """Generar reporte para SUNAFIL según Ley 29783"""
    st.header("📋 Reporte Legal SUNAFIL - Ley 29783")
    
    # Cálculos de indicadores legales
    st.markdown("### 📊 Indicadores de Seguridad Obligatorios")
    
    # Simular horas hombre (debería venir de sistema de asistencia)
    col1, col2 = st.columns(2)
    with col1:
        horas_hombre = st.number_input("Horas Hombre Trabajadas (periodo)", 
                                      min_value=1, value=50000)
    with col2:
        num_trabajadores = st.number_input("N° Promedio de Trabajadores", 
                                          min_value=1, value=200)
    
    accidentes = len(data['incidentes'][data['incidentes']['tipo'] == 'accidente'])
    incidentes = len(data['incidentes'][data['incidentes']['tipo'] == 'incidente'])
    enfermedades = len(data['incidentes'][data['incidentes']['tipo'] == 'enfermedad_laboral'])
    
    # Cálculo de tasas (Art. 37)
    tasa_frecuencia = (accidentes * 1_000_000) / horas_hombre if horas_hombre > 0 else 0
    dias_perdidos = accidentes * 15  # Simulación
    tasa_severidad = (dias_perdidos * 1_000_000) / horas_hombre if horas_hombre > 0 else 0
    indice_incidencia = (accidentes / num_trabajadores) * 100 if num_trabajadores > 0 else 0
    
    # Tabla de indicadores
    st.markdown("#### 📈 Tabla de Indicadores Legales")
    indicadores = pd.DataFrame({
        'Indicador': ['Tasa de Frecuencia', 'Tasa de Severidad', 'Índice de Incidencia', 
                     'N° Accidentes', 'N° Incidentes', 'N° Enfermedades Laborales'],
        'Valor': [f"{tasa_frecuencia:.2f}", f"{tasa_severidad:.2f}", f"{indice_incidencia:.2f}",
                  accidentes, incidentes, enfermedades],
        'Unidad': ['accidents/1Mh-h', 'días/1Mh-h', '%', 'eventos', 'eventos', 'eventos'],
        'Meta Legal': ['< 5.0', '< 100', '< 1.0', '0', 'No especificado', 'No especificado'],
        'Cumple': ['✅' if tasa_frecuencia < 5 else '❌', 
                   '✅' if tasa_severidad < 100 else '❌',
                   '✅' if indice_incidencia < 1 else '❌',
                   '✅' if accidentes == 0 else '❌', '-', '-']
    })
    st.dataframe(indicadores, use_container_width=True)
    
    # Requisitos legales cumplidos
    st.markdown("#### ✅ Cumplimiento Normativo")
    requisitos = {
        'Art. 24': 'Registros documentados' if len(data['documentos']) > 0 else '⚠️ Pendiente',
        'Art. 26-28': 'Evaluación de riesgos' if len(data['riesgos']) > 0 else '⚠️ Pendiente',
        'Art. 29': 'Gestión EPP' if len(data['epp']) > 0 else '⚠️ Pendiente',
        'Art. 31': 'Capacitaciones registradas' if len(data['capacitaciones']) > 0 else '⚠️ Pendiente',
        'Art. 33-34': 'Sistema de incidentes' if len(data['incidentes']) > 0 else '⚠️ Pendiente'
    }
    
    for articulo, estado in requisitos.items():
        st.write(f"**{articulo}**: {estado}")

def mostrar_matriz_riesgos_interactiva(data, filtros):
    """Mostrar matriz de riesgos para análisis"""
    st.header("⚠️ Matriz de Riesgos Interactiva")
    
    if data['riesgos'].empty:
        st.info("No hay datos de riesgos")
        return
    
    # Filtros adicionales
    col1, col2, col3 = st.columns(3)
    with col1:
        estado_riesgo = st.multiselect("Estado", 
                                      options=['pendiente', 'en_mitigacion', 'controlado'],
                                      default=['pendiente', 'en_mitigacion'])
    with col2:
        area_seleccionada = st.multiselect("Área Específica", 
                                          options=sorted(data['riesgos']['area'].unique()),
                                          default=sorted(data['riesgos']['area'].unique()))
    with col3:
        tipo_peligro = st.multiselect("Tipo de Peligro",
                                     options=sorted(data['riesgos']['tipo_peligro'].unique()),
                                     default=sorted(data['riesgos']['tipo_peligro'].unique()))
    
    # Filtrar datos
    riesgos_filtrados = data['riesgos'][
        (data['riesgos']['estado'].isin(estado_riesgo)) &
        (data['riesgos']['area'].isin(area_seleccionada)) &
        (data['riesgos']['tipo_peligro'].isin(tipo_peligro))
    ]
    
    # Matriz de riesgo (probabilidad vs severidad)
    st.subheader("📊 Mapa de Calor de Riesgo")
    
    # Crear matriz 5x5 asegurando que tenga todas las combinaciones
    matriz = riesgos_filtrados.groupby(['probabilidad', 'severidad']).size().unstack(fill_value=0)
    
    # Asegurar que la matriz tenga exactamente 5x5 (probabilidad 1-5, severidad 1-5)
    # Reindexar para incluir todos los valores posibles
    probabilidades = [1, 2, 3, 4, 5]
    severidades = [1, 2, 3, 4, 5]
    
    # Reindexar filas (probabilidad) y columnas (severidad) para asegurar 5x5
    matriz = matriz.reindex(index=probabilidades, columns=severidades, fill_value=0)
    
    # Etiquetas para los ejes
    labels_x = ['Baja (1)', 'Media (2)', 'Moderada (3)', 'Alta (4)', 'Muy Alta (5)']
    labels_y = ['Casi Nula (1)', 'Remota (2)', 'Posible (3)', 'Probable (4)', 'Muy Probable (5)']
    
    # Crear el gráfico usando la matriz directamente (no .values) para que Plotly maneje los índices
    fig = px.imshow(
        matriz,
        x=labels_x,
        y=labels_y,
        title="Matriz de Riesgo: Probabilidad vs Severidad",
        color_continuous_scale="Reds",
        aspect="auto"
    )
    fig.update_xaxes(title="Severidad")
    fig.update_yaxes(title="Probabilidad")
    st.plotly_chart(fig, use_container_width=True)
    
    # Tabla de riesgos críticos
    st.subheader("🎯 Riesgos Críticos (Nivel ≥ 15)")
    criticos = riesgos_filtrados[riesgos_filtrados['nivel_riesgo'] >= 15]
    if not criticos.empty:
        st.dataframe(criticos[['codigo', 'area', 'puesto_trabajo', 'peligro', 'nivel_riesgo', 'estado']], 
                    use_container_width=True)
    else:
        st.success("✅ No hay riesgos críticos en este filtro")

def mostrar_analisis_estadistico(data, filtros):
    """Análisis estadístico avanzado"""
    st.header("📉 Análisis Estadístico Avanzado")
    
    # Distribución de incidentes
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Distribución por Área")
        if not data['incidentes'].empty:
            fig = px.bar(data['incidentes']['area'].value_counts(), 
                        title="Incidentes por Área",
                        orientation='h')
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("Distribución por Tipo de Peligro")
        if not data['riesgos'].empty:
            fig = px.pie(data['riesgos'], names='tipo_peligro', 
                        title="Tipos de Peligros Identificados")
            st.plotly_chart(fig, use_container_width=True)
    
    # Análisis de hallazgos
    st.subheader("📋 Análisis de Hallazgos de Inspección")
    if not data['hallazgos'].empty:
        # Hallazgos por estado
        fig = px.sunburst(data['hallazgos'], path=['categoria', 'estado'], 
                         title="Hallazgos por Categoría y Estado",
                         height=500)
        st.plotly_chart(fig, use_container_width=True)

def mostrar_exportar_enviar(data, filtros):
    """Opciones de exportación y envío automático"""
    st.header("📤 Exportar y Enviar Reportes")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### 📥 Exportación")
        formato_export = st.selectbox("Formato", ["Excel", "PDF"], key="formato_export")
        tipo_reporte = st.selectbox("Tipo de Reporte", 
                                   ["Completo", "Legal SUNAFIL", "Riesgos", "Incidentes"],
                                   key="tipo_reporte")
        
        if st.button(f"📥 Generar {formato_export}", type="primary"):
            try:
                if formato_export == "Excel":
                    archivo = generar_reporte_excel(data, tipo_reporte, filtros)
                    st.download_button(
                        label="⬇️ Descargar Excel",
                        data=archivo['data'],
                        file_name=archivo['filename'],
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:  # PDF
                    archivo = generar_reporte_pdf(data, tipo_reporte, filtros)
                    st.download_button(
                        label="⬇️ Descargar PDF",
                        data=archivo['data'],
                        file_name=archivo['filename'],
                        mime="application/pdf"
                    )
            except Exception as e:
                st.error(f"Error generando reporte: {e}")
    
    with col2:
        st.markdown("### 📧 Enviar Automáticamente")
        st.info("Enviar reporte vía n8n a emails configurados")
        
        email_destino = st.text_input("Email destino", "gerencia@empresa.com")
        frecuencia_envio = st.selectbox("Frecuencia", ["Diario", "Semanal", "Mensual"])
        
        if st.button("📨 Configurar Envio Automático", type="secondary"):
            configurar_webhook_n8n(data, filtros, email_destino, frecuencia_envio)
            st.success("✅ Webhook configurado. El reporte se enviará automáticamente.")

def generar_reporte_excel(data, tipo, filtros):
    """Generar reporte Excel completo con múltiples hojas"""
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Hoja 1: Resumen Ejecutivo
        resumen = pd.DataFrame({
            'Métrica': ['Total Incidentes', 'Riesgos Pendientes', 'EPP por Vencer', 
                       'Hallazgos Abiertos', 'Capacitaciones Completadas'],
            'Valor': [
                len(data['incidentes']),
                len(data['riesgos'][data['riesgos']['estado'] == 'pendiente']),
                len(data['epp'][pd.to_datetime(data['epp']['fecha_vencimiento']) <= datetime.now() + timedelta(days=30)]) if not data['epp'].empty and 'fecha_vencimiento' in data['epp'].columns else 0,
                len(data['hallazgos'][data['hallazgos']['estado'] == 'abierto']),
                len(data['capacitaciones'][data['capacitaciones']['estado'] == 'realizada'])
            ]
        })
        resumen.to_excel(writer, sheet_name='Resumen_Ejecutivo', index=False)
        
        # Hoja 2: Incidentes (obligatorio Art. 34)
        if not data['incidentes'].empty:
            incidentes_export = data['incidentes'][['codigo', 'tipo', 'fecha_hora', 'area', 'descripcion', 
                                                   'consecuencias', 'estado', 'fecha_cierre']].copy()
            incidentes_export.to_excel(writer, sheet_name='Incidentes', index=False)
        
        # Hoja 3: Riesgos (Art. 26-28)
        if not data['riesgos'].empty:
            riesgos_export = data['riesgos'][['codigo', 'area', 'puesto_trabajo', 'peligro', 
                                            'tipo_peligro', 'probabilidad', 'severidad', 
                                            'nivel_riesgo', 'estado']].copy()
            riesgos_export.to_excel(writer, sheet_name='Riesgos', index=False)
        
        # Hoja 4: Hallazgos
        if not data['hallazgos'].empty:
            hallazgos_export = data['hallazgos'][['descripcion', 'categoria', 'estado', 'fecha_limite', 
                                                'fecha_cierre']].copy()
            hallazgos_export.to_excel(writer, sheet_name='Hallazgos', index=False)
        
        # Hoja 5: EPP
        if not data['epp'].empty:
            # Verificar que las columnas existan antes de exportar
            epp_cols = ['nombre_completo', 'epp_nombre', 'fecha_entrega', 'fecha_vencimiento']
            epp_cols_disponibles = [col for col in epp_cols if col in data['epp'].columns]
            epp_export = data['epp'][epp_cols_disponibles].copy() if epp_cols_disponibles else pd.DataFrame()
            epp_export.to_excel(writer, sheet_name='EPP', index=False)
        
        # Hoja 6: Capacitaciones (Art. 31)
        if not data['capacitaciones'].empty:
            capac_export = data['capacitaciones'][['codigo', 'tema', 'area_destino', 'fecha_programada',
                                                  'estado', 'duracion_horas']].copy()
            capac_export.to_excel(writer, sheet_name='Capacitaciones', index=False)
    
    output.seek(0)
    return {
        'data': output.read(),
        'filename': f"Reporte_SST_{tipo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    }

def generar_reporte_pdf(data, tipo, filtros):
    """Generar reporte PDF profesional con ReportLab"""
    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4)
    
    # Elementos del PDF
    elements = []
    styles = getSampleStyleSheet()
    
    # Título
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['title'],
        fontSize=24,
        alignment=1,  # Center
        color=colors.HexColor('#1e3a8a'),
        spaceAfter=30
    )
    
    elements.append(Paragraph("REPORTE DE SEGURIDAD Y SALUD EN EL TRABAJO", title_style))
    elements.append(Paragraph(f"Generado el: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", styles['normal']))
    elements.append(Paragraph(f"Ley 29783 - Período: {filtros['fecha_inicio']} al {filtros['fecha_fin']}", styles['normal']))
    elements.append(Spacer(1, 30))
    
    # KP
    kpi_data = [
        ['Métrica', 'Valor', 'Interpretación'],
        ['Total Incidentes', str(len(data['incidentes'])), 'Ver detalle en tabla'],
        ['Riesgos Críticos', str(len(data['riesgos'][data['riesgos']['nivel_riesgo'] >= 15])), 'Requieren atención inmediata'],
        ['EPP por Vencer', str(len(data['epp'][pd.to_datetime(data['epp']['fecha_vencimiento']) <= datetime.now() + timedelta(days=30)]) if not data['epp'].empty and 'fecha_vencimiento' in data['epp'].columns else 0), 'Programar renovación']
    ]
    
    kpi_table = Table(kpi_data, colWidths=[200, 100, 200])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e3a8a')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 12),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#f8f9fa')),
        ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#dee2e6'))
    ]))
    
    elements.append(kpi_table)
    elements.append(Spacer(1, 20))
    
    # Tabla de incidentes
    if not data['incidentes'].empty:
        elements.append(Paragraph("DETALLE DE INCIDENTES", styles['heading2']))
        incidentes_pdf = data['incidentes'][['codigo', 'tipo', 'area', 'descripcion']].head(10)
        incidentes_data = [incidentes_pdf.columns.tolist()] + incidentes_pdf.values.tolist()
        incidentes_table = Table(incidentes_data, colWidths=[80, 80, 100, 250])
        incidentes_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#6c757d')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#dee2e6'))
        ]))
        elements.append(incidentes_table)
    
    # Build PDF
    doc.build(elements)
    output.seek(0)
    
    return {
        'data': output.read(),
        'filename': f"Reporte_SST_Legal_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    }

def configurar_webhook_n8n(data, filtros, email, frecuencia):
    """Configurar webhook para envío automático"""
    supabase = get_supabase_client()
    
    try:
        # Guardar configuración en Supabase (tabla configuraciones_reportes)
        config = {
            'email_destino': email,
            'frecuencia': frecuencia,
            'filtros': json.dumps(filtros),
            'activo': True,
            'ultimo_envio': None
        }
        
        supabase.table('configuraciones_reportes').upsert(config).execute()
        
        # Disparar webhook de n8n para validación
        requests.post(
            st.secrets["N8N_WEBHOOK_URL"] + "/configurar-reporte-automatico",
            json={
                'email': email,
                'frecuencia': frecuencia,
                'filtros': filtros,
                'config_id': config.get('id')
            }
        )
    except Exception as e:
        st.error(f"Error configurando webhook: {e}")



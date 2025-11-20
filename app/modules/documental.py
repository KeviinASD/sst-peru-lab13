import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from app.utils.supabase_client import get_supabase_client
from app.utils.storage_helper import subir_archivo_storage
from app.auth import requerir_rol
import requests

def mostrar(usuario):
    """Módulo de Gestión Documental (Ley 29783 Art. 24)"""
    requerir_rol(['admin', 'sst', 'supervisor', 'gerente'])
    
    st.title("📚 Gestión Documental SST")
    
    # Tabs principales
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📂 Repositorio Documental",
        "➕ Subir/Editar Documento",
        "✅ Revisión y Aprobación",
        "🔔 Alertas y Vencimientos",
        "📊 Reportes de Auditoría"
    ])
    
    with tab1:
        repositorio_documental(usuario)
    
    with tab2:
        subir_editar_documento(usuario)
    
    with tab3:
        revision_aprobacion(usuario)
    
    with tab4:
        alertas_vencimientos(usuario)
    
    with tab5:
        reportes_auditoria(usuario)

def repositorio_documental(usuario):
    """Repositorio centralizado de documentos"""
    
    st.subheader("📂 Repositorio Documental")
    
    supabase = get_supabase_client()
    
    # Filtros avanzados
    st.markdown("### 🔍 Búsqueda y Filtros")
    
    col_filtro1, col_filtro2, col_filtro3 = st.columns(3)
    
    with col_filtro1:
        # Buscar por texto
        buscar = st.text_input(
            "🔎 Buscar por título o contenido",
            placeholder="Ej: procedimiento seguridad"
        )
    
    with col_filtro2:
        # Filtrar por tipo
        tipos = ["todos", "manual", "procedimiento", "politica", "plan_emergencia", "informe_auditoria"]
        tipo_filtro = st.selectbox(
            "Tipo de Documento",
            options=tipos,
            format_func=lambda x: x.replace('_', ' ').title()
        )
    
    with col_filtro3:
        # Filtrar por estado
        estado_filtro = st.selectbox(
            "Estado de Aprobación",
            options=["todos", "borrador", "revision", "aprobado", "obsoleto"]
        )
    
    # Filtrar por área
    col_filtro4, col_filtro5 = st.columns(2)
    
    with col_filtro4:
        areas = supabase.table('usuarios').select('area').execute().data
        areas_unicas = sorted(list(set([a['area'] for a in areas if a['area']])))
        area_filtro = st.multiselect(
            "Área Aplicación",
            options=areas_unicas,
            default=areas_unicas
        )
    
    with col_filtro5:
        # Filtrar por vigencia
        vigencia_filtro = st.selectbox(
            "Estado de Vigencia",
            options=["todos", "vigente", "por_vencer", "vencido"],
            help="Filtrar por fecha de vigencia"
        )
    
    # Consultar documentos
    query = supabase.table('documentos').select(
        '*, historial_versiones(*), usuarios(nombre_completo)'
    )
    
    if tipo_filtro != "todos":
        query = query.eq('tipo', tipo_filtro)
    
    if estado_filtro != "todos":
        query = query.eq('estado', estado_filtro)
    
    if area_filtro:
        query = query.in_('area', area_filtro)
    
    if buscar:
        query = query.ilike('titulo', f'%{buscar}%').or_().ilike('keywords', f'%{buscar}%')
    
    documentos = query.execute().data
    
    if not documentos:
        st.info("ℹ️ No se encontraron documentos con los filtros seleccionados")
        return
    
    # Procesar documentos para mostrar
    df_docs = pd.DataFrame(documentos)
    df_docs['fecha_vigencia'] = pd.to_datetime(df_docs['fecha_vigencia']).dt.date
    
    # Aplicar filtro de vigencia
    if vigencia_filtro != "todos":
        hoy = datetime.now().date()
        if vigencia_filtro == "vigente":
            df_docs = df_docs[df_docs['fecha_vigencia'] > hoy]
        elif vigencia_filtro == "por_vencer":
            fecha_limite = hoy + timedelta(days=30)
            df_docs = df_docs[(df_docs['fecha_vigencia'] <= fecha_limite) & (df_docs['fecha_vigencia'] > hoy)]
        elif vigencia_filtro == "vencido":
            df_docs = df_docs[df_docs['fecha_vigencia'] <= hoy]
    
    # Mostrar documentos en formato de cards
    st.markdown(f"### 📄 Documentos Encontrados: {len(df_docs)}")
    
    for _, doc in df_docs.iterrows():
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
            
            with col1:
                st.write(f"**📄 {doc['titulo']}**")
                st.caption(f"Versión: {doc['version']} | Código: {doc['codigo']}")
                st.write(f"Tipo: {doc['tipo'].replace('_', ' ').title()} | Área: {doc['area']}")
                
                # Mostrar estado de vigencia
                hoy = datetime.now().date()
                if doc['fecha_vigencia'] <= hoy:
                    st.error("🔴 VENCIDO")
                elif doc['fecha_vigencia'] <= hoy + timedelta(days=30):
                    st.warning("🟡 POR VENCER")
                else:
                    st.success("🟢 VIGENTE")
            
            with col2:
                # Mostrar etiquetas
                if doc.get('keywords'):
                    st.caption(f"🎯 {doc['keywords']}")
                
                # Estado de aprobación
                estado_color = {
                    'borrador': '📝',
                    'revision': '🔍',
                    'aprobado': '✅',
                    'obsoleto': '⚠️'
                }
                st.write(f"{estado_color.get(doc['estado'], '')} {doc['estado'].title()}")
            
            with col3:
                # Mostrar responsable
                st.write(f"👤 {doc['usuarios']['nombre_completo']}")
                st.caption(f"Vigente hasta: {doc['fecha_vigencia']}")
            
            with col4:
                # Acciones
                if st.button("📥 Descargar", key=f"down_{doc['id']}"):
                    st.link_button("Abrir Documento", doc['archivo_url'])
                
                if usuario['rol'] in ['admin', 'sst']:
                    if st.button("✏️ Editar", key=f"edit_doc_{doc['id']}"):
                        st.session_state['editar_documento_id'] = doc['id']
                        st.rerun()
            
            st.divider()

def subir_editar_documento(usuario):
    """Subir nuevo documento o editar existente"""
    
    st.subheader("➕ Subir o Editar Documento")
    
    supabase = get_supabase_client()
    
    # Verificar si hay documento en edición
    if 'editar_documento_id' in st.session_state:
        doc_id = st.session_state['editar_documento_id']
        documento_editar = supabase.table('documentos').select('*').eq('id', doc_id).execute().data
        
        if documento_editar:
            documento_editar = documento_editar[0]
            st.info(f"✏️ Editando documento: {documento_editar['titulo']}")
        else:
            del st.session_state['editar_documento_id']
            documento_editar = None
    else:
        documento_editar = None
    
    with st.form("form_documento", clear_on_submit=False):
        col1, col2 = st.columns(2)
        
        with col1:
            # Código automático o manual
            if documento_editar:
                codigo = st.text_input(
                    "Código del Documento",
                    value=documento_editar['codigo'],
                    disabled=True
                )
            else:
                codigo = st.text_input(
                    "Código del Documento",
                    value=f"DOC-{datetime.now().strftime('%Y%m%d')}-",
                    help="Formato: DOC-YYYYMMDD-###"
                )
            
            titulo = st.text_input(
                "Título del Documento",
                value=documento_editar['titulo'] if documento_editar else "",
                placeholder="Ej: Procedimiento de Uso de Extintores"
            )
            
            tipo = st.selectbox(
                "Tipo de Documento",
                options=["manual", "procedimiento", "politica", "plan_emergencia", "informe_auditoria"],
                format_func=lambda x: x.replace('_', ' ').title(),
                index=[i for i, t in enumerate(["manual", "procedimiento", "politica", "plan_emergencia", "informe_auditoria"]) if documento_editar and documento_editar['tipo'] == t][0] if documento_editar else 0
            )
        
        with col2:
            version = st.text_input(
                "Versión",
                value=documento_editar['version'] if documento_editar else "1.0",
                help="Formato: Mayor.Minor (ej: 2.1)"
            )
            
            fecha_vigencia = st.date_input(
                "Fecha de Vigencia",
                value=pd.to_datetime(documento_editar['fecha_vigencia']).date() if documento_editar else datetime.now().date() + timedelta(days=365),
                help="Fecha límite de validez del documento"
            )
            
            # Obtener áreas disponibles
            areas = supabase.table('usuarios').select('area').execute().data
            areas_unicas = sorted(list(set([a['area'] for a in areas if a['area']])))
            area = st.selectbox(
                "Área de Aplicación",
                options=areas_unicas,
                index=areas_unicas.index(documento_editar['area']) if documento_editar and documento_editar['area'] in areas_unicas else 0
            )
        
        # Responsable y palabras clave
        col3, col4 = st.columns(2)
        
        with col3:
            responsable_id = st.selectbox(
                "Responsable del Documento",
                options=[usuario['id']],
                format_func=lambda x: usuario['nombre_completo'],
                disabled=True
            )
        
        with col4:
            keywords = st.text_input(
                "Palabras Clave (separadas por coma)",
                value=documento_editar.get('keywords', '') if documento_editar else "",
                placeholder="Ej: seguridad, extintores, emergencia, capacitación"
            )
        
        # Archivo del documento
        archivo = st.file_uploader(
            "📄 Archivo del Documento (PDF, DOCX, PPTX)",
            type=['pdf', 'docx', 'pptx'],
            help="Máximo 50MB"
        )
        
        # Si es edición, mostrar archivo actual
        if documento_editar and documento_editar.get('archivo_url'):
            st.info(f"📥 Archivo actual: {documento_editar['archivo_url']}")
        
        # Observaciones
        observaciones = st.text_area(
            "Observaciones/Comentarios",
            value=documento_editar.get('observaciones', '') if documento_editar else "",
            placeholder="Notas sobre el documento, cambios realizados, etc."
        )
        
        # Botón de envío
        submitted = st.form_submit_button(
            "💾 Guardar Documento",
            type="primary"
        )
        
        if submitted:
            if not titulo or not codigo:
                st.error("❌ Título y código son obligatorios")
                return
            
            # Subir archivo si es nuevo
            archivo_url = None
            if archivo:
                archivo_url = subir_archivo_storage(
                    archivo,
                    bucket='sst-documentos',
                    carpeta=f'documentos/{tipo}/'
                )
            elif documento_editar:
                archivo_url = documento_editar['archivo_url']
            
            if not archivo_url:
                st.error("❌ Debes subir un archivo")
                return
            
            # Preparar data
            data = {
                'codigo': codigo,
                'titulo': titulo,
                'tipo': tipo,
                'version': version,
                'fecha_vigencia': fecha_vigencia.isoformat(),
                'area': area,
                'responsable_id': responsable_id,
                'keywords': keywords,
                'observaciones': observaciones,
                'archivo_url': archivo_url,
                'estado': 'borrador' if not documento_editar else documento_editar['estado'],
                'aprobado': False
            }
            
            # Guardar o actualizar
            if documento_editar:
                # Actualizar documento existente
                supabase.table('documentos').update(data).eq('id', doc_id).execute()
                
                # Guardar en historial de versiones
                guardar_version_historial(doc_id, documento_editar)
                
                del st.session_state['editar_documento_id']
                st.success(f"✅ Documento actualizado: {titulo}")
            else:
                # Insertar nuevo documento
                supabase.table('documentos').insert(data).execute()
                st.success(f"✅ Documento registrado: {titulo}")
                
                # Notificar vía n8n
                notificar_documento_nuevo(data)
            
            st.rerun()

def guardar_version_historial(documento_id, version_anterior):
    """Guardar versión anterior en historial"""
    supabase = get_supabase_client()
    
    try:
        supabase.table('historial_versiones').insert({
            'documento_id': documento_id,
            'version': version_anterior['version'],
            'archivo_url': version_anterior['archivo_url'],
            'fecha_reemplazo': datetime.now().isoformat()
        }).execute()
    except Exception as e:
        st.warning(f"⚠️ No se pudo guardar historial: {e}")

def notificar_documento_nuevo(data):
    """Notificar a n8n sobre nuevo documento"""
    try:
        requests.post(
            st.secrets["N8N_WEBHOOK_URL"] + "/documento-nuevo",
            json=data,
            timeout=5
        )
    except:
        pass

def revision_aprobacion(usuario):
    """Workflow de revisión y aprobación de documentos"""
    
    st.subheader("✅ Revisión y Aprobación de Documentos")
    
    supabase = get_supabase_client()
    
    # Cargar documentos en revisión o pendientes de aprobación
    documentos = supabase.table('documentos').select(
        '*, usuarios(nombre_completo)'
    ).in_('estado', ['revision', 'borrador']).execute().data
    
    if not documentos:
        st.success("✅ No hay documentos pendientes de revisión/aprobación")
        return
    
    # Seleccionar documento
    doc_seleccionado = st.selectbox(
        "Seleccionar Documento para Revisar/Aprobar",
        options=documentos,
        format_func=lambda x: f"{x['codigo']} - {x['titulo']} ({x['estado'].title()})"
    )
    
    if not doc_seleccionado:
        return
    
    # Mostrar detalles del documento
    with st.expander("📋 Detalles del Documento", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            st.write(f"**Código:** {doc_seleccionado['codigo']}")
            st.write(f"**Título:** {doc_seleccionado['titulo']}")
            st.write(f"**Versión:** {doc_seleccionado['version']}")
            st.write(f"**Tipo:** {doc_seleccionado['tipo'].replace('_', ' ').title()}")
        
        with col2:
            st.write(f"**Área:** {doc_seleccionado['area']}")
            st.write(f"**Responsable:** {doc_seleccionado['usuarios']['nombre_completo']}")
            st.write(f"**Vigencia:** {doc_seleccionado['fecha_vigencia']}")
            st.write(f"**Estado Actual:** {doc_seleccionado['estado'].title()}")
        
        # Mostrar archivo
        st.link_button("📥 Descargar y Revisar", doc_seleccionado['archivo_url'])
        
        if doc_seleccionado.get('observaciones'):
            st.markdown(f"**Observaciones:** {doc_seleccionado['observaciones']}")
    
    # Formulario de revisión/aprobación
    st.markdown("### ✍️ Acción de Revisión")
    
    with st.form("form_revision", clear_on_submit=True):
        col_accion1, col_accion2 = st.columns(2)
        
        with col_accion1:
            accion = st.selectbox(
                "Acción",
                options=[
                    ("Solicitar Revisión", "revision"),
                    ("Aprobar Documento", "aprobado"),
                    ("Rechazar/ solicitar cambios", "borrador")
                ],
                format_func=lambda x: x[0]
            )[1]
        
        with col_accion2:
            # Notificación al responsable
            notificar_responsable = st.checkbox(
                "Notificar al responsable",
                value=True,
                help="Enviará email con los comentarios"
            )
        
        comentarios_revision = st.text_area(
            "Comentarios de Revisión/Aprobación",
            placeholder="Detalles de los cambios necesarios o motivo de aprobación"
        )
        
        # Subir evidencia de revisión (firma, sello, etc.)
        evidencia_revision = st.file_uploader(
            "Evidencia de Revisión (firma digital, sello)",
            type=['pdf', 'jpg', 'png'],
            help="Documento de aprobación firmado"
        )
        
        submitted = st.form_submit_button(
            "💾 Ejecutar Acción",
            type="primary"
        )
        
        if submitted:
            # Actualizar estado
            data_update = {
                'estado': accion,
                'aprobado': accion == 'aprobado'
            }
            
            # Subir evidencia si existe
            if evidencia_revision:
                url_evidencia = subir_archivo_storage(
                    evidencia_revision,
                    bucket='sst-documentos',
                    carpeta=f'revisiones/{doc_seleccionado["id"]}/'
                )
                data_update['revision_evidencia_url'] = url_evidencia
            
            supabase.table('documentos').update(data_update).eq('id', doc_seleccionado['id']).execute()
            
            # Guardar comentarios en tabla de auditoría
            supabase.table('revisiones_documentos').insert({
                'documento_id': doc_seleccionado['id'],
                'revisado_por': usuario['id'],
                'accion': accion,
                'comentarios': comentarios_revision,
                'fecha_revision': datetime.now().isoformat()
            }).execute()
            
            # Notificar
            if notificar_responsable:
                notificar_revision_documento({
                    'documento_id': doc_seleccionado['id'],
                    'codigo': doc_seleccionado['codigo'],
                    'titulo': doc_seleccionado['titulo'],
                    'accion': accion,
                    'comentarios': comentarios_revision,
                    'responsable_id': doc_seleccionado['responsable_id']
                })
            
            st.success(f"✅ Documento {accion} exitosamente")
            st.rerun()

def notificar_revision_documento(data):
    """Notificar a n8n sobre revisión de documento"""
    try:
        requests.post(
            st.secrets["N8N_WEBHOOK_URL"] + "/documento-revisado",
            json=data
        )
    except:
        pass

def alertas_vencimientos(usuario):
    """Alertas de documentos por vencer o vencidos"""
    
    st.subheader("🔔 Alertas de Vencimiento y Revisión")
    
    supabase = get_supabase_client()
    
    # KPIs de documentos
    st.markdown("### 📊 Estado de Documentos")
    
    col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
    
    with col_kpi1:
        total_docs = supabase.table('documentos').select('*', count='exact').execute()
        st.metric("📄 Total Documentos", total_docs.count)
    
    with col_kpi2:
        vigentes = supabase.table('documentos').select('*', count='exact').gt('fecha_vigencia', datetime.now().date()).execute()
        st.metric("✅ Vigentes", vigentes.count)
    
    with col_kpi3:
        por_vencer = supabase.table('documentos').select('*', count='exact').lte('fecha_vigencia', datetime.now().date() + timedelta(days=30)).gt('fecha_vigencia', datetime.now().date()).execute()
        st.metric("⚠️ Por Vencer", por_vencer.count)
    
    with col_kpi4:
        vencidos = supabase.table('documentos').select('*', count='exact').lte('fecha_vigencia', datetime.now().date()).execute()
        st.metric("🔴 Vencidos", vencidos.count)
    
    # Tabla de documentos críticos
    st.markdown("### 🚨 Documentos Críticos (Vencidos o Próximos)")
    
    documentos_criticos = supabase.table('documentos').select(
        '*, usuarios(nombre_completo)'
    ).lte('fecha_vigencia', datetime.now().date() + timedelta(days=30)).execute().data
    
    if documentos_criticos:
        df_criticos = pd.DataFrame(documentos_criticos)
        df_criticos['dias_restantes'] = (pd.to_datetime(df_criticos['fecha_vigencia']).dt.date - datetime.now().date()).apply(lambda x: x.days)
        
        # Colorear por urgencia
        def colorear_urgencia(row):
            if row['dias_restantes'] < 0:
                return ['background-color: #ffcccc'] * len(row)
            elif row['dias_restantes'] <= 7:
                return ['background-color: #ff9999'] * len(row)
            elif row['dias_restantes'] <= 30:
                return ['background-color: #ffff99'] * len(row)
            else:
                return [''] * len(row)
        
        df_display = df_criticos[['codigo', 'titulo', 'tipo', 'area', 'fecha_vigencia', 'dias_restantes', 'estado']]
        
        styled = df_display.style.apply(colorear_urgencia, axis=1)
        st.dataframe(styled, use_container_width=True)
    else:
        st.success("✅ No hay documentos críticos")
    
    # Programar revisión
    st.markdown("### 📅 Programar Revisión Manual")
    
    doc_a_revisar = st.selectbox(
        "Seleccionar documento para programar revisión",
        options=sorted([d['id'] for d in documentos_criticos], key=lambda x: [d['dias_restantes'] for d in documentos_criticos if d['id'] == x][0] if documentos_criticos else 0),
        format_func=lambda x: f"{[d['codigo'] for d in documentos_criticos if d['id'] == x][0]} - {[d['titulo'] for d in documentos_criticos if d['id'] == x][0][:50]}... ({[d['dias_restantes'] for d in documentos_criticos if d['id'] == x][0]} días)"
    )
    
    if doc_a_revisar:
        fecha_revision = st.date_input(
            "Fecha de Revisión Programada",
            value=datetime.now().date() + timedelta(days=7)
        )
        
        if st.button("📅 Programar Revisión", type="primary"):
            try:
                supabase.table('recordatorios_documentos').insert({
                    'documento_id': doc_a_revisar,
                    'fecha_recordatorio': fecha_revision.isoformat(),
                    'tipo': 'revision',
                    'creado_por': usuario['id']
                }).execute()
                st.success("✅ Revisión programada")
                
                # Notificar a n8n
                requests.post(
                    st.secrets["N8N_WEBHOOK_URL"] + "/revision-programada",
                    json={
                        'documento_id': doc_a_revisar,
                        'fecha_revision': fecha_revision.isoformat()
                    }
                )
            except Exception as e:
                st.error(f"Error programando revisión: {e}")

def reportes_auditoria(usuario):
    """Reportes de auditoría documental"""
    
    st.subheader("📊 Reportes de Auditoría")
    
    supabase = get_supabase_client()
    
    # Opciones de reporte
    tipo_reporte = st.selectbox(
        "Tipo de Reporte",
        [
            "Lista Maestra de Documentos",
            "Documentos por Vencer (30 días)",
            "Historial de Versiones",
            "Documentos sin Aprobar",
            "Cumplimiento por Área"
        ]
    )
    
    if st.button("📥 Generar Reporte", type="primary"):
        if tipo_reporte == "Lista Maestra de Documentos":
            generar_lista_maestra(supabase)
        elif tipo_reporte == "Documentos por Vencer (30 días)":
            generar_reporte_vencimiento(supabase)
        elif tipo_reporte == "Historial de Versiones":
            generar_reporte_versiones(supabase)
        elif tipo_reporte == "Documentos sin Aprobar":
            generar_reporte_sin_aprobar(supabase)
        elif tipo_reporte == "Cumplimiento por Área":
            generar_reporte_cumplimiento_area(supabase)

def generar_lista_maestra(supabase):
    """Generar lista maestra de documentos (formato auditoría)"""
    
    documentos = supabase.table('documentos').select(
        '*, usuarios(nombre_completo)'
    ).order('tipo').execute().data
    
    if not documentos:
        st.warning("No hay documentos para reportar")
        return
    
    df = pd.DataFrame(documentos)
    
    # Preparar columnas para auditoría
    df['estado_vigencia'] = df['fecha_vigencia'].apply(
        lambda x: 'Vigente' if pd.to_datetime(x).date() > datetime.now().date() else 'Vencido'
    )
    
    df['aprobado_si_no'] = df['aprobado'].apply(lambda x: 'Sí' if x else 'No')
    
    # Columnas estándar de auditoría
    df_export = df[[
        'codigo', 'titulo', 'tipo', 'version', 'area',
        'estado', 'aprobado_si_no', 'fecha_vigencia',
        'estado_vigencia', 'usuarios'
    ]].copy()
    
    df_export['responsable'] = df_export['usuarios'].apply(lambda x: x['nombre_completo'])
    df_export.drop('usuarios', axis=1, inplace=True)
    
    # Descargar
    csv = df_export.to_csv(index=False).encode('utf-8')
    st.download_button(
        "📥 Descargar Lista Maestra",
        csv,
        f"lista_maestra_documentos_{datetime.now().strftime('%Y%m%d')}.csv",
        "text/csv"
    )

def generar_reporte_vencimiento(supabase):
    """Reporte de documentos por vencer en 30 días"""
    
    fecha_limite = datetime.now().date() + timedelta(days=30)
    
    documentos = supabase.table('documentos').select(
        '*, usuarios(nombre_completo)'
    ).lte('fecha_vigencia', fecha_limite).gt('fecha_vigencia', datetime.now().date()).execute().data
    
    if not documentos:
        st.info("No hay documentos por vencer en 30 días")
        return
    
    df = pd.DataFrame(documentos)
    df['dias_restantes'] = (pd.to_datetime(df['fecha_vigencia']).dt.date - datetime.now().date()).apply(lambda x: x.days)
    
    df_export = df[['codigo', 'titulo', 'tipo', 'area', 'fecha_vigencia', 'dias_restantes', 'usuarios']]
    df_export['responsable'] = df_export['usuarios'].apply(lambda x: x['nombre_completo'])
    df_export.drop('usuarios', axis=1, inplace=True)
    
    csv = df_export.to_csv(index=False).encode('utf-8')
    st.download_button(
        "📥 Descargar Reporte Vencimientos",
        csv,
        f"documentos_por_vencer_{datetime.now().strftime('%Y%m%d')}.csv",
        "text/csv"
    )

def generar_reporte_versiones(supabase):
    """Reporte de historial de versiones"""
    
    versiones = supabase.table('historial_versiones').select(
        '*, documentos(codigo, titulo)'
    ).order('documento_id').execute().data
    
    if not versiones:
        st.info("No hay historial de versiones")
        return
    
    df = pd.DataFrame(versiones)
    
    df_export = df[['documentos', 'version', 'fecha_reemplazo']].copy()
    df_export['codigo'] = df_export['documentos'].apply(lambda x: x['codigo'])
    df_export['titulo'] = df_export['documentos'].apply(lambda x: x['titulo'])
    df_export.drop('documentos', axis=1, inplace=True)
    
    csv = df_export.to_csv(index=False).encode('utf-8')
    st.download_button(
        "📥 Descargar Historial",
        csv,
        f"historial_versiones_{datetime.now().strftime('%Y%m%d')}.csv",
        "text/csv"
    )

def generar_reporte_sin_aprobar(supabase):
    """Reporte de documentos sin aprobar"""
    
    documentos = supabase.table('documentos').select(
        '*, usuarios(nombre_completo)'
    ).eq('aprobado', False).execute().data
    
    if not documentos:
        st.success("✅ Todos los documentos están aprobados")
        return
    
    df = pd.DataFrame(documentos)
    df_export = df[['codigo', 'titulo', 'tipo', 'area', 'estado', 'usuarios']]
    df_export['responsable'] = df_export['usuarios'].apply(lambda x: x['nombre_completo'])
    df_export.drop('usuarios', axis=1, inplace=True)
    
    csv = df_export.to_csv(index=False).encode('utf-8')
    st.download_button(
        "📥 Descargar Documentos sin Aprobar",
        csv,
        f"documentos_sin_aprobar_{datetime.now().strftime('%Y%m%d')}.csv",
        "text/csv"
    )

def generar_reporte_cumplimiento_area(supabase):
    """Reporte de cumplimiento documental por área"""
    
    # Documentos vigentes por área
    documentos = supabase.table('documentos').select('area', 'aprobado', 'fecha_vigencia').execute().data
    
    if not documentos:
        return
    
    df = pd.DataFrame(documentos)
    df['estado_vigencia'] = df['fecha_vigencia'].apply(
        lambda x: 'Vigente' if pd.to_datetime(x).date() > datetime.now().date() else 'Vencido'
    )
    
    # Agrupar por área
    cumplimiento = df.groupby(['area', 'aprobado', 'estado_vigencia']).size().unstack(fill_value=0)
    
    # Calcular porcentajes
    for area in cumplimiento.index:
        total = cumplimiento.loc[area].sum()
        if total > 0:
            cumplimiento.loc[area, '% Cumplimiento'] = (cumplimiento.loc[area, 'Vigente'] / total * 100)
    
    csv = cumplimiento.to_csv().encode('utf-8')
    st.download_button(
        "📥 Descargar Cumplimiento por Área",
        csv,
        f"cumplimiento_area_{datetime.now().strftime('%Y%m%d')}.csv",
        "text/csv"
    )

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from app.utils.supabase_client import get_supabase_client
from app.utils.storage_helper import subir_archivo_storage
from app.auth import requerir_rol
import json
import requests

def mostrar(usuario):
    """Módulo de Gestión de EPP (Ley 29783 Art. 29)"""
    requerir_rol(['admin', 'sst', 'supervisor'])
    
    st.title("🛡️ Gestión de Equipos de Protección Personal (EPP)")
    
    # Tabs principales
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📦 Catálogo de EPP",
        "👤 Asignar EPP",
        "🔄 Renovar/Reasignar",
        "📊 Inventario y Vencimientos",
        "🔔 Configurar Alertas"
    ])
    
    with tab1:
        gestionar_catalogo(usuario)
    
    with tab2:
        asignar_epp(usuario)
    
    with tab3:
        renovar_epp(usuario)
    
    with tab4:
        dashboard_epp(usuario)
    
    with tab5:
        configurar_alertas_epp(usuario)

def gestionar_catalogo(usuario):
    """Gestionar catálogo maestro de EPP"""
    
    st.subheader("📦 Catálogo de Equipos de Protección")
    
    supabase = get_supabase_client()
    
    # Formulario para nuevo equipo
    with st.expander("➕ Registrar Nuevo EPP", expanded=True):
        with st.form("form_epp_catalogo", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                nombre = st.text_input(
                    "Nombre del EPP",
                    placeholder="Ej: Casco de Seguridad Industrial",
                    help="Nombre descriptivo del equipo"
                )
                
                descripcion = st.text_area(
                    "Descripción Técnica",
                    placeholder="Material: Polietileno de alta densidad, Norma: NTP 123.456"
                )
                
                categoria = st.selectbox(
                    "Categoría",
                    ["Cabeza", "Ojos", "Vías Respiratorias", "Manos", "Pies", "Cuerpo", "Oídos", "Caídas"],
                    help="Clasificación según zona de protección"
                )
            
            with col2:
                vida_util_meses = st.number_input(
                    "Vida Útil (meses)",
                    min_value=1,
                    max_value=120,
                    value=12,
                    help="Período de validez antes de reemplazo obligatorio"
                )
                
                certificacion = st.text_input(
                    "Certificación/Norma",
                    placeholder="Ej: ISO 9001, NTP 234.567",
                    help="Normativa que cumple el equipo"
                )
                
                requiere_mantenimiento = st.checkbox(
                    "Requiere Mantenimiento Periódico",
                    value=False,
                    help="Marca si necesita inspecciones/calibraciones periódicas"
                )
            
            # Foto del equipo
            foto_referencia = st.file_uploader(
                "Foto de Referencia del EPP",
                type=['jpg', 'png'],
                help="Imagen para identificación en inventario"
            )
            
            submitted = st.form_submit_button("💾 Guardar EPP", type="primary")
            
            if submitted:
                if not nombre or not categoria:
                    st.error("❌ Nombre y categoría son obligatorios")
                    return
                
                # Subir foto si existe
                foto_url = None
                if foto_referencia:
                    foto_url = subir_archivo_storage(
                        foto_referencia,
                        bucket='sst-documentos',
                        carpeta='epp_catalogo/'
                    )
                
                # Guardar en BD
                data = {
                    'nombre': nombre,
                    'descripcion': descripcion,
                    'categoria': categoria,
                    'vida_util_meses': vida_util_meses,
                    'certificacion': certificacion,
                    'requiere_mantenimiento': requiere_mantenimiento,
                    'foto_url': foto_url,
                    'activo': True
                }
                
                guardar_epp_catalogo(data)
                st.success(f"✅ EPP registrado: {nombre}")
                st.rerun()
    
    # Listar catálogo
    st.markdown("### 📋 Catálogo Actual")
    
    epp_catalogo = supabase.table('epp_catalogo').select('*').eq('activo', True).execute().data
    
    if not epp_catalogo:
        st.info("ℹ️ No hay EPP registrados en el catálogo")
        return
    
    df_epp = pd.DataFrame(epp_catalogo)
    
    # Filtro
    col_filtro1, col_filtro2 = st.columns(2)
    
    with col_filtro1:
        categoria_filtro = st.selectbox(
            "Filtrar por Categoría",
            options=["todos"] + df_epp['categoria'].unique().tolist()
        )
    
    with col_filtro2:
        buscar = st.text_input("🔍 Buscar EPP", "")
    
    if categoria_filtro != "todos":
        df_epp = df_epp[df_epp['categoria'] == categoria_filtro]
    
    if buscar:
        df_epp = df_epp[df_epp['nombre'].str.contains(buscar, case=False)]
    
    # Mostrar en cards
    for _, epp in df_epp.iterrows():
        with st.container():
            col1, col2, col3, col4 = st.columns([2, 3, 1, 1])
            
            with col1:
                if epp.get('foto_url'):
                    st.image(epp['foto_url'], width=80)
                else:
                    st.caption("Sin foto")
            
            with col2:
                st.write(f"**{epp['nombre']}**")
                st.caption(f"Categoría: {epp['categoria']} | Vida útil: {epp['vida_util_meses']} meses")
                if epp['requiere_mantenimiento']:
                    st.warning("⚠️ Requiere mantenimiento")
            
            with col3:
                st.write(f"Certificación: {epp['certificacion']}")
            
            with col4:
                if st.button("✏️ Editar", key=f"edit_{epp['id']}"):
                    # Lógica de edición (puedes crear un modal con st.dialog si usas Streamlit 1.37+)
                    st.info("Función de edición disponible en versión premium")
            
            st.divider()

def guardar_epp_catalogo(data):
    """Guardar nuevo EPP en catálogo"""
    supabase = get_supabase_client()
    
    try:
        supabase.table('epp_catalogo').insert(data).execute()
    except Exception as e:
        st.error(f"Error guardando EPP: {e}")

def asignar_epp(usuario):
    """Asignar EPP a trabajador con fecha de entrega y vencimiento"""
    
    st.subheader("👤 Asignar EPP a Trabajador")
    
    supabase = get_supabase_client()
    
    # Cargar catálogo
    epp_catalogo = supabase.table('epp_catalogo').select('*').eq('activo', True).execute().data
    
    if not epp_catalogo:
        st.warning("⚠️ Primero registra EPP en el catálogo")
        return
    
    # Cargar trabajadores
    trabajadores = supabase.table('usuarios').select('id', 'nombre_completo', 'area').eq('activo', True).neq('rol', 'admin').execute().data
    
    if not trabajadores:
        st.warning("⚠️ No hay trabajadores activos")
        return
    
    with st.form("form_asignar_epp", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            # Seleccionar trabajador
            trabajador_id = st.selectbox(
                "Trabajador",
                options=[t['id'] for t in trabajadores],
                format_func=lambda x: next(f"{t['nombre_completo']} ({t['area']})" for t in trabajadores if t['id'] == x)
            )
            
            # Obtener área del trabajador
            area_trabajador = next(t['area'] for t in trabajadores if t['id'] == trabajador_id)
        
        with col2:
            # Seleccionar EPP
            epp_id = st.selectbox(
                "EPP a Asignar",
                options=[e['id'] for e in epp_catalogo],
                format_func=lambda x: next(e['nombre'] for e in epp_catalogo if e['id'] == x)
            )
            
            # Obtener datos del EPP
            epp_seleccionado = next(e for e in epp_catalogo if e['id'] == epp_id)
        
        # Fechas
        col_fecha1, col_fecha2 = st.columns(2)
        
        with col_fecha1:
            fecha_entrega = st.date_input(
                "Fecha de Entrega",
                value=datetime.now().date(),
                help="Fecha en que se entrega el EPP al trabajador"
            )
        
        with col_fecha2:
            # Calcular fecha de vencimiento automáticamente
            vida_util_dias = epp_seleccionado['vida_util_meses'] * 30
            fecha_vencimiento = st.date_input(
                "Fecha de Vencimiento",
                value=datetime.now().date() + timedelta(days=vida_util_dias),
                help=f"Vencimiento calculado: {epp_seleccionado['vida_util_meses']} meses"
            )
        
        # Campos adicionales
        st.markdown("### 📄 Información Adicional")
        
        col_add1, col_add2 = st.columns(2)
        
        with col_add1:
            condicion = st.selectbox(
                "Condición del EPP",
                options=["Nuevo", "Usado - Buena condición", "Usado - Regular", "Renovado"],
                help="Estado físico del equipo en la entrega"
            )
            
            numero_serie = st.text_input(
                "Número de Serie/Lote",
                placeholder="Opcional, para trazabilidad"
            )
        
        with col_add2:
            proveedor = st.text_input(
                "Proveedor",
                placeholder="Nombre del proveedor"
            )
            
            orden_compra = st.text_input(
                "Orden de Compra",
                placeholder="Referencia de compra"
            )
        
        # Foto de entrega
        foto_entrega = st.file_uploader(
            "Foto del EPP al momento de entrega (opcional)",
            type=['jpg', 'png'],
            help="Comprobante visual de entrega"
        )
        
        submitted = st.form_submit_button("🎁 Asignar EPP", type="primary")
        
        if submitted:
            # Subir foto si existe
            foto_url = None
            if foto_entrega:
                foto_url = subir_archivo_storage(
                    foto_entrega,
                    bucket='sst-evidencias',
                    carpeta=f'epp_entregas/{trabajador_id}/'
                )
            
            # Guardar asignación
            data = {
                'trabajador_id': trabajador_id,
                'epp_id': epp_id,
                'fecha_entrega': fecha_entrega.isoformat(),
                'fecha_vencimiento': fecha_vencimiento.isoformat(),
                'estado': 'activo',
                'condicion': condicion,
                'numero_serie': numero_serie,
                'proveedor': proveedor,
                'orden_compra': orden_compra,
                'foto_entrega_url': foto_url,
                'asignado_por': usuario['id']
            }
            
            guardar_asignacion_epp(data)
            
            # Notificar a n8n
            notificar_asignacion_epp({
                'trabajador_id': trabajador_id,
                'epp_nombre': epp_seleccionado['nombre'],
                'fecha_vencimiento': fecha_vencimiento.isoformat(),
                'area': area_trabajador
            })
            
            st.success(f"✅ EPP asignado exitosamente a {next(t['nombre_completo'] for t in trabajadores if t['id'] == trabajador_id)}")
            st.rerun()

def guardar_asignacion_epp(data):
    """Guardar asignación en BD"""
    supabase = get_supabase_client()
    
    try:
        supabase.table('epp_asignaciones').insert(data).execute()
    except Exception as e:
        st.error(f"Error en asignación: {e}")

def notificar_asignacion_epp(data):
    """Notificar a n8n sobre nueva asignación"""
    try:
        requests.post(
            st.secrets["N8N_WEBHOOK_URL"] + "/epp-asignado",
            json=data,
            timeout=5
        )
    except:
        pass

def renovar_epp(usuario):
    """Renovar o reasignar EPP vencido o dañado"""
    
    st.subheader("🔄 Renovar / Reasignar EPP")
    
    supabase = get_supabase_client()
    
    # Cargar asignaciones activas por vencer o vencidas
    asignaciones = supabase.from_('epp_asignaciones').select(
        '*, epp_catalogo(*), usuarios(id, nombre_completo, area)'
    ).eq('estado', 'activo').execute().data
    
    if not asignaciones:
        st.info("ℹ️ No hay asignaciones activas")
        return
    
    # Filtrar por vencimiento (próximos 30 días o ya vencidos)
    df_asignaciones = pd.DataFrame(asignaciones)
    df_asignaciones['fecha_vencimiento'] = pd.to_datetime(df_asignaciones['fecha_vencimiento']).dt.date
    df_asignaciones['dias_restantes'] = (df_asignaciones['fecha_vencimiento'] - datetime.now().date()).dt.days
    
    df_vencidas = df_asignaciones[
        (df_asignaciones['dias_restantes'] <= 30) | 
        (df_asignaciones['dias_restantes'] < 0)
    ]
    
    if df_vencidas.empty:
        st.success("✅ No hay EPP por renovar en los próximos 30 días")
        return
    
    # Mostrar tabla
    st.markdown("#### ⚠️ EPP por Renovar/Reasignar")
    
    for _, asig in df_vencidas.iterrows():
        with st.container():
            col1, col2, col3, col4 = st.columns([2, 3, 2, 2])
            
            with col1:
                st.write(f"**{asig['usuarios']['nombre_completo']}**")
                st.caption(f"Área: {asig['usuarios']['area']}")
            
            with col2:
                st.write(f"**{asig['epp_catalogo']['nombre']}**")
                st.caption(f"Condición: {asig['condicion']}")
            
            with col3:
                if asig['dias_restantes'] < 0:
                    st.error(f"🚨 VENCIDO hace {abs(asig['dias_restantes'])} días")
                else:
                    st.warning(f"⏰ Vence en {asig['dias_restantes']} días")
                st.caption(f"Fecha: {asig['fecha_vencimiento']}")
            
            with col4:
                if st.button("🔄 Renovar", key=f"renov_{asig['id']}"):
                    # Llamar a función de renovación
                    renovar_asignacion_epp(asig['id'], usuario['id'])
                    st.rerun()
            
            st.divider()

def renovar_asignacion_epp(asignacion_id, usuario_id):
    """Renovar una asignación de EPP"""
    supabase = get_supabase_client()
    
    try:
        # Obtener datos actuales
        asignacion = supabase.table('epp_asignaciones').select('*').eq('id', asignacion_id).execute().data[0]
        epp = supabase.table('epp_catalogo').select('*').eq('id', asignacion['epp_id']).execute().data[0]
        
        # Actualizar asignación actual a 'renovado'
        supabase.table('epp_asignaciones').update({
            'estado': 'renovado',
            'fecha_devolucion': datetime.now().date().isoformat()
        }).eq('id', asignacion_id).execute()
        
        # Crear nueva asignación
        vida_util_dias = epp['vida_util_meses'] * 30
        nueva_asignacion = {
            'trabajador_id': asignacion['trabajador_id'],
            'epp_id': asignacion['epp_id'],
            'fecha_entrega': datetime.now().date().isoformat(),
            'fecha_vencimiento': (datetime.now().date() + timedelta(days=vida_util_dias)).isoformat(),
            'estado': 'activo',
            'condicion': 'Nuevo',
            'asignado_por': usuario_id,
            'renovado_de': asignacion_id  # Referencia a asignación anterior
        }
        
        result = supabase.table('epp_asignaciones').insert(nueva_asignacion).execute()
        
        # Notificar
        notificar_renovacion_epp({
            'trabajador_id': asignacion['trabajador_id'],
            'epp_nombre': epp['nombre'],
            'nueva_fecha_vencimiento': nueva_asignacion['fecha_vencimiento']
        })
        
        st.success("✅ EPP renovado exitosamente")
        
    except Exception as e:
        st.error(f"Error en renovación: {e}")

def notificar_renovacion_epp(data):
    """Notificar a n8n sobre renovación"""
    try:
        requests.post(
            st.secrets["N8N_WEBHOOK_URL"] + "/epp-renovado",
            json=data,
            timeout=5
        )
    except:
        pass

def dashboard_epp(usuario):
    """Dashboard de inventario y vencimientos"""
    
    st.subheader("📊 Dashboard de EPP")
    
    supabase = get_supabase_client()
    
    # KPIs
    col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
    
    total_asignaciones = supabase.table('epp_asignaciones').select('*', count='exact').execute()
    total_activos = supabase.table('epp_asignaciones').select('*', count='exact').eq('estado', 'activo').execute()
    total_vencidos = supabase.table('epp_asignaciones').select('*', count='exact').eq('estado', 'activo').lte('fecha_vencimiento', datetime.now().date()).execute()
    
    with col_kpi1:
        st.metric("📦 Total Asignaciones", total_activos.count)
    
    with col_kpi2:
        # EPP por vencer en 30 días
        fecha_vencimiento = datetime.now().date() + timedelta(days=30)
        por_vencer = supabase.table('epp_asignaciones').select('*', count='exact').eq('estado', 'activo').lte('fecha_vencimiento', fecha_vencimiento).gt('fecha_vencimiento', datetime.now().date()).execute()
        st.metric("⏰ Por Vencer", por_vencer.count)
    
    with col_kpi3:
        st.metric("🚨 Vencidos", total_vencidos.count)
    
    with col_kpi4:
        tasa_cumplimiento = (total_activos.count - total_vencidos.count) / total_activos.count * 100 if total_activos.count > 0 else 0
        st.metric("✅ Cumplimiento", f"{tasa_cumplimiento:.1f}%")
    
    # Filtros
    st.markdown("### 🔍 Detalle de Asignaciones")
    
    col_filtro1, col_filtro2 = st.columns(2)
    
    with col_filtro1:
        area_filtro = st.selectbox(
            "Filtrar por Área",
            options=["todos"] + [a['area'] for a in supabase.table('usuarios').select('area').execute().data if a['area']]
        )
    
    with col_filtro2:
        estado_filtro = st.selectbox(
            "Filtrar por Estado",
            options=["todos", "activo", "vencido", "renovado"]
        )
    
    # Cargar asignaciones
    query = supabase.from_('epp_asignaciones').select(
        '*, epp_catalogo(nombre, categoria), usuarios(nombre_completo, area)'
    )
    
    if estado_filtro != "todos":
        query = query.eq('estado', estado_filtro)
    
    asignaciones = query.execute().data
    
    if not asignaciones:
        st.info("ℹ️ No hay asignaciones con los filtros seleccionados")
        return
    
    df = pd.DataFrame(asignaciones)
    
    # Aplicar filtro de área si es necesario
    if area_filtro != "todos":
        df = df[df['usuarios']['area'] == area_filtro]
    
    # Preparar datos
    df['fecha_vencimiento'] = pd.to_datetime(df['fecha_vencimiento']).dt.date
    df['dias_restantes'] = (df['fecha_vencimiento'] - datetime.now().date()).apply(lambda x: x.days)
    
    # Mostrar tabla
    df_display = df[['epp_catalogo', 'usuarios', 'fecha_entrega', 'fecha_vencimiento', 'estado', 'dias_restantes']].copy()
    
    # Renombrar columnas
    df_display['EPP'] = df_display['epp_catalogo'].apply(lambda x: x['nombre'])
    df_display['Trabajador'] = df_display['usuarios'].apply(lambda x: x['nombre_completo'])
    df_display['Área'] = df_display['usuarios'].apply(lambda x: x['area'])
    df_display['Fecha Entrega'] = pd.to_datetime(df_display['fecha_entrega']).dt.strftime('%d/%m/%Y')
    df_display['Fecha Vencimiento'] = pd.to_datetime(df_display['fecha_vencimiento']).dt.strftime('%d/%m/%Y')
    
    # Colorear por estado
    def colorear_epp(row):
        if row['estado'] == 'vencido' or row['dias_restantes'] < 0:
            return ['background-color: #ffcccc'] * len(row)
        elif row['dias_restantes'] <= 30:
            return ['background-color: #ffff99'] * len(row)
        else:
            return ['background-color: #ccffcc'] * len(row)
    
    styled = df_display.style.apply(colorear_epp, axis=1)
    
    st.dataframe(
        styled[['EPP', 'Trabajador', 'Área', 'Fecha Entrega', 'Fecha Vencimiento', 'estado']],
        use_container_width=True
    )
    
    # Exportar inventario
    if st.button("📥 Exportar Inventario"):
        excel_data = df_display.to_csv(index=False).encode('utf-8')
        st.download_button(
            "Descargar Inventario",
            excel_data,
            f"inventario_epp_{datetime.now().strftime('%Y%m%d')}.csv",
            "text/csv"
        )

def configurar_alertas_epp(usuario):
    """Configurar parámetros de alertas automáticas"""
    
    st.subheader("🔔 Configuración de Alertas EPP")
    
    st.info("Las alertas se gestionan automáticamente vía n8n según los siguientes parámetros:")
    
    col1, col2 = st.columns(2)
    
    with col1:
        dias_alerta_1 = st.number_input(
            "Días de Alerta Inicial",
            min_value=0,
            max_value=90,
            value=30,
            help="Cuántos días antes del vencimiento enviar primer recordatorio"
        )
        
        dias_alerta_2 = st.number_input(
            "Días de Alerta Final",
            min_value=0,
            max_value=7,
            value=7,
            help="Cuántos días antes enviar alerta final"
        )
    
    with col2:
        incluir_vencidos = st.checkbox(
            "Alertar EPP ya vencidos",
            value=True,
            help="Enviar notificaciones diarias para equipos vencidos"
        )
        
        canal_urgente = st.selectbox(
            "Canal de Alerta Urgente",
            ["Email", "Slack", "Email + Slack"]
        )
    
    # Mostrar vista previa de configuración
    st.markdown("### 📅 Programación de Alertas")
    
    configuracion = {
        "trigger_diario": "7:00 AM",
        "alerta_1": f"{dias_alerta_1} días antes",
        "alerta_2": f"{dias_alerta_2} días antes",
        "vencidos": "Diario" if incluir_vencidos else "No",
        "canal_urgente": canal_urgente
    }
    
    st.json(configuracion)
    
    # Botón para activar/desactivar flujo n8n
    st.markdown("### 🚀 Activar/Desactivar Automatización")
    
    col_btn1, col_btn2 = st.columns(2)
    
    with col_btn1:
        if st.button("▶️ Activar Flujo de Alertas", type="primary"):
            try:
                requests.post(
                    st.secrets["N8N_WEBHOOK_URL"] + "/activar-alertas-epp",
                    json=configuracion
                )
                st.success("✅ Flujo de alertas EPP activado")
            except:
                st.error("❌ No se pudo conectar con n8n")
    
    with col_btn2:
        if st.button("⏸️ Pausar Alertas"):
            try:
                requests.post(
                    st.secrets["N8N_WEBHOOK_URL"] + "/pausar-alertas-epp",
                    json={}
                )
                st.warning("⚠️ Alertas EPP pausadas")
            except:
                st.error("❌ No se pudo conectar con n8n")

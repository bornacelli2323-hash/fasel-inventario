import streamlit as st
import pandas as pd
import sqlite3
from database import obtener_conexion, inicializar_base_de_datos
from services import AutoService, InventarioService, VentasService, AdministracionService

# Asegurar inicialización de la base de datos
inicializar_base_de_datos()

# Configuración inicial de la página
st.set_page_config(
    page_title="Sistema POS - Gestión Comercial",
    page_icon="🛒",
    layout="wide"
)

# Inicializar sesión de usuario
if "usuario" not in st.session_state:
    st.session_state.usuario = None

# Inicializar carrito de compras en la sesión si no existe
if "carrito" not in st.session_state:
    st.session_state.carrito = []

def pantalla_login():
    st.title("🔐 Inicio de Sesión - Sistema POS")
    col1, _ = st.columns([1, 1])
    with col1:
        st.write("Ingrese sus credenciales de acceso:")
        username = st.text_input("Usuario", value="admin")
        password = st.text_input("Contraseña", type="password", value="admin123")
        
        if st.button("Ingresar al Sistema", type="primary"):
            usuario_validado = AutoService.autenticar_usuario(username, password)
            if usuario_validado:
                st.session_state.usuario = usuario_validado
                st.success("¡Acceso concedido!")
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos.")

def obtener_productos_negocio(negocio):
    """Función auxiliar para poblar listas desplegables de productos por sucursal."""
    conexion = obtener_conexion()
    conexion.row_factory = sqlite3.Row
    cursor = conexion.cursor()
    cursor.execute("""
        SELECT id, sku, nombre, descripcion, precio_compra, precio_venta, stock_actual, stock_minimo 
        FROM productos 
        WHERE negocio = ? AND estado = 1
    """, (negocio,))
    productos = [dict(row) for row in cursor.fetchall()]
    conexion.close()
    return productos

def main():
    if st.session_state.usuario is None:
        pantalla_login()
        return

    usuario = st.session_state.usuario
    rol_usuario = usuario.get('rol', 'CAJERO')

    # ==========================================
    # BARRA LATERAL: SUCURSAL Y MENÚ
    # ==========================================
    st.sidebar.title("📍 Sucursal Activa")
    
    try:
        sucursales_disponibles = InventarioService.obtener_negocios_activos()
        if not sucursales_disponibles:
            sucursales_disponibles = ["Sucursal Principal"]
    except Exception:
        sucursales_disponibles = ["Sucursal Principal"]

    # Si cambia la sucursal, vaciamos el carrito para evitar mezcla de stock entre tiendas
    if "negocio_actual" not in st.session_state:
        st.session_state.negocio_actual = sucursales_disponibles[0]

    negocio_previo = st.session_state.negocio_actual
    negocio_seleccionado = st.sidebar.selectbox(
        "Seleccione el negocio:",
        sucursales_disponibles,
        key="negocio_actual"
    )

    if negocio_previo != negocio_seleccionado:
        st.session_state.carrito = []  # Reiniciar carrito al cambiar de sede
        st.rerun()

    st.sidebar.info(f"Operando en: **{negocio_seleccionado}**")
    st.sidebar.divider()

    st.sidebar.title("Panel de Control")
    st.sidebar.write(f"👤 **{usuario.get('nombre_completo', usuario.get('username'))}**")
    st.sidebar.caption(f"Rol: {rol_usuario}")
    st.sidebar.divider()
    
    # Menú principal
    st.sidebar.title("Menú Principal")
    opciones_menu = [
        "📦 Inventario",
        "📥 Compras / Entradas",
        "💰 Ventas / POS",
        "📊 Reportes y Movimientos"
    ]
    menu_opcion = st.sidebar.radio("Seleccione un módulo:", opciones_menu)
    
    st.sidebar.divider()
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.usuario = None
        st.session_state.carrito = []
        st.rerun()

    # ==========================================
    # CUERPO PRINCIPAL SEGÚN EL MÓDULO
    # ==========================================
    st.title(f"{menu_opcion}")
    st.write(f"Sucursal activa actual: **{negocio_seleccionado}**")
    st.divider()

    # 1. MÓDULO INVENTARIO (Consultar, Editar y Crear)
    if menu_opcion == "📦 Inventario":
        if menu_opcion == "📦 Inventario":
            tab1, tab2, tab3, tab4 = st.tabs([
                        "📋 Consultar Catálogo", 
                        "✏️ Editar Producto", 
                        "✨ Registrar Nuevo Producto", 
                        "🗑️ Registrar Merma / Defecto"
        ])
        
        with tab1:
            busqueda = st.text_input("Buscar por SKU o Nombre de producto:")
            if busqueda:
                resultados = InventarioService.buscar_producto(busqueda)
                if resultados:
                    st.dataframe(pd.DataFrame(resultados), use_container_width=True)
                else:
                    st.warning("No se encontraron productos con ese criterio en esta sucursal.")
            else:
                prods_db = obtener_productos_negocio(negocio_seleccionado)
                if prods_db:
                    st.dataframe(pd.DataFrame(prods_db), use_container_width=True)
                else:
                    st.info(f"No hay productos registrados en {negocio_seleccionado}.")

        with tab2:
            st.subheader("✏️ Modificar Información de un Producto")
            prods_edit = obtener_productos_negocio(negocio_seleccionado)
            
            if prods_edit:
                dict_prods_edit = {f"{p['sku']} - {p['nombre']}": p for p in prods_edit}
                prod_label_sel = st.selectbox("Seleccione el producto a editar:", list(dict_prods_edit.keys()), key="select_edit_prod")
                p_actual = dict_prods_edit[prod_label_sel]
                
                with st.form("form_editar_producto"):
                    st.info(f"Editando producto con SKU: **{p_actual['sku']}** (El SKU no se puede modificar)")
                    
                    nuevo_nombre = st.text_input("Nombre del Producto", value=p_actual['nombre'])
                    nueva_desc = st.text_area("Descripción", value=p_actual['descripcion'] if p_actual['descripcion'] else "")
                    
                    col_e1, col_e2 = st.columns(2)
                    with col_e1:
                        nuevo_pcompra = st.number_input("Precio Compra ($)", min_value=0.0, value=float(p_actual['precio_compra']))
                        nuevo_smin = st.number_input("Stock Mínimo (Alerta)", min_value=0, value=int(p_actual['stock_minimo']))
                    with col_e2:
                        nuevo_pventa = st.number_input("Precio Venta ($)", min_value=0.0, value=float(p_actual['precio_venta']))
                    
                    submit_editar = st.form_submit_button("Guardar Cambios", type="primary")
                    
                    if submit_editar:
                        exito, msg = InventarioService.actualizar_producto(
                            sku=p_actual['sku'],
                            nombre=nuevo_nombre,
                            descripcion=nueva_desc,
                            precio_compra=float(nuevo_pcompra),
                            precio_venta=float(nuevo_pventa),
                            stock_minimo=int(nuevo_smin)
                        )
                        if exito:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
            else:
                st.warning("No hay productos disponibles para editar en esta sucursal.")

        with tab3:
            st.subheader("✨ Crear Producto en el Catálogo")
            p_sku = st.text_input("SKU Único:")
            p_nombre = st.text_input("Nombre del Producto:")
            p_desc = st.text_area("Descripción:")
            col1, col2 = st.columns(2)
            with col1:
                p_pcompra = st.number_input("Precio Compra ($)", min_value=0.0, value=0.0)
                p_stock = st.number_input("Stock Inicial", min_value=0, value=0, step=1)
            with col2:
                p_pventa = st.number_input("Precio Venta ($)", min_value=0.0, value=0.0)
                p_smin = st.number_input("Stock Mínimo (Alerta)", min_value=0, value=5, step=1)
            
            if st.button("Registrar Producto", type="primary"):
                exito, msg = InventarioService.crear_producto(p_sku, p_nombre, p_desc, p_pcompra, p_pventa, p_stock, p_smin)
                if exito:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

        with tab4:  # O la pestaña que prefieras habilitar
            st.subheader("🗑️ Registro de Productos Defectuosos / Mermas")
            prods_defectuosos = obtener_productos_negocio(negocio_seleccionado)
            
            if prods_defectuosos:
                opciones_def = {f"{p['sku']} - {p['nombre']} (Stock: {p['stock_actual']})": p for p in prods_defectuosos}
                prod_def_label = st.selectbox("Seleccione el producto defectuoso:", list(opciones_def.keys()))
                p_elegido = opciones_def[prod_def_label]
                
                cant_def = st.number_input("Cantidad defectuosa:", min_value=1, max_value=int(p_elegido['stock_actual']), value=1, step=1)
                motivo_def = st.text_input("Motivo o causa del daño:", value="Defecto de fábrica / Dañado")
                
                if st.button("Registrar Baja por Defecto", type="primary"):
                    exito, msg = InventarioService.registrar_producto_defectuoso(
                        p_elegido['sku'], int(cant_def), motivo=motivo_def
                    )
                    if exito:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
            else:
                st.warning("No hay productos disponibles en esta sucursal.")

    # 2. MÓDULO COMPRAS / ENTRADAS
    elif menu_opcion == "📥 Compras / Entradas":
        st.subheader("📥 Registro de Compras y Entradas de Stock")
        productos_disponibles = obtener_productos_negocio(negocio_seleccionado)
        
        if productos_disponibles:
            opciones_dict = {f"{p['sku']} - {p['nombre']} (Stock actual: {p['stock_actual']})": p for p in productos_disponibles}
            prod_seleccionado_label = st.selectbox("Seleccione el producto de la lista:", list(opciones_dict.keys()))
            producto_elegido = opciones_dict[prod_seleccionado_label]
            
            cant_ent = st.number_input("Cantidad a ingresar:", min_value=1, value=1, step=1)
            costo_ent = st.number_input("Precio de Costo unitario ($):", min_value=0.0, value=float(producto_elegido['precio_compra']))
            obs_ent = st.text_input("Observación / Factura de compra:")
            
            if st.button("Guardar Entrada de Stock", type="primary"):
                exito, msg = InventarioService.registrar_entrada_stock(
                    producto_elegido['sku'], int(cant_ent), float(costo_ent), usuario['id'], observacion=obs_ent
                )
                if exito:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        else:
            st.warning("No hay productos registrados en esta sucursal. Por favor, agregue productos primero en el módulo de Inventario.")

    # 3. MÓDULO VENTAS / POS (CON CARRITO DE COMPRAS COMPLETO)
    elif menu_opcion == "💰 Ventas / POS":
        st.subheader("💰 Terminal de Ventas / POS")
        productos_disponibles = obtener_productos_negocio(negocio_seleccionado)
        
        if productos_disponibles:
            col_sel, col_cart = st.columns([1, 1])
            
            with col_sel:
                st.markdown("### 🛒 Agregar Producto al Carrito")
                opciones_dict = {f"{p['sku']} - {p['nombre']} (Stock: {p['stock_actual']} | ${p['precio_venta']})": p for p in productos_disponibles}
                prod_venta_label = st.selectbox("Seleccione el producto:", list(opciones_dict.keys()))
                producto_venta = opciones_dict[prod_venta_label]
                
                # Calcular disponible restando lo que ya está en el carrito
                cant_en_carrito = sum(item['cantidad'] for item in st.session_state.carrito if item['producto_id'] == producto_venta['id'])
                stock_disponible_real = producto_venta['stock_actual'] - cant_en_carrito
                
                st.caption(f"Disponibles en tienda: **{producto_venta['stock_actual']}** | En carrito actual: **{cant_en_carrito}**")
                
                if stock_disponible_real > 0:
                    cant_v = st.number_input("Cantidad a agregar:", min_value=1, max_value=stock_disponible_real, value=1, step=1)
                    precio_v = st.number_input("Precio de Venta Unitario ($):", min_value=0.0, value=float(producto_venta['precio_venta']))
                    
                    if st.button("➕ Agregar al Carrito", type="secondary"):
                        # Si ya existe en el carrito, sumamos la cantidad
                        encontrado = False
                        for item in st.session_state.carrito:
                            if item['producto_id'] == producto_venta['id']:
                                item['cantidad'] += int(cant_v)
                                item['subtotal'] = item['cantidad'] * item['precio_venta']
                                encontrado = True
                                break
                        
                        if not encontrado:
                            st.session_state.carrito.append({
                                "producto_id": producto_venta['id'],
                                "sku": producto_venta['sku'],
                                "nombre": producto_venta['nombre'],
                                "cantidad": int(cant_v),
                                "precio_venta": float(precio_v),
                                "subtotal": int(cant_v) * float(precio_v)
                            })
                        st.success(f"¡{producto_venta['nombre']} agregado al carrito!")
                        st.rerun()
                else:
                    st.warning("No hay más stock disponible para agregar este producto al carrito.")
            
            with col_cart:
                st.markdown("### 📋 Resumen del Carrito de Compras")
                if st.session_state.carrito:
                    total_venta = 0.0
                    
                    # Mostrar cada ítem con opción de eliminar individualmente
                    for idx, item in enumerate(st.session_state.carrito):
                        c1, c2, c3, c4 = st.columns([3, 1, 2, 1])
                        with c1:
                            st.write(f"**{item['nombre']}** ({item['sku']})")
                        with c2:
                            st.write(f"x{item['cantidad']}")
                        with c3:
                            st.write(f"${item['subtotal']:,.2f}")
                        with c4:
                            if st.button("🗑️", key=f"btn_del_{idx}"):
                                st.session_state.carrito.pop(idx)
                                st.rerun()
                        total_venta += item['subtotal']
                    
                    st.divider()
                    st.markdown(f"### **Total Venta: ${total_venta:,.2f}**")
                    
                    col_b1, col_b2 = st.columns(2)
                    with col_b1:
                        if st.button("✅ Procesar y Cobrar Venta", type="primary"):
                            exito, msg = VentasService.registrar_venta(st.session_state.carrito, usuario['id'])
                            if exito:
                                st.success(msg)
                                st.session_state.carrito = []  # Vaciar carrito tras la venta
                                st.rerun()
                            else:
                                st.error(msg)
                    with col_b2:
                        if st.button("🧹 Vaciar Carrito completo"):
                            st.session_state.carrito = []
                            st.rerun()
                else:
                    st.info("El carrito está vacío. Agregue productos desde la lista de la izquierda.")
        else:
            st.warning("No hay productos con stock disponible para la venta en esta sucursal.")

    # 4. MÓDULO REPORTES Y MOVIMIENTOS
    elif menu_opcion == "📊 Reportes y Movimientos":
        st.subheader("📊 Reportes Gerenciales y Auditoría")
        
        tipo_reporte = st.selectbox(
            "Seleccione el tipo de informe:",
            [
                "Consolidado de Ventas",
                "Consolidado de Compras",
                "Balance General (Ventas vs Compras)",
                "Informe Detallado por Fecha y Producto (Movimientos)"
            ]
        )
        
        col1, col2 = st.columns(2)
        with col1:
            fecha_inicio = st.date_input("Fecha de Inicio")
        with col2:
            fecha_fin = st.date_input("Fecha de Fin")
            
        if tipo_reporte == "Informe Detallado por Fecha y Producto (Movimientos)":
            st.markdown("---")
            st.markdown("### Filtros Avanzados de Movimientos")
            sub_tipo = st.selectbox(
                "Tipo de Movimiento:",
                ["TODOS", "SALIDA_VENTA", "ENTRADA_COMPRA", "AJUSTE"]
            )
            
            prods_rep = obtener_productos_negocio(negocio_seleccionado)
            prod_opciones = {"TODOS LOS PRODUCTOS": "TODOS"}
            for p in prods_rep:
                prod_opciones[f"{p['sku']} - {p['nombre']}"] = p['id']
                
            prod_sel_label = st.selectbox("Filtrar por producto específico:", list(prod_opciones.keys()))
            producto_id_filtro = prod_opciones[prod_sel_label]
            
            if st.button("Generar Informe Detallado", type="primary"):
                try:
                    patron_tipo = "%" if sub_tipo == "TODOS" else sub_tipo
                    df_det = AdministracionService.obtener_detalle_movimientos(
                        patron_tipo, fecha_inicio, fecha_fin, producto_id=producto_id_filtro
                    )
                    if not df_det.empty:
                        st.dataframe(df_det, use_container_width=True)
                    else:
                        st.warning("No hay movimientos registrados para los filtros seleccionados.")
                except Exception as e:
                    st.error(f"Error al generar informe detallado: {e}")
        else:
            if st.button("Generar Reporte Consolidado", type="primary"):
                try:
                    if tipo_reporte == "Consolidado de Ventas":
                        df_rep = AdministracionService.obtener_consolidado_ventas(fecha_inicio, fecha_fin)
                    elif tipo_reporte == "Consolidado de Compras":
                        df_rep = AdministracionService.obtener_consolidado_compras(fecha_inicio, fecha_fin)
                    else:
                        df_rep = AdministracionService.obtener_balance_ventas_compras(fecha_inicio, fecha_fin)
                    
                    if not df_rep.empty:
                        st.dataframe(df_rep, use_container_width=True)
                    else:
                        st.warning("No hay registros para el rango de fechas seleccionado en esta sucursal.")
                except Exception as e:
                    st.error(f"Error al generar el reporte: {e}")

if __name__ == "__main__":
    main()
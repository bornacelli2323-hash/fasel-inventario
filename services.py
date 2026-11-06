import pandas as pd
import sqlite3
import streamlit as st
from database import obtener_conexion

PERMISOS_POR_ROL = {
    "ADMINISTRADOR": [
        "acceso_ventas",
        "acceso_compras",
        "acceso_inventario",
        "gestionar_catalogo",
        "ajustes_stock",
        "acceso_administracion",
        "exportar_excel",
        "gestionar_usuarios"
    ],
    "CAJERO": [
        "acceso_ventas",
        "consultar_stock"
    ],
    "BODEGUERO": [
        "acceso_compras",
        "acceso_inventario",
        "consultar_stock"
    ]
}

class AutoService:
    """
    Autenticación de usuarios, control de acceso de usuarios y validación de permisos 
    """
    
    @staticmethod
    def verificar_permiso(rol_usuario, permiso_requerido):
        permisos = PERMISOS_POR_ROL.get(rol_usuario, [])
        return permiso_requerido in permisos
    
    @staticmethod
    def autenticar_usuario(username, password):
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute(
            "SELECT id, username, nombre_completo, rol FROM usuarios WHERE username = ? AND password = ?",
            (username, password)
        )
        usuario = cursor.fetchone()
        conexion.close()

        if usuario:
            user_dict = dict(usuario)
            user_dict['permisos'] = PERMISOS_POR_ROL.get(user_dict['rol'], [])
            return user_dict
        return None
    
    @staticmethod
    def listar_usuarios():
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute("SELECT id, username, nombre_completo, rol, estado, creado_en FROM usuarios")
        usuarios = [dict(row) for row in cursor.fetchall()]
        conexion.close()
        return usuarios

    @staticmethod
    def crear_usuario(username, password, nombre_completo, rol):
        if rol not in PERMISOS_POR_ROL:
            return False, "Rol no válido"
        
        conexion = obtener_conexion()   
        try:
            cursor = conexion.cursor()
            cursor.execute(
                "INSERT INTO usuarios (username, password, nombre_completo, rol) VALUES (?, ?, ?, ?)",
                (username, password, nombre_completo, rol)
            )
            conexion.commit()
            return True, "Usuario creado exitosamente"
        except sqlite3.IntegrityError:
            return False, "El nombre de usuario ya existe"
        finally:
            conexion.close()

class InventarioService:
    """Servicio para el catálogo de productos, búsquedas duales y gestión de bodega filtrado por sucursal."""

    @staticmethod
    def buscar_producto(criterio):
        negocio_actual = st.session_state.get("negocio_actual", "Sucursal Principal")
        conexion = obtener_conexion()
        conexion.row_factory = sqlite3.Row 
        cursor = conexion.cursor()
        
        cursor.execute("""
            SELECT id, sku, nombre, stock_actual, precio_venta, negocio 
            FROM productos 
            WHERE sku = ? AND negocio = ? AND estado = 1
        """, (criterio, negocio_actual))
        
        producto_exacto = cursor.fetchone()
        
        if producto_exacto:
            conexion.close()
            return [dict(producto_exacto)]
        
        cursor.execute("""
            SELECT id, sku, nombre, stock_actual, precio_venta, negocio 
            FROM productos 
            WHERE negocio = ? AND (nombre LIKE ? OR sku LIKE ?) AND estado = 1
        """, (negocio_actual, f"%{criterio}%", f"%{criterio}%"))
        
        resultados = [dict(row) for row in cursor.fetchall()]
        conexion.close()
        return resultados

    @staticmethod
    def obtener_negocios_activos():
        return ["Sucursal 20 de julio", "Sucursal Yucal"]
        
    @staticmethod
    def obtener_producto_por_sku(sku):
        negocio_actual = st.session_state.get("negocio_actual", "Sucursal Principal")
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute("SELECT * FROM productos WHERE sku = ? AND negocio = ? AND estado = 1", (sku, negocio_actual))
        prod = cursor.fetchone()
        conexion.close()
        return dict(prod) if prod else None

    @staticmethod
    def crear_producto(sku, nombre, descripcion, precio_compra, precio_venta, stock_actual, stock_minimo):
        negocio_actual = st.session_state.get("negocio_actual", "Sucursal Principal")
        conexion = obtener_conexion()
        try:
            cursor = conexion.cursor()
            
            cursor.execute("SELECT id, estado FROM productos WHERE sku = ? AND negocio = ?", (sku, negocio_actual))
            prod_existente = cursor.fetchone()
            
            if prod_existente:
                if prod_existente['estado'] == 0:
                    cursor.execute("""
                        UPDATE productos 
                        SET nombre = ?, descripcion = ?, precio_compra = ?, precio_venta = ?, stock_actual = ?, stock_minimo = ?, estado = 1
                        WHERE id = ?
                    """, (nombre, descripcion, precio_compra, precio_venta, stock_actual, stock_minimo, prod_existente['id']))
                    conexion.commit()
                    return True, f"El producto con SKU '{sku}' estaba inactivo, ha sido reactivado y actualizado en {negocio_actual}."
                else:
                    return False, f"El SKU '{sku}' ya se encuentra registrado y activo en esta sucursal ({negocio_actual})."
            
            cursor.execute("""
                INSERT INTO productos (sku, nombre, descripcion, precio_compra, precio_venta, stock_actual, stock_minimo, negocio)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (sku, nombre, descripcion, precio_compra, precio_venta, stock_actual, stock_minimo, negocio_actual))
            
            conexion.commit()
            return True, f"Producto registrado correctamente en {negocio_actual}."
            
        except Exception as e:
            return False, f"Error al crear producto: {str(e)}"
        finally:
            if conexion:
                conexion.close()

    @staticmethod
    def registrar_entrada_stock(sku, cantidad, precio_costo, usuario_id, proveedor_id=1, observacion="", fecha_personalizada=None):
        if cantidad <= 0:
            return False, "La cantidad de entrada debe ser mayor a cero."

        negocio_actual = st.session_state.get("negocio_actual", "Sucursal Principal")
        conexion = obtener_conexion()
        try:
            cursor = conexion.cursor()
            cursor.execute("SELECT id, stock_actual FROM productos WHERE sku = ? AND negocio = ? AND estado = 1", (sku, negocio_actual))
            producto = cursor.fetchone()

            if not producto:
                return False, f"Producto con SKU '{sku}' no encontrado o inactivo en {negocio_actual}."

            producto_id = producto['id']

            cursor.execute("""
                UPDATE productos 
                SET stock_actual = stock_actual + ?, precio_compra = ?
                WHERE id = ?
            """, (cantidad, precio_costo, producto_id))

            if fecha_personalizada:
                cursor.execute("""
                    INSERT INTO movimientos (producto_id, tipo_movimiento, cantidad, precio_unitario, usuario_id, observacion, fecha, negocio)
                    VALUES (?, 'ENTRADA_COMPRA', ?, ?, ?, ?, ?, ?)
                """, (producto_id, cantidad, precio_costo, usuario_id, observacion, fecha_personalizada, negocio_actual))
            else:
                cursor.execute("""
                    INSERT INTO movimientos (producto_id, tipo_movimiento, cantidad, precio_unitario, usuario_id, observacion, negocio)
                    VALUES (?, 'ENTRADA_COMPRA', ?, ?, ?, ?, ?)
                """, (producto_id, cantidad, precio_costo, usuario_id, observacion, negocio_actual))

            conexion.commit()
            return True, f"Entrada de stock registrada con éxito en {negocio_actual} (+{cantidad} unidades)."
        except Exception as e:
            conexion.rollback()
            return False, f"Error al registrar entrada: {str(e)}"
        finally:
            conexion.close()

    @staticmethod
    def actualizar_producto(sku, nombre, descripcion, precio_compra, precio_venta, stock_minimo):
        negocio_actual = st.session_state.get("negocio_actual", "Sucursal Principal")
        conexion = obtener_conexion()
        try:
            cursor = conexion.cursor()
            cursor.execute("""
                UPDATE productos 
                SET nombre = ?, descripcion = ?, precio_compra = ?, precio_venta = ?, stock_minimo = ?
                WHERE sku = ? AND negocio = ? AND estado = 1
            """, (nombre, descripcion, precio_compra, precio_venta, stock_minimo, sku, negocio_actual))
            
            conexion.commit()
            if cursor.rowcount > 0:
                return True, "Producto actualizado exitosamente."
            return False, "Producto no encontrado en esta sucursal."
        except sqlite3.Error as e:
            return False, f"Error al actualizar producto: {str(e)}"
        finally:
            conexion.close()

    @staticmethod
    def registrar_producto_defectuoso(sku, cantidad, motivo=""):
        if cantidad <= 0:
            return False, "La cantidad defectuosa debe ser mayor a cero."

        negocio_actual = st.session_state.get("negocio_actual", "Sucursal Principal")
        conexion = obtener_conexion()
        try:
            cursor = conexion.cursor()
            cursor.execute("SELECT id, stock_actual FROM productos WHERE sku = ? AND negocio = ? AND estado = 1", (sku, negocio_actual))
            producto = cursor.fetchone()

            if not producto:
                return False, "Producto no encontrado o inactivo en esta sucursal."

            producto_id = producto['id']
            stock_actual = producto['stock_actual']

            if cantidad > stock_actual:
                return False, f"No hay suficiente stock. Disponible: {stock_actual}, Solicitado: {cantidad}."

            cursor.execute("""
                UPDATE productos 
                SET stock_actual = stock_actual - ? 
                WHERE id = ?
            """, (cantidad, producto_id))

            conexion.commit()
            return True, f"Se registraron {cantidad} unidad(es) defectuosa(s) correctamente."
        except sqlite3.Error as e:
            return False, f"Error al registrar producto defectuoso: {str(e)}"
        finally:
            conexion.close()

    @staticmethod
    def obtener_alertas_stock_minimo():
        negocio_actual = st.session_state.get("negocio_actual", "Sucursal Principal")
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT sku, nombre, stock_actual, stock_minimo 
            FROM productos 
            WHERE stock_minimo IS NOT NULL 
              AND stock_minimo > 0 
              AND stock_actual <= stock_minimo 
              AND estado = 1
              AND negocio = ?
        """, (negocio_actual,))
        alertas = [dict(row) for row in cursor.fetchall()]
        conexion.close()
        return alertas

    @staticmethod
    def registrar_ajuste_manual(producto_id, cantidad, tipo_ajuste, usuario_id, observacion):
        if tipo_ajuste not in ["AJUSTE_ENTRADA", "AJUSTE_SALIDA"]:
            return False, "Tipo de ajuste no válido"

        negocio_actual = st.session_state.get("negocio_actual", "Sucursal Principal")
        conexion = obtener_conexion()
        try:
            cursor = conexion.cursor()
            cursor.execute("SELECT stock_actual, precio_compra, negocio FROM productos WHERE id = ? AND negocio = ?", (producto_id, negocio_actual))
            prod = cursor.fetchone()

            if not prod:
                return False, "Producto no encontrado en esta sucursal"

            if tipo_ajuste == "AJUSTE_SALIDA" and prod["stock_actual"] < cantidad:
                return False, "Stock insuficiente para realizar el ajuste de salida."

            delta = cantidad if tipo_ajuste == "AJUSTE_ENTRADA" else -cantidad

            cursor.execute("UPDATE productos SET stock_actual = stock_actual + ? WHERE id = ?", (delta, producto_id))

            cursor.execute("""
                INSERT INTO movimientos (producto_id, tipo_movimiento, cantidad, precio_unitario, usuario_id, observacion, negocio)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (producto_id, tipo_ajuste, cantidad, prod["precio_compra"], usuario_id, observacion, negocio_actual))

            conexion.commit()
            return True, "Ajuste de inventario registrado correctamente."
        except Exception as e:
            conexion.rollback()
            return False, f"Error al procesar el ajuste: {str(e)}"
        finally:
            conexion.close()

class VentasService:
    """Módulo POS: Procesamiento de ventas directas segregado por sucursal."""

    @staticmethod
    def registrar_venta(items_venta, usuario_id, cliente_id=1, fecha_personalizada=None):
        if not items_venta:
            return False, "La venta no contiene productos"

        negocio_actual = st.session_state.get("negocio_actual", "Sucursal Principal")
        conexion = obtener_conexion()
        try:
            cursor = conexion.cursor()

            for item in items_venta:
                prod_id = item["producto_id"]
                cant = item["cantidad"]
                precio = item["precio_venta"]

                cursor.execute("SELECT stock_actual, nombre FROM productos WHERE id = ? AND negocio = ?", (prod_id, negocio_actual))
                prod = cursor.fetchone()
                
                if not prod:
                    raise ValueError(f"Producto con ID {prod_id} no encontrado en {negocio_actual}.")
                
                if prod['stock_actual'] < cant:
                    raise ValueError(f"Stock insuficiente para '{prod['nombre']}'. Disponible: {prod['stock_actual']}")
                
                cursor.execute("UPDATE productos SET stock_actual = stock_actual - ? WHERE id = ?", (cant, prod_id))
                
                if fecha_personalizada:
                    cursor.execute("""
                        INSERT INTO movimientos (producto_id, tipo_movimiento, cantidad, precio_unitario, usuario_id, observacion, fecha, negocio)
                        VALUES (?, 'SALIDA_VENTA', ?, ?, ?, ?, ?, ?)
                    """, (prod_id, cant, precio, usuario_id, f"Venta POS - Cliente ID: {cliente_id}", fecha_personalizada, negocio_actual))
                else:
                    cursor.execute("""
                        INSERT INTO movimientos (producto_id, tipo_movimiento, cantidad, precio_unitario, usuario_id, observacion, negocio)
                        VALUES (?, 'SALIDA_VENTA', ?, ?, ?, ?, ?)
                    """, (prod_id, cant, precio, usuario_id, f"Venta POS - Cliente ID: {cliente_id}", negocio_actual))

            conexion.commit()
            return True, f"Venta registrada con éxito en {negocio_actual}."
        except Exception as e:
            conexion.rollback()
            return False, str(e)
        finally:
            conexion.close()

    @staticmethod
    def corregir_venta_y_ajustar_inventario(movimiento_id, nuevo_producto_sku):
        """
        Corrige un error en el registro de una venta (cambia el producto asociado),
        reversando el stock del producto erróneo y descontando el del correcto de forma transaccional (ACID).
        """
        negocio_actual = st.session_state.get("negocio_actual", "Sucursal Principal")
        conexion = obtener_conexion()
        try:
            conexion.execute("BEGIN TRANSACTION")
            cursor = conexion.cursor()

            # SELECT AGREGADO CORRECTAMENTE
            cursor.execute("""
                SELECT m.id, p.sku, m.cantidad, m.producto_id 
                FROM movimientos m
                JOIN productos p ON m.producto_id = p.id
                WHERE m.id = ? AND m.negocio = ? AND m.tipo_movimiento LIKE '%VENTA%'
            """, (movimiento_id, negocio_actual))
            
            movimiento_actual = cursor.fetchone()
            
            if not movimiento_actual:
                raise Exception("El movimiento de venta especificado no existe o no pertenece a esta sucursal.")
            
            sku_antiguo = movimiento_actual[1]
            cantidad = movimiento_actual[2]
            prod_id_antiguo = movimiento_actual[3]

            # Reversión de stock antiguo
            cursor.execute("""
                UPDATE productos 
                SET stock_actual = stock_actual + ? 
                WHERE id = ? AND negocio = ?
            """, (cantidad, prod_id_antiguo, negocio_actual))

            # Validación de nuevo producto
            cursor.execute("""
                SELECT id, stock_actual, nombre FROM productos 
                WHERE sku = ? AND negocio = ? AND estado = 1
            """, (nuevo_producto_sku, negocio_actual))
            nuevo_prod = cursor.fetchone()

            if not nuevo_prod:
                raise Exception(f"El nuevo producto con SKU '{nuevo_producto_sku}' no existe o está inactivo en {negocio_actual}.")
            
            nuevo_prod_id = nuevo_prod[0]
            stock_disponible = nuevo_prod[1]
            nombre_nuevo = nuevo_prod[2]

            if stock_disponible < cantidad:
                raise Exception(f"Stock insuficiente en '{nombre_nuevo}'. Disponible: {stock_disponible}, Requerido: {cantidad}")

            # Descuento de stock nuevo
            cursor.execute("""
                UPDATE productos 
                SET stock_actual = stock_actual - ? 
                WHERE id = ? AND negocio = ?
            """, (cantidad, nuevo_prod_id, negocio_actual))

            # Actualización del registro del movimiento
            cursor.execute("""
                UPDATE movimientos 
                SET producto_id = ?, observacion = observacion || ' [CORREGIDO: Producto cambiado a SKU ' || ? || ']'
                WHERE id = ? AND negocio = ?
            """, (nuevo_prod_id, nuevo_producto_sku, movimiento_id, negocio_actual))

            conexion.commit()
            return True, f"Venta corregida con éxito. Stock devuelto a '{sku_antiguo}' y descontado de '{nuevo_producto_sku}'."

        except Exception as e:
            conexion.rollback()
            return False, f"Error en la transacción (Revertida): {str(e)}"
        finally:
            conexion.close()

class AdministracionService:
    """
    Clase Fachada Centralizada para reportes gerenciales filtrados por la sucursal activa.
    """    
    @staticmethod
    def obtener_consolidado_ventas(fecha_inicio, fecha_fin=None):
        negocio_actual = st.session_state.get("negocio_actual", "Sucursal Principal")
        conexion = obtener_conexion()
        if not fecha_fin:
            fecha_fin = fecha_inicio

        f_inicio_str = str(fecha_inicio)
        f_fin_str = str(fecha_fin)

        query = """
            SELECT 
                p.sku AS "SKU",
                p.nombre AS "Producto",
                SUM(m.cantidad) AS "Unidades Vendidas",
                SUM(m.cantidad * m.precio_unitario) AS "Ingresos Totales"
            FROM movimientos m
            JOIN productos p ON m.producto_id = p.id
            WHERE m.tipo_movimiento LIKE '%VENTA%'
              AND m.negocio = ?
              AND DATE(m.fecha) BETWEEN DATE(?) AND DATE(?)
            GROUP BY p.sku, p.nombre
            ORDER BY "Ingresos Totales" DESC
        """
        df = pd.read_sql_query(query, conexion, params=(negocio_actual, f_inicio_str, f_fin_str))
        conexion.close()
        return df

    @staticmethod
    def obtener_consolidado_compras(fecha_inicio, fecha_fin=None):
        negocio_actual = st.session_state.get("negocio_actual", "Sucursal Principal")
        conexion = obtener_conexion()
        if not fecha_fin:
            fecha_fin = fecha_inicio
                                    
        f_inicio_str = str(fecha_inicio)
        f_fin_str = str(fecha_fin)

        query = """
            SELECT 
                p.sku AS "SKU",
                p.nombre AS "Producto",
                SUM(m.cantidad) AS "Unidades Compradas",
                SUM(m.cantidad * m.precio_unitario) AS "Gastos Totales"
            FROM movimientos m
            JOIN productos p ON m.producto_id = p.id
            WHERE m.tipo_movimiento LIKE '%COMPRA%'
              AND m.negocio = ?
              AND DATE(m.fecha) BETWEEN DATE(?) AND DATE(?)
            GROUP BY p.sku, p.nombre
            ORDER BY "Gastos Totales" DESC
        """
        df = pd.read_sql_query(query, conexion, params=(negocio_actual, f_inicio_str, f_fin_str))
        conexion.close()
        return df

    @staticmethod
    def obtener_balance_ventas_compras(fecha_inicio, fecha_fin=None):
        negocio_actual = st.session_state.get("negocio_actual", "Sucursal Principal")
        conexion = obtener_conexion()
        if not fecha_fin:
            fecha_fin = fecha_inicio
                            
        f_inicio_str = str(fecha_inicio)
        f_fin_str = str(fecha_fin)

        query = """
            SELECT 
                p.sku AS "SKU",
                p.nombre AS "Producto",
                COALESCE(SUM(CASE WHEN m.tipo_movimiento LIKE '%VENTA%' THEN m.cantidad ELSE 0 END), 0) AS "Unidades Vendidas",
                COALESCE(SUM(CASE WHEN m.tipo_movimiento LIKE '%VENTA%' THEN m.cantidad * m.precio_unitario ELSE 0 END), 0) AS "Total Ventas ($)",
                COALESCE(SUM(CASE WHEN m.tipo_movimiento LIKE '%COMPRA%' THEN m.cantidad ELSE 0 END), 0) AS "Unidades Compradas",
                COALESCE(SUM(CASE WHEN m.tipo_movimiento LIKE '%COMPRA%' THEN m.cantidad * m.precio_unitario ELSE 0 END), 0) AS "Total Compras ($)",
                (
                    COALESCE(SUM(CASE WHEN m.tipo_movimiento LIKE '%VENTA%' THEN m.cantidad * m.precio_unitario ELSE 0 END), 0) - 
                    COALESCE(SUM(CASE WHEN m.tipo_movimiento LIKE '%COMPRA%' THEN m.cantidad * m.precio_unitario ELSE 0 END), 0)
                ) AS "Diferencia Neta ($)"
            FROM movimientos m
            JOIN productos p ON m.producto_id = p.id
            WHERE m.negocio = ?
              AND DATE(m.fecha) BETWEEN DATE(?) AND DATE(?)
            GROUP BY p.sku, p.nombre
            ORDER BY "Diferencia Neta ($)" DESC
        """
        df = pd.read_sql_query(query, conexion, params=(negocio_actual, f_inicio_str, f_fin_str))
        conexion.close()
        return df

    @staticmethod
    def obtener_detalle_movimientos(tipo_movimiento, fecha_inicio, fecha_fin=None, producto_id=None):
        negocio_actual = st.session_state.get("negocio_actual", "Sucursal Principal")
        conexion = obtener_conexion()
        if not fecha_fin:
            fecha_fin = fecha_inicio
                            
        f_inicio_str = str(fecha_inicio)
        f_fin_str = str(fecha_fin)

        # INCLUYE m.id AS "ID Movimiento" PARA VER EL ID EN REPORTES
        query = """
            SELECT 
                m.id AS "ID Movimiento",
                m.fecha AS "Fecha del Movimiento",
                p.sku AS "SKU",
                p.nombre AS "Producto",
                m.cantidad AS "Cantidad",
                m.precio_unitario AS "Precio Unitario ($)",
                (m.cantidad * m.precio_unitario) AS "Total ($)",
                m.observacion AS "Observación"
            FROM movimientos m
            JOIN productos p ON m.producto_id = p.id
            WHERE m.tipo_movimiento LIKE ?
              AND m.negocio = ?
              AND DATE(m.fecha) BETWEEN DATE(?) AND DATE(?)
        """
        params = [f'%{tipo_movimiento}%', negocio_actual, f_inicio_str, f_fin_str]

        if producto_id and producto_id != "TODOS":
            query += " AND p.id = ?"
            params.append(producto_id)

        query += " ORDER BY m.fecha DESC"

        df = pd.read_sql_query(query, conexion, params=params)
        conexion.close()
        return df
        
    @staticmethod
    def exportar_dataframe_a_excel(df, ruta_archivo):
        try:
            with pd.ExcelWriter(ruta_archivo, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Reporte_Consolidado', index=False)
            return True, f"Reporte exportado exitosamente a {ruta_archivo}"
        except Exception as e:
            return False, f"Error al generar archivo Excel: {str(e)}"

    

    
                



    



            

                

                
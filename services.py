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
        
        # 1. Búsqueda exacta por SKU dentro de la sucursal activa
        cursor.execute("""
            SELECT id, sku, nombre, stock_actual, precio_venta, negocio 
            FROM productos 
            WHERE sku = ? AND negocio = ? AND estado = 1
        """, (criterio, negocio_actual))
        
        producto_exacto = cursor.fetchone()
        
        if producto_exacto:
            conexion.close()
            return [dict(producto_exacto)]
        
        # 2. Búsqueda flexible por nombre o SKU parcial dentro de la sucursal activa
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
        # Reemplaza estos nombres por los que el cliente te haya pedido
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
            
            # Validar si el SKU ya existe EXCLUSIVAMENTE en la sucursal actual
            cursor.execute("SELECT id, estado FROM productos WHERE sku = ? AND negocio = ?", (sku, negocio_actual))
            prod_existente = cursor.fetchone()
            
            if prod_existente:
                if prod_existente['estado'] == 0:
                    # Si estaba inactivo, lo reactivamos y actualizamos
                    cursor.execute("""
                        UPDATE productos 
                        SET nombre = ?, descripcion = ?, precio_compra = ?, precio_venta = ?, stock_actual = ?, stock_minimo = ?, estado = 1
                        WHERE id = ?
                    """, (nombre, descripcion, precio_compra, precio_venta, stock_actual, stock_minimo, prod_existente['id']))
                    conexion.commit()
                    return True, f"El producto con SKU '{sku}' estaba inactivo, ha sido reactivado y actualizado en {negocio_actual}."
                else:
                    return False, f"El SKU '{sku}' ya se encuentra registrado y activo en esta sucursal ({negocio_actual})."
            
            # Insertar el producto vinculado estrictamente al negocio activo
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

            # 1. Aumentar stock y costo
            cursor.execute("""
                UPDATE productos 
                SET stock_actual = stock_actual + ?, precio_compra = ?
                WHERE id = ?
            """, (cantidad, precio_costo, producto_id))

            # 2. Registrar movimiento con sucursal
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
                
                # 1. Descontar stock
                cursor.execute("UPDATE productos SET stock_actual = stock_actual - ? WHERE id = ?", (cant, prod_id))
                
                # 2. Registrar movimiento asociado a la sucursal activa
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

        query = """
            SELECT 
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
    
                



    



            

                

                
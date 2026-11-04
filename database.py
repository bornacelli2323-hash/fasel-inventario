import sqlite3
import os

DB_NAME = "gestion_inventario.db"

def obtener_conexion():
    """
    Establece y retorna la conexión a la base de datos SQLite.
    Activa el soporte nativo para llaves foráneas (Foreign Keys).
    """
    conexion = sqlite3.connect(DB_NAME)
    conexion.execute("PRAGMA foreign_keys = ON;")
    conexion.row_factory = sqlite3.Row  # Permite acceder a las columnas por nombre
    return conexion

def inicializar_base_de_datos():
    """
    Crea la estructura de tablas e índices si no existen,
    aplica la migración para sucursales (negocios),
    e inserta los registros por defecto.
    """
    conexion = obtener_conexion()
    cursor = conexion.cursor()

    # 1. Tabla de Usuarios (Soporta Roles)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        nombre_completo TEXT NOT NULL,
        rol TEXT NOT NULL CHECK(rol IN ('ADMINISTRADOR', 'CAJERO', 'BODEGUERO')),
        estado INTEGER NOT NULL DEFAULT 1,
        creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Tabla de Clientes
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        documento TEXT UNIQUE NOT NULL,
        nombre TEXT NOT NULL,
        telefono TEXT,
        email TEXT,
        creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 3. Tabla de Proveedores
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS proveedores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nit TEXT UNIQUE NOT NULL,
        razon_social TEXT NOT NULL,
        telefono TEXT,
        email TEXT,
        direccion TEXT,
        creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 4. Tabla de Productos (Identificador principal: SKU) - Con soporte de Negocio
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS productos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT NOT NULL,
    nombre TEXT NOT NULL,
    descripcion TEXT,
    precio_compra REAL DEFAULT 0,
    precio_venta REAL DEFAULT 0,
    stock_actual INTEGER DEFAULT 0,
    stock_minimo INTEGER DEFAULT 5,
    negocio TEXT NOT NULL,
    estado INTEGER DEFAULT 1,
    UNIQUE(sku, negocio)
    );
    """)

    # 5. Tabla de Movimientos / Transacciones - Con soporte de Negocio
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS movimientos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        producto_id INTEGER NOT NULL,
        tipo_movimiento TEXT NOT NULL CHECK(
            tipo_movimiento IN ('SALIDA_VENTA', 'ENTRADA_COMPRA', 'AJUSTE_ENTRADA', 'AJUSTE_SALIDA')
        ),
        cantidad INTEGER NOT NULL,
        precio_unitario REAL NOT NULL,
        fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        usuario_id INTEGER NOT NULL,
        cliente_id INTEGER,
        proveedor_id INTEGER,
        observacion TEXT,
        negocio TEXT NOT NULL DEFAULT 'Sucursal Principal',
        FOREIGN KEY (producto_id) REFERENCES productos(id),
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
        FOREIGN KEY (cliente_id) REFERENCES clientes(id),
        FOREIGN KEY (proveedor_id) REFERENCES proveedores(id)
    );
    """)

    # 6. Tabla de Negocios
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS negocios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT UNIQUE NOT NULL,
        descripcion TEXT,
        estado INTEGER NOT NULL DEFAULT 1,
        creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    INSERT OR IGNORE INTO negocios (id, nombre, descripcion)
    VALUES (1, 'Sucursal Principal', 'Sede 20 de julio');
    """)
    
    cursor.execute("""
    INSERT OR IGNORE INTO negocios (id, nombre, descripcion)
    VALUES (2, 'Sucursal Secundaria', 'Sede yucal');
    """)
    

    # ------------------------------------------------------------------
    # MIGRACIÓN SEGURA PARA TABLAS YA EXISTENTES (Por si acaso)
    # ------------------------------------------------------------------
    tablas_a_migrar = ["usuarios", "clientes", "proveedores", "productos", "movimientos"]
    for tabla in tablas_a_migrar:
        try:
            cursor.execute(f"ALTER TABLE {tabla} ADD COLUMN negocio TEXT DEFAULT 'Sucursal Principal';")
        except sqlite3.OperationalError:
            # Si la columna ya existe, SQLite genera un error que ignoramos tranquilamente
            pass

    # ------------------------------------------------------------------
    # ÍNDICES PARA OPTIMIZAR CONSULTAS
    # ------------------------------------------------------------------
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_productos_sku ON productos(sku);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_productos_nombre ON productos(nombre);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_productos_negocio ON productos(negocio);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_movimientos_fecha ON movimientos(fecha);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_movimientos_producto ON movimientos(producto_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_movimientos_negocio ON movimientos(negocio);")

    # ------------------------------------------------------------------
    # INSERCIÓN DE REGISTROS POR DEFECTO
    # ------------------------------------------------------------------
    cursor.execute("""
    INSERT OR IGNORE INTO clientes (id, documento, nombre, telefono, email)
    VALUES (1, '222222222222', 'Cliente General / Consumidor Final', '0000000000', 'general@tienda.com');
    """)

    cursor.execute("""
    INSERT OR IGNORE INTO usuarios (id, username, password, nombre_completo, rol, estado)
    VALUES (1, 'admin', 'admin123', 'Administrador Plenipotenciario', 'ADMINISTRADOR', 1);
    """)

    # Se ejecuta el commit y se cierra la conexión una sola vez al finalizar todo el proceso
    conexion.commit()
    conexion.close()
    print("Base de datos inicializada y adaptada para multi-sucursal correctamente.")

if __name__ == "__main__":
    inicializar_base_de_datos()



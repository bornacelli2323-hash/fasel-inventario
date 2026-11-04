import json

# 1. Función para crear un producto en forma de diccionario
def crear_producto(nombre, cantidad, precio):
    return {
        "nombre": nombre,
        "cantidad": cantidad,
        "precio": precio
    }

# 2. Creamos una lista con varios productos de nuestro laboratorio IoT
inventario = [
    crear_producto("ESP32 DevKit V1", 3, 30000),
    crear_producto("Sensor BME280 (I2C)", 5, 25000),
    crear_producto("Analizador Lógico USB 8CH", 1, 45000)
]

# 3. Guardar la lista de productos en un archivo JSON
nombre_archivo = "inventario.json"

with open(nombre_archivo, "w", encoding="utf-8") as archivo:
    json.dump(inventario, archivo, indent=4, ensure_ascii=False)

print(f"✅ ¡Inventario guardado exitosamente en '{nombre_archivo}'!")
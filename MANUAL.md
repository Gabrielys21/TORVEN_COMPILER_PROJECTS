# Manual de Usuario — TORVEN

> Lenguaje de programación compilado, tipado estático, con su propia VM.  
> Si sabes algo de Python, esto te va a sonar familiar. Si no, aquí aprenderás desde cero.

---

## Índice

1. [¿Cómo correr un programa?](#1-cómo-correr-un-programa)
2. [Variables](#2-variables)
3. [Tipos de dato](#3-tipos-de-dato)
4. [Operadores](#4-operadores)
5. [Imprimir en pantalla (vent)](#5-imprimir-en-pantalla-vent)
6. [Condicionales (ignite / drift)](#6-condicionales-ignite--drift)
7. [Bucle while (rev)](#7-bucle-while-rev)
8. [Bucle for (burn)](#8-bucle-for-burn)
9. [Funciones (forge)](#9-funciones-forge)
10. [Listas (barrel)](#10-listas-barrel)
11. [Diccionarios (chassis)](#11-diccionarios-chassis)
12. [El operador pipe (->)](#12-el-operador-pipe--)
13. [Manejo de errores (stall / redline)](#13-manejo-de-errores-stall--redline)
14. [Constantes (lock)](#14-constantes-lock)
15. [Tabla de referencia rápida](#15-tabla-de-referencia-rápida)
16. [Programa de ejemplo completo](#16-programa-de-ejemplo-completo)

---

## 1. ¿Cómo correr un programa?

Guarda tu código en un archivo con extensión `.trv` y usa uno de estos comandos:

```bash
# Compilar Y ejecutar en un solo paso (el más cómodo)
python -m torven.main exec mi_programa.trv

# Solo compilar (produce mi_programa.tvbc)
python -m torven.main compile mi_programa.trv

# Ejecutar el bytecode ya compilado
python -m torven.main run mi_programa.tvbc
```

> **Tip de debug:** Si algo sale mal puedes ver exactamente qué tokens generó tu código:
> ```bash
> python -m torven.main tokens mi_programa.trv
> ```

---

## 2. Variables

En TORVEN hay dos tipos de variables:

| Palabra clave | Equivalente | ¿Se puede cambiar? |
|---------------|-------------|-------------------|
| `load`        | `let` / `var` | Sí             |
| `lock`        | `const`       | No             |

### Sintaxis

```
load nombre => valor
load nombre@tipo => valor
```

### Ejemplos

```torven
load edad => 20
load nombre => "Luis"
load precio => 9.99
load activo => on
```

Con anotación de tipo (opcional pero recomendado):

```torven
load edad@torq    => 20
load nombre@exhaust => "Luis"
load precio@venom  => 9.99
load activo@spark  => on
```

### Reasignar una variable

Para cambiar el valor de una variable que ya existe, simplemente escribe:

```torven
load puntos@torq => 0

puntos => puntos + 10
puntos => 50
```

> **¡Ojo!** No repitas `load` al reasignar. `load` solo se usa la primera vez.

---

## 3. Tipos de dato

| Nombre TORVEN | Qué es         | Ejemplo de valor       |
|---------------|----------------|------------------------|
| `torq`        | Número entero  | `5`, `-3`, `100`       |
| `venom`       | Número decimal | `3.14`, `-0.5`         |
| `exhaust`     | Texto (string) | `"hola"`, `'mundo'`    |
| `spark`       | Booleano       | `on` (True), `off` (False) |
| `barrel`      | Lista          | `[1, 2, 3]`            |
| `chassis`     | Diccionario    | `{"clave": "valor"}`   |
| `void`        | Nada / None    | `void`                 |

### Ejemplos

```torven
load entero@torq    => 42
load decimal@venom  => 3.14
load texto@exhaust  => "TORVEN manda"
load bandera@spark  => on
load lista@barrel   => [10, 20, 30]
```

---

## 4. Operadores

### Aritméticos

```torven
load a => 10
load b => 3

load suma      => a + b      # 13
load resta     => a - b      # 7
load producto  => a * b      # 30
load division  => a / b      # 3.333...
load modulo    => a % b      # 1
load potencia  => a ^^ b     # 1000   ← operador especial de TORVEN
```

### Comparación

| Operador TORVEN | Significado       | Ejemplo          |
|-----------------|-------------------|------------------|
| `~~`            | igual a           | `x ~~ 5`         |
| `!~`            | diferente de      | `x !~ 0`         |
| `<`             | menor que         | `x < 10`         |
| `>`             | mayor que         | `x > 0`          |
| `<=`            | menor o igual     | `x <= 100`       |
| `>=`            | mayor o igual     | `x >= 1`         |

```torven
load x@torq => 7

ignite x ~~ 7:
    vent "x es siete"

ignite x !~ 0:
    vent "x no es cero"

ignite x >= 5:
    vent "x es grande"
```

---

## 5. Imprimir en pantalla (vent)

`vent` es el equivalente a `print`. Imprime lo que sea que le pongas.

```torven
vent "Hola mundo"
vent 42
vent on
```

También puedes imprimir variables:

```torven
load nombre@exhaust => "Carlos"
vent nombre
```

O expresiones directamente:

```torven
load x@torq => 5
vent x * 2
vent x ^^ 3
```

---

## 6. Condicionales (ignite / drift)

### Solo if

```torven
ignite condicion:
    # código si es verdadero
```

### if / else

```torven
ignite condicion:
    # código si es verdadero
drift:
    # código si es falso
```

### if / else if / else

```torven
ignite condicion1:
    # primera rama
drift ignite condicion2:
    # segunda rama
drift ignite condicion3:
    # tercera rama
drift:
    # rama por defecto
```

### Ejemplos

```torven
load nota@torq => 85

ignite nota >= 90:
    vent "Excelente"
drift ignite nota >= 70:
    vent "Aprobado"
drift ignite nota >= 60:
    vent "Suficiente"
drift:
    vent "Reprobado"
```

```torven
load temperatura@venom => 36.6

ignite temperatura > 37.5:
    vent "Fiebre"
drift:
    vent "Normal"
```

> **Regla importante:** La indentación define el bloque, igual que en Python.  
> Usa 4 espacios (o un tab) para indentar. Sé consistente.

---

## 7. Bucle while (rev)

`rev` repite el bloque mientras la condición sea verdadera.

### Sintaxis

```torven
rev condicion:
    # código que se repite
```

### Ejemplos

```torven
load i@torq => 1

rev i <= 5:
    vent i
    i => i + 1
```

Salida:
```
1
2
3
4
5
```

Contador regresivo:

```torven
load cuenta@torq => 10

rev cuenta > 0:
    vent cuenta
    cuenta => cuenta - 1

vent "Despegue!"
```

### Romper el bucle (kill)

`kill` es el equivalente a `break`. Sale del bucle inmediatamente.

```torven
load n@torq => 0

rev on:
    ignite n ~~ 5:
        kill
    vent n
    n => n + 1
```

Salida: `0 1 2 3 4`

---

## 8. Bucle for (burn)

`burn` itera sobre una lista o rango.

### Sintaxis

```torven
burn variable in iterable:
    # código por cada elemento
```

### Iterar sobre una lista

```torven
load frutas@barrel => ["manzana", "pera", "uva"]

burn fruta in frutas:
    vent fruta
```

Salida:
```
manzana
pera
uva
```

### Iterar sobre números (con range)

```torven
burn i in range(5):
    vent i
```

Salida: `0 1 2 3 4`

```torven
burn i in range(1, 11):
    vent i
```

Salida: `1 2 3 4 5 6 7 8 9 10`

### Ejemplo con operaciones dentro del bucle

```torven
load numeros@barrel => [1, 2, 3, 4, 5]

burn n in numeros:
    load cuadrado@torq => n ^^ 2
    vent cuadrado
```

Salida: `1 4 9 16 25`

---

## 9. Funciones (forge)

Las funciones se declaran con `forge` y devuelven valores con `eject`.

### Sintaxis

```torven
forge nombre_funcion(param1, param2):
    # cuerpo
    eject resultado
```

Con tipos anotados (recomendado):

```torven
forge nombre_funcion(param1@tipo1, param2@tipo2):
    # cuerpo
    eject resultado
```

### Función simple

```torven
forge saludar(nombre@exhaust):
    vent "Hola,"
    vent nombre

saludar("mundo")
```

### Función que retorna valor

```torven
forge sumar(a@torq, b@torq):
    eject a + b

load resultado@torq => sumar(3, 4)
vent resultado
```

Salida: `7`

### Función con condicional adentro

```torven
forge clasificar(n@torq):
    ignite n > 0:
        eject "positivo"
    drift ignite n ~~ 0:
        eject "cero"
    drift:
        eject "negativo"

vent clasificar(10)
vent clasificar(0)
vent clasificar(-5)
```

Salida:
```
positivo
cero
negativo
```

### Función que usa un bucle

```torven
forge factorial(n@torq):
    load resultado@torq => 1
    load i@torq => 1
    rev i <= n:
        resultado => resultado * i
        i => i + 1
    eject resultado

vent factorial(5)
vent factorial(10)
```

Salida:
```
120
3628800
```

### Llamar a una función desde otra

```torven
forge cuadrado(n@torq):
    eject n ^^ 2

forge suma_cuadrados(a@torq, b@torq):
    eject cuadrado(a) + cuadrado(b)

vent suma_cuadrados(3, 4)
```

Salida: `25`

---

## 10. Listas (barrel)

Las listas son colecciones ordenadas de valores.

### Crear una lista

```torven
load numeros@barrel => [1, 2, 3, 4, 5]
load nombres@barrel => ["Ana", "Beto", "Carla"]
load mixta@barrel   => [1, "dos", on, 3.14]
```

### Iterar una lista

```torven
load colores@barrel => ["rojo", "verde", "azul"]

burn color in colores:
    vent color
```

### Usar len() para saber el tamaño

```torven
load items@barrel => [10, 20, 30, 40]
vent len(items)
```

Salida: `4`

### Lista con range()

```torven
load nums@barrel => list(range(1, 6))

burn n in nums:
    vent n
```

---

## 11. Diccionarios (chassis)

Los diccionarios guardan pares `clave: valor`.

### Crear un diccionario

```torven
load persona@chassis => {"nombre": "Luis", "edad": 25, "activo": on}
```

### Iterar un diccionario

```torven
load config@chassis => {"host": "localhost", "puerto": 8080}

burn clave in config:
    vent clave
```

---

## 12. El operador pipe (->)

El operador `->` pasa el resultado de una expresión como argumento a la siguiente función. Es como una cadena de transformaciones.

### Sintaxis

```torven
valor -> funcion
valor -> funcion1 -> funcion2 -> funcion3
```

Esto es equivalente a:

```torven
funcion3(funcion2(funcion1(valor)))
```

### Ejemplo

```torven
forge duplicar(n@torq):
    eject n * 2

forge incrementar(n@torq):
    eject n + 1

forge mostrar(n@torq):
    vent n
    eject n

load x@torq => 5
vent x -> duplicar
```

Salida: `10`

### Ejemplo con vent y pipe

```torven
forge al_reves(texto@exhaust):
    eject texto

load mensaje@exhaust => "TORVEN"
vent mensaje -> al_reves
```

### Usar pipe para imprimir con transformación

```torven
forge negativo(n@torq):
    eject n * -1

load nums@barrel => [1, 2, 3]

burn n in nums:
    vent n -> negativo
```

Salida: `-1 -2 -3`

---

## 13. Manejo de errores (stall / redline)

### stall = try / except

`stall` protege un bloque de código. Si algo sale mal, `redline` lanza el error.

```torven
stall:
    load x@torq => "esto no es un número"
redline "TypeError: se esperaba torq"
```

### redline = raise / lanzar error

Puedes lanzar errores manualmente con `redline`:

```torven
forge dividir(a@torq, b@torq):
    ignite b ~~ 0:
        redline "Error: no se puede dividir entre cero"
    eject a / b

vent dividir(10, 2)
```

---

## 14. Constantes (lock)

`lock` declara una variable que NO puede cambiar después.

```torven
lock PI@venom       => 3.14159
lock GRAVEDAD@venom => 9.81
lock APP_NAME@exhaust => "MiApp"

vent PI
vent GRAVEDAD
```

Si intentas reasignar una constante, el compilador te dará un error semántico:

```torven
lock MAX@torq => 100
MAX => 200        # ERROR: no puedes modificar una constante lock
```

---

## 15. Tabla de referencia rápida

### Keywords

| TORVEN    | Equivalente Python | ¿Qué hace?                     |
|-----------|--------------------|-------------------------------|
| `load`    | `x =`              | Declarar variable mutable     |
| `lock`    | `const x =`        | Declarar constante            |
| `forge`   | `def`              | Definir función               |
| `eject`   | `return`           | Retornar valor de función     |
| `vent`    | `print()`          | Imprimir en pantalla          |
| `ignite`  | `if`               | Condicional                   |
| `drift`   | `else` / `elif`    | Rama alternativa              |
| `rev`     | `while`            | Bucle mientras condición      |
| `burn`    | `for`              | Bucle para cada elemento      |
| `kill`    | `break`            | Salir del bucle               |
| `idle`    | `pass`             | No hacer nada                 |
| `stall`   | `try`              | Bloque protegido de errores   |
| `redline` | `raise`            | Lanzar error                  |
| `inject`  | `import`           | Importar módulo               |
| `in`      | `in`               | Pertenencia / iteración       |
| `on`      | `True`             | Verdadero                     |
| `off`     | `False`            | Falso                         |
| `void`    | `None`             | Nada / vacío                  |

### Operadores especiales

| Operador | Significado       | Ejemplo         |
|----------|-------------------|-----------------|
| `=>`     | Asignación        | `load x => 5`   |
| `~~`     | Igualdad          | `x ~~ 10`       |
| `!~`     | Diferencia        | `x !~ 0`        |
| `^^`     | Potencia          | `2 ^^ 8`        |
| `->`     | Pipe              | `x -> funcion`  |
| `@tipo`  | Anotación de tipo | `load x@torq`   |

---

## 16. Programa de ejemplo completo

Este programa usa todo lo aprendido:

```torven
# programa_completo.trv

# ---- Funciones ----

forge potencia(base@torq, exp@torq):
    eject base ^^ exp

forge es_par(n@torq):
    ignite n % 2 ~~ 0:
        eject on
    drift:
        eject off

forge clasificar_numero(n@torq):
    ignite n > 100:
        eject "grande"
    drift ignite n > 10:
        eject "mediano"
    drift ignite n > 0:
        eject "pequeño"
    drift ignite n ~~ 0:
        eject "cero"
    drift:
        eject "negativo"

# ---- Constantes ----

lock VERSION@exhaust => "1.0.0"
lock MAX_INTENTOS@torq => 3

vent "TORVEN Demo v"
vent VERSION

# ---- Variables ----

load puntos@torq => 0
load jugador@exhaust => "Mario"

vent jugador

# ---- Bucle for ----

load numeros@barrel => [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

vent "Números pares:"
burn n in numeros:
    ignite es_par(n):
        vent n

# ---- Bucle while ----

load intentos@torq => 0

vent "Contando intentos:"
rev intentos < MAX_INTENTOS:
    vent intentos
    intentos => intentos + 1

# ---- Potencias ----

vent "Potencias de 2:"
burn i in range(1, 9):
    load resultado@torq => potencia(2, i)
    vent resultado

# ---- Clasificacion ----

load valores@barrel => [-5, 0, 7, 15, 200]

vent "Clasificacion:"
burn v in valores:
    load etiqueta@exhaust => clasificar_numero(v)
    vent etiqueta

# ---- Pipe ----

vent "Via pipe:"
load base@torq => 3
vent base -> clasificar_numero
```

Guárdalo como `programa_completo.trv` y corre:

```bash
python -m torven.main exec programa_completo.trv
```

---

## Errores comunes y cómo solucionarlos

| Error que ves | Causa probable | Solución |
|---------------|----------------|----------|
| `[LEX ERROR] Unexpected character` | Usaste un carácter que TORVEN no reconoce | Revisa operadores, usa `=>` no `=` |
| `[TYPE ERROR] Type mismatch` | Declaraste `@torq` pero asignaste un decimal | Cambia el tipo o el valor |
| `[TYPE ERROR] Undefined variable` | Usaste variable antes de declararla con `load` | Declara la variable primero |
| `[TYPE ERROR] Cannot reassign lock` | Intentaste cambiar una constante `lock` | Usa `load` en vez de `lock` |
| `[PARSE ERROR] Unexpected token` | Error de sintaxis | Revisa que uses `:` después de `ignite/forge/rev/burn` |
| La indentación falla | Mezclaste tabs y espacios | Usa solo espacios (4 por nivel) |

---

> **Reglas de oro para no volverse loco:**
> 1. La asignación siempre es `=>`, nunca `=`
> 2. La igualdad siempre es `~~`, nunca `==`
> 3. Los bloques se abren con `:` y se indentan con 4 espacios
> 4. `load` solo se escribe la **primera vez** que declaras una variable
> 5. Para potencias usa `^^`, no `**`

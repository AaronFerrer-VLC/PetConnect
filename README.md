# PetConnect - Plataforma de Cuidado de Mascotas

Plataforma web completa para conectar propietarios de mascotas con cuidadores profesionales. Desarrollada con FastAPI (backend) y React + TypeScript (frontend).

## 📋 Tabla de Contenidos

- [Características](#características)
- [Tecnologías](#tecnologías)
- [Instalación](#instalación)
- [Configuración](#configuración)
- [Uso](#uso)
- [Estructura del Proyecto](#estructura-del-proyecto)
- [API Endpoints](#api-endpoints)
- [Capturas de Pantalla](#capturas-de-pantalla)
- [Tests](#tests)
- [Arquitectura](#arquitectura)

## ✨ Características

- 🔐 **Autenticación y Autorización**: Sistema de login/registro con JWT
- 🔍 **Búsqueda Avanzada**: Búsqueda de cuidadores por ubicación, radio de distancia y filtros
- 📅 **Sistema de Reservas**: Gestión completa de reservas con estados (pending, accepted, completed, cancelled)
- 💳 **Sistema de Pagos**: Integración con Stripe (mock disponible para desarrollo)
- ⭐ **Sistema de Reseñas**: Reseñas para cuidadores, propietarios y mascotas
- 💬 **Mensajería en Tiempo Real**: Chat en tiempo real usando WebSockets
- 📍 **Geolocalización**: Búsqueda por proximidad y geocodificación automática
- 🛡️ **Seguridad**: Rate limiting, validación de inputs, CORS configurado
- 📊 **Dashboard de Pagos**: Visualización de ganancias para cuidadores

## 🛠️ Tecnologías

### Backend

- **FastAPI**: Framework web moderno y rápido
- **MongoDB + Motor**: Base de datos NoSQL con driver async
- **Pydantic**: Validación de datos y serialización
- **JWT**: Autenticación basada en tokens
- **slowapi**: Rate limiting
- **WebSockets**: Mensajería en tiempo real

### Frontend

- **React 18**: Biblioteca de UI
- **TypeScript**: Tipado estático
- **Vite**: Build tool rápido
- **Tailwind CSS**: Framework CSS utility-first
- **React Router**: Navegación
- **WebSocket API**: Comunicación en tiempo real

## 📦 Instalación

### Prerrequisitos

- Python 3.12+
- Node.js 18+
- MongoDB (local o Atlas)

### Backend

```bash
# 1. Navegar a la carpeta del backend
cd petconnect-starter

# 2. Crear entorno virtual
python -m venv .venv

# 3. Activar entorno virtual
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 4. Instalar dependencias
pip install -r requirements.txt

# 5. Crear archivo .env
cp .env.example .env
# o en Windows:
copy .env.example .env

# 6. Editar .env con tus configuraciones (opcional)
# Por defecto usa MongoDB local: mongodb://localhost:27017
```

### Frontend

```bash
# 1. Navegar a la carpeta del frontend
cd petconnect-web-starter

# 2. Instalar dependencias
npm install

# 3. Crear archivo .env (opcional)
cp .env.example .env
```

## ⚙️ Configuración

### Variables de Entorno (.env)

**Backend** (`petconnect-starter/.env`):

```env
APP_NAME=PetConnect
APP_ENV=dev
MONGODB_URI=mongodb://localhost:27017
DB_NAME=petconnect
JWT_SECRET=tu-secreto-super-seguro-aqui
JWT_EXPIRES_HOURS=8
FRONTEND_BASE_URL=http://localhost:5173
BILLING_PROVIDER=mock  # o "stripe" para producción
```

**Frontend** (`petconnect-web-starter/.env`):

```env
VITE_API_URL=http://localhost:8000
```

## 🚀 Uso

### Iniciar MongoDB

Si usas MongoDB local:

```bash
# Windows (si está en PATH):
mongod

# O usar MongoDB Compass que inicia el servidor automáticamente
```

Si usas MongoDB Atlas, actualiza `MONGODB_URI` en el `.env`.

### Iniciar Backend

```bash
cd petconnect-starter
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # macOS/Linux

uvicorn app.main:app --reload
```

El backend estará disponible en: **http://localhost:8000**

- API Docs (Swagger): http://localhost:8000/docs
- Health check: http://localhost:8000/health

### Iniciar Frontend

```bash
cd petconnect-web-starter
npm run dev
```

El frontend estará disponible en: **http://localhost:5173**

## 📁 Estructura del Proyecto

```
petconnect/
├── petconnect-starter/          # Backend (FastAPI)
│   ├── app/
│   │   ├── main.py              # Aplicación principal
│   │   ├── config.py            # Configuración
│   │   ├── db.py                # Conexión MongoDB
│   │   ├── security.py          # Autenticación JWT
│   │   ├── utils.py             # Utilidades
│   │   ├── middleware/          # Middleware (rate limiting)
│   │   ├── routers/             # Endpoints API
│   │   │   ├── auth.py          # Autenticación
│   │   │   ├── users.py         # Usuarios
│   │   │   ├── pets.py          # Mascotas
│   │   │   ├── services.py      # Servicios
│   │   │   ├── bookings.py      # Reservas
│   │   │   ├── payments.py      # Pagos
│   │   │   ├── reviews.py       # Reseñas
│   │   │   ├── messages.py      # Mensajes
│   │   │   ├── websocket.py     # WebSocket
│   │   │   └── ...
│   │   └── schemas/             # Modelos Pydantic
│   ├── tests/                   # Tests automatizados
│   └── requirements.txt
│
└── petconnect-web-starter/      # Frontend (React)
    ├── src/
    │   ├── App.tsx              # Componente principal
    │   ├── pages/               # Páginas
    │   ├── components/           # Componentes reutilizables
    │   └── lib/                 # Utilidades (API, tipos)
    └── package.json
```

## 🔌 API Endpoints Principales

### Autenticación

- `POST /auth/signup` - Registro de usuario
- `POST /auth/login` - Inicio de sesión

### Usuarios

- `GET /users/me` - Perfil del usuario actual
- `PATCH /users/me` - Actualizar perfil
- `GET /users` - Listar usuarios

### Mascotas

- `GET /pets` - Listar mascotas
- `POST /pets` - Crear mascota
- `DELETE /pets/{id}` - Eliminar mascota

### Servicios

- `GET /services` - Listar servicios
- `POST /services` - Crear servicio
- `PATCH /services/{id}` - Actualizar servicio

### Reservas

- `GET /bookings` - Listar reservas
- `POST /bookings` - Crear reserva
- `PATCH /bookings/{id}/status` - Actualizar estado

### Pagos

- `POST /payments` - Crear pago
- `POST /payments/{id}/process` - Procesar pago
- `GET /payments/caretaker/stats` - Estadísticas de pagos

### Reseñas

- `GET /reviews` - Listar reseñas
- `POST /reviews` - Crear reseña
- `PATCH /reviews/{id}` - Actualizar reseña

### Mensajería

- `GET /messages` - Listar mensajes
- `POST /messages` - Enviar mensaje
- `WebSocket /ws/{token}` - Chat en tiempo real

### Búsqueda

- `GET /sitters` - Buscar cuidadores (con filtros de ubicación)

📖 **Documentación completa de la API**: http://localhost:8000/docs (Swagger UI)

## 📸 Capturas de Pantalla

> **Nota**: Añade aquí capturas de pantalla de las funcionalidades principales de tu aplicación.

### Página Principal / Búsqueda

<!-- ![Búsqueda de Cuidadores](docs/screenshots/search.png) -->

### Perfil de Cuidador

<!-- ![Perfil de Cuidador](docs/screenshots/sitter-profile.png) -->

### Sistema de Reservas

<!-- ![Reservas](docs/screenshots/bookings.png) -->

### Chat en Tiempo Real

<!-- ![Mensajería](docs/screenshots/messages.png) -->

### Dashboard de Pagos

<!-- ![Pagos](docs/screenshots/payments.png) -->

## 🧪 Tests

### Ejecutar Tests

```bash
cd petconnect-starter
pytest tests/
```

### Cobertura de Tests

- ✅ Tests de autenticación (signup, login, validación)
- ✅ Tests de pagos (validación de datos)
- ✅ Tests de usuarios
- ✅ Tests de flujo de reservas

**Nota**: Algunos tests async pueden tener problemas en Windows debido a limitaciones de pytest-asyncio. Los tests síncronos funcionan correctamente.

## 🏗️ Arquitectura

### Backend

- **Arquitectura REST**: API RESTful con FastAPI
- **Base de datos**: MongoDB con índices optimizados
- **Autenticación**: JWT con tokens de expiración
- **Rate Limiting**: Protección contra abuso con slowapi
- **WebSockets**: Comunicación bidireccional en tiempo real

### Frontend

- **SPA (Single Page Application)**: React con React Router
- **Estado**: React hooks y contexto
- **Comunicación**: Fetch API y WebSocket nativo
- **UI**: Tailwind CSS para estilos

### Seguridad Implementada

- ✅ Rate limiting en endpoints críticos
- ✅ Validación de inputs con Pydantic
- ✅ CORS configurado por entorno
- ✅ Autenticación JWT
- ✅ Autorización basada en roles
- ✅ Sanitización de datos

## 📚 Documentación Adicional

- [Manual de Instalación](docs/manual_instalación.md)
- [Índice de Memoria](docs/indice_memoria.md)
- [Tests README](tests/README.md)

## 🎓 Proyecto de Fin de Grado

Este proyecto ha sido desarrollado como Trabajo de Fin de Grado (TFG) y demuestra:

- Arquitectura de software moderna
- Integración de tecnologías full-stack
- Implementación de buenas prácticas de desarrollo
- Sistema completo y funcional

## 📝 Licencia

Este proyecto es parte de un trabajo académico.

---

**Desarrollado con ❤️ para el cuidado de mascotas**

# Tests para PetConnect

## Ejecutar tests

```bash
# Instalar dependencias de test (ya incluidas en requirements.txt)
pip install -r requirements.txt

# Ejecutar todos los tests
pytest

# Ejecutar tests con más detalle
pytest -v

# Ejecutar un archivo específico
pytest tests/test_auth.py

# Ejecutar un test específico
pytest tests/test_auth.py::test_signup_success

# Ejecutar con cobertura (requiere pytest-cov)
pytest --cov=app --cov-report=html
```

## Estructura

- `conftest.py`: Configuración y fixtures compartidos
- `test_auth.py`: Tests de autenticación (signup, login)
- `test_payments.py`: Tests de validación de pagos

## Notas

- Los tests usan una base de datos separada (`petconnect_test`)
- La base de datos se limpia antes de cada test
- Rate limiting está deshabilitado en tests


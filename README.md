# 📊 Dashboard Automatizado de Subvenciones Públicas y Privadas (Trivium / MORIARTY)

[![Abrir en Streamlit Cloud](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io/)

👉 **[HAZ CLIC AQUÍ PARA ABRIR O LANZAR LA APLICACIÓN EN STREAMLIT CLOUD](https://share.streamlit.io/)**

*(Si es la primera vez o necesitas desplegarla desde cero en Streamlit Cloud, selecciona el repositorio `mikel-sanz/Dashboard-Subvenciones`, rama `main` y en **Main file path** escribe: `src/visualization/app.py`).*

---

## 🚀 Cómo lanzar la aplicación en tu ordenador (Windows)

### Opción 1: Doble clic (Automático)
Haz doble clic sobre el archivo **`lanzar_dashboard.bat`** situado en la carpeta principal del proyecto. Se abrirá automáticamente en tu navegador en `http://localhost:8501`.

### Opción 2: Desde terminal (PowerShell)
```powershell
.\.venv\Scripts\streamlit.exe run src/visualization/app.py
```

---

## 🧩 Funcionalidades Principales

1. **Ingesta Automatizada Multi-Nivel (Pública y Privada)**:
   - **Unión Europea**: Portal SEDIA (Funding & Tenders), CORDIS, TED y fundaciones europeas (*Fondation Carasso, European Cultural Foundation, Philea, Robert Bosch Stiftung, VolkswagenStiftung, Fondazione Cariplo*).
   - **España**: Base de Datos Nacional de Subvenciones (BDNS) y grandes fundaciones nacionales (*Taller Argal, Fundación ”la Caixa” / CaixaResearch, Fundación BBVA, Fundación Mapfre, Fundación Botín, Fundación Repsol*).
   - **Navarra y Pamplona**: Open Data Navarra (CKAN), Ayuntamiento de Pamplona y ecosistema foral (*Programa Innova, Laboratorios Cinfa, Fundación LuzIA, Consorcio SINAI*).
2. **🌐 Explorador Web de Subvenciones Privadas en Vivo**:
   - Buscador interactivo por palabras clave, ámbito territorial y sector estratégico.
   - Analizador web en tiempo real con protección anti-SSRF que inspecciona cualquier URL de fundación privada, detecta cuantías y fechas e incorpora las convocatorias a la base de datos con un clic.
3. **Clasificador Semántico NLP Local**:
   - Categorización automática en 6 sectores estratégicos con fallback resiliente.
4. **Sistema de Alertas por Correo y Exportación Corporativa**:
   - Notificaciones automáticas tras cada ciclo de ingesta y descarga de informes en **Excel (`.xlsx`)** y **PDF**.

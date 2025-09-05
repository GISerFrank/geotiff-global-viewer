# GeoAI Studio: A Next-Generation Platform for Geospatial AI Data Production

[![Build Status](https://img.shields.io/badge/build-passing-brightgreen)](https://github.com/your-username/your-repo)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)

**GeoAI Studio** is an open-source, end-to-end solution designed to accelerate and scale the production of high-quality datasets for training the next generation of Geospatial Artificial Intelligence (GeoAI) models. Our vision is to become the "Scale AI of the GeoAI field," providing researchers and developers with powerful tools for data annotation, management, and collaboration.

---

### 📖 Table of Contents

* [Vision](#-vision)
* [✨ Key Features](#-key-features)
* [🛠️ Tech Stack](#️-tech-stack)
* [🏗️ System Architecture](#️-system-architecture)
* [🚀 Getting Started](#-getting-started)
* [🗺️ Roadmap](#️-roadmap)
* [🤝 Contributing](#-contributing)
* [📄 License](#-license)

---

### 🎯 Vision

The development of GeoAI currently faces a core bottleneck: the scarcity of high-quality, large-scale, geo-referenced labeled datasets. The mission of **GeoAI Studio** is to solve this challenge. We are not content to be mere "users" of AI; we aim to be "enablers" of the AI industry. This platform provides a comprehensive pipeline—from raw data management and multi-modal data visualization to AI-assisted annotation, team collaboration, and standardized data export—to supply the "data fuel" for a wide range of GeoAI tasks like semantic segmentation, object detection, and change detection.

### ✨ Key Features

* **🌐 Unified Multi-Source Data Management**:
    * Supports automated ingestion and processing from various sources, including local files and Google Drive.
    * Built on PostGIS to create a powerful spatial database for managing multi-source, multi-modal, and heterogeneous data.

* **🗺️ High-Performance 3D Visualization**:
    * Powered by CesiumJS to create a high-performance digital twin of the Earth, enabling smooth loading and rendering of global-scale raster and vector data layers.
    * Supports professional GIS tools like dynamic layer stacking, opacity adjustments, and a spyglass/slider for layer comparison.

* **🖊️ Professional Annotation Toolset**:
    * **Vector Annotation**: Includes tools for Polygons, Bounding Boxes, and Points to meet the needs of various tasks like semantic/instance segmentation and object detection.
    * **Raster Annotation**: Provides brush and eraser tools for efficiently creating pixel-level semantic segmentation masks.

* **🤖 AI-Powered Semi-Automatic Annotation (Planned)**:
    * Integration with foundation models like the Segment Anything Model (SAM) to enable "one-click segmentation," dramatically boosting annotation efficiency.
    * Support for AI pre-labeling and active learning, creating a human-in-the-loop workflow where the model continuously improves.

* **👥 Enterprise-Grade Collaboration & QA (Planned)**:
    * A multi-user system with role-based access control (Annotator, Reviewer, Admin).
    * A built-in "Annotate-Review-Fix" workflow to ensure the highest data quality and compliance standards.

* **📈 Standardized Data Export**:
    * One-click export to industry-standard formats like COCO JSON, YOLO TXT, and Labeled PNG Masks for seamless integration with major AI training frameworks.

### 🛠️ Tech Stack

* **Backend**:
    * **Framework**: Flask
    * **Database**: PostgreSQL + PostGIS Extension
    * **Geospatial Processing**: GDAL, GeoPandas, Rasterio
    * **Async Tasks**: Celery + Redis (Planned)
* **Frontend**:
    * **Core Library**: CesiumJS
    * **Framework/Tools**: Vanilla JavaScript (extendable to React/Vue), Vite, Chart.js
* **DevOps**:
    * Docker, Nginx (Recommended for production deployment)

### 🏗️ System Architecture

```mermaid
graph TD
    A[User Browser] --> B{Frontend UI (CesiumJS)};
    B --> C{Backend API Service (Flask)};
    C --> D[PostgreSQL/PostGIS Database];
    C --> E[File System / Object Storage];
    F[Data Ingestion Scripts] --> D;
    F --> E;

    subgraph "Frontend"
        B
    end

    subgraph "Backend"
        C
    end

    subgraph "Data Storage"
        D
        E
    end

    subgraph "Data Processing"
        F
    end
```

### 🚀 Getting Started

**Prerequisites:**
* Python 3.9+
* Node.js 16+
* PostgreSQL 14+ with the PostGIS extension installed
* Git

**1. Clone the Repository**
```bash
git clone [https://github.com/your-username/your-repo.git](https://github.com/your-username/your-repo.git)
cd your-repo
```

**2. Backend Setup**
```bash
# Navigate to the backend directory
cd backend

# Create and activate a Python virtual environment
python -m venv venv
source venv/bin/activate  # on Windows use `venv\Scripts\activate`

# Install dependencies
pip install -r requirements.txt

# Configure environment variables (create a .env file)
# Add the following content:
# DATABASE_URL=postgresql://<your_username>:<your_password>@localhost:5432/<your_database>
# UPLOAD_FOLDER=path/to/your/data/storage

# Initialize the database (if needed)
# Manually log in to psql and run: CREATE EXTENSION postgis;

# Run the backend service
python app.py
```
The backend service will start on `http://127.0.0.1:5000`.

**3. Frontend Setup**
```bash
# In a new terminal, navigate to the frontend directory
cd frontend

# Install dependencies
npm install

# Start the development server
npm run dev
```
The frontend development server will start on `http://127.0.0.1:5173` (or another available port). Open this URL in your browser to access the platform.

### 🗺️ Roadmap

-   [x] **Q3 2025**: Core platform setup (data ingestion, 3D visualization, API services).
-   [ ] **Q4 2025**: Implement basic vector annotation features (Polygons) and storage.
-   [ ] **Q1 2026**: Integrate an AI-assisted annotation engine (e.g., SAM).
-   [ ] **Q2 2026**: Develop user authentication, project management, and team collaboration modules.
-   [ ] **Q3 2026**: Enhance data export functionality to support more standard formats.

### 🤝 Contributing

We welcome all forms of contributions! Whether it's reporting a bug, suggesting a new feature, or contributing code. Please read our `CONTRIBUTING.md` file for more details.

### 📄 License

This project is licensed under the [MIT License](LICENSE).
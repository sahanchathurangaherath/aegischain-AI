# 🛡️ AegisChain

> **AI-Powered Supply Chain Controller**

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Django](https://img.shields.io/badge/Django-5.0+-green.svg)](https://www.djangoproject.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-teal.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🎯 What is AegisChain?

**AegisChain** is a next-generation AI-powered supply chain controller that combines the reliability of traditional ERP systems with the intelligence of multi-agent AI orchestration. Named after "Aegis" (shield/protection) and "Chain" (supply chain), it provides a protective intelligence layer over supply chain operations.

### The Problem

Modern supply chains suffer from:
- ❌ Poor visibility across ERP systems, warehouses, and suppliers
- ❌ Late detection of risks and disruptions
- ❌ Reactive, manual decision-making
- ❌ Fragmented data across multiple systems
- ❌ Inability to predict shortages or delays

### The AegisChain Solution

✅ **Real-time Intelligence**: Multi-agent AI continuously monitors and analyzes supply chain health  
✅ **Predictive Insights**: Forecast demand (`baseline_ma7`), detect shortages, and flag supplier delays before they happen  
✅ **Explainable AI**: Every decision is transparent, traceable, and backed by ERP data  
✅ **Physical Integration**: QR-based tracking bridges the gap between physical and digital inventory  
✅ **Automated Alerts**: Proactive risk assessments with actionable recommendations  

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Supply Chain Manager                      │
│               (Django Admin & REST API Clients)              │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   AI Orchestration Layer                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  Inventory   │  │   Forecast   │  │  Supplier    │       │
│  │    Agent     │  │    Agent     │  │  Risk Agent  │       │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘       │
│         │                  │                  │              │
│         └──────────────────┴──────────────────┘              │
│                            │                                 │
│                   ┌────────▼────────┐                        │
│                   │   Supervisor    │                        │
│                   │  Orchestrator   │                        │
│                   └─────────────────┘                        │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    ERP Core Backend                          │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐             │
│  │  Inventory │  │Procurement │  │   Sales    │             │
│  │   Module   │  │   Module   │  │   Module   │             │
│  └────────────┘  └────────────┘  └────────────┘             │
│                                                              │
│  🗄️ PostgreSQL Database                                      │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Physical Supply Chain                           │
│  📦 Warehouses  🚚 Shipments  🏭 Suppliers                   │
│  📱 QR Scanners                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Key Features

### 1️⃣ Multi-Agent AI System
- **Inventory Agent**: Detects stock discrepancies, variance, and reorder needs
- **Forecast Agent (`baseline_ma7`)**: Predicts demand using a 7-day moving average baseline and estimates days of supply
- **Supplier Risk Agent**: Assesses delivery delays and supplier reliability
- **Supervisor Orchestrator**: Combines agent insights and synthesizes explainable decisions

### 2️⃣ ERP Core Backend
- Product master data management
- Multi-warehouse inventory tracking
- Purchase order lifecycle management
- Sales order processing
- Shipment tracking with delay detection

### 3️⃣ QR-Based Physical Tracking
- Real-time inventory movements (`IN` / `OUT` / `AUDIT` / `TRANSFER` / `ADJUSTMENT`)
- Automatic balance updates
- Variance detection triggers AI analysis

### 4️⃣ Intelligent Orchestration
- Rule-based intent classification
- Parallel agent execution
- Context-aware risk aggregation
- Structured execution logging

---

## 🛠️ Technology Stack

| Layer | Technologies |
|-------|-------------|
| **AI Layer** | FastAPI, Python 3.12, Pydantic v2, HTTPX, Structlog |
| **Backend** | Django 5.0+, Django REST Framework, `drf-spectacular` |
| **Database** | PostgreSQL 16 (`pgvector/pgvector:pg16`) |
| **Packaging & Lint** | `uv`, `ruff`, `mypy` |
| **Testing** | `pytest`, `pytest-asyncio`, `pytest-django`, `respx` |
| **DevOps** | Docker, Docker Compose v2, GitHub Actions |

---

## 📦 Installation

### Prerequisites
- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/)
- PostgreSQL 16+
- Docker & Docker Compose v2

### Quick Start (Docker — Recommended)

1. **Clone the repository and configure environment**
```bash
git clone https://github.com/sahanchathurangaherath/aegischain-AI.git
cd aegischain-AI
cp .env.example .env
```

2. **Start services using the Makefile**
```bash
make up        # Build and start containers
make seed      # Seed sample supply chain data
make test      # Run test suite
make lint      # Run ruff check and format check
make logs      # View container logs
make down      # Stop containers
```

3. **Access the system**
- Django Admin: `http://localhost:8000/admin`
- ERP API Schema: `http://localhost:8000/api/schema/swagger-ui/`
- AI Service Docs: `http://localhost:8001/docs`

### Manual Local Setup

1. **Backend Setup (Django)**
```bash
cd erp_core
uv sync
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

2. **AI Layer Setup (FastAPI)**
```bash
cd aegis_ai
uv sync
uv run uvicorn main:app --reload --port 8001
```

---

## 🎯 Use Cases

### Manufacturing
- Real-time production material tracking
- Supplier delay impact on production schedule
- Just-in-time inventory optimization

### Retail
- Multi-location inventory visibility
- Demand forecasting for seasonal products
- Stock transfer optimization

### E-commerce
- Warehouse stock synchronization
- Fulfillment center coordination
- Supplier performance monitoring

### Automotive
- Critical parts shortage prediction
- Supplier tier risk management
- Production line material planning

---

## 🧪 Example Workflows

### 1. QR Scan Triggers AI Analysis
```
Worker scans QR code → Inventory updated → 
Variance detected → Agents analyze → 
Risk assessment returned → Manager notified
```

### 2. Automated Shortage Prediction
```
Forecast Agent (baseline_ma7) predicts demand → 
Inventory Agent checks stock → 
Shortage detected in 7 days → 
Recommendation: Expedite PO
```

### 3. Supplier Risk Assessment
```
Shipment delayed → Supplier Risk Agent evaluates → 
Pattern of delays detected → 
Alert: High risk supplier → 
Recommendation: Evaluate alternative supplier
```

---

## 🎓 Learning Outcomes

Building AegisChain demonstrates mastery of:

✅ **Backend & API Development**: Django 5, Django REST Framework, FastAPI  
✅ **AI/ML Integration**: Multi-agent systems, parallel orchestration  
✅ **Supply Chain Architecture**: ERP domain modeling, inventory & procurement workflows  
✅ **Data Engineering**: Transactional integrity, PostgreSQL modeling  
✅ **DevOps & Quality**: Containerization, automated CI testing, reproducible dependency locking  
✅ **Product Thinking**: Real-world supply chain problem solving  

---

## 🤝 Contributing

We welcome contributions! Please feel free to open an issue or submit a pull request.

---

## 📝 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

Inspired by supply chain control tower systems like:
- SAP S/4HANA Supply Chain Control Tower
- Oracle Supply Chain Management Cloud
- Blue Yonder Luminate Control Tower
- Kinaxis RapidResponse

Built with modern AI capabilities to democratize supply chain intelligence.

---

<div align="center">

### ⭐ Star this repo if you find it helpful!

Built with ❤️ for the future of intelligent supply chains

</div>

# Plagiarism Analysis Application

Live Preview  
https://plagiarismanalyser-d8a6d0f9f2deczhn.southindia-01.azurewebsites.net/



## Project Overview

The Plagiarism Analysis Application is a full-stack web platform designed to detect, analyze, and manage plagiarism in academic and professional documents. It supports multiple file formats, role-based access, secure authentication, and AI-assisted analysis workflows.

The application allows users to:

- Upload documents for plagiarism analysis
- View analysis results and similarity insights
- Manage users with admin and student roles
- Reset, reseed, and maintain database consistency
- Perform OCR-based analysis for scanned documents
- Maintain a clean and predictable development environment

This project demonstrates a production-grade full-stack system using modern backend and frontend technologies.

---

## Key Features

- Role-based access with admin and student roles
- Secure JWT-based authentication
- Multi-format document upload support
- AI-assisted plagiarism analysis
- Database seeding with default users
- Safe database resets without schema loss
- Frontend dashboards for uploads and results
- Predictable development and restart workflow

---

## Tech Stack

### Backend
- FastAPI for REST APIs and authentication
- SQLAlchemy for ORM and database interaction
- PostgreSQL for data storage
- JWT for secure authentication
- Gemini API for OCR and text analysis
- Uvicorn as ASGI server

### Frontend
- React for user interface and dashboards

---

## Project Architecture

The application follows a clean client-server architecture with role-based access and secure communication.

### High-Level Architecture Flow

- React frontend handles user interaction and dashboards
- FastAPI backend exposes secure REST APIs
- JWT tokens manage authentication and authorization
- PostgreSQL stores users, documents, and analysis results
- Gemini API performs OCR and plagiarism analysis
- Backend validates roles before every protected action

### Architecture Layers

- Presentation Layer
  - React components
  - Role-based routing
  - Secure token storage

- Application Layer
  - FastAPI routes
  - Authentication and authorization
  - File upload and validation
  - Analysis orchestration

- Service Layer
  - AI plagiarism analysis
  - OCR processing
  - Report generation

- Data Layer
  - PostgreSQL database
  - SQLAlchemy ORM
  - Secure hashed credentials

---

## API Endpoints Overview

### Authentication APIs

- POST /auth/login  
  - Authenticates user
  - Returns JWT token with role and user details

- GET /auth/validate-token  
  - Validates JWT token
  - Used for session persistence

---

### Document Management APIs

- POST /upload  
  - Upload document for plagiarism analysis
  - Protected by authentication

- GET /analysis-status/{document_id}  
  - Polls plagiarism analysis status
  - Returns similarity score and summary

- GET /download/{document_id}  
  - Download analyzed document
  - Role-based access enforced

---

### Admin APIs

- GET /admin/dashboard  
  - Fetches all uploaded documents
  - Admin-only access

- GET /admin/users  
  - Lists all users
  - Admin-only access

---

### Student APIs

- GET /student/documents  
  - Fetches documents uploaded by logged-in student only

---

## Security Design

- JWT-based authentication
- Role-based access control at backend level
- Secure password hashing
- Token validation on every protected API
- CORS configuration for frontend-backend isolation
- No sensitive data exposed to frontend

---

## Development Best Practices Followed

- Modular backend structure
- Centralized database service
- Token-based frontend API calls
- Predictable reset and seeding flow
- Clean separation of concerns
- Production-grade error handling



---

## Backend Setup

Create and Activate Virtual Environment

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
```

You should see:
```
(venv)
```

Install Backend Dependencies:
```
pip install -r requirements.txt
```
Start Backend Server:
```
uvicorn main:app --reload
```
Backend runs at:
```
http://127.0.0.1:8000
```
---
## Frontend Setup


Navigate to Frontend Directory
```
cd frontend
```

Install Dependencies:
```
npm install
```

Start Frontend Server:
```
npm start
```


Frontend runs at:
```
http://localhost:3000
```
---


## Database Setup


Enter PostgreSQL Shell:
```
psql -U postgres
```

If your database name is plagiarism_db:
```
\c plagiarism_db;
```

Run:
```
psql -U username -d dbname -f schema.sql
```
```
TRUNCATE TABLE analysis_results CASCADE;
TRUNCATE TABLE documents CASCADE;
TRUNCATE TABLE users CASCADE;
```


---

## Database Seeding (seed.py)

Purpose: seed.py creates default admin and student users with known credentials for testing, demos, and development.

```
python seed.py
```

## Example Seeded Accounts


| Role    | Username      | Password   |
|---------|---------------|------------|
| Admin   | admin-001     | admin123   |
| Admin   | admin-002     | admin123   |
| Student | student-001   | student123 |
| Student | student-002   | student123 |

Run Seeding Script:
```
cd backend
```
```
python seed.py
```

Expected Output:

- Admin users created
- Student users created
- Database seeding completed
---

## Changing Passwords (Recommended Method)

Truncate users & documents (SQL above)
Modify credentials inside seed.py

Re-run:
```
python seed.py
```

- Passwords are hashed automatically
- No manual SQL updates required
---

## Full Restart Flow (Recommended)


-Stop backend & frontend
-Truncate users, documents, analysis_results
-Run seed.py
-Start backend
-Start frontend

- Guarantees a clean, predictable state
- Avoids token, cache & mismatch issues
---
## Supported File Types


- PDF (text & scanned)
- DOC / DOCX
- PPT / PPTX
- PDF (Imagescanner/Digital)
- TXT
- Images (OCR via Gemini)

---

## Deployment


- Backend deployed on Azure App Service
- Frontend deployed with backend integration
- Environment-based configuration
- Production-ready CORS and security settings

<h3 align="center">Landing & Login Page</h3>

<p align="center">
   <img src="https://raw.githubusercontent.com/iprashanthvanam/plagiarism_analysis_app/main/images/1769236967149.jpg" width="60%" />
  
</p>
<h3 align="center">Admin Dashboard</h3>

<p align="center">
  <img src="https://raw.githubusercontent.com/iprashanthvanam/plagiarism_analysis_app/main/images/1769236964970.jpg" width="60%" />
 
</p>
<h3 align="center">Student Dashboard</h3>

<p align="center">
   <img src="https://raw.githubusercontent.com/iprashanthvanam/plagiarism_analysis_app/main/images/1769236965169.jpg" width="60%" />
 
</p>
<h3 align="center">Student Analysis Dashboard</h3>

<p align="center">
  <img src="https://raw.githubusercontent.com/iprashanthvanam/plagiarism_analysis_app/main/images/1769236965138.jpg" width="60%" />
</p>
<h3 align="center">Admin Analysis Dashboard</h3>

<p align="center">
   <img src="https://raw.githubusercontent.com/iprashanthvanam/plagiarism_analysis_app/main/images/1769236965162.jpg" width="60%" />
 
</p>
<h3 align="center">Plagiarism Analysis Results</h3>

<p align="center">
   <img src="https://raw.githubusercontent.com/iprashanthvanam/plagiarism_analysis_app/main/images/1769236964998.jpg" width="60%" />
 
</p>
<h3 align="center">Plagiarism Report</h3>

<p align="center">
  <img src="https://raw.githubusercontent.com/iprashanthvanam/plagiarism_analysis_app/main/images/Screenshot from 2026-02-09 11-45-15.png" width="60%" />
</p>

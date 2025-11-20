# Improve My City – Backend API

A fast, scalable, enterprise-grade REST API powering the **Improve My City** platform. Built with FastAPI, PostgreSQL, and modern Python best practices for municipal issue reporting and management.

This project was created as part of **HackArena 2025, hosted by Masaiverse × NoBroker**.

---

## 🌐 Live API

[![Backend Live](https://img.shields.io/badge/Backend-API-blue)](https://imcb.varunanalytics.com/)

**API Base URL:**  
https://imcb.varunanalytics.com/

**API Documentation:**
- **Swagger UI:** https://imcb.varunanalytics.com/docs
- **ReDoc:** https://imcb.varunanalytics.com/redoc

---

## 🛠️ Tech Stack

### Core Framework
- **FastAPI** - Modern, fast web framework for building APIs
- **Python 3.11** - Latest Python features and performance
- **Uvicorn** - ASGI server for production deployment

### Database & ORM
- **PostgreSQL** - Robust relational database (Supabase managed)
- **SQLAlchemy 2.0** - Modern ORM with async support
- **Alembic** - Database migration tool
- **psycopg3** - High-performance PostgreSQL adapter

### Authentication & Security
- **JWT (PyJWT)** - Token-based authentication
- **bcrypt** - Secure password hashing
- **slowapi** - Rate limiting middleware
- **CORS** - Cross-origin resource sharing

### Services & Integrations
- **SMTP** - Email delivery (Gmail, SendGrid, or custom SMTP)
- **VAPID (pywebpush)** - Web Push Notifications
- **Supabase Storage** - Image storage for issue photos
- **Google Maps API** - Location services (via frontend)

### Validation & Configuration
- **Pydantic** - Data validation and settings management
- **pydantic-settings** - Environment variable management

### Development Tools
- **Ruff** - Fast Python linter
- **Black** - Code formatter
- **pytest** - Testing framework
- **httpx** - HTTP client for testing

---

## 🏗️ Architecture

### API Structure

```
/api
├── /auth              # Authentication endpoints
│   ├── POST /register
│   ├── POST /login
│   ├── POST /forgot
│   ├── POST /reset
│   └── POST /verify
│
├── /issues            # Issue management
│   ├── GET /          # List issues (with filters)
│   ├── POST /         # Create issue
│   ├── GET /{id}      # Get issue details
│   ├── PATCH /{id}/status
│   ├── POST /{id}/comments
│   ├── GET /{id}/comments
│   ├── GET /{id}/activity
│   ├── GET /{id}/related
│   └── POST /bulk     # Bulk operations
│
├── /issues/stats      # Analytics endpoints
│   ├── GET /summary
│   ├── GET /by-type
│   ├── GET /by-state
│   └── GET /by-type-status
│
├── /admin             # Admin endpoints
│   ├── /users         # User management
│   ├── /issue-types   # Issue type management
│   ├── /settings      # App settings
│   └── /regions       # Region management
│
├── /bot               # Chatbot API
│   └── POST /chat
│
├── /push              # Push notifications
│   ├── POST /subscribe
│   └── POST /unsubscribe
│
└── /public            # Public endpoints
    ├── GET /settings
    └── GET /issue-types
```

### Database Models

- **users** - User accounts (admin, staff, citizen)
- **issues** - Issue reports with location, status, assignment
- **issue_types** - Issue categories with descriptions and colors
- **issue_attachments** - Photo attachments for issues
- **issue_activity** - Activity timeline for issues
- **staff_regions** - Region assignments for staff
- **app_settings** - Application configuration
- **push_subscriptions** - Web push notification subscriptions

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.11+**
- **PostgreSQL 14+** (or Supabase account)
- **pip** for dependency management

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/vs-ai-ds/improve-my-city-backend
   cd improve-my-city-backend
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   
   # On Windows
   venv\Scripts\activate
   
   # On macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   
   Create `.env` file (refer to `.env.example` for all available variables):
   ```bash
   cp .env.example .env
   # Edit .env with your actual values
   ```

5. **Run database migrations**
   ```bash
   alembic upgrade head
   ```

6. **Start development server**
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

   The API will be available at `http://localhost:8000`
   - Swagger UI: `http://localhost:8000/docs`
   - ReDoc: `http://localhost:8000/redoc`

---

## 🔧 Environment Variables

All environment variables are documented in `.env.example`. Key variables include:

### Required
- `DATABASE_URL` - PostgreSQL connection string
- `JWT_SECRET` - Secret key for JWT token signing

### Email Configuration (SMTP)
- `SMTP_HOST` - SMTP server hostname
- `SMTP_PORT` - SMTP port (587 for TLS, 465 for SSL)
- `SMTP_USERNAME` - SMTP authentication username
- `SMTP_PASSWORD` - SMTP authentication password
- `SMTP_USE_SSL` - Use SSL (true/false)
- `EMAIL_FROM_NAME` - Sender display name
- `EMAIL_FROM_ADDRESS` - Sender email address

### Push Notifications (VAPID)
- `VAPID_PUBLIC_KEY` - VAPID public key
- `VAPID_PRIVATE_KEY` - VAPID private key
- `VAPID_SUB` - VAPID subject (mailto: format)

### Storage (Supabase)
- `SUPABASE_URL` - Supabase project URL

### Application
- `FRONTEND_BASE_URL` - Frontend application URL
- `BACKEND_CORS_ORIGINS` - Comma-separated allowed origins

See `.env.example` for complete list and descriptions.

---

## 📊 Database Migrations

This project uses **Alembic** for database schema management.

### Running Migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Create a new migration
alembic revision --autogenerate -m "description"

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history

# Check current revision
alembic current
```

### Recent Migrations

- `add_issue_type_fields` - Adds description, color, display_order to issue_types
- `add_settings_fields` - Adds SLA, branding, and notification settings
- `add_email_from_name_to_app_settings` - Adds email sender name field

---

## 🧪 API Testing

### Using Swagger UI

1. Navigate to `http://localhost:8000/docs`
2. Click "Authorize" and enter your JWT token
3. Test endpoints directly from the browser

### Using curl

```bash
# Health check
curl http://localhost:8000/health

# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password"}'

# Get issues (with auth token)
curl http://localhost:8000/issues \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```
---

## ☁️ Deployment

### Option 1: Render (Recommended)

**Render** provides seamless deployment with automatic SSL, zero-downtime deployments, and managed PostgreSQL.

1. **Connect Repository**
   - Link your GitHub repository to Render
   - Select "Web Service"

2. **Configure Build**
   ```bash
   Build Command: pip install -r requirements.txt && alembic upgrade head
   Start Command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```

3. **Environment Variables**
   - Add all required variables from `.env.example`
   - Use Render's environment variable management
   - For secrets, use Render's secret management

4. **Database**
   - Create a PostgreSQL database in Render
   - Use the connection string in `DATABASE_URL`

5. **Deploy**
   - Render automatically deploys on every push to main branch
   - Preview deployments for pull requests

**Benefits:**
- Automatic HTTPS
- Zero-downtime deployments
- Managed PostgreSQL
- Free tier available
- Easy scaling

### Option 2: Google Cloud Run

1. **Build Docker Image**
   ```bash
   docker build -t improve-my-city-backend .
   ```

2. **Push to Container Registry**
   ```bash
   gcloud builds submit --tag gcr.io/PROJECT_ID/improve-my-city-backend
   ```

3. **Deploy to Cloud Run**
   ```bash
   gcloud run deploy improve-my-city-backend \
     --image gcr.io/PROJECT_ID/improve-my-city-backend \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated
   ```

4. **Configure Secrets**
   - Use Google Secret Manager for sensitive variables
   - Set environment variables in Cloud Run service

**Benefits:**
- Serverless scaling
- Pay per request
- Integrated with Google Cloud services
- Global CDN

---

## 🔐 Security Features

### Authentication
- **JWT Tokens**: Secure token-based authentication
- **Password Hashing**: bcrypt with salt rounds
- **Email Verification**: Required for account activation
- **Password Reset**: Secure token-based reset flow

### Rate Limiting
- **Issue Creation**: 10 requests per minute per user
- **API Endpoints**: 20 requests per minute
- **Configurable**: Adjust limits in `app/core/ratelimit.py`

### Data Protection
- **Input Validation**: Pydantic models for all inputs
- **SQL Injection Prevention**: SQLAlchemy ORM parameterized queries
- **CORS Protection**: Configurable allowed origins
- **Duplicate Detection**: Prevents duplicate issue creation (50m radius, 2 hours)

### Role-Based Access Control
- **Super Admin**: Full system access
- **Admin**: User and issue management
- **Staff**: Assigned issues management
- **Citizen**: Issue reporting and tracking

---

## 📡 Services Integration

### Email Service (SMTP)

The backend supports SMTP for email delivery. Configure in `.env`:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_USE_SSL=false
EMAIL_FROM_NAME=Improve My City
EMAIL_FROM_ADDRESS=noreply@yourdomain.com
```

**Email Types:**
- Email verification
- Password reset
- Issue creation confirmation
- Status change notifications
- Assignment notifications

### Push Notifications (VAPID)

Web Push Notifications using VAPID protocol:

1. **Generate VAPID Keys**
   ```bash
   npm install -g web-push
   web-push generate-vapid-keys
   ```

2. **Configure in `.env`**
   ```env
   VAPID_PUBLIC_KEY=your-public-key
   VAPID_PRIVATE_KEY=your-private-key
   VAPID_SUB=mailto:admin@yourdomain.com
   ```

**Notification Types:**
- Issue status changes
- Assignment notifications
- Comment notifications

### Storage (Supabase)

Image storage for issue photos:

1. **Create Supabase Project**
2. **Create Storage Bucket** (default: `issue-photos`)
3. **Configure in `.env`**
   ```env
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_SERVICE_ROLE=your-service-role-key
   SUPABASE_BUCKET=issue-photos
   ```

**Features:**
- Automatic image upload
- Public URL generation
- File type validation (JPEG, PNG, WebP, GIF)
- Size limits (2MB per file, 10 files per issue)

---

## 🎯 Key Features

### Issue Management
- **CRUD Operations**: Create, read, update, delete issues
- **Status Workflow**: Pending → In Progress → Resolved
- **Assignment**: Assign issues to staff by region/workload
- **Comments**: Threaded comments with user attribution
- **Activity Timeline**: Complete audit trail of all changes
- **Related Issues**: Find similar issues within 50m radius
- **Bulk Operations**: Assign, update status, delete multiple issues
- **Duplicate Detection**: Prevent duplicate reports (same location + type within 2 hours)

### Analytics & Statistics
- **Summary Stats**: Total, pending, in-progress, resolved counts
- **By Type**: Issue breakdown by category
- **By Region**: Issue breakdown by state/region
- **By Status**: Status distribution
- **Time Ranges**: Today, 7d, 15d, 30d, 90d, all-time
- **Filtered Queries**: All stats respect current filters

### User Management
- **Role Management**: Super Admin, Admin, Staff, Citizen
- **User Profiles**: Complete user information and stats
- **Bulk Operations**: Activate, deactivate, assign regions, delete
- **Password Reset**: Admin-triggered password resets
- **Region Assignment**: Assign staff to specific regions

### Auto-Assignment
- **Smart Assignment**: Automatically assign issues based on:
  - Region/state code matching
  - Staff workload (least open issues)
  - Issue type expertise
- **Fallback Chain**: Staff → Admin → Super Admin
- **Configurable**: Enable/disable in app settings

### Issue Types Management
- **Rich Metadata**: Description, color, display order
- **Analytics**: Per-type statistics and trends
- **Reordering**: Drag-and-drop support via API
- **Protection**: Prevent deletion of types with existing issues

### Settings Management
- **SLA Configuration**: Default SLA hours and reminder settings
- **Branding**: City logo, support email, website URL
- **Notifications**: Email and push notification toggles
- **Feature Flags**: Enable/disable features

---

## 📁 Project Structure

```
improve-my-city-backend/
├── app/
│   ├── core/              # Core configuration
│   │   ├── config.py      # Settings and environment variables
│   │   ├── security.py    # Authentication and authorization
│   │   └── ratelimit.py  # Rate limiting middleware
│   │
│   ├── db/                # Database configuration
│   │   ├── base.py        # SQLAlchemy base
│   │   └── session.py    # Database session management
│   │
│   ├── models/            # SQLAlchemy models
│   │   ├── user.py        # User model
│   │   ├── issue.py       # Issue model
│   │   ├── issue_type.py  # Issue type model
│   │   ├── issue_activity.py  # Activity timeline
│   │   ├── attachment.py   # Image attachments
│   │   ├── region.py      # Region assignments
│   │   ├── app_settings.py # App configuration
│   │   └── push.py        # Push subscriptions
│   │
│   ├── routers/           # API route handlers
│   │   ├── auth.py        # Authentication endpoints
│   │   ├── issues.py      # Issue management
│   │   ├── issues_stats.py # Analytics endpoints
│   │   ├── admin_users.py  # Admin user management
│   │   ├── issue_types.py  # Issue type management
│   │   ├── settings.py     # Settings management
│   │   ├── regions.py      # Region management
│   │   ├── push_subscriptions.py # Push notifications
│   │   ├── bot.py          # Chatbot API
│   │   └── public.py       # Public endpoints
│   │
│   ├── schemas/           # Pydantic models
│   │   ├── auth.py        # Auth request/response models
│   │   ├── issue.py       # Issue models
│   │   └── user.py         # User models
│   │
│   ├── services/          # Business logic
│   │   ├── notify_email.py    # Email service
│   │   ├── notify_push.py     # Push notification service
│   │   └── storage.py         # Image storage service
│   │
│   └── main.py           # FastAPI application
│
├── alembic/              # Database migrations
│   ├── versions/        # Migration files
│   └── env.py          # Alembic configuration
│
├── scripts/             # Utility scripts
├── Dockerfile          # Container configuration
├── requirements.txt    # Python dependencies
├── alembic.ini        # Alembic configuration
└── .env.example       # Environment variables template
```

---

## 🔄 API Workflow Examples

### Issue Creation Flow

1. **User submits issue** → `POST /issues`
2. **Backend validates** → Check location, category, files
3. **Duplicate detection** → Check for similar issues within 50m
4. **Create issue** → Save to database
5. **Upload images** → Store in Supabase
6. **Auto-assign** → Assign to staff based on region/workload
7. **Send notifications** → Email confirmation + push notification
8. **Return issue** → Return created issue with ID

### Status Update Flow

1. **Staff updates status** → `PATCH /issues/{id}/status`
2. **Validate permission** → Check if user can modify
3. **Update status** → Update in database
4. **Create activity** → Log in activity timeline
5. **Send notifications** → Email + push to creator
6. **Return updated issue** → Return with new status

---

## 🧪 Testing

### Manual Testing Checklist

- [ ] Authentication (register, login, verify, reset)
- [ ] Issue creation with photos
- [ ] Issue status updates
- [ ] Comments creation and retrieval
- [ ] Email notifications
- [ ] Push notifications
- [ ] Admin user management
- [ ] Bulk operations
- [ ] Analytics endpoints
- [ ] Rate limiting
- [ ] Duplicate detection

---

## 📚 API Documentation

### Interactive Documentation

- **Swagger UI**: `/docs` - Interactive API explorer
- **ReDoc**: `/redoc` - Alternative documentation format

### Authentication

Most endpoints require authentication via JWT token:

```http
Authorization: Bearer YOUR_JWT_TOKEN
```

### Response Format

**Success Response:**
```json
{
  "id": 123,
  "title": "Pothole on Main Street",
  "status": "pending",
  ...
}
```

**Error Response:**
```json
{
  "detail": "Error message here"
}
```

---

## 🐛 Troubleshooting

### Common Issues

**Database Connection Error**
- Check `DATABASE_URL` in `.env`
- Verify PostgreSQL is running
- Check network connectivity

**Migration Errors**
- Ensure database is up to date: `alembic upgrade head`
- Check for conflicting migrations
- Review migration files in `alembic/versions/`

**Email Not Sending**
- Verify SMTP credentials
- Check SMTP server allows connections
- Review email service logs

**Push Notifications Not Working**
- Verify VAPID keys are correct
- Check browser console for errors
- Ensure HTTPS in production (required for push)

---

## 📝 Code Style

- Follow **PEP 8** Python style guide
- Use **Black** for code formatting
- Use **Ruff** for linting
- Type hints for all functions
- Docstrings for public functions
- No `[AI]` comments or special markers

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and linting (`pytest` and `ruff check`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License. See the `LICENSE` file for details.

---

## 🙏 Acknowledgments

- Built for **HackArena 2025** (Masai x NoBroker)
- Powered by **FastAPI** and **PostgreSQL**
- Deployed on **Render** for reliable hosting
- Uses **Supabase** for storage and database
- **VAPID** for web push notifications
- **SMTP** for email delivery

---

## 📞 Support

For issues, questions, or contributions, please open an issue on GitHub.

---

**Last Updated:** November 2025

# StoryTog — Backend API

**The API behind collaborative storytelling.**

StoryTog is a platform where writers create stories together, one chapter at a time. Writers can submit a continuation to an existing story, and its current authors review and vote on whether the proposed chapter should be accepted.

**[Try StoryTog](https://storytog.netlify.app)** · **[Angular frontend](https://github.com/NITSOMA/storytogFront)**

## The collaborative writing workflow

1. A registered writer creates a story and publishes its first chapter.
2. Another writer submits a proposed continuation chapter.
3. Existing story authors review the proposal and vote.
4. The chapter requires approval from **more than 50% of existing authors** before acceptance.

For four existing authors, that means **three approvals**. This majority rule gives contributors a voice in how their shared story develops.

## Technologies

- **Python** and **Django 6**
- **Django REST Framework** for the API
- **Simple JWT** for token-based authentication
- **PostgreSQL** for persistent data
- **Django Channels** and **Redis** for real-time infrastructure
- **Cloudinary** for media storage

## Backend structure

| Django app | Responsibility |
| --- | --- |
| `users` | Accounts, authentication, and profiles |
| `storyapp` | Stories, chapters, chapter requests, and approval workflows |
| `social` | Social interactions such as comments and votes |
| `writespace` | Project configuration, URL routing, and ASGI/WSGI setup |

The API is organized under `/user/`, `/story/`, and `/social/`. Individual endpoints have authentication and permission requirements appropriate to their operations.

## Authentication

StoryTog uses JWT access tokens and refresh tokens. Refresh tokens are stored in HTTP-only cookies, and token rotation and blacklisting are configured in the backend.

## Run locally

**Prerequisites:** A compatible Python installation, PostgreSQL, and Redis. You will also need development credentials for any configured external services.

```bash
git clone https://github.com/NITSOMA/storytog.git
cd storytog
python -m venv .venv
```

Activate the virtual environment:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file in the project root with your **own development values**:

```dotenv
SECRET_KEY=your-local-development-secret
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:4200

DB_NAME=your_database
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DB_HOST=localhost
DB_PORT=5432

REDIS_URL=redis://localhost:6379/0

CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
```

Never commit `.env` files or real credentials to version control. Ensure PostgreSQL and Redis are running, then start the application:

```bash
python manage.py migrate
python manage.py runserver
```

The local API runs at **http://localhost:8000** by default.

## Tests

Run Django's test command with:

```bash
python manage.py test
```

## Deployment

The backend is hosted on **Render**, with configuration provided through environment variables. The Angular frontend is hosted on **Netlify**.

---

**Frontend source:** [github.com/NITSOMA/storytogFront](https://github.com/NITSOMA/storytogFront)

---
name: devops
description: >-
  Use this skill when configuring Docker containers, Docker Compose stacks, environment variable files, Redis worker processes, or deployment health check scripts.
---

# DevOps & Infrastructure Skill

## 1. Purpose & Scope
Guide local development container setups, Dockerfiles, environment variable management, health check endpoints, and worker service orchestration.

## 2. Activation Triggers
Activate when modifying Docker Compose configuration, setting up environment variable templates (`.env.example`), adding background worker processes, or building health check scripts.

## 3. Inspection Targets
- [`ARCHITECTURE.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/ARCHITECTURE.md) (Container architecture & background worker specs)
- [`DEVELOPMENT.md`](file:///c:/Users/ascora/Desktop/maher/Car-Export-CRM/DEVELOPMENT.md) (Local setup blueprint)

## 4. Constraints
- **Infrastructure Simplicity**: Only approve Docker Compose setups with PostgreSQL, Redis, FastAPI web server, and background worker containers.
- **Secret Protection**: Secrets MUST NEVER be committed to Git. Provide explicit `.env.example` templates.
- **Health Checks**: Web service containers MUST provide a `/health` endpoint checking DB and Redis ping status.

## 5. Execution Procedure
1. Define clean multi-stage `Dockerfile` for backend and frontend.
2. Maintain `docker-compose.yml` declaring `postgres`, `redis`, `backend`, and `worker` services.
3. Verify environment variable loading via Pydantic `BaseSettings`.

## 6. Expected Outputs
- Validated `docker-compose.yml` and `.env.example` configurations.
- Working container definitions and health check endpoints.

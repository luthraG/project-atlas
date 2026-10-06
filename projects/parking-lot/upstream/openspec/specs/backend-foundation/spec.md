# backend-foundation Specification

## Purpose
TBD - created by archiving change foundation. Update Purpose after archive.
## Requirements
### Requirement: Health endpoint
The backend SHALL expose a `GET /health` endpoint that reports service availability
without requiring authentication.

#### Scenario: Healthy service responds
- **WHEN** a client calls `GET /health` on a running service
- **THEN** the service responds with a 200 status and a healthy payload

### Requirement: Async PostgreSQL persistence
The backend SHALL provide an async SQLAlchemy 2.0 persistence layer configured for
PostgreSQL, including a session factory and an engine built from application settings.

#### Scenario: Session factory is available
- **WHEN** the application starts
- **THEN** an async session can be created from the configured engine

### Requirement: Database migrations
The backend SHALL use Alembic to manage schema migrations against the configured
PostgreSQL database.

#### Scenario: Migration environment is configured
- **WHEN** a migration is generated
- **THEN** Alembic produces a migration script bound to the async engine

### Requirement: Authentication scaffolding
The backend SHALL provide password hashing (Argon2id) and JWT token creation and
verification primitives for authenticating operators.

#### Scenario: Password is hashed and verified
- **WHEN** a plaintext password is hashed
- **THEN** the hash verifies against the original password and rejects an incorrect one

#### Scenario: JWT roundtrip
- **WHEN** a token is issued for a subject
- **THEN** the token decodes back to the same subject and rejects an invalid token

### Requirement: Hexagonal backend structure
The backend SHALL organize code by feature following Hexagonal Clean Architecture,
with `domain/`, `application/`, `infrastructure/`, and `presentation/` layers where
`domain/` SHALL NOT depend on any outer layer.

#### Scenario: Backend layer boundaries hold
- **WHEN** a backend feature is created
- **THEN** it contains the four layers and `domain/` has no imports from outer layers


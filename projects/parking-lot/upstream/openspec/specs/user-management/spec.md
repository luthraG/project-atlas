# user-management Specification

## Purpose
TBD - created by archiving change auth. Update Purpose after archive.
## Requirements
### Requirement: Admin lists users
An admin SHALL be able to list all registered users.

#### Scenario: Admin fetches users
- **WHEN** an admin requests the user list
- **THEN** the system returns all users with their id, username, display name,
  role, and active status

### Requirement: Admin creates a user
An admin SHALL be able to create a user with a username, display name, role, and an
initial PIN.

#### Scenario: Create operator
- **WHEN** an admin creates a user with a unique username and a valid PIN
- **THEN** the system stores the user with a hashed PIN and returns the created user

#### Scenario: Duplicate username
- **WHEN** an admin creates a user with an already-existing username
- **THEN** the system rejects the request with a conflict error

### Requirement: Admin updates a user
An admin SHALL be able to update a user's display name, role, or active status.

#### Scenario: Change role
- **WHEN** an admin updates a user's role
- **THEN** the system persists the new role

### Requirement: Admin deactivates a user
An admin SHALL be able to deactivate a user so that the user can no longer sign in.

#### Scenario: Deactivated user cannot log in
- **WHEN** a deactivated user attempts to log in
- **THEN** the system rejects the login even with correct credentials

### Requirement: Operator cannot manage users
A non-admin user SHALL NOT be able to create, list, update, or deactivate users.

#### Scenario: Operator attempts user management
- **WHEN** an operator attempts any user management action
- **THEN** the system rejects the request with a forbidden error


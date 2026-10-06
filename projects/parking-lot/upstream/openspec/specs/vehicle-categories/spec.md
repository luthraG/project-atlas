# vehicle-categories Specification

## Purpose
TBD - created by archiving change vehicle-categories. Update Purpose after archive.
## Requirements
### Requirement: List categories
An authenticated user SHALL be able to list all vehicle categories.

#### Scenario: Operator fetches categories
- **WHEN** an authenticated user requests the category list
- **THEN** the system returns all categories with their id and name

### Requirement: Admin creates a category
An admin SHALL be able to create a category with a unique, non-empty name.

#### Scenario: Create a category
- **WHEN** an admin creates a category with a new name
- **THEN** the system stores the category and returns it with an id

#### Scenario: Duplicate name
- **WHEN** an admin creates a category with an existing name
- **THEN** the system rejects the request with a conflict error

### Requirement: Admin updates a category
An admin SHALL be able to rename a category.

#### Scenario: Rename a category
- **WHEN** an admin updates a category's name
- **THEN** the system persists the new name

### Requirement: Admin deletes a category
An admin SHALL be able to delete a category.

#### Scenario: Delete a category
- **WHEN** an admin deletes a category
- **THEN** the category is removed from the list

### Requirement: Operator cannot manage categories
A non-admin user SHALL NOT be able to create, update, or delete categories.

#### Scenario: Operator attempts mutation
- **WHEN** an operator attempts to create, update, or delete a category
- **THEN** the system rejects the request with a forbidden error


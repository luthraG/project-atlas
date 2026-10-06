# vehicles Specification

## Purpose
TBD - created by archiving change vehicles. Update Purpose after archive.
## Requirements
### Requirement: List and search vehicles
An authenticated user SHALL be able to list vehicles, optionally filtered by plate.

#### Scenario: Fetch all vehicles
- **WHEN** an authenticated user requests the vehicle list
- **THEN** the system returns all vehicles with id, plate, color, brand, and category id

#### Scenario: Find by plate
- **WHEN** a user searches a vehicle by its plate
- **THEN** the system returns the matching vehicle, ignoring case and surrounding whitespace

### Requirement: Admin creates a vehicle
An admin SHALL be able to create a vehicle with a normalized unique plate, optional
color and brand, and a category.

#### Scenario: Create a vehicle
- **WHEN** an admin creates a vehicle with a new plate
- **THEN** the system stores the normalized plate and returns the vehicle with an id

#### Scenario: Duplicate plate
- **WHEN** an admin creates a vehicle with an existing plate
- **THEN** the system rejects the request with a conflict error

### Requirement: Admin updates a vehicle
An admin SHALL be able to update a vehicle's color, brand, or category.

#### Scenario: Update category
- **WHEN** an admin updates a vehicle's category
- **THEN** the system persists the new category

### Requirement: Admin deletes a vehicle
An admin SHALL be able to delete a vehicle.

#### Scenario: Delete a vehicle
- **WHEN** an admin deletes a vehicle
- **THEN** the vehicle is removed from the list

### Requirement: Operator cannot manage vehicles
A non-admin user SHALL NOT be able to create, update, or delete vehicles.

#### Scenario: Operator attempts mutation
- **WHEN** an operator attempts to create, update, or delete a vehicle
- **THEN** the system rejects the request with a forbidden error


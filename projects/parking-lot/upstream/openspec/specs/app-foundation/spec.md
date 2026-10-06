# app-foundation Specification

## Purpose
TBD - created by archiving change foundation. Update Purpose after archive.
## Requirements
### Requirement: App builds and runs on Android and Web
The Flutter application SHALL build and run targeting both `android` and `web`
platforms from a single codebase.

#### Scenario: Android build succeeds
- **WHEN** the developer runs the Android build
- **THEN** the app compiles without errors and launches on the Android target

#### Scenario: Web build succeeds
- **WHEN** the developer runs the Web build
- **THEN** the app compiles without errors and serves the web target

### Requirement: Hexagonal feature structure
The app SHALL organize code by feature following Hexagonal Clean Architecture, with
each feature containing `domain/`, `application/`, `infrastructure/`, and
`presentation/` layers, and `domain/` SHALL NOT depend on any outer layer.

#### Scenario: Feature layer boundaries hold
- **WHEN** a feature is created
- **THEN** it contains the four layers and `domain/` has no imports from outer layers

### Requirement: Dependency injection container
The app SHALL provide a global dependency injection container so dependencies are
resolved via abstractions rather than concrete construction.

#### Scenario: Resolve a registered dependency
- **WHEN** a class registers a dependency with the DI container
- **THEN** consumers can resolve it through the container

### Requirement: Router and base page
The app SHALL expose a `go_router`-based router and SHALL render a base page at the
root route when the application starts.

#### Scenario: App launches to base page
- **WHEN** the application starts
- **THEN** the router navigates to the root route and renders the base page

### Requirement: Cop currency formatting
The app SHALL format monetary amounts as Colombian pesos (COP) using `intl` with no
decimal places.

#### Scenario: Format an integer amount
- **WHEN** an amount of 5000 is formatted
- **THEN** the output represents 5000 COP without decimal places


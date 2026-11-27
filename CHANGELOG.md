# Base Service Changelog

## Changelog Format

Use this template for each new release:

```markdown
### [X.Y.Z] - YYYY-MM-DD (Author Name)

#### Breaking
-

#### Features
-

#### Additions
- 

#### Fixes
- 

#### Removals
- 
```

## Entries

### [v0.4.0] - 2026-11-27 (Keeth Spindler)

#### Added

- Pydantic-based `ServiceSettings` with environment loading, explicit
  overrides, validated timeouts and logging configuration
- Safe settings rendering with automatic and explicit secret redaction
- Idempotent text and JSON logging with component fields and exception output
- Correlation context helpers for synchronous and awaited work
- Component health protocols, bounded checks, and service readiness aggregation

#### Changed

- `BaseService` and `BaseServiceBuilder` accept service settings
- Components expose an asynchronous health check with a required-readiness
  policy
- Lifecycle and FastAPI events use structured logging fields

#### Fixed

- Repeated logging setup no longer duplicates owned handlers
- Invalid logging levels and timeout values fail during configuration
- A timed-out or failed health check no longer blocks other readiness checks

### [v0.3.0] - 2026-11-27 (Keeth Spindler)

#### Added

- Async lifecycle state and generic component registration by string or enum key
- Cancellation and partial-startup cleanup behavior
- Grouped reporting for multiple shutdown failures

#### Changed

- Component initialization is asynchronous
- Service lifecycle follows registration order during startup and reverse order
  during shutdown
- Component registration is limited to explicit bundled-component setters
- `run()`, `bootstrap()`, one internal driver, and `shutdown()` own the
  lifecycle

#### Fixed

- Failed startup and runtime tasks now trigger component cleanup
- Shutdown continues after individual component failures
- Repeated shutdown requests share one cleanup operation

### [0.2.0] - 2026-11-09 (Keeth Spindler)

#### Features

- Added FastAPI Component and wiring to Base Service and it's Builder

### [0.1.0] - 2026-06-08 (Keeth Spindler)

#### Features

- Base Service Builder and Instance classes with component attachment mechanism
- Component-level Interface definition

#### Additions

- Added Unit tests for Base Service
- Added Changelog markdown
- Added initial README markdown
- Added Dockefile and .dockerignore Files
- Initial Commit

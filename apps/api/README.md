# API boundary

Packaged implementation: `src/archguard/api/`. Start with
`python -m uvicorn archguard.api.app:create_app --factory` from the installed environment.
This directory records the deployment boundary without a second Python package or duplicate app.
The app factory is the composition root. Only liveness and system information exist in v0.1.0.

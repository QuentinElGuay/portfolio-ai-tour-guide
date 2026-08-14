# Repository instructions

## Configuration and defaults

Avoid propagating default argument values through multiple layers of function calls.

Prefer defining package-wide defaults in a central constants module. Resolve
configuration at the application boundary, such as CLI options, environment-backed
settings, or a pipeline entry point, and pass explicit values to lower-level functions.

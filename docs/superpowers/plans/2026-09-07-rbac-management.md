# RBAC management implementation plan

## Goal

Replace the `/rbac` placeholder with a usable super-admin screen for managing users, roles, and region scope without exposing password hashes or changing the existing station authorization rules.

## Tasks

1. Add repository functions and API schemas for listing roles/regions, listing users, creating users, updating user profile/role/regions, and disabling users. Enforce `super_admin`, validate role and region IDs, hash passwords with PostgreSQL `crypt`, and prevent self-disable or disabling the last active super admin.
2. Write backend tests for authorization and repository SQL/response behavior, run them red, then implement the minimum backend code and run green.
3. Add frontend API helpers and replace the `/rbac` placeholder with a user table and create/edit/disable form. Show role and region labels, never show passwords, and display API errors.
4. Build the frontend and run the complete backend test suite in the backend Docker image. Review the diff for scope and security before handoff.

## Success criteria

- A super admin can list, create, edit, and disable users from `/rbac`.
- Non-super-admin users receive HTTP 403 for all RBAC management endpoints.
- User responses contain no password or password hash.
- Role and region assignments affect the existing `fetch_user_context` authorization path.
- Existing backend tests and the production frontend build pass.

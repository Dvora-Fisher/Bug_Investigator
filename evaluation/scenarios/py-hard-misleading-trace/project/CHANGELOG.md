# Changelog

## 1.4.0
- serializer: the API field `active` was renamed to `is_active` (`to_api` now reads `user["is_active"]`).
- serializer: `name` falls back to the part of the email before "@".
- internal: tidied up the repository module.

## 1.3.2
- service: emails are stored lower-case.

## 1.3.0
- api: `get_user` returns 404 for unknown ids instead of 500.

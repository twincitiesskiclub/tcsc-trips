# Contributing to TCSC Registration System

## User & Season Registration Model

- **User**: Stores all personal and contact information for each club member. This is the single source of truth for user data.
- **UserSeason**: Represents a user's registration for a specific season, linking a user to a season and tracking their per-season status and registration type.

## Registration Flow

1. When a user submits the registration form:
   - The backend checks if a `User` exists with the submitted email.
     - If yes: Update the User's info with the latest form data.
     - If no: Create a new User with the form data.
   - A `UserSeason` record is created (or updated) for the current season, linking to the User and storing per-season registration details.

## Status Fields

- **User.status** (global, applies to the user across all seasons):
  - Allowed values: `pending`, `active`, `inactive`, `dropped`
- **UserSeason.status** (per-season, applies to a user's registration for a specific season):
  - Allowed values: `PENDING_LOTTERY`, `ACTIVE`, `DROPPED`

## Member Type Logic (New vs. Returning)

- A user is considered a **returning/former member** if they have at least one `UserSeason` with `status == 'ACTIVE'` in any past season.
- If a user has only `PENDING_LOTTERY` or `DROPPED` UserSeason records (i.e., they registered but never actually participated), they are still considered a **new member** in future seasons.
- This ensures fairness: only users who have actually participated in a season can register as "returning/former" in the future.

## Implementation Recommendation

- Do **not** store "member type" as a column in the database, as it is a derived property.
- Instead, add a **helper property or method** on the `User` model to determine if a user is returning, based on their UserSeason history.
- Use this property in your registration logic and UI to control which registration options are available to the user.

## Best Practices

- Keep user data normalized and avoid redundancy.
- Ensure accurate, up-to-date member type logic.
- Use helper properties for derived values.

---

For questions or to propose changes, please open an issue or pull request. 
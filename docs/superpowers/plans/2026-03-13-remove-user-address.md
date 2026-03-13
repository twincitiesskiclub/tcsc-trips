# Remove User Address Field — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the `address` column from the User model and all associated UI, routes, validation, and autocomplete — the club no longer needs to collect or store member home addresses.

**Architecture:** Delete the `address` field from the User model, remove it from the registration form + admin views + CSV/JSON exports + validation, remove the Google Places autocomplete integration (its only purpose was address input), and create a database migration to drop the column (which also wipes all stored address data).

**Tech Stack:** Flask, SQLAlchemy, Jinja2, JavaScript, Flask-Migrate (Alembic)

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `app/models.py:141` | Modify | Remove `address` column from User model |
| `app/constants.py:68` | Modify | Remove `MAX_ADDRESS_LENGTH` |
| `app/utils.py:245-248` | Modify | Remove address validation block |
| `app/routes/registration.py:99` | Modify | Remove `address=form['address']` from user creation |
| `app/routes/admin.py:585,611,700,815` | Modify | Remove address from CSV export, JSON API, and edit handler |
| `app/routes/payments.py:17-19` | Modify | Remove `/get-google-places-key` endpoint |
| `app/templates/season_register.html:67-70` | Modify | Remove address form field |
| `app/templates/admin/user_detail.html:58-59` | Modify | Remove address display |
| `app/templates/admin/user_edit.html:47-51` | Modify | Remove address edit field |
| `app/static/admin_users.js:138` | Modify | Remove address column from Tabulator grid |
| `app/static/script.js:334,413-447` | Modify | Remove address from saved fields + Google Places autocomplete |
| `migrations/versions/` | Create | Migration to drop `address` column |

---

### Task 1: Remove address from the User model and constants

**Files:**
- Modify: `app/models.py:141`
- Modify: `app/constants.py:68`
- Modify: `app/utils.py:245-248`

- [ ] **Step 1: Remove the `address` column from User model**

In `app/models.py`, delete line 141:
```python
    address = db.Column(db.String(255))
```

- [ ] **Step 2: Remove `MAX_ADDRESS_LENGTH` from constants**

In `app/constants.py`, delete line 68:
```python
MAX_ADDRESS_LENGTH = 500
```

- [ ] **Step 3: Remove `MAX_ADDRESS_LENGTH` from the import in utils.py**

In `app/utils.py`, remove `MAX_ADDRESS_LENGTH` from the import on line 10:
```python
    MAX_NAME_LENGTH, MAX_ADDRESS_LENGTH, MAX_PHONE_LENGTH, MAX_PRONOUNS_LENGTH,
```
becomes:
```python
    MAX_NAME_LENGTH, MAX_PHONE_LENGTH, MAX_PRONOUNS_LENGTH,
```

- [ ] **Step 4: Remove address validation block from utils.py**

In `app/utils.py`, delete lines 245-248 (the `# Address` comment and validation call):
```python
    # Address
    valid, msg = validate_required_string(form.get('address', ''), 'Address', MAX_ADDRESS_LENGTH)
    if not valid:
        errors.append(msg)
```

- [ ] **Step 5: Commit**

```bash
git add app/models.py app/constants.py app/utils.py
git commit -m "refactor: remove address field from User model, constants, and validation"
```

---

### Task 2: Remove address from registration route and form

**Files:**
- Modify: `app/routes/registration.py:99`
- Modify: `app/templates/season_register.html:67-70`

- [ ] **Step 1: Remove `address` from user creation in registration route**

In `app/routes/registration.py`, delete line 99:
```python
                address=form['address'],
```

- [ ] **Step 2: Remove address form field from registration template**

In `app/templates/season_register.html`, delete lines 67-70 (the entire address form-row div):
```html
              <div class="sr-form-row form-group">
                <label for="address">Home Address</label>
                <input class="sr-input" type="text" id="address" name="address" placeholder="Home Address" required>
              </div>
```

- [ ] **Step 3: Commit**

```bash
git add app/routes/registration.py app/templates/season_register.html
git commit -m "refactor: remove address from registration form and route"
```

---

### Task 3: Remove address from admin views and API

**Files:**
- Modify: `app/routes/admin.py:585,611,700,815`
- Modify: `app/templates/admin/user_detail.html:58-59`
- Modify: `app/templates/admin/user_edit.html:47-51`
- Modify: `app/static/admin_users.js:138`

- [ ] **Step 1: Remove address from CSV export header**

In `app/routes/admin.py`, delete line 585:
```python
        'Address',
```

- [ ] **Step 2: Remove address from CSV export data row**

In `app/routes/admin.py`, delete line 611:
```python
            user.address or '',
```

- [ ] **Step 3: Remove address from JSON API response**

In `app/routes/admin.py`, delete line 700:
```python
            'address': user.address or '',
```

- [ ] **Step 4: Remove address from admin edit handler**

In `app/routes/admin.py`, delete line 815:
```python
            update_if_present('address', request.form.get('address'))
```

- [ ] **Step 5: Remove address from admin user detail template**

In `app/templates/admin/user_detail.html`, delete lines 58-59:
```html
                <dt class="font-medium text-tcsc-gray-600 text-sm mt-3">Address</dt>
                <dd class="m-0 mt-1 text-tcsc-navy">{{ user.address or '-' }}</dd>
```

- [ ] **Step 6: Remove address from admin user edit template**

In `app/templates/admin/user_edit.html`, delete lines 47-51 (the entire address div):
```html
            <div class="mb-4">
                <label class="block text-sm font-medium text-tcsc-gray-600 mb-1.5">Address</label>
                <input type="text" name="address" value="{{ user.address or '' }}"
                       class="w-full px-3 py-2 border border-tcsc-gray-100 rounded-tcsc text-sm focus:outline-none focus:ring-2 focus:ring-tcsc-navy/20 focus:border-tcsc-navy">
            </div>
```

- [ ] **Step 7: Remove address column from Tabulator grid**

In `app/static/admin_users.js`, delete line 138:
```javascript
            {title: "Address", field: "address", minWidth: 200},
```

- [ ] **Step 8: Commit**

```bash
git add app/routes/admin.py app/templates/admin/user_detail.html app/templates/admin/user_edit.html app/static/admin_users.js
git commit -m "refactor: remove address from admin views, CSV export, and JSON API"
```

---

### Task 4: Remove Google Places autocomplete (address-only feature)

**Files:**
- Modify: `app/routes/payments.py:17-19`
- Modify: `app/static/script.js:334,413-447`

- [ ] **Step 1: Remove the `/get-google-places-key` endpoint**

In `app/routes/payments.py`, delete lines 17-19:
```python
@payments.route('/get-google-places-key')
def get_google_places_key():
    return jsonify({'apiKey': os.getenv('GOOGLE_PLACES_API_KEY', '')})
```

- [ ] **Step 2: Remove `'address'` from FIELDS_TO_SAVE in script.js**

In `app/static/script.js`, on line 334, remove `'address'` from the array:
```javascript
      'email', 'status', 'firstName', 'lastName', 'pronouns', 'dob',
      'phone', 'address', 'tshirtSize', 'technique', 'experience',
```
becomes:
```javascript
      'email', 'status', 'firstName', 'lastName', 'pronouns', 'dob',
      'phone', 'tshirtSize', 'technique', 'experience',
```

- [ ] **Step 3: Remove `GOOGLE_PLACES_API_KEY` from `.env.example`**

In `.env.example`, delete lines 46-47:
```
# Google Places API key for address autocomplete
# GOOGLE_PLACES_API_KEY=AIza...
```

- [ ] **Step 4: Remove the entire Google Places autocomplete section from script.js**

In `app/static/script.js`, delete the address autocomplete block (~lines 407-447). This includes the `initAddressAutocomplete` function definition and its call. The block starts with:
```javascript
    async function initAddressAutocomplete() {
```
and ends with:
```javascript
    // Initialize address autocomplete
    initAddressAutocomplete();
    // --- End Address Autocomplete ---
```

Delete all of it.

- [ ] **Step 5: Commit**

```bash
git add app/routes/payments.py app/static/script.js .env.example
git commit -m "refactor: remove Google Places autocomplete (only used for address input)"
```

---

### Task 5: Create and run database migration to drop the column

**Files:**
- Create: `migrations/versions/<auto>_remove_user_address_column.py`

- [ ] **Step 1: Generate the migration**

```bash
source env/bin/activate && flask db migrate -m "remove user address column"
```

Verify the generated migration contains:
```python
op.drop_column('users', 'address')
```

And the downgrade contains:
```python
op.add_column('users', sa.Column('address', sa.String(length=255), nullable=True))
```

If the auto-generated migration is empty or incorrect (sometimes happens when the dev DB is out of sync), create it manually.

- [ ] **Step 2: Test the migration locally**

```bash
flask db upgrade
```

Expected: Migration applies cleanly, `address` column is dropped from `users` table.

- [ ] **Step 3: Commit the migration**

```bash
git add migrations/versions/
git commit -m "migration: drop address column from users table"
```

---

### Task 6: Deploy to wipe production data

- [ ] **Step 1: Push to main / create PR**

All code changes are committed. Push and deploy. The `release.sh` script runs `flask db upgrade` automatically on deploy, which will drop the `address` column and all stored address data from production.

- [ ] **Step 2: Verify production**

After deploy, confirm:
- Registration form no longer shows address field
- Admin user detail/edit pages no longer show address
- Admin users grid no longer has address column
- CSV export no longer includes address column

---

## Notes

- **PracticeLocation.address and SocialLocation.address are NOT touched** — those are venue/location addresses needed for practice management.
- **GOOGLE_PLACES_API_KEY env var** can be removed from Render after deploy, but is not blocking.
- The migration is destructive and irreversible (address data is permanently deleted). This is the intent.

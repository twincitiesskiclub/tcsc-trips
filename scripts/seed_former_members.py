import csv
from app import create_app
from app.models import db, User

CSV_PATH = 'scripts/former_members.csv'

app = create_app()

with app.app_context():
    # Check if the CSV file exists
    try:
        with open(CSV_PATH, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            count = 0
            skipped = 0
            for row in reader:
                email = row.get('email', '').strip().lower()
                first_name = row.get('first_name', '').strip()
                last_name = row.get('last_name', '').strip()
                
                if not email: # Skip rows with no email
                    print(f"Skipping row {reader.line_num}: Missing email.")
                    skipped += 1
                    continue

                # Add validation for required fields
                if not first_name or not last_name:
                    print(f"Skipping row for email {email}: Missing first_name or last_name.")
                    skipped += 1
                    continue # Skip this row

                # Only add if not already present
                if not User.query.filter_by(email=email).first():
                    user = User(
                        email=email,
                        first_name=first_name,
                        last_name=last_name,
                        status='inactive' # Set status explicitly
                    )
                    db.session.add(user)
                    count += 1
            db.session.commit()
        print(f"Former members seeded successfully. Added: {count}, Skipped: {skipped}.")
    except FileNotFoundError:
        print(f"Error: CSV file not found at {CSV_PATH}")
    except Exception as e:
        db.session.rollback()
        print(f"An error occurred: {e}")

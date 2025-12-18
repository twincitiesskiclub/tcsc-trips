from app import create_app
from app.models import db, User, Season, UserSeason
from app.constants import UserStatus, UserSeasonStatus
from datetime import date

app = create_app()

with app.app_context():
    # 1. Ensure the stub season exists
    season = Season.query.filter_by(name='Former Members (Legacy)').first()
    if not season:
        season = Season(
            name='Former Members (Legacy)',
            season_type='legacy',
            year=1900,
            start_date=date(1900, 1, 1),
            end_date=date(1900, 12, 31)
        )
        db.session.add(season)
        db.session.commit()
        print("Created 'Former Members (Legacy)' season.")
    else:
        print("'Former Members (Legacy)' season already exists.")

    # 2. For each 'former' user, create UserSeason if not present
    former_users = User.query.filter_by(status=UserStatus.ALUMNI).all()
    count = 0
    skipped = 0
    for user in former_users:
        us = UserSeason.query.filter_by(user_id=user.id, season_id=season.id).first()
        if not us:
            us = UserSeason(
                user_id=user.id,
                season_id=season.id,
                registration_type='returning',
                registration_date=date(1900, 1, 1),
                status=UserSeasonStatus.ACTIVE
            )
            db.session.add(us)
            count += 1
        else:
            skipped += 1
    db.session.commit()
    print(f'Linked {count} former users to the legacy season. Skipped {skipped} already-linked users.') 
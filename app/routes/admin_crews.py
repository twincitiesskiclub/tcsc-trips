"""Admin crews: make drafts, compare, fix by hand, mark one final."""
from datetime import datetime

from flask import Blueprint, Response, flash, redirect, render_template, request, url_for

from app.auth import admin_required
from app.crews import service
from app.crews.engine import LEVELS, TRAIT_LABELS, TRAITS
from app.crews.models import CrewDraft
from app.crews.roster import load_members
from app.crews import slack
from app.crews.slack import SPEEDY_CHANNEL_NAME, channel_member_user_ids
from app.models import Season, db

admin_crews_bp = Blueprint("admin_crews", __name__, url_prefix="/admin/crews")


def _seasons():
    return Season.query.filter(Season.season_type != "legacy").order_by(Season.start_date.desc())


def _back(season, anchor=""):
    return redirect(url_for(".season_page", season_id=season.id) + (f"#{anchor}" if anchor else ""))


def _count(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


@admin_crews_bp.get("/")
@admin_required
def index():
    season = Season.query.filter_by(is_current=True).first() or _seasons().first()
    if season is None:
        return render_template("admin/crews/season.html", season=None)
    return _back(season)


@admin_crews_bp.get("/season/<int:season_id>")
@admin_required
def season_page(season_id):
    season = db.get_or_404(Season, season_id)
    config = service.get_config(season)
    rows = load_members(season, config)
    settings = service.config_settings(config)
    drafts = [(d, service.summary(d)) for d in CrewDraft.query.filter_by(season_id=season.id)]
    drafts.sort(key=lambda pair: pair[1]["score"])
    return render_template(
        "admin/crews/season.html", season=season, config=config, settings=settings,
        balancing=[TRAIT_LABELS[t].lower() for t in TRAITS if settings["levels"][t] != "off"],
        crews=service.crew_count(len(rows), settings["size"]), sizes=service.describe_sizes(len(rows), settings["size"]),
        rows=rows, names={r.user_id: r.person.name for r in rows}, drafts=drafts,
        final=next((d for d, _ in drafts if d.status == "final"), None), seasons=_seasons().all(),
        traits=TRAITS, trait_labels=TRAIT_LABELS, levels=list(LEVELS), genders=service.GENDERS,
        speedy_channel=SPEEDY_CHANNEL_NAME, batch=service.DRAFTS_PER_BATCH,
        board_count=sum(r.person.board for r in rows),
        no_gender=sum(r.person.gender == "?" for r in rows),
    )


@admin_crews_bp.post("/season/<int:season_id>/settings")
@admin_required
def save_settings(season_id):
    season = db.get_or_404(Season, season_id)
    settings, error = service.parse_settings(request.form)
    if error:
        flash(error, "error")
    else:
        service.get_config(season, create=True).settings = settings
        db.session.commit()
        flash("Settings saved. They apply to new drafts.", "success")
    return _back(season, "settings")


@admin_crews_bp.post("/season/<int:season_id>/members")
@admin_required
def save_members(season_id):
    season = db.get_or_404(Season, season_id)
    service.set_overrides(service.get_config(season, create=True), load_members(season, None), request.form)
    db.session.commit()
    flash("Member values saved.", "success")
    return _back(season, "members")


@admin_crews_bp.post("/season/<int:season_id>/members/clear")
@admin_required
def clear_overrides(season_id):
    season = db.get_or_404(Season, season_id)
    service.get_config(season, create=True).overrides = {}
    db.session.commit()
    flash("Cleared every hand-set value. Members now use the computed values.", "success")
    return _back(season, "members")


@admin_crews_bp.post("/season/<int:season_id>/speedy/refresh")
@admin_required
def refresh_speedy(season_id):
    season = db.get_or_404(Season, season_id)
    try:
        user_ids, unlinked = channel_member_user_ids()
    except Exception as e:  # Slack down, token missing, bot not in channel
        flash(f"Could not read {SPEEDY_CHANNEL_NAME} from Slack: {e}", "error")
        return _back(season)
    config = service.get_config(season, create=True)
    config.speedy_user_ids, config.speedy_refreshed_at = user_ids, datetime.utcnow()
    db.session.commit()
    flash(f"Speedy group: {_count(len(user_ids), 'member')} from {SPEEDY_CHANNEL_NAME}"
          + (f" ({unlinked} Slack accounts not linked to a member)." if unlinked else "."), "success")
    return _back(season)


@admin_crews_bp.post("/season/<int:season_id>/rules")
@admin_required
def add_rule(season_id):
    season = db.get_or_404(Season, season_id)
    config = service.get_config(season, create=True)
    member_ids = {r.user_id for r in load_members(season, config)}
    crews = service.crew_count(len(member_ids), service.config_settings(config)["size"])
    rule, error = service.parse_rule(request.form, member_ids, crews)
    if error:
        flash(error, "error")
    elif rule in config.rules:
        flash("That rule is already there.", "warning")
    else:
        config.rules = [*config.rules, rule]
        db.session.commit()
        flash("Rule added. It applies to new drafts.", "success")
    return _back(season, "rules")


@admin_crews_bp.post("/season/<int:season_id>/rules/<int:index>/delete")
@admin_required
def delete_rule(season_id, index):
    season = db.get_or_404(Season, season_id)
    config = service.get_config(season, create=True)
    if 0 <= index < len(config.rules):
        config.rules = [r for i, r in enumerate(config.rules) if i != index]
        db.session.commit()
    return _back(season, "rules")


@admin_crews_bp.post("/season/<int:season_id>/drafts")
@admin_required
def create_drafts(season_id):
    season = db.get_or_404(Season, season_id)
    drafts = service.make_drafts(season, service.get_config(season, create=True))
    db.session.commit()
    flash(f"Made {_count(len(drafts), 'draft')}. The best one is at the top.", "success")
    return _back(season)


@admin_crews_bp.get("/draft/<int:draft_id>")
@admin_required
def draft_page(draft_id):
    draft = db.get_or_404(CrewDraft, draft_id)
    return render_template("admin/crews/draft.html", draft=draft, summary=service.summary(draft),
                           crews=service.crews_of(draft), trait_labels=TRAIT_LABELS)


@admin_crews_bp.post("/draft/<int:draft_id>")
@admin_required
def save_draft(draft_id):
    draft = db.get_or_404(CrewDraft, draft_id)
    try:
        service.save_draft(draft, request.form)
    except ValueError as e:
        db.session.rollback()
        flash(str(e), "error")
        return redirect(url_for(".draft_page", draft_id=draft.id))
    db.session.commit()  # names are saved even if Slack fails below
    failed = slack.rename_channels(draft) if draft.crew_channels else {}
    db.session.commit()
    if failed:
        flash("Saved, but these Slack channels kept their old names: "
              + ", ".join(f"crew {n} ({err})" for n, err in failed.items())
              + ". Save again or use Update crews in Slack to retry.", "warning")
    else:
        flash("Saved.", "success")
    return redirect(url_for(".draft_page", draft_id=draft.id))


@admin_crews_bp.post("/draft/<int:draft_id>/final")
@admin_required
def mark_final(draft_id):
    draft = db.get_or_404(CrewDraft, draft_id)
    service.mark_final(draft)
    db.session.commit()
    flash(f"{draft.label} is now the final crews for {draft.season.name}.", "success")
    return redirect(url_for(".draft_page", draft_id=draft.id))


def _final_or_back(draft_id):
    draft = db.get_or_404(CrewDraft, draft_id)
    if draft.status != "final":
        flash("Mark this draft as final before launching it in Slack.", "error")
        return draft, redirect(url_for(".draft_page", draft_id=draft.id))
    return draft, None


@admin_crews_bp.get("/draft/<int:draft_id>/launch")
@admin_required
def launch_confirm(draft_id):
    draft, back = _final_or_back(draft_id)
    if back:
        return back
    return render_template("admin/crews/launch.html", draft=draft, results=None,
                           plan=slack.launch_plan(draft, service.crews_of(draft)))


@admin_crews_bp.post("/draft/<int:draft_id>/launch")
@admin_required
def launch(draft_id):
    draft, back = _final_or_back(draft_id)
    if back:
        return back
    results = slack.launch(draft, service.crews_of(draft))
    db.session.commit()
    return render_template("admin/crews/launch.html", draft=draft, results=results, plan=None)


@admin_crews_bp.post("/draft/<int:draft_id>/delete")
@admin_required
def delete_draft(draft_id):
    draft = db.get_or_404(CrewDraft, draft_id)
    season = draft.season
    db.session.delete(draft)
    db.session.commit()
    flash("Draft deleted.", "success")
    return _back(season)


@admin_crews_bp.get("/draft/<int:draft_id>/export.csv")
@admin_required
def export(draft_id):
    draft = db.get_or_404(CrewDraft, draft_id)
    filename = f"crews-{draft.season.name}-{draft.label}".lower().replace(" ", "-").replace("/", "-")
    return Response(service.export_csv(draft), mimetype="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'})

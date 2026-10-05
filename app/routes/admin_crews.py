"""Admin crews: tune the method, make drafts, compare, hand-edit, mark final."""
from datetime import datetime

from flask import (Blueprint, Response, flash, redirect, render_template, request,
                   session, url_for)

from app.auth import admin_required
from app.crews import service
from app.crews.engine import LEVELS, TRAIT_LABELS, TRAITS
from app.crews.models import CrewDraft
from app.crews.roster import load_members
from app.crews.slack import channel_member_user_ids
from app.models import Season, db

admin_crews_bp = Blueprint("admin_crews", __name__, url_prefix="/admin/crews")


def _season(season_id):
    return db.get_or_404(Season, season_id)


def _draft(draft_id):
    return db.get_or_404(CrewDraft, draft_id)


def _back(season, anchor=""):
    return redirect(url_for(".season_page", season_id=season.id) + (f"#{anchor}" if anchor else ""))


def _count(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def _me():
    return (session.get("user") or {}).get("email")


@admin_crews_bp.get("/")
@admin_required
def index():
    season = Season.query.filter_by(is_current=True).first() or \
        Season.query.filter(Season.season_type != "legacy").order_by(Season.start_date.desc()).first()
    if season is None:
        return render_template("admin/crews/season.html", season=None, seasons=[])
    return _back(season)


@admin_crews_bp.get("/season/<int:season_id>")
@admin_required
def season_page(season_id):
    season = _season(season_id)
    config = service.get_config(season)
    db.session.commit()
    rows = load_members(season, config)
    names = {r.user_id: r.person.name for r in rows}
    drafts = CrewDraft.query.filter_by(season_id=season.id).order_by(CrewDraft.created_at.desc()).all()
    return render_template(
        "admin/crews/season.html", season=season, config=config, settings=service.config_settings(config),
        rows=rows, names=names, drafts=[(d, service.summary(d)) for d in drafts],
        seasons=Season.query.filter(Season.season_type != "legacy").order_by(Season.start_date.desc()).all(),
        traits=TRAITS, trait_labels=TRAIT_LABELS, levels=list(LEVELS), genders=service.GENDERS,
        board_count=sum(r.computed["board"] for r in rows),
        next_seed=max([d.seed or 0 for d in drafts] + [0]) + 1,
    )


@admin_crews_bp.post("/season/<int:season_id>/settings")
@admin_required
def save_settings(season_id):
    season = _season(season_id)
    config = service.get_config(season)
    settings, error = service.parse_settings(request.form)
    if error:
        flash(error, "error")
    else:
        config.settings = settings
        db.session.commit()
        flash("Settings saved.", "success")
    return _back(season)


@admin_crews_bp.post("/season/<int:season_id>/members")
@admin_required
def save_members(season_id):
    season = _season(season_id)
    config = service.get_config(season)
    service.set_overrides(config, load_members(season, None), request.form)
    db.session.commit()
    flash("Member values saved.", "success")
    return _back(season, "members")


@admin_crews_bp.post("/season/<int:season_id>/overrides/upload")
@admin_required
def upload_overrides(season_id):
    season = _season(season_id)
    config = service.get_config(season)
    upload = request.files.get("file")
    if not upload or not upload.filename:
        flash("Choose a CSV file first.", "error")
        return _back(season)
    try:
        updated, unknown = service.import_overrides(config, load_members(season, None), upload)
    except ValueError as e:
        flash(str(e), "error")
        return _back(season)
    db.session.commit()
    msg = f"Updated {_count(updated, 'member')} from the CSV."
    if unknown:
        msg += f" Not members this season: {', '.join(unknown[:10])}" + (" and more." if len(unknown) > 10 else ".")
    flash(msg, "success")
    return _back(season, "members")


@admin_crews_bp.post("/season/<int:season_id>/overrides/clear")
@admin_required
def clear_overrides(season_id):
    season = _season(season_id)
    service.get_config(season).overrides = {}
    db.session.commit()
    flash("Cleared every hand-set value. Members now use the computed values.", "success")
    return _back(season, "members")


@admin_crews_bp.post("/season/<int:season_id>/speedy/refresh")
@admin_required
def refresh_speedy(season_id):
    season = _season(season_id)
    config = service.get_config(season)
    channel = service.config_settings(config)["speedy_channel"]
    try:
        user_ids, unlinked = channel_member_user_ids(channel)
    except Exception as e:  # Slack down, token missing, bot not in channel
        flash(f"Could not read the Slack channel {channel}: {e}", "error")
        return _back(season)
    config.speedy_user_ids, config.speedy_refreshed_at = user_ids, datetime.utcnow()
    db.session.commit()
    flash(f"Speedy group: {_count(len(user_ids), 'member')} from Slack"
          + (f" ({unlinked} Slack accounts not linked to a member)." if unlinked else "."), "success")
    return _back(season)


@admin_crews_bp.post("/season/<int:season_id>/rules")
@admin_required
def add_rule(season_id):
    season = _season(season_id)
    config = service.get_config(season)
    member_ids = {r.user_id for r in load_members(season, config)}
    rule, error = service.parse_rule(request.form, member_ids, int(service.config_settings(config)["crews"]))
    if error:
        flash(error, "error")
    elif rule in (config.rules or []):
        flash("That rule is already there.", "warning")
    else:
        config.rules = [*(config.rules or []), rule]
        db.session.commit()
        flash("Rule added. It applies to new drafts.", "success")
    return _back(season, "rules")


@admin_crews_bp.post("/season/<int:season_id>/rules/<int:index>/delete")
@admin_required
def delete_rule(season_id, index):
    season = _season(season_id)
    config = service.get_config(season)
    rules = list(config.rules or [])
    if 0 <= index < len(rules):
        rules.pop(index)
        config.rules = rules
        db.session.commit()
    return _back(season, "rules")


@admin_crews_bp.post("/season/<int:season_id>/drafts")
@admin_required
def create_drafts(season_id):
    season = _season(season_id)
    config = service.get_config(season)
    try:
        count = min(max(int(request.form.get("count", 5)), 1), 10)
        start = int(request.form.get("start_seed") or 1)
    except ValueError:
        flash("Number of drafts and starting seed must be whole numbers.", "error")
        return _back(season)
    drafts = service.make_drafts(season, config, count, start, _me())
    db.session.commit()
    flash(f"Made {_count(len(drafts), 'draft')}. Lower imbalance is more even.", "success")
    return _back(season, "drafts")


@admin_crews_bp.post("/season/<int:season_id>/drafts/import")
@admin_required
def import_draft(season_id):
    season = _season(season_id)
    config = service.get_config(season)
    upload = request.files.get("file")
    if not upload or not upload.filename:
        flash("Choose a CSV file first.", "error")
        return _back(season)
    try:
        draft, missing = service.import_draft(season, config, load_members(season, config), upload, _me())
    except ValueError as e:
        flash(str(e), "error")
        return _back(season)
    db.session.commit()
    if missing:
        flash("Not in the file, so placed in the smallest crews: "
              + ", ".join(r.person.name for r in missing), "warning")
    return redirect(url_for(".draft_page", draft_id=draft.id))


def _draft_context(draft):
    return dict(draft=draft, summary=service.summary(draft), crews=service.crews_of(draft),
                trait_labels=TRAIT_LABELS)


@admin_crews_bp.get("/draft/<int:draft_id>")
@admin_required
def draft_page(draft_id):
    return render_template("admin/crews/draft.html", **_draft_context(_draft(draft_id)))


def _edit(draft_id, change):
    draft = _draft(draft_id)
    try:
        change(draft)
    except (ValueError, TypeError) as e:
        db.session.rollback()
        return Response(str(e), 400, mimetype="text/plain")
    db.session.commit()
    return render_template("admin/crews/_draft_body.html", **_draft_context(draft))


@admin_crews_bp.post("/draft/<int:draft_id>/move")
@admin_required
def move(draft_id):
    return _edit(draft_id, lambda d: service.move(d, int(request.form["user_id"]), int(request.form["crew"])))


@admin_crews_bp.post("/draft/<int:draft_id>/swap")
@admin_required
def swap(draft_id):
    return _edit(draft_id, lambda d: service.swap(d, int(request.form["a"]), int(request.form["b"])))


@admin_crews_bp.post("/draft/<int:draft_id>/names")
@admin_required
def save_names(draft_id):
    draft = _draft(draft_id)
    k = int(draft.settings["crews"])
    draft.crew_names = {str(i): name[:80] for i in range(1, k + 1)
                        if (name := request.form.get(f"name_{i}", "").strip())}
    label = request.form.get("label", "").strip()
    if label:
        draft.label = label[:120]
    db.session.commit()
    flash("Names saved.", "success")
    return redirect(url_for(".draft_page", draft_id=draft.id))


@admin_crews_bp.post("/draft/<int:draft_id>/final")
@admin_required
def mark_final(draft_id):
    draft = _draft(draft_id)
    service.mark_final(draft)
    db.session.commit()
    flash(f"{draft.label} is now the final crews for {draft.season.name}.", "success")
    return redirect(url_for(".draft_page", draft_id=draft.id))


@admin_crews_bp.post("/draft/<int:draft_id>/delete")
@admin_required
def delete_draft(draft_id):
    draft = _draft(draft_id)
    season = draft.season
    db.session.delete(draft)
    db.session.commit()
    flash("Draft deleted.", "success")
    return _back(season, "drafts")


@admin_crews_bp.get("/draft/<int:draft_id>/export.csv")
@admin_required
def export(draft_id):
    draft = _draft(draft_id)
    filename = f"crews-{draft.season.name}-{draft.label}".lower().replace(" ", "-").replace("/", "-")
    return Response(service.export_csv(draft), mimetype="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'})


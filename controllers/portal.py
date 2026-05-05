from odoo import http
from odoo.http import request


class OlympiadPortal(http.Controller):
    """Portal routes for external mentor and jury users."""

    # ── Mentor Dashboard ──────────────────────────────────────────────────
    @http.route('/my/olympiad/mentor', auth='user', website=True)
    def my_olympiad_mentor(self, **kw):
        return request.render('moo_olympiad_portal.mentor_dashboard')

    # ── Jury Dashboard ────────────────────────────────────────────────────
    @http.route('/my/olympiad/jury', auth='user', website=True)
    def my_olympiad_jury(self, **kw):
        return request.render('moo_olympiad_portal.jury_dashboard')
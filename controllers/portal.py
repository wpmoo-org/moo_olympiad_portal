from odoo import http
from odoo.http import request


class OlympiadPortal(http.Controller):
    """Portal routes for external mentor and jury users."""

    def _get_olympiad_partner(self):
        """Return the current user's res.partner, or None if not logged in."""
        user = request.env.user
        if user._is_public():
            return None
        return user.partner_id

    def _check_mentor(self, partner):
        """Return True if partner is an approved mentor."""
        return partner and partner.is_olympiad_mentor

    def _check_jury(self, partner):
        """Return True if partner is an approved jury."""
        return partner and partner.is_olympiad_jury and partner.jury_state == 'approved'

    # ── Portal Home ─────────────────────────────────────────────────────────
    @http.route('/my/olympiad', auth='user', website=True)
    def my_olympiad_home(self, **kw):
        partner = self._get_olympiad_partner()
        if not partner:
            return request.redirect('/my')

        values = {
            'partner': partner,
            'is_mentor': self._check_mentor(partner),
            'is_jury': self._check_jury(partner),
        }

        # Mentor counters
        if values['is_mentor']:
            projects = request.env['moo_olympiad.project'].sudo().search([
                ('mentor_id', '=', partner.id)
            ])
            values['mentor_project_count'] = len(projects)
            values['mentor_student_count'] = sum(p.num_students for p in projects)
        else:
            values['mentor_project_count'] = 0
            values['mentor_student_count'] = 0

        # Jury counters
        if values['is_jury']:
            assignments = request.env['moo_olympiad.jury.assignment'].sudo().search([
                ('jury_id', '=', partner.id)
            ])
            values['jury_assignment_count'] = len(assignments)
            values['jury_scored_count'] = len(assignments.filtered(lambda a: a.score > 0))
        else:
            values['jury_assignment_count'] = 0
            values['jury_scored_count'] = 0

        return request.render('moo_olympiad_portal.olympiad_home', values)

    # ── Mentor Dashboard ──────────────────────────────────────────────────
    @http.route('/my/olympiad/mentor', auth='user', website=True)
    def my_olympiad_mentor(self, **kw):
        partner = self._get_olympiad_partner()
        if not partner or not self._check_mentor(partner):
            return request.redirect('/my/olympiad')

        projects = request.env['moo_olympiad.project'].sudo().search([
            ('mentor_id', '=', partner.id)
        ])

        values = {
            'partner': partner,
            'projects': projects,
            'project_count': len(projects),
            'student_count': sum(p.num_students for p in projects),
        }
        return request.render('moo_olympiad_portal.mentor_dashboard', values)

    # ── Jury Dashboard ────────────────────────────────────────────────────
    @http.route('/my/olympiad/jury', auth='user', website=True)
    def my_olympiad_jury(self, **kw):
        partner = self._get_olympiad_partner()
        if not partner or not self._check_jury(partner):
            return request.redirect('/my/olympiad')

        assignments = request.env['moo_olympiad.jury.assignment'].sudo().search([
            ('jury_id', '=', partner.id)
        ])

        values = {
            'partner': partner,
            'assignments': assignments,
            'assignment_count': len(assignments),
            'scored_count': len(assignments.filtered(lambda a: a.score > 0)),
        }
        return request.render('moo_olympiad_portal.jury_dashboard', values)

    # ── Mentor: Project Detail ────────────────────────────────────────────
    @http.route('/my/olympiad/project/<int:project_id>', auth='user', website=True)
    def my_olympiad_project_detail(self, project_id, **kw):
        partner = self._get_olympiad_partner()
        if not partner or not self._check_mentor(partner):
            return request.redirect('/my/olympiad')

        project = request.env['moo_olympiad.project'].sudo().browse(project_id)
        if not project.exists() or project.mentor_id.id != partner.id:
            return request.redirect('/my/olympiad/mentor')

        values = {
            'partner': partner,
            'project': project,
            'students': project.student_ids,
        }
        return request.render('moo_olympiad_portal.mentor_project_detail', values)

    # ── Jury: Assignment Detail ───────────────────────────────────────────
    @http.route('/my/olympiad/assignment/<int:assignment_id>', auth='user', website=True)
    def my_olympiad_assignment_detail(self, assignment_id, **kw):
        partner = self._get_olympiad_partner()
        if not partner or not self._check_jury(partner):
            return request.redirect('/my/olympiad')

        assignment = request.env['moo_olympiad.jury.assignment'].sudo().browse(assignment_id)
        if not assignment.exists() or assignment.jury_id.id != partner.id:
            return request.redirect('/my/olympiad/jury')

        values = {
            'partner': partner,
            'assignment': assignment,
            'project': assignment.project_id,
        }
        return request.render('moo_olympiad_portal.jury_assignment_detail', values)

    # ── Jury: Score Submission ────────────────────────────────────────────
    @http.route('/my/olympiad/assignment/<int:assignment_id>/score', auth='user', website=True, methods=['POST'])
    def my_olympiad_assignment_score(self, assignment_id, **post):
        partner = self._get_olympiad_partner()
        if not partner or not self._check_jury(partner):
            return request.redirect('/my/olympiad')

        assignment = request.env['moo_olympiad.jury.assignment'].sudo().browse(assignment_id)
        if not assignment.exists() or assignment.jury_id.id != partner.id:
            return request.redirect('/my/olympiad/jury')

        score = post.get('score')
        comments = post.get('comments', '')
        if score is not None:
            try:
                score_val = float(score)
                assignment.write({
                    'score': score_val,
                    'comments': comments,
                })
            except ValueError:
                pass

        return request.redirect(f'/my/olympiad/assignment/{assignment_id}')
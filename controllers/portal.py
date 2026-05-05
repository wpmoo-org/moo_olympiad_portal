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
        return partner and partner.is_olympiad_mentor and partner.mentor_state == 'approved'

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
    @http.route('/my/olympiad/assignment/<<intint:assignment_id>/score', auth='user', website=True, methods=['POST'])
    def my_olympiad_assignment_score(self, assignment_id, **post):
        partner = self._get_olympiad_partner()
        if not partner or not self._check_jury(partner):
            return request.redirect('/my/olympiad')

        assignment = request.env['moo_olympiad.jury.assignment'].sudo().browse(assignment_id)
        if not assignment.exists() or assignment.jury_id.id != partner.id:
            return request.redirect('/my/olympiad/jury')

        # Validation: Event state must be open or finished to score
        if assignment.event_id.state not in ['open', 'finished']:
            return request.redirect('/my/olympiad/jury')

        score = post.get('score')
        comments = post.get('comments', '')
        if score is not None:
            try:
                score_val = float(score)
                if 0 <= score_val <= 100:
                    assignment.write({
                        'score': score_val,
                        'comments': comments,
                    })
            except ValueError:
                pass

        return request.redirect(f'/my/olympiad/assignment/{assignment_id}')

    # ── Public: Events ──────────────────────────────────────────────────────

    # ── Public: Events ──────────────────────────────────────────────────────
    @http.route('/olympiad/events', auth='public', website=True)
    def olympiad_events(self, **kw):
        events = request.env['moo_olympiad.event'].sudo().search([
            ('state', 'in', ['open', 'finished'])
        ])
        return request.render('moo_olympiad_portal.public_events', {
            'events': events,
        })

    # ── Public: Event Detail ────────────────────────────────────────────────
    @http.route('/olympiad/event/<int:event_id>', auth='public', website=True)
    def olympiad_event_detail(self, event_id, **kw):
        event = request.env['moo_olympiad.event'].sudo().browse(event_id)
        if not event.exists() or event.state == 'cancelled':
            return request.redirect('/olympiad/events')
        return request.render('moo_olympiad_portal.public_event_detail', {
            'event': event,
            'categories': event.category_ids,
        })

    # ── Public: Categories ────────────────────────────────────────────────
    @http.route('/olympiad/categories', auth='public', website=True)
    def olympiad_categories(self, **kw):
        categories = request.env['moo_olympiad.category'].sudo().search([
            ('active', '=', True)
        ])
        return request.render('moo_olympiad_portal.public_categories', {
            'categories': categories,
        })

    # ── Public: Category Detail ───────────────────────────────────────────
    @http.route('/olympiad/category/<int:category_id>', auth='public', website=True)
    def olympiad_category_detail(self, category_id, **kw):
        category = request.env['moo_olympiad.category'].sudo().browse(category_id)
        if not category.exists() or not category.active:
            return request.redirect('/olympiad/categories')
        return request.render('moo_olympiad_portal.public_category_detail', {
            'category': category,
        })

    # ── Mentor/Jury Application Pages ─────────────────────────────────────
    @http.route('/olympiad/apply/mentor', auth='user', website=True)
    def olympiad_apply_mentor(self, **kw):
        partner = self._get_olympiad_partner()
        if not partner:
            return request.redirect('/web/login')
        # If already a mentor, redirect to mentor dashboard
        if self._check_mentor(partner):
            return request.redirect('/my/olympiad/mentor')
        return request.render('moo_olympiad_portal.apply_mentor', {
            'partner': partner,
        })

    @http.route('/olympiad/apply/jury', auth='user', website=True)
    def olympiad_apply_jury(self, **kw):
        partner = self._get_olympiad_partner()
        if not partner:
            return request.redirect('/web/login')
        # If already approved jury, redirect to jury dashboard
        if self._check_jury(partner):
            return request.redirect('/my/olympiad/jury')
        return request.render('moo_olympiad_portal.apply_jury', {
            'partner': partner,
        })

    # ── Mentor/Jury Application Submit ─────────────────────────────────────
    @http.route('/olympiad/apply/mentor/submit', auth='user', website=True, methods=['POST'])
    def olympiad_apply_mentor_submit(self, **post):
        partner = self._get_olympiad_partner()
        if not partner:
            return request.redirect('/web/login')
        if self._check_mentor(partner):
            return request.redirect('/my/olympiad/mentor')
        partner.sudo().write({'is_olympiad_mentor': True, 'mentor_state': 'pending'})
        return request.redirect('/my/olympiad')

    @http.route('/olympiad/apply/jury/submit', auth='user', website=True, methods=['POST'])
    def olympiad_apply_jury_submit(self, **post):
        partner = self._get_olympiad_partner()
        if not partner:
            return request.redirect('/web/login')
        if self._check_jury(partner):
            return request.redirect('/my/olympiad/jury')
        partner.sudo().write({'is_olympiad_jury': True, 'jury_state': 'pending'})
        return request.render('moo_olympiad_portal.apply_jury_success', {
            'partner': partner,
        })

    # ── Project Registration ───────────────────────────────────────────────
    @http.route('/olympiad/register/project', auth='user', website=True)
    def olympiad_register_project(self, **kw):
        partner = self._get_olympiad_partner()
        if not partner or not self._check_mentor(partner):
            return request.redirect('/my/olympiad')

        events = request.env['moo_olympiad.event'].sudo().search([('state', '=', 'open')])
        return request.render('moo_olympiad_portal.register_project', {
            'partner': partner,
            'events': events,
        })

    @http.route('/olympiad/register/project/submit', auth='user', website=True, methods=['POST'])
    def olympiad_register_project_submit(self, **post):
        partner = self._get_olympiad_partner()
        if not partner or not self._check_mentor(partner):
            return request.redirect('/my/olympiad')

        event_id = int(post.get('event_id', 0))
        name = post.get('name', '').strip()
        category_id = int(post.get('category_id', 0))

        if not all([event_id, name, category_id]):
            return request.redirect('/olympiad/register/project')

        event = request.env['moo_olympiad.event'].sudo().browse(event_id)
        if not event.exists() or event.state != 'open':
            return request.redirect('/olympiad/register/project')

        if category_id not in event.category_ids.ids:
            return request.redirect('/olympiad/register/project')

        project = request.env['moo_olympiad.project'].sudo().create({
            'name': name,
            'mentor_id': partner.id,
            'event_id': event_id,
            'category_id': category_id,
            'pres_lang': post.get('pres_lang', 'en'),
        })
        return request.redirect(f'/my/olympiad/project/{project.id}')
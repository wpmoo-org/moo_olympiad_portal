from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError, UserError


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
    @http.route('/my/olympiad/assignment/<int:assignment_id>/score', auth='user', website=True, methods=['POST'])
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
                if not (0 <= score_val <= 100):
                    raise ValueError()
                assignment.write({
                    'score': score_val,
                    'comments': comments,
                })
            except (ValueError, TypeError):
                return request.render('moo_olympiad_portal.jury_assignment_detail', {
                    'partner': partner,
                    'assignment': assignment,
                    'project': assignment.project_id,
                    'score_error': True,
                })
            except (ValidationError, UserError) as e:
                return request.render('moo_olympiad_portal.jury_assignment_detail', {
                    'partner': partner,
                    'assignment': assignment,
                    'project': assignment.project_id,
                    'score_error': True,
                    'error_msg': str(e),
                })

        return request.redirect(f'/my/olympiad/assignment/{assignment_id}')

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
        partner.sudo().write({
            'is_olympiad_mentor': True,
            'mentor_state': 'pending',
            'olympiad_bio': post.get('bio', ''),
        })
        return request.redirect('/my/olympiad')

    @http.route('/olympiad/apply/jury/submit', auth='user', website=True, methods=['POST'])
    def olympiad_apply_jury_submit(self, **post):
        partner = self._get_olympiad_partner()
        if not partner:
            return request.redirect('/web/login')
        if self._check_jury(partner):
            return request.redirect('/my/olympiad/jury')
        partner.sudo().write({
            'is_olympiad_jury': True,
            'jury_state': 'pending',
            'olympiad_expertise': post.get('expertise', ''),
        })
        return request.render('moo_olympiad_portal.apply_jury_success', {
            'partner': partner,
        })

    # ── Project Registration Wizard ──────────────────────────────────────
    REGISTRATION_STEPS = ['project', 'students', 'accommodation', 'excursion', 'summary']

    def _get_registration_step_index(self, step):
        try:
            return self.REGISTRATION_STEPS.index(step)
        except ValueError:
            return 0

    def _validate_project_ownership(self, partner, project):
        return project.exists() and project.mentor_id.id == partner.id and project.state == 'draft'

    @http.route('/olympiad/register/project', auth='user', website=True)
    def olympiad_register_project(self, **kw):
        partner = self._get_olympiad_partner()
        if not partner or not self._check_mentor(partner):
            return request.redirect('/my/olympiad')

        events = request.env['moo_olympiad.event'].sudo().search([('state', '=', 'open')])
        countries = request.env['res.country'].sudo().search([])
        return request.render('moo_olympiad_portal.register_project', {
            'partner': partner,
            'events': events,
            'countries': countries,
            'step': 'project',
            'step_index': 0,
            'step_total': len(self.REGISTRATION_STEPS),
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
        return request.redirect(f'/olympiad/register/{project.id}/students')

    @http.route('/olympiad/register/<int:project_id>/students', auth='user', website=True)
    def olympiad_register_students(self, project_id, **kw):
        partner = self._get_olympiad_partner()
        if not partner or not self._check_mentor(partner):
            return request.redirect('/my/olympiad')

        project = request.env['moo_olympiad.project'].sudo().browse(project_id)
        if not self._validate_project_ownership(partner, project):
            return request.redirect('/my/olympiad/mentor')

        countries = request.env['res.country'].sudo().search([])
        return request.render('moo_olympiad_portal.register_students', {
            'partner': partner,
            'project': project,
            'countries': countries,
            'step': 'students',
            'step_index': 1,
            'step_total': len(self.REGISTRATION_STEPS),
        })

    @http.route('/olympiad/register/<int:project_id>/students/submit', auth='user', website=True, methods=['POST'])
    def olympiad_register_students_submit(self, project_id, **post):
        partner = self._get_olympiad_partner()
        if not partner or not self._check_mentor(partner):
            return request.redirect('/my/olympiad')

        project = request.env['moo_olympiad.project'].sudo().browse(project_id)
        if not self._validate_project_ownership(partner, project):
            return request.redirect('/my/olympiad/mentor')

        Student = request.env['moo_olympiad.student'].sudo()
        ProjectStudent = request.env['moo_olympiad.project.student'].sudo()

        student_count = int(post.get('student_count', 0))
        for i in range(student_count):
            first_name = post.get(f'student_{i}_first_name', '').strip()
            last_name = post.get(f'student_{i}_last_name', '').strip()
            birth_date = post.get(f'student_{i}_birth_date', '')
            gender = post.get(f'student_{i}_gender', '')
            country_id = int(post.get(f'student_{i}_country_id', 0))
            tshirt_size = post.get(f'student_{i}_tshirt_size', '')

            if not all([first_name, last_name, birth_date, gender, country_id, tshirt_size]):
                continue

            try:
                student = Student.create({
                    'first_name': first_name,
                    'last_name': last_name,
                    'birth_date': birth_date,
                    'gender': gender,
                    'country_id': country_id,
                    'tshirt_size': tshirt_size,
                    'email': post.get(f'student_{i}_email', ''),
                    'phone': post.get(f'student_{i}_phone', ''),
                })
                ProjectStudent.create({
                    'project_id': project.id,
                    'student_id': student.id,
                    'role': 'leader' if i == 0 else 'member',
                })
            except (ValidationError, UserError):
                continue

        if not project.student_ids:
            countries = request.env['res.country'].sudo().search([])
            return request.render('moo_olympiad_portal.register_students', {
                'partner': partner,
                'project': project,
                'countries': countries,
                'step': 'students',
                'step_index': 1,
                'step_total': len(self.REGISTRATION_STEPS),
                'student_error': True,
            })

        return request.redirect(f'/olympiad/register/{project.id}/accommodation')

    @http.route('/olympiad/register/<int:project_id>/accommodation', auth='user', website=True)
    def olympiad_register_accommodation(self, project_id, **kw):
        partner = self._get_olympiad_partner()
        if not partner or not self._check_mentor(partner):
            return request.redirect('/my/olympiad')

        project = request.env['moo_olympiad.project'].sudo().browse(project_id)
        if not self._validate_project_ownership(partner, project):
            return request.redirect('/my/olympiad/mentor')

        accommodations = project.event_id.accommodation_ids
        return request.render('moo_olympiad_portal.register_accommodation', {
            'partner': partner,
            'project': project,
            'accommodations': accommodations,
            'step': 'accommodation',
            'step_index': 2,
            'step_total': len(self.REGISTRATION_STEPS),
        })

    @http.route('/olympiad/register/<int:project_id>/accommodation/submit', auth='user', website=True, methods=['POST'])
    def olympiad_register_accommodation_submit(self, project_id, **post):
        partner = self._get_olympiad_partner()
        if not partner or not self._check_mentor(partner):
            return request.redirect('/my/olympiad')

        project = request.env['moo_olympiad.project'].sudo().browse(project_id)
        if not self._validate_project_ownership(partner, project):
            return request.redirect('/my/olympiad/mentor')

        for line in project.student_ids:
            no_acc = post.get(f'no_accommodation_{line.id}') == 'on'
            line.write({'no_accommodation': no_acc})
            if not no_acc:
                acc_ids = post.get(f'accommodation_{line.id}', '')
                if acc_ids:
                    ids = [int(x) for x in acc_ids.split(',') if x.strip().isdigit()]
                    line.write({'accommodation_ids': [(6, 0, ids)]})

        return request.redirect(f'/olympiad/register/{project.id}/excursion')

    @http.route('/olympiad/register/<int:project_id>/excursion', auth='user', website=True)
    def olympiad_register_excursion(self, project_id, **kw):
        partner = self._get_olympiad_partner()
        if not partner or not self._check_mentor(partner):
            return request.redirect('/my/olympiad')

        project = request.env['moo_olympiad.project'].sudo().browse(project_id)
        if not self._validate_project_ownership(partner, project):
            return request.redirect('/my/olympiad/mentor')

        return request.render('moo_olympiad_portal.register_excursion', {
            'partner': partner,
            'project': project,
            'step': 'excursion',
            'step_index': 3,
            'step_total': len(self.REGISTRATION_STEPS),
        })

    @http.route('/olympiad/register/<int:project_id>/excursion/submit', auth='user', website=True, methods=['POST'])
    def olympiad_register_excursion_submit(self, project_id, **post):
        partner = self._get_olympiad_partner()
        if not partner or not self._check_mentor(partner):
            return request.redirect('/my/olympiad')

        project = request.env['moo_olympiad.project'].sudo().browse(project_id)
        if not self._validate_project_ownership(partner, project):
            return request.redirect('/my/olympiad/mentor')

        mentor_excursion = post.get('mentor_excursion') == 'on'
        project.write({'mentor_excursion': mentor_excursion})

        for line in project.student_ids:
            excursion = post.get(f'excursion_{line.id}') == 'on'
            line.write({'excursion': excursion})

        return request.redirect(f'/olympiad/register/{project.id}/summary')

    @http.route('/olympiad/register/<int:project_id>/summary', auth='user', website=True)
    def olympiad_register_summary(self, project_id, **kw):
        partner = self._get_olympiad_partner()
        if not partner or not self._check_mentor(partner):
            return request.redirect('/my/olympiad')

        project = request.env['moo_olympiad.project'].sudo().browse(project_id)
        if not self._validate_project_ownership(partner, project):
            return request.redirect('/my/olympiad/mentor')

        event = project.event_id
        registration_total = project.num_students * event.registration_fee
        student_excursion_total = sum(
            event.excursion_fee for line in project.student_ids if line.excursion
        )
        mentor_excursion_total = event.excursion_fee if project.mentor_excursion else 0.0
        accommodation_total = sum(
            event.accommodation_fee * line.accommodation_nights for line in project.student_ids
        )
        grand_total = registration_total + student_excursion_total + mentor_excursion_total + accommodation_total

        return request.render('moo_olympiad_portal.register_summary', {
            'partner': partner,
            'project': project,
            'step': 'summary',
            'step_index': 4,
            'step_total': len(self.REGISTRATION_STEPS),
            'registration_total': registration_total,
            'student_excursion_total': student_excursion_total,
            'mentor_excursion_total': mentor_excursion_total,
            'accommodation_total': accommodation_total,
            'grand_total': grand_total,
        })

    @http.route('/olympiad/register/<int:project_id>/confirm', auth='user', website=True, methods=['POST'])
    def olympiad_register_confirm(self, project_id, **post):
        partner = self._get_olympiad_partner()
        if not partner or not self._check_mentor(partner):
            return request.redirect('/my/olympiad')

        project = request.env['moo_olympiad.project'].sudo().browse(project_id)
        if not self._validate_project_ownership(partner, project):
            return request.redirect('/my/olympiad/mentor')

        if project.num_students < 1:
            return request.redirect(f'/olympiad/register/{project.id}/students')

        project.write({'state': 'published'})
        return request.redirect(f'/my/olympiad/project/{project.id}')
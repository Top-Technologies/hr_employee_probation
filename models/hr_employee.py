# -*- coding: utf-8 -*-
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # --- Probation Fields ---
    has_probation = fields.Boolean(
        string='Subject to Probation',
        default=True,
        tracking=True,
        help="Check if this employee is subject to a probation/trial period."
    )
    probation_duration = fields.Selection(
        [
            ('1', '1 Month'),
            ('2', '2 Months'),
            ('3', '3 Months'),
            ('6', '6 Months'),
            ('custom', 'Custom Duration'),
        ],
        string='Probation Duration',
        default='3',
        tracking=True,
    )
    probation_date_start = fields.Date(
        string='Probation Start Date',
        tracking=True,
        compute='_compute_probation_dates',
        store=True,
        readonly=False,
    )
    probation_date_end = fields.Date(
        string='Probation End Date',
        tracking=True,
        compute='_compute_probation_dates',
        store=True,
        readonly=False,
    )
    probation_status = fields.Selection(
        [
            ('in_progress', 'Under Probation'),
            ('passed', 'Passed / Confirmed'),
            ('extended', 'Extended'),
            ('failed', 'Terminated'),
        ],
        string='Probation Status',
        default='in_progress',
        tracking=True,
        compute='_compute_probation_status',
        store=True,
        readonly=False,
    )
    probation_notes = fields.Text(
        string='Probation Notes / Evaluation',
        tracking=True,
        help="Performance feedback, milestones, or evaluation notes during probation."
    )

    # --- Hiring & GM Approval Lifecycle for Contract Employees ---
    is_contract_employee = fields.Boolean(
        string='Contract / Fixed-Term Employee',
        compute='_compute_is_contract_employee',
        store=True,
        readonly=False,
        tracking=True,
        help="Flag indicating whether this employee is hired under a contract/fixed-term basis."
    )
    hiring_approval_state = fields.Selection(
        [
            ('draft', 'Draft / In Hiring'),
            ('waiting_gm', 'Waiting GM Approval'),
            ('approved', 'Approved / Hiring Completed'),
            ('rejected', 'Rejected by GM'),
        ],
        string='Hiring Status',
        default='draft',
        tracking=True,
        copy=False,
    )
    gm_approved_by_id = fields.Many2one('res.users', string='GM Approved By', readonly=True, copy=False)
    gm_approval_date = fields.Date(string='GM Approval Date', readonly=True, copy=False)
    gm_rejection_reason = fields.Text(string='GM Rejection Reason', copy=False)

    # --- Project Contract Tracking ---
    is_project_contract = fields.Boolean(
        string='Project Contract',
        tracking=True,
        help="Check this if this employee is hired specifically for a project contract."
    )
    contract_project_id = fields.Many2one(
        'project.project',
        string='Hiring Project',
        tracking=True,
        check_company=True,
        help="The specific project this employee is hired for."
    )
    project_section = fields.Char(
        string='Project Section / Phase / WBS',
        tracking=True,
        help="Identify which section, site, lot, or phase of the project the employee is hired for."
    )
    project_end_date = fields.Date(
        string='Project End Date',
        related='contract_project_id.date',
        readonly=True,
        store=False,
        help="Scheduled completion date of the selected project."
    )
    project_completion_state = fields.Selection(
        [
            ('ongoing', 'Project Ongoing / Active'),
            ('approaching_completion', 'Project / Contract Approaching Completion'),
            ('project_completed', 'Project Completed'),
        ],
        string='Project Completion State',
        compute='_compute_project_completion_status',
        store=False,
    )
    contract_expiry_action = fields.Selection(
        [
            ('pending_review', 'Pending Review'),
            ('renew', 'Renew / Extend Contract'),
            ('offboarding', 'Start Offboarding / Clearance'),
        ],
        string='Contract End Action',
        default='pending_review',
        tracking=True,
        help="Decision taken when employee wants to leave or their contract ends: Renew or Offboard."
    )

    @api.depends('employee_type', 'contract_type_id', 'is_project_contract')
    def _compute_is_contract_employee(self):
        for emp in self:
            is_contract = False
            if emp.is_project_contract:
                is_contract = True
            elif emp.employee_type in ('contractor', 'freelance', 'worker', 'trainee', 'student'):
                is_contract = True
            elif emp.contract_type_id and emp.contract_type_id.name:
                type_name = emp.contract_type_id.name.lower() if isinstance(emp.contract_type_id.name, str) else str(emp.contract_type_id.name)
                if any(k in type_name for k in ('contract', 'temporary', 'interim', 'seasonal', 'fixed')):
                    is_contract = True
            emp.is_contract_employee = is_contract

    @api.depends('has_probation', 'contract_date_start', 'probation_duration')
    def _compute_probation_dates(self):
        for employee in self:
            if not employee.has_probation:
                continue
            if not employee.probation_date_start and employee.contract_date_start:
                employee.probation_date_start = employee.contract_date_start

            if employee.probation_date_start and employee.probation_duration in ('1', '2', '3', '6'):
                months = int(employee.probation_duration)
                employee.probation_date_end = employee.probation_date_start + relativedelta(months=months) - relativedelta(days=1)

    @api.onchange('contract_date_start')
    def _onchange_contract_date_start(self):
        if self.contract_date_start and self.has_probation and not self.probation_date_start:
            self.probation_date_start = self.contract_date_start

    @api.onchange('probation_date_start', 'probation_duration')
    def _onchange_probation_duration(self):
        if self.probation_date_start and self.probation_duration in ('1', '2', '3', '6'):
            months = int(self.probation_duration)
            self.probation_date_end = self.probation_date_start + relativedelta(months=months) - relativedelta(days=1)

    @api.depends('has_probation', 'probation_date_end')
    def _compute_probation_status(self):
        for employee in self:
            if not employee.has_probation:
                continue
            if not employee.probation_status:
                employee.probation_status = 'in_progress'

    @api.depends('contract_date_end', 'contract_project_id.date', 'is_project_contract')
    def _compute_project_completion_status(self):
        today = fields.Date.today()
        for emp in self:
            if not emp.is_project_contract or not emp.contract_project_id:
                emp.project_completion_state = 'ongoing'
                continue

            proj_end = emp.contract_project_id.date
            contract_end = emp.contract_date_end

            # Check if project has completed
            if proj_end and proj_end <= today:
                emp.project_completion_state = 'project_completed'
            elif (proj_end and (proj_end - today).days <= 30) or (contract_end and (contract_end - today).days <= 30):
                emp.project_completion_state = 'approaching_completion'
            else:
                emp.project_completion_state = 'ongoing'

    # --- GM Approval Methods ---
    def action_submit_for_gm_approval(self):
        for emp in self:
            if not emp.is_contract_employee:
                raise UserError(_("GM Approval is specifically designated for contract employees."))
            emp.hiring_approval_state = 'waiting_gm'
            # Notify GM via chatter
            gm_user = emp.company_id.acme_gm_user_id if hasattr(emp.company_id, 'acme_gm_user_id') else False
            msg = _("Contract Employee <b>%s</b> has been submitted for General Manager (GM) hiring approval.") % emp.name
            emp.message_post(body=msg, partner_ids=[gm_user.partner_id.id] if gm_user else [])

    def action_gm_approve_hiring(self):
        for emp in self:
            gm_user = emp.company_id.acme_gm_user_id if hasattr(emp.company_id, 'acme_gm_user_id') else False
            is_gm_user = (gm_user and self.env.user == gm_user) or self.env.user.has_group('base.group_system')
            if not is_gm_user:
                raise UserError(_("Only the General Manager (GM) or Administrator can approve contract employee hiring."))
            emp.hiring_approval_state = 'approved'
            emp.gm_approved_by_id = self.env.user
            emp.gm_approval_date = fields.Date.today()
            emp.message_post(body=_("Hiring confirmed and approved by General Manager <b>%s</b>.") % self.env.user.name)

    def action_gm_reject_hiring(self):
        for emp in self:
            gm_user = emp.company_id.acme_gm_user_id if hasattr(emp.company_id, 'acme_gm_user_id') else False
            is_gm_user = (gm_user and self.env.user == gm_user) or self.env.user.has_group('base.group_system')
            if not is_gm_user:
                raise UserError(_("Only the General Manager (GM) or Administrator can reject contract employee hiring."))
            emp.hiring_approval_state = 'rejected'
            emp.message_post(body=_("Hiring rejected by General Manager <b>%s</b>.") % self.env.user.name)

    def action_reset_hiring_draft(self):
        for emp in self:
            emp.hiring_approval_state = 'draft'

    # --- Probation Actions ---
    def action_probation_pass(self):
        self.ensure_one()
        self.probation_status = 'passed'

    def action_probation_extend(self):
        self.ensure_one()
        self.probation_status = 'extended'

    def action_probation_fail(self):
        self.ensure_one()
        self.probation_status = 'failed'

    def action_probation_reset(self):
        self.ensure_one()
        self.probation_status = 'in_progress'

    # --- Contract Expiry / End of Project Actions ---
    def action_decide_renew(self):
        self.ensure_one()
        self.contract_expiry_action = 'renew'
        self.message_post(body=_("Decision taken: <b>Renew / Extend Contract</b> based on project status."))

    def action_start_offboarding(self):
        """Initiate offboarding: open Departure Wizard or HR Clearance if installed."""
        self.ensure_one()
        self.contract_expiry_action = 'offboarding'
        self.message_post(body=_("Initiated offboarding process for employee <b>%s</b> due to contract/project completion.") % self.name)
        
        # Check if hr.clearance from hr_resignation_v19c is available
        if 'hr.clearance' in self.env:
            existing_clearance = self.env['hr.clearance'].search([('employee_id', '=', self.id)], limit=1)
            if existing_clearance:
                return {
                    'type': 'ir.actions.act_window',
                    'name': _('Employee Clearance'),
                    'res_model': 'hr.clearance',
                    'view_mode': 'form',
                    'res_id': existing_clearance.id,
                }
            clearance = self.env['hr.clearance'].create({
                'employee_id': self.id,
            })
            return {
                'type': 'ir.actions.act_window',
                'name': _('Employee Clearance'),
                'res_model': 'hr.clearance',
                'view_mode': 'form',
                'res_id': clearance.id,
            }
        
        # Standard Odoo departure wizard fallback
        return {
            'name': _('Employee Offboarding / Departure'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.departure.wizard',
            'views': [[False, 'form']],
            'target': 'new',
            'context': {
                'active_id': self.id,
                'active_ids': self.ids,
                'default_employee_id': self.id,
            },
        }

    # --- Scheduled Cron: Contract Expiration & Project Completion Alerts ---
    @api.model
    def cron_check_project_contract_expiration(self):
        """
        Scans all project contract employees whose contract or project is expiring within 30 days.
        Posts alerts in employee chatter and notifies HR Managers.
        """
        today = fields.Date.today()
        threshold = today + timedelta(days=30)
        hr_group = self.env.ref('hr.group_hr_manager', raise_if_not_found=False)
        hr_users = hr_group.users if hr_group else self.env['res.users']
        hr_partners = hr_users.mapped('partner_id').ids

        employees = self.search([
            ('active', '=', True),
            ('is_contract_employee', '=', True),
            '|',
            '&', ('contract_date_end', '!=', False), ('contract_date_end', '<=', threshold),
            '&', ('is_project_contract', '=', True), ('contract_project_id', '!=', False),
        ])

        for emp in employees:
            proj = emp.contract_project_id
            proj_end = proj.date if proj else False
            contract_end = emp.contract_date_end

            # Check if project completed or contract expiring
            reasons = []
            if contract_end and contract_end <= threshold:
                days = (contract_end - today).days
                reasons.append(f"Contract ends on {contract_end.strftime('%d %b %Y')} ({days} days remaining)")
            if emp.is_project_contract and proj_end and proj_end <= threshold:
                proj_days = (proj_end - today).days
                reasons.append(f"Project '{proj.name}' ends on {proj_end.strftime('%d %b %Y')} ({proj_days} days remaining)")

            if reasons:
                status_summary = "<br/>• ".join(reasons)
                body = _(
                    "<b>Contract Expiry / Project Completion Notice</b><br/>"
                    "Employee: <b>%(emp_name)s</b><br/>"
                    "Section/Phase: <b>%(section)s</b><br/>"
                    "• %(summary)s<br/><br/>"
                    "<b>Action Required:</b> Check project end date to either initiate contract renewal or start offboarding."
                ) % {
                    'emp_name': emp.name,
                    'section': emp.project_section or 'General',
                    'summary': status_summary,
                }
                emp.message_post(body=body, partner_ids=hr_partners)
        return True

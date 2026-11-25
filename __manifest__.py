# -*- coding: utf-8 -*-
{
    'name': 'Employee Probation & Project Contract Management',
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Contract employee GM approval, Project Contract tracking, probation period, and completion alerts',
    'description': """
Employee Probation & Project Contract Management
================================================
Comprehensive contract overview extensions for Odoo 19:

1. **Contract Employee GM Approval**:
   - Automatic detection of contract/fixed-term employees.
   - GM approval workflow before hiring is finalized (`draft` -> `waiting_gm` -> `approved` / `rejected`).
   - Notification to GM and tracking of GM approval date & user.

2. **Project Contract Tracking**:
   - Checkbox `is_project_contract` in Contract Overview.
   - Link employee to specific Project (`contract_project_id`).
   - Identify project section/phase/WBS (`project_section`).
   - Live project end date and project completion state badge (`ongoing`, `approaching_completion`, `project_completed`).

3. **Contract Expiry, Renewal & Offboarding**:
   - When contract ends or employee leaves: check project end date.
   - One-click actions to either **Renew Contract** or **Start Offboarding** (launching HR Clearance or Departure Wizard).
   - Automated daily cron checking expiring project contracts (within 30 days) and notifying HR.

4. **Probation Period Management**:
   - Configurable duration (1, 2, 3, 6 months, or custom) and auto-computed dates.
   - Probation status badge (`in_progress`, `passed`, `extended`, `failed`).
   - Quick action buttons to Pass, Extend, or Fail probation.
    """,
    'author': 'Top Technologies',
    'website': 'https://toptechnologies.et',
    'license': 'LGPL-3',
    'depends': [
        'hr',
        'project',
        'mail',
    ],
    'data': [
        'data/ir_cron_data.xml',
        'views/hr_employee_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

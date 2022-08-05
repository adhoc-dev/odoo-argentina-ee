from odoo import models, fields


class ResCompany(models.Model):

    _inherit = 'res.company'

    l10n_ar_use_caea = fields.Boolean(compute="compute_l10n_ar_use_caea", store=True)

    l10n_ar_contingency_mode = fields.Boolean('Contingency Mode')

    def compute_l10n_ar_use_caea(self):
        """ Boolean used to know if we need CAEA number sincronization each fornight"""
        caea_companies = self.env['account.journal'].search([('l10n_ar_afip_pos_system', '=', 'RAW_MAW_CAEA')]).mapped('company_id')
        caea_companies.l10n_ar_use_caea = True
        (self - caea_companies).l10n_ar_use_caea = False

    def _l10n_ar_get_connection(self, afip_ws):
        """ Get simil ws for caea """
        self.ensure_one()
        if 'caea' in afip_ws:
            afip_ws = self.env['account.journal']._get_caea_simil_ws(afip_ws)
        return super()._l10n_ar_get_connection(afip_ws=afip_ws)

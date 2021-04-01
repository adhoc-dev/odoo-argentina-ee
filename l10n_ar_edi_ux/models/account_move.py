from odoo import models, fields, api, _
from odoo.addons.l10n_ar_edi.models.account_move import WS_DATE_FORMAT
from odoo.addons.l10n_ar_edi.models.afip_errors import _hint_msg as _original_hint_msg

def _hint_msg(error_code, afipws):
    """ Get expĺanation of errors returned by wsfe webservice and a hint of how to solved """
    data = _original_hint_msg(error_code, afipws) or {}
    if afipws == 'wsfe':
        data.update({
            '10216': _('The new RG 4919/2021 define that MiPYME document requires to inform the FCE Transmission Option. Set this one in "FCE: Transmission Option" field in your Accounting Settings'),
        })
    # Common errors
    data.update({'reprocess': _('The invoice is trying to be reprocessed'),
                 'rejected': _('The invoice has not been accepted by AFIP, please fix the errors and try again')})

    return data.get(error_code, '')


_original_hint_msg = _hint_msg


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_ar_afip_asoc_period_start = fields.Date(
        string='Associated Period Start',
        states={'draft': [('readonly', False)]},
        help='Set this field if it is you are reporting debit/credit note and have not related invoice')
    l10n_ar_afip_asoc_period_end = fields.Date(
        string='Associated Perdio End',
        states={'draft': [('readonly', False)]},
        help='Set this field if it is you are reporting debit/credit note and have not related invoice')

    def _found_related_invoice(self):
        """
        TODO borrar cuando se mezcle https://github.com/odoo/enterprise/pull/12972/files
        """
        res = super()._found_related_invoice()
        if not res and self.l10n_latam_document_type_id.internal_type in ['credit_note', 'debit_note'] and \
           self.sudo().env.ref('base.module_sale').state == 'installed':
            original_entry = self.mapped('invoice_line_ids.sale_line_ids.invoice_lines').filtered(
                lambda x:  x.move_id.l10n_latam_document_type_id.country_id.code == 'AR' and
                x.move_id.l10n_latam_document_type_id.internal_type != self.l10n_latam_document_type_id.internal_type
                and x.move_id.l10n_ar_afip_result in ['A', 'O'] and x.move_id.l10n_ar_afip_auth_code).mapped('move_id')
            return original_entry and original_entry[0] or res
        return res

    @api.model
    def wsfe_get_cae_request(self, client=None):
        res = super().wsfe_get_cae_request(client=client)
        if self.l10n_latam_document_type_id.internal_type in ['credit_note', 'debit_note']:
            related_invoices = self._get_related_invoice_data()
            if not related_invoices and self.l10n_ar_afip_asoc_period_start and self.l10n_ar_afip_asoc_period_end:
                res.get('FeDetReq')[0].get('FECAEDetRequest').update({'PeriodoAsoc': {
                    'FchDesde': self.l10n_ar_afip_asoc_period_start.strftime(WS_DATE_FORMAT['wsfe']),
                    'FchHasta': self.l10n_ar_afip_asoc_period_end.strftime(WS_DATE_FORMAT['wsfe'])}})
        return res

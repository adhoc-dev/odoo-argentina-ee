from odoo import _, models, fields
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):

    _inherit = 'account.move'

    l10n_ar_caea_id = fields.Many2one('l10n.ar.caea', copy=False)
    is_caea = fields.Boolean(compute="compute_is_caea")
    l10n_ar_afip_pos_system = fields.Selection(related="journal_id.l10n_ar_afip_pos_system")

    def compute_is_caea(self):
        cae_invoices = self.filtered(
            lambda x: (x.journal_id.l10n_ar_afip_pos_system and 'CAEA' in x.journal_id.l10n_ar_afip_pos_system and x.journal_id.l10n_ar_contingency_journal_id)
            or x.journal_id.l10n_ar_afip_ws == 'wsfe' and x.journal_id.company_id.l10n_ar_contingency_mode)
        cae_invoices.is_caea = True
        (self - cae_invoices).is_caea = False

    def _l10n_ar_do_afip_ws_request_cae(self, client, auth, transport):
        """ Extendemos el metodo original que termina haciendo lo de factura electrónica para integrar
        lo de CAEA, dicho caso no reportamos a AFIP de manera inmediata """
        # TODO KZ hacer cuando implementemos contingencia or .journal_id.caea_journal_id
        send_caea = self.env.context.get('send_cae_invoices', False)
        cae_invoices = self.filtered(lambda x: x.is_caea and not x.l10n_ar_afip_auth_code and not send_caea)
        cae_invoices._l10n_ar_caea_validate_local()

        return super(AccountMove, self - cae_invoices)._l10n_ar_do_afip_ws_request_cae(client=client, auth=auth, transport=transport)

    def _l10n_ar_caea_validate_local(self):
        """ Add CAEA number to the invoices that we need to validate and that will be inform later with CAEA """
        for inv in self:
            _logger.info("Validando Factura CAEA solo en local %s", inv.display_name)
            # TODO KZ oportunidad de mejora. mover el calculo del afip_caea previo al loop. desde alli ver los caea d
            # todas las compa;ias y hacer early return si no existe.
            afip_caea = inv.get_active_caea()
            if not afip_caea:
                raise UserError(_('Dont have CAEA Active'))
            values = {
                'l10n_ar_afip_auth_mode': 'CAEA',
                'l10n_ar_caea_id': afip_caea.id,
                'l10n_ar_afip_auth_code': afip_caea.name,
                'l10n_ar_afip_auth_code_due': self.invoice_date,
                'l10n_ar_afip_result': '',
            }
            inv.sudo().write(values)

    def get_active_caea(self):
        """Obtiene el CAEA actual que se puede usar para dicha factura """
        self.ensure_one()
        return self.env['l10n.ar.caea'].search([
            ('company_id', '=', self.company_id.id),
            ('date_from', '<=', self.date), ('date_to', '>=', self.date)])

    def wsfe_get_cae_request(self, client=None):
        """ Add more info needed for report to webserive with CAEA"""
        self.ensure_one()
        res = super().wsfe_get_cae_request(client=client)
        if self.l10n_ar_afip_ws == 'wsfe' and self.is_caea:
            afip_caea = self.get_active_caea()
            if not afip_caea:
                raise UserError(_('Dont have CAEA Active'))

            FeDetReq = res.get('FeDetReq')[0]
            FeDetReq['FECAEADetRequest'].update({
                'CAEA': afip_caea.name,
            })
            # * Code 1442: Si el punto de venta no es del tipo CONTINGENCIA para el CAEA en cuestion, no informar el campo CbteFchHsGen
            # 'CbteFchHsGen': self.date.strftime('%Y%m%d%H%M%S'),

            res.update({'FeDetReq': [FeDetReq]})
        return res

    def get_inv_tag_ws(self):
        return 'FECAEADetRequest' if self.is_caea else 'FECAEDetRequest'

    def action_reprocess_caea_afip(self):
        invoices = self.filtered(lambda x: x.is_caea and x.state == 'posted' and x.l10n_ar_afip_result == 'R')
        if not invoices:
            raise UserError(_('There is not Reject CAEA Invoices ro reject'))

        invoices.l10n_ar_afip_result = False
        for inv in invoices:
            _logger.info("Reprocesar Factura CAEA fallida en AFIP %s", inv.display_name)
            afip_caea = inv.get_active_caea()
            afip_ws = afip_caea.get_afip_ws()
            return_info_all = []
            client, auth, transport = inv.company_id._l10n_ar_get_connection(afip_ws)._get_client(return_transport=True)
            return_info = inv.with_context(send_cae_invoices=True)._l10n_ar_do_afip_ws_request_cae(client, auth, transport)
            if return_info:
                return_info_all.append("<strong>%s</strong> %s" % (inv.name, return_info))
        if return_info_all:
            self.message_post(body='<p><b>' + _('AFIP Messages') +
                              '</b></p><p><ul><li>%s</li></ul></p>' % ('</li><li>'.join(return_info_all)))

    def _post(self, soft=True):
        """ Si estoy en modo contingencia entonces cambio el diario automaticamente al diairo debackup
        que este configurando en el diaro seleccionado por el usuario """
        for inv in self.filtered(lambda x: x.company_id.l10n_ar_contingency_mode and x.journal_id.l10n_ar_contingency_journal_id):
            inv.journal_id = inv.journal_id.l10n_ar_contingency_journal_id
            inv.message_post(body=("Debido a que esta en modo contigencia se cambio el diario seleccionado por el de contigencia relacionado"))

        return super()._post(soft=soft)

    def get_invoices_to_inform_afip(self):
        return self.filtered(lambda x: x.journal_id.l10n_ar_afip_ws and (not x.l10n_ar_afip_auth_code or (x.is_caea and x.l10n_ar_afip_result not in ['A', 'O'])))

    def get_auth_mode(self):
        self.ensure_one()
        return 'CAEA' if self.is_caea else 'CAE'

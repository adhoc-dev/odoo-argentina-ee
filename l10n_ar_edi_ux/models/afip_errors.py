from odoo import _
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

from rest_framework.renderers import BaseRenderer


class CSVRenderer(BaseRenderer):
    """Lets DRF content negotiation accept `?format=csv` on report endpoints.
    The views themselves return a prepared text/csv HttpResponse."""

    media_type = 'text/csv'
    format = 'csv'
    charset = 'utf-8'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data

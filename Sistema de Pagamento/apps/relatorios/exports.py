import csv

from django.http import HttpResponse
from django.template.loader import render_to_string


def response_csv(filename, headers, rows):
    """RF53 — exportação CSV."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(headers)
    writer.writerows(rows)
    return response


def response_excel(filename, headers, rows):
    """RF53 — exportação Excel."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response


def response_pdf(template_name, context, filename):
    """RF53 — exportação PDF (também usado para a Ordem de Pagamento — RF33)."""
    from xhtml2pdf import pisa

    html = render_to_string(template_name, context)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    pisa.CreatePDF(html, dest=response)
    return response

from fastapi import APIRouter, HTTPException, Query, Depends
from api.modules.qbo import QBOManager
from fastapi_limiter.depends import RateLimiter
import logging
import pytz
from datetime import datetime

router = APIRouter()

@router.get("/get_invoice", dependencies=[Depends(RateLimiter(times=5, seconds=60))])
async def get_invoice(id: str = Query(..., description="The ID (DocNumber) of the invoice to retrieve")):
    """Retrieve a specific invoice by its ID (DocNumber)."""
    try:
        manager = QBOManager()
        client = manager.get_client()
        query = f"SELECT * FROM Invoice WHERE DocNumber = '{id}'"
        logging.info(f"Executing query: {query}")
        invoices = client.query(query)
        logging.info(f"Query result: {invoices}")
        invoice_list = invoices.get('QueryResponse', {}).get('Invoice', [])
        if not invoice_list:
            logging.warning("Invoice not found")
            raise HTTPException(status_code=404, detail="Invoice not found")
        invoice = invoice_list[0]
        return {
            'id': invoice['Id'],
            'doc_number': invoice['DocNumber'],
            'customer_ref': invoice['CustomerRef']['name'] if 'CustomerRef' in invoice else None,
            'total_amount': float(invoice['TotalAmt']) if 'TotalAmt' in invoice else 0.0,
            'balance': float(invoice['Balance']) if 'Balance' in invoice else 0.0,
            'date': invoice['TxnDate'],
            'due_date': invoice['DueDate'],
            'status': invoice['EmailStatus'],
            'last_modified_utc': datetime.fromisoformat(invoice['MetaData']['LastUpdatedTime']).astimezone(pytz.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        }
    except Exception as e:
        logging.error(f"Error retrieving invoice: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve invoice: {str(e)}"
        ) 
import random
import string
from datetime import datetime

def generate_transaction_reference(prefix='TXN'):
    """Generate a unique transaction reference.
    Format: PREFIX-YYYYMMDD-XXXXX where X is alphanumeric
    Example: TXN-20231205-A7B2C
    """
    # Get current date
    date_str = datetime.now().strftime('%Y%m%d')
    
    # Generate 5 random alphanumeric characters
    chars = string.ascii_uppercase + string.digits
    random_str = ''.join(random.choices(chars, k=5))
    
    # Combine all parts
    reference = f"{prefix}-{date_str}-{random_str}"
    
    return reference

def generate_mpesa_reference():
    """Generate a reference number similar to M-PESA transaction IDs.
    Format: PXJ<7 digits>
    Example: PXJ1234567
    """
    prefix = 'PXJ'
    # Generate 7 random digits
    digits = ''.join(random.choices(string.digits, k=7))
    
    return f"{prefix}{digits}"

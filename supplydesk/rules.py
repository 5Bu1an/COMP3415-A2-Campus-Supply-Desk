"""Business rules for Campus Supply Desk, defined once and shared.
All money values are integer cents."""

# Customer types
REGULAR = "regular"
STUDENT = "student"
CUSTOMER_TYPES = (REGULAR, STUDENT)
DEFAULT_CUSTOMER_TYPE = REGULAR

# Fulfillment options
PICKUP = "pickup"
DELIVERY = "delivery"
EXPRESS = "express"                      # CR-01
FULFILLMENT_OPTIONS = (PICKUP, DELIVERY, EXPRESS)
DEFAULT_FULFILLMENT = PICKUP

# Quantity limits per line
MIN_QUANTITY = 1
MAX_QUANTITY = 99

# Student discount: 10% when subtotal is over the threshold
STUDENT_DISCOUNT_THRESHOLD_CENTS = 5000
STUDENT_DISCOUNT_PERCENT = 10

# Standard delivery: flat fee unless the discounted subtotal reaches the threshold
DELIVERY_FEE_CENTS = 600
FREE_DELIVERY_THRESHOLD_CENTS = 10000

# Express delivery (CR-01): flat fee, never waived
EXPRESS_FEE_CENTS = 1200
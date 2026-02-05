import stripe, uuid, time
from open_webui.models.users import Users

stripe.api_key = "sk_test_xxx"

# Create test user
uid = f"billing_test_{uuid.uuid4().hex[:8]}"
email = f"{uid}@example.com"
print('Creating test user', uid, email)
user = Users.insert_new_user(uid, 'Billing Test', email)
print('Inserted user:', user)

# Create Stripe customer
cust = stripe.Customer.create(email=email, metadata={'user_id': uid})
print('Created Stripe customer:', cust.id)

# Persist customer id in user.info
u = Users.get_user_by_id(uid)
info = u.info or {}
info['stripe_customer_id'] = cust.id
Users.update_user_by_id(uid, {'info': info})
print('Updated user info with stripe_customer_id')

# Create billing portal session
return_url = 'http://localhost:8080'
session = stripe.billing_portal.Session.create(customer=cust.id, return_url=return_url)
print('Portal URL:', session.url)

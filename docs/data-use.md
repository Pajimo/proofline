# Data use

Checked on 28 Oct 2026 against the [Meta Model API Terms of Service](https://dev.meta.ai/legal/terms-of-service). This is our reading, not legal advice.

## Does Meta train on what we send?

- **Standard Services (what this product uses, with an API key): no.** Section 5.1 says Meta will not use content submitted in a request to the Standard Services to train Meta models.
- **Contributor Services: yes.** Section 6.1 lets Meta use the content to train, develop, evaluate and improve its models. You opt in by calling a model id ending in `-contributor`. **We never call `-contributor` models.** Section 6.2 also bans sending sensitive or personal information to them.
- **Careful with Muse Code.** Section 3.3 says coding-harness subscription users are on Contributor Services by default, whichever model they pick. That covers building the code, not the product's runtime calls. No customer data goes through Muse Code.

## Does Meta store it?

Section 4.4 says Meta keeps content and usage data "as needed" to provide the service (and for things like abuse and policy review). It gives no fixed period. Zero Data Retention exists for qualified accounts by request ([help article](https://dev.meta.ai/help/policies-and-privacy/zero-data-retention)). We don't have it.

What we do:
- Uploaded customer videos are deleted from the Files API (`DELETE /v1/files/{id}`) straight after each Spark call.
- WhatsApp media is downloaded to the tradesperson's own server. WhatsApp media URLs expire.

## Who is responsible for customer data?

**The tradesperson is the business responsible for their customers' data** (the controller, under UK GDPR). The product is software they run. Under section 6.2 of the terms, the tradesperson needs a privacy policy that tells customers what's collected. The first automated reply says it's an AI assistant.

## Other conditions in the terms

- Users must be 18 or over (section 10.1). The product is not for under-18s.
- Customers film their own homes, by choice, to get help. The tradesperson never films customers.
- The demo uses only footage we filmed ourselves or free stock clips. No real customer data is committed to this repo.

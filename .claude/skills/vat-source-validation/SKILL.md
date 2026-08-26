---
name: vat-source-validation
description: Workflow for validating a candidate UK VAT source and reporting findings for the vat-identifier-discovery project — how to verify VAT numbers via HMRC/VIES, and how to structure the resulting write-up.
---

## Source Validation

In order to verify the validity of a source (mainly checking if any VAT values obtained from it are valid VAT numbers and that there is a valid and verifiable correspondence with any of the sample's entries), there are several options to consider:

* The __HMRC VAT number checker API:__ Your main goto validation option. You can try using it through the [form webpage](https://www.tax.service.gov.uk/check-vat-number/enter-vat-details), or through its V2 API for authenticated, rate-limited repeated checks. Regarding the latter, I have created the necessary environment variables - `HMRC_CLIENT_ID` and `HMRC_CLIENT_SECRET` - that are required to generate an access token to be used for the API calls; you only need to link them in any Python script that you draft, using `dotenv` (the module is already installed in the Python environment that you will use; for how to use it, refer to these 2 links: [How to handle Secrets in Python](https://medium.com/@michael.hannecke/secure-python-secret-management-cloud-local-e80cfa986d4c) and [Documentation](https://www.dotenv.org/docs/)). Any code you write must read these two values from the process environment at call time only, and must never copy, log, or commit them. Sandbox access requires registering an application on the HMRC Developer Hub, subscribing it to this API, and using the sandbox test credentials issued for it (since the production one would require applying for permission and waiting around 2 weeks for a response). For more information on how to use the API in the sandbox/test environment and how to handle the authorization part, refer to the following links:
  * [Check a UK VAT number API](https://developer.service.hmrc.gov.uk/api-documentation/docs/api/service/vat-registered-companies-api/2.0);
  * [Check a UK VAT number (2.0) (OpenAPI docs)](https://developer.service.hmrc.gov.uk/api-documentation/docs/api/service/vat-registered-companies-api/2.0/oas/page);
  * [Reference guide](https://developer.service.hmrc.gov.uk/api-documentation/docs/reference-guide);
  * [Authorisation: Application-restricted endpoints](https://developer.service.hmrc.gov.uk/api-documentation/docs/authorisation/application-restricted-endpoints);
  * [Testing in the sandbox](https://developer.service.hmrc.gov.uk/api-documentation/docs/testing).
* The __HMRC EORI number checker API:__ Another validation option for the adjacent identifier path. Unlike the __VAT API__, this one is available through an open access endpoint (no authorisation required). For more details on the API, refer to [this](https://developer.service.hmrc.gov.uk/api-documentation/docs/api/service/check-eori-number-api/1.0).
* __[VIES](https://ec.europa.eu/taxation_customs/vies/#/vat-validation):__ Use this only for EU VAT identifiers and `XI`-prefixed Northern Ireland identifiers; never submit ordinary `GB` VAT numbers to VIES. Validate `GB` VAT numbers through HMRC, and retain HMRC confirmation for every UK VAT number reported in the final deliverable, including any `XI` identifier also checked through VIES.

These options are what I can provide you with at the moment; should you discover other candidate validation options, you are more than welcome to pitch them to me.

## Communication

When validating a candidate VAT source against the sample, ensure that your reasoning includes:

* How the sample was chosen and why it is representative.
* A traceable source trail showing what was tried, the evidence returned, and the resulting conclusions.
* Material dead ends, including the source, the expected result, and the specific reason each path failed.
* HMRC confirmation for every UK VAT number reported as found.
* The measured false-positive rate, how it was measured, and the sample used.
* The limitations of the process and what the reported results do not capture.

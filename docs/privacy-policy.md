# Privacy policy: FirstLook (working name)

Last updated: 29 October 2026

FirstLook is an AI assistant that answers a tradesperson's WhatsApp messages. Customers send a photo, video, voice note or text about a problem in their home. The assistant looks at it, asks follow-up questions, gives safety advice where needed, and prepares an estimate for the tradesperson to check. This policy explains what data that involves.

This is a hackathon prototype (Meta Global AI Developer Hackathon, 27 Oct – 4 Nov 2026). During the hackathon it is used only with test numbers and by people taking part in testing. It isn't offered to the public.

## Who is responsible

The tradesperson whose WhatsApp number you message is the business responsible for your data (the "controller" under UK GDPR). FirstLook is software that runs for them. During the hackathon, the tradesperson in the demo ("Dave's Plumbing") is fictional, and the operator is the developer of this repository.

## What we collect

When you message the number, we receive what WhatsApp sends us:
- your WhatsApp phone number and profile name,
- the messages you send: text, photos, videos, voice notes and button taps,
- the time of each message.

We don't ask for, and you shouldn't send, payment details, health information, or images of people. Point the camera at the problem, not at people.

## How we use it

- To understand the problem: the video and audio are analysed by Meta's AI models (Muse Spark, SAM, Muse Voice Transcribe, Muse Wonder) through the Meta Model API.
- To reply to you: follow-up questions, safety advice, and a highlighted clip of what the assistant spotted.
- To give the tradesperson a summary and a draft estimate. Every price is checked and approved by the tradesperson before you see it.
- To test and improve the assistant's safety and accuracy (only on data from people taking part in testing).

We don't sell your data and don't use it for advertising.

## Who else processes it

- **Meta (WhatsApp)** carries the messages. See WhatsApp's own privacy policy.
- **Meta (Model API)** runs the AI models. Under Meta's terms for the standard Model API, request content is not used to train Meta's models. Meta may keep it for as long as needed to provide the service and for safety and abuse review.
- **Cloudflare** may carry webhook traffic between WhatsApp and our server during testing.

## How long we keep it

- Videos uploaded for analysis are deleted from the Meta Model API's file storage straight after each analysis.
- Media and messages on our server are kept only for as long as needed to handle the job, and no longer than 30 days during the hackathon. Test media is never published or committed to the source code repository.

## Your rights

You can ask for a copy of your data, ask us to correct it, or ask us to delete it. To delete your data, send the message "delete my data" to the same WhatsApp number, or open an issue on the project's GitHub page. We'll delete your messages and media within 30 days and confirm when it's done. You can also complain to the UK Information Commissioner's Office (ico.org.uk).

## Age

The service is for people aged 18 or over.

## Changes

If this policy changes, the date at the top will change.

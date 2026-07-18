# Axon Lead Suite

Find businesses without a website. Reach out to them on WhatsApp automatically. Built for freelancers and agencies doing manual outreach at scale.

## Demo
https://github.com/user-attachments/assets/518836b5-6e9d-4bf6-903d-044dee458d09

## What it does

Axon Lead Suite scrapes Google Maps for businesses in any location and category, filters out anyone who already has a website, and hands you a clean lead list with name, phone number, and Maps link. From there you can launch automated, personalized WhatsApp campaigns straight from the dashboard, and get help along the way from Axon, a built-in AI assistant for coding and outreach questions.

This exists because manually searching Google Maps for "restaurants near X with no website" doesn't work. Google doesn't expose that as a filter. So the tool does the filtering itself, one listing at a time.

## How the lead detection works

The scraper opens every business listing found in a search and checks two DOM signals Google Maps uses for the website field: a data attribute Google reserves for verified business websites, and a fallback label that catches anything Google displays as "Website" on the listing. If neither is present, the business gets flagged as a lead and its name, phone number, and Maps URL get pulled out.

One known tradeoff: the fallback selector doesn't distinguish a real business domain from a Facebook or Instagram page listed as the "website." Google's verified-website field is checked first and is reliable, but the fallback is intentionally permissive to avoid missing real websites, which means it occasionally lets a social-media-only listing through. Worth knowing if you're relying on lead quality over lead quantity.

## Features

- **Google Maps Lead Hunter** — scrape any location and business category, get back only businesses without a website
- **WhatsApp Automated Outreach** — bulk, personalized messaging straight from scraped leads, no manual copy-pasting
- **Axon AI Chat** — an assistant built into the dashboard for coding help and outreach message drafting
- **Live Dashboard** — track scraping and messaging jobs in real time, with progress and logs

## Tech Stack

| Layer | Tech |
|---|---|
| Backend | Python, Flask |
| Scraping | Playwright |
| Messaging | WhatsApp Web automation |
| AI | OpenAI-compatible API |
| Frontend | Vanilla HTML/CSS/JS |

## Architecture

app.py                    → API routes, background task manager, WhatsApp auth
index.html                → single-page dashboard (Lead Hunter, Campaigns, Axon Chat)
leads/leads.py             → Playwright scraper, website detection, lead extraction
leads/sender.py             → WhatsApp bulk messaging
leads/whatsapp_link.py       → QR code auth for WhatsApp Web

## Setup

```bash
git clone https://github.com/Tayyab-Hussayn/leadsGen.git
cd leadsGen
pip install -r requirements.txt
playwright install

# set your API key
export OPENAI_API_KEY=your_key_here

python app.py
```

Scan the WhatsApp QR code on first run to link your account. Then hunt leads, launch campaigns, and let Axon help you along the way.

## Status

Open source, fully working end to end.

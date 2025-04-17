# Date Formatting Logic in Old Style Flickr

This project displays dates (such as "Date uploaded" and "Date taken") in a friendly, human-readable format (e.g., "Today at 7:00 PM", "Yesterday at 10:15 AM", "Apr 16, 2025, 7:00 PM").

## Where Formatting Happens

- **Backend (Python, Jinja2 templates):**
  - The function `datetimeformat` in `main.py` is used as a Jinja2 filter for server-rendered templates.
- **Frontend (JavaScript, dynamic pages):**
  - The function `datetimeformat` in the inline script of `templates/friends.html` is used for client-side rendering.

## Keeping Logic in Sync

- **IMPORTANT:** The logic for formatting dates is duplicated in both Python (`main.py`) and JavaScript (`templates/friends.html`).
- If you update date/time formatting in one place, you **must** update the other to match.
- Each implementation includes a comment/docstring referencing the other.

## Why?

- Some pages are rendered server-side (Jinja2), others use dynamic JS rendering. This requires both environments to have the same formatting logic.

## How to Update

1. Edit both the Python and JavaScript `datetimeformat` implementations if you want to change how dates are displayed.
2. Ensure the output matches for the same input.
3. See comments in `main.py` and `templates/friends.html` for details and locations.

---

_Last updated: 2025-04-16_

"""Donation / support links shown in the "❤ 후원하기" dialog.

Edit this file to set your actual URLs. Entries with ``url=""`` are hidden.
Use ``copy_text`` for bank accounts or Toss IDs you'd rather have copied
than opened in a browser.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DonationOption:
    key: str               # i18n key suffix: "donation.<key>"
    url: str = ""          # opened in browser when clicked
    copy_text: str = ""    # copied to clipboard (shown instead of URL if set)
    icon: str = "❤"


# Donation targets for KyoungSeok Ko (artmouse / kuoungseok).
DONATIONS: list[DonationOption] = [
    DonationOption(
        key="paypal",
        url="https://paypal.me/KyoungseokKo",
        icon="💰",
    ),
    DonationOption(
        key="github_sponsors",
        url="https://github.com/sponsors/kuoungseok",
        icon="💝",
    ),
    DonationOption(
        key="github_star",
        url="https://github.com/kuoungseok/gifcam",
        icon="⭐",
    ),
]


def enabled_donations() -> list[DonationOption]:
    return [d for d in DONATIONS if d.url or d.copy_text]

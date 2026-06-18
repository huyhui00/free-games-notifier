name: Free Games Notifier

on:
  schedule:
    - cron: '0 11 * * 4'  # ทุกวันพฤหัส 18:00 น. (เวลาไทย = UTC+7)
  workflow_dispatch:        # กดรันมือได้จาก GitHub

jobs:
  notify:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install requests

      - name: Run notifier
        env:
          DISCORD_WEBHOOK_URL: ${{ secrets.DISCORD_WEBHOOK_URL }}
        run: python notify.py

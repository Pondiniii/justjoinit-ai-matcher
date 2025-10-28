#!/bin/bash
# Fetch ALL job offers from JustJoin.IT
# Usage: ./fetch_offers.sh

set -e

OUTPUT_DIR="data"
PAGES_DIR="$OUTPUT_DIR/pages"
OFFERS_JSON="$OUTPUT_DIR/offers.json"

mkdir -p "$PAGES_DIR"

echo "🔍 Fetching ALL offers from JustJoin.IT..."
echo ""

# Clean old pages
rm -f "$PAGES_DIR"/*.html

BASE_URL="https://justjoin.it/job-offers/remote?employment-type=b2b&experience-level=mid,senior&with-salary=yes&orderBy=DESC&sortBy=published"
#BASE_URL="https://justjoin.it/"

# Fetch first page
echo "📥 Downloading first page..."
curl -s "$BASE_URL" \
    -H 'user-agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36' \
    -o "$PAGES_DIR/all_page_0.html"

# Extract total count (try both patterns: base URL and filtered URL)
TOTAL=$(grep -oP '(?<=- )[\d\s]+(?= offers)' "$PAGES_DIR/all_page_0.html" | tr -d ' ' | head -1)
if [ -z "$TOTAL" ]; then
    # Try meta description pattern (for filtered URLs)
    TOTAL=$(grep -oP -- '- [\d\s,]+ current' "$PAGES_DIR/all_page_0.html" | grep -oP '[\d\s,]+' | head -1 | tr -d ' ,')
fi
TOTAL=$(echo "$TOTAL" | tr -cd '0-9')

if [ -z "$TOTAL" ] || [ "$TOTAL" -eq 0 ]; then
    echo "  ⚠️  No offers found"
    exit 1
fi

PAGES=$(( (TOTAL + 99) / 100 ))
echo "  → $TOTAL offers across $PAGES pages"
echo ""

# Detect query separator (? or &)
if [[ "$BASE_URL" == *"?"* ]]; then
    SEPARATOR="&"
else
    SEPARATOR="?"
fi

# Fetch remaining pages
for i in $(seq 1 $((PAGES - 1))); do
    FROM=$((i * 100))
    echo "📥 Downloading page $((i + 1))/$PAGES..."
    curl -s "${BASE_URL}${SEPARATOR}from=${FROM}&itemsCount=100" \
        -H 'user-agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36' \
        -o "$PAGES_DIR/all_page_$i.html"

    sleep 0.5  # Rate limiting
done

echo ""
echo "✓ Downloaded $PAGES HTML pages"
echo ""
echo "📝 Parsing HTML → JSON..."

# Use external parser
python3 scripts/parse_pages.py

echo ""
echo "🎉 Done! Run: python main.py"

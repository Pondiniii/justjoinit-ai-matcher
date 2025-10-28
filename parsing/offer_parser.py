#!/usr/bin/env python3
"""Parser for single job offer detail page"""

import re
import subprocess
from bs4 import BeautifulSoup
from typing import Dict, Any, Optional


def fetch_offer_html(url: str) -> Optional[str]:
    """Fetch offer HTML using curl"""
    cmd = [
        'curl', '-s', url,
        '-H', 'accept: text/html,application/xhtml+xml,application/xml;q=0.9',
        '-H', 'accept-language: pl-PL,pl;q=0.7',
        '-H', 'user-agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and len(result.stdout) > 1000:
            return result.stdout
    except Exception as e:
        print(f"Error fetching {url}: {e}")

    return None


def parse_offer_detail(html: str) -> Dict[str, Any]:
    """
    Parse detailed offer page HTML
    Extract: title, company, location, salary, tech_stack, requirements, benefits, description
    """
    soup = BeautifulSoup(html, 'html.parser')

    result = {
        'title': None,
        'company': None,
        'location': None,
        'salary_min': None,
        'salary_max': None,
        'salary_currency': None,
        'salary_rate': None,  # hourly, monthly, yearly
        'salary_type': None,  # gross, net
        'tech_stack': {},
        'requirements': {},
        'benefits': [],
        'description': '',
        'remote_mode': None,
        'contract_type': None,
        'exp_level': None,
        'employment_type': None,
    }

    # Title and Company - parse from <title> tag (format: "JobTitle - CompanyName")
    title_elem = soup.find('title')
    if title_elem:
        title_text = title_elem.get_text(strip=True)
        # Format is usually "JobTitle - CompanyName"
        if ' - ' in title_text:
            parts = title_text.split(' - ', 1)
            result['title'] = parts[0].strip()
            result['company'] = parts[1].strip()[:100]  # Limit length
        else:
            result['title'] = title_text

    # Fallback: use h1 for title if <title> tag didn't work
    if not result['title']:
        h1_tag = soup.find('h1')
        if h1_tag:
            result['title'] = h1_tag.get_text(strip=True)

    # Get full text for pattern matching
    full_text = soup.get_text()

    # Location - look for location patterns
    location_patterns = [
        r'Location:\s*([A-Za-zęółąśżźćńĘÓŁĄŚŻŹĆŃ\s,]+)',
        r'Lokalizacja:\s*([A-Za-zęółąśżźćńĘÓŁĄŚŻŹĆŃ\s,]+)',
        r'📍\s*([A-Za-zęółąśżźćńĘÓŁĄŚŻŹĆŃ\s,]+)',
    ]
    for pattern in location_patterns:
        loc_match = re.search(pattern, full_text, re.I)
        if loc_match:
            result['location'] = loc_match.group(1).strip()[:100]
            break

    # Tech stack - szukamy sekcji z językami/technologiami
    # IMPORTANT: Remove script tags first (React/Next.js hydration scripts contain garbage)
    for script in soup.find_all('script'):
        script.decompose()

    tech_sections = soup.find_all(string=re.compile(r'Tech stack|Technology', re.I))
    tech_items = []

    for section in tech_sections:
        parent = section.find_parent()
        if parent:
            # Szukaj poziomów: advanced, regular, nice to have
            siblings = parent.find_next_siblings()
            for sib in siblings[:10]:  # Ogranicz do 10 następnych elementów
                text = sib.get_text(strip=True)
                # Filter out garbage: must be short, not contain script artifacts
                if text and 5 < len(text) < 100 and 'self.__next_f' not in text and 'push([' not in text:
                    # Parsuj format: "Python advanced" lub "Docker regular"
                    match = re.match(r'(.+?)\s*(advanced|regular|nice to have|expert)?$', text, re.I)
                    if match:
                        tech = match.group(1).strip()
                        # Skip if tech name contains script garbage
                        if 'self.' not in tech and 'push' not in tech and '__next' not in tech:
                            level = match.group(2) or 'regular'
                            tech_items.append({'name': tech, 'level': level.lower()})

    # Grupuj tech stack
    for item in tech_items:
        level = item['level']
        if level not in result['tech_stack']:
            result['tech_stack'][level] = []
        result['tech_stack'][level].append(item['name'])

    # Job description - główny tekst
    desc_markers = ['Job description', 'About the', 'Your responsibilities', 'What you']
    for marker in desc_markers:
        section = soup.find(string=re.compile(marker, re.I))
        if section:
            parent = section.find_parent()
            if parent:
                # Zbierz następne paragrafy
                desc_parts = []
                for elem in parent.find_next_siblings()[:20]:
                    text = elem.get_text(strip=True)
                    if text and len(text) > 50:
                        desc_parts.append(text)
                    if len(desc_parts) >= 5:  # Max 5 paragrafów
                        break

                if desc_parts:
                    result['description'] = '\n\n'.join(desc_parts)
                    break

    # Requirements
    req_section = soup.find(string=re.compile(r'Our requirements|Requirements', re.I))
    if req_section:
        parent = req_section.find_parent()
        if parent:
            reqs = []
            for elem in parent.find_next_siblings()[:15]:
                text = elem.get_text(strip=True)
                if text and 20 < len(text) < 200:
                    reqs.append(text)
            result['requirements'] = {'items': reqs}

    # Benefits
    benefits_section = soup.find(string=re.compile(r'Our offer|Benefits|We offer', re.I))
    if benefits_section:
        parent = benefits_section.find_parent()
        if parent:
            for elem in parent.find_next_siblings()[:15]:
                text = elem.get_text(strip=True)
                if text and 10 < len(text) < 200:
                    result['benefits'].append(text)

    # Remote mode - szukaj w całym dokumencie
    full_text_lower = full_text.lower()
    if 'fully remote' in full_text_lower or '100% remote' in full_text_lower:
        result['remote_mode'] = 'remote'
    elif 'hybrid' in full_text_lower:
        result['remote_mode'] = 'hybrid'
    elif 'on-site' in full_text_lower or 'onsite' in full_text_lower or 'office' in full_text_lower:
        result['remote_mode'] = 'onsite'

    # Contract type
    if 'b2b' in full_text_lower:
        result['contract_type'] = 'b2b'
    elif 'uop' in full_text_lower or 'umowa o pracę' in full_text_lower:
        result['contract_type'] = 'uop'

    # Experience level
    if 'senior' in full_text_lower:
        result['exp_level'] = 'senior'
    elif 'junior' in full_text_lower:
        result['exp_level'] = 'junior'
    else:
        result['exp_level'] = 'mid'

    # Salary parsing - widełki lub pojedyncza kwota + rate + type
    # Pattern: "9 000 - 16 000 PLN/month" lub "120 - 160 PLN/h"
    salary_patterns = [
        r'(\d[\d\s]+)\s*-\s*(\d[\d\s]+)\s*(PLN|USD|EUR|zł)(?:/(\w+))?',  # Range with optional rate
        r'(\d[\d\s]+)\s*(PLN|USD|EUR|zł)(?:/(\w+))?',  # Single with optional rate
    ]

    for pattern in salary_patterns:
        salary_match = re.search(pattern, full_text, re.I)
        if salary_match:
            groups = salary_match.groups()
            if len(groups) == 4 and groups[2]:  # Range with optional rate
                result['salary_min'] = int(groups[0].replace(' ', ''))
                result['salary_max'] = int(groups[1].replace(' ', ''))
                result['salary_currency'] = groups[2].upper().replace('ZŁ', 'PLN')
                # Parse rate: month, h (hour), year
                if groups[3]:
                    rate_lower = groups[3].lower()
                    if 'month' in rate_lower or 'mies' in rate_lower:
                        result['salary_rate'] = 'monthly'
                    elif 'h' in rate_lower or 'hour' in rate_lower or 'godz' in rate_lower:
                        result['salary_rate'] = 'hourly'
                    elif 'year' in rate_lower or 'rok' in rate_lower or 'annual' in rate_lower:
                        result['salary_rate'] = 'yearly'
            elif len(groups) == 3 and groups[1]:  # Single value with optional rate
                amount = int(groups[0].replace(' ', ''))
                result['salary_min'] = amount
                result['salary_max'] = amount
                result['salary_currency'] = groups[1].upper().replace('ZŁ', 'PLN')
                if groups[2]:
                    rate_lower = groups[2].lower()
                    if 'month' in rate_lower or 'mies' in rate_lower:
                        result['salary_rate'] = 'monthly'
                    elif 'h' in rate_lower or 'hour' in rate_lower or 'godz' in rate_lower:
                        result['salary_rate'] = 'hourly'
                    elif 'year' in rate_lower or 'rok' in rate_lower or 'annual' in rate_lower:
                        result['salary_rate'] = 'yearly'
            break

    # Salary type (gross/net) - search near salary info
    if result['salary_min']:
        # Look for gross/net keywords in context around salary
        if re.search(r'gross|brutto', full_text_lower):
            result['salary_type'] = 'gross'
        elif re.search(r'\bnet\b|netto', full_text_lower):
            result['salary_type'] = 'net'

    # Employment type (Full-time, Part-time, etc.)
    if 'full-time' in full_text_lower or 'full time' in full_text_lower:
        result['employment_type'] = 'full-time'
    elif 'part-time' in full_text_lower or 'part time' in full_text_lower:
        result['employment_type'] = 'part-time'

    return result


def extract_content_for_llm(parsed: Dict[str, Any], html: str) -> str:
    """
    Extract text content for LLM analysis
    Zoptymalizowane - tylko istotne fragmenty
    """
    soup = BeautifulSoup(html, 'html.parser')

    # Usuń skrypty, style, SVG
    for tag in soup(['script', 'style', 'svg', 'path']):
        tag.decompose()

    # Zbierz tekst
    text = soup.get_text(separator='\n', strip=True)

    # Cleanup - usuń puste linie i nadmiar whitespace
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    cleaned = '\n'.join(lines)

    # Ogranicz długość do ~4000 znaków (żeby nie przekroczyć context LLM)
    if len(cleaned) > 4000:
        cleaned = cleaned[:4000] + "\n\n[...TRUNCATED...]"

    return cleaned


if __name__ == '__main__':
    # Test na przykładowej ofercie
    test_url = 'https://justjoin.it/job-offer/travelplanet-pl-sa-senior-devops-engineer-wroclaw-devops'

    print(f"Fetching: {test_url}")
    html = fetch_offer_html(test_url)

    if html:
        print(f"✓ Fetched {len(html)} bytes")

        parsed = parse_offer_detail(html)
        print(f"\n✓ Parsed offer:")
        print(f"  Remote: {parsed['remote_mode']}")
        print(f"  Contract: {parsed['contract_type']}")
        print(f"  Level: {parsed['exp_level']}")
        print(f"  Tech stack: {list(parsed['tech_stack'].keys())}")
        print(f"  Benefits: {len(parsed['benefits'])} items")
        print(f"  Description length: {len(parsed['description'])} chars")

        # Test LLM content extraction
        llm_content = extract_content_for_llm(parsed, html)
        print(f"\n✓ LLM content: {len(llm_content)} chars")
        print(f"\nFirst 500 chars:\n{llm_content[:500]}...")
    else:
        print("✗ Failed to fetch")

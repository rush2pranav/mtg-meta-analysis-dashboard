"""
Magic: The Gathering Data Fetcher
==================================
Pulls card data from Scryfall's bulk data API and transforms it into a Power BI-ready CSV file.
API docs: https://scryfall.com/docs/api
"""

import requests
import pandas as pd
import json
import os
import time

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
os.makedirs(DATA_DIR, exist_ok=True)


def fetch_bulk_data():
    """Download Oracle Cards bulk data from Scryfall."""
    print("=== Fetching Scryfall Bulk Data ===\n")
    
    # download url for the Oracle cards
    print("Getting bulk data URL...")
    headers = {
        'User-Agent': 'MTGAnalysisDashboard/1.0',
        'Accept': 'application/json'
    }
    resp = requests.get('https://api.scryfall.com/bulk-data/oracle-cards', headers=headers)
    resp.raise_for_status()
    bulk_info = resp.json()
    
    download_url = bulk_info['download_uri']
    print(f"  Download URL: {download_url}")
    print(f"  Size: ~{bulk_info.get('size', 0) / 1024 / 1024:.1f} MB")
    
    # downloading the actual data
    print("-----Downloading the data-----")
    resp = requests.get(download_url, headers=headers, timeout=120)
    resp.raise_for_status()
    
    cards = resp.json()
    print(f"Downloaded {len(cards):,} cards")
    
    # save as raw JSON
    raw_path = os.path.join(DATA_DIR, 'scryfall_oracle_cards.json')
    with open(raw_path, 'w', encoding='utf-8') as f:
        json.dump(cards, f)
    print(f"Raw JSON saved: {raw_path}")
    
    return cards


def transform_cards(cards):
    """Transform raw Scryfall JSON into a clean DataFrame"""
    print("\n=== Transforming Card Data ===\n")
    
    processed = []
    for card in cards:
        # skipping the non game cards along with tokens and emblems
        layout = card.get('layout', '')
        if layout in ['token', 'emblem', 'art_series', 'double_faced_token']:
            continue
        if card.get('set_type', '') in ['token', 'memorabilia', 'funny']:
            continue
        
        # extracting the mana cost info
        mana_cost = card.get('mana_cost', '') or ''
        cmc = card.get('cmc', 0) or 0
        
        # extracting the colors
        colors = card.get('colors', []) or []
        color_identity = card.get('color_identity', []) or []
        
        # color classification
        num_colors = len(colors)
        if num_colors == 0:
            color_group = 'Colorless'
        elif num_colors == 1:
            color_map = {'W': 'White', 'U': 'Blue', 'B': 'Black', 'R': 'Red', 'G': 'Green'}
            color_group = color_map.get(colors[0], 'Colorless')
        elif num_colors == 2:
            color_group = 'Two-Color'
        elif num_colors >= 3:
            color_group = 'Multi-Color (3+)'
        else:
            color_group = 'Colorless'
        
        # extracting power/toughness for the creatures
        power = card.get('power', '')
        toughness = card.get('toughness', '')
        
        # converting the numerics since some values are not identifiable
        try:
            power_num = float(power) if power and power.replace('.', '').isdigit() else None
        except (ValueError, TypeError):
            power_num = None
        try:
            toughness_num = float(toughness) if toughness and toughness.replace('.', '').isdigit() else None
        except (ValueError, TypeError):
            toughness_num = None
        
        # prices
        prices = card.get('prices', {}) or {}
        usd_price = prices.get('usd')
        usd_foil_price = prices.get('usd_foil')
        
        try:
            usd_price = float(usd_price) if usd_price else None
        except (ValueError, TypeError):
            usd_price = None
        try:
            usd_foil_price = float(usd_foil_price) if usd_foil_price else None
        except (ValueError, TypeError):
            usd_foil_price = None
        
        # line parsing
        type_line = card.get('type_line', '') or ''
        is_creature = 'Creature' in type_line
        is_instant = 'Instant' in type_line
        is_sorcery = 'Sorcery' in type_line
        is_enchantment = 'Enchantment' in type_line
        is_artifact = 'Artifact' in type_line
        is_planeswalker = 'Planeswalker' in type_line
        is_land = 'Land' in type_line
        
        # card types which are broad
        if is_creature:
            card_type = 'Creature'
        elif is_planeswalker:
            card_type = 'Planeswalker'
        elif is_instant:
            card_type = 'Instant'
        elif is_sorcery:
            card_type = 'Sorcery'
        elif is_enchantment:
            card_type = 'Enchantment'
        elif is_artifact:
            card_type = 'Artifact'
        elif is_land:
            card_type = 'Land'
        else:
            card_type = 'Other'
        
        # set info
        released_at = card.get('released_at', '')
        release_year = int(released_at[:4]) if released_at and len(released_at) >= 4 else None
        
        # legality
        legalities = card.get('legalities', {}) or {}
        
        # keywords
        keywords = card.get('keywords', []) or []
        
        processed.append({
            'name': card.get('name', ''),
            'mana_cost': mana_cost,
            'cmc': cmc,
            'colors': ', '.join(colors) if colors else 'Colorless',
            'color_group': color_group,
            'num_colors': num_colors,
            'color_identity': ', '.join(color_identity) if color_identity else 'Colorless',
            'type_line': type_line,
            'card_type': card_type,
            'rarity': card.get('rarity', 'unknown'),
            'power': power_num,
            'toughness': toughness_num,
            'oracle_text': (card.get('oracle_text', '') or '')[:300],
            'keywords': ', '.join(keywords) if keywords else '',
            'num_keywords': len(keywords),
            'set_name': card.get('set_name', ''),
            'set_code': card.get('set', ''),
            'set_type': card.get('set_type', ''),
            'released_at': released_at,
            'release_year': release_year,
            'price_usd': usd_price,
            'price_usd_foil': usd_foil_price,
            'standard_legal': legalities.get('standard', '') == 'legal',
            'modern_legal': legalities.get('modern', '') == 'legal',
            'commander_legal': legalities.get('commander', '') == 'legal',
            'legacy_legal': legalities.get('legacy', '') == 'legal',
            'edh_rank': card.get('edhrec_rank'),
            'layout': layout,
        })
    
    df = pd.DataFrame(processed)
    
    # CMC tiers
    df['cmc_tier'] = pd.cut(
        df['cmc'], bins=[-1, 0, 1, 2, 3, 4, 5, 6, 99],
        labels=['0', '1', '2', '3', '4', '5', '6', '7+']
    )
    
    # adding price tier
    df['price_tier'] = pd.cut(
        df['price_usd'].fillna(0),
        bins=[-0.01, 0.25, 1, 5, 20, 100, 99999],
        labels=['Bulk (<$0.25)', 'Budget ($0.25-1)', 'Moderate ($1-5)', 
                'Valuable ($5-20)', 'Expensive ($20-100)', 'Premium ($100+)']
    )
    
    # add era classification
    df['era'] = pd.cut(
        df['release_year'].fillna(1993),
        bins=[1992, 1999, 2005, 2010, 2015, 2020, 2030],
        labels=['Classic (93-99)', 'Golden Age (00-05)', 'Modern Era (06-10)', 
                'Renaissance (11-15)', 'Arena Era (16-20)', 'Current (21+)']
    )
    
    print(f"  Processed: {len(df):,} cards")
    print(f"  Card types: {df['card_type'].value_counts().to_dict()}")
    print(f"  With prices: {df['price_usd'].notna().sum():,}")
    
    return df


def save_data(df):
    """Save the processed data as CSV for Power BI"""
    output_path = os.path.join(DATA_DIR, 'mtg_powerbi_ready.csv')
    df.to_csv(output_path, index=False)
    print(f"\n=== OUTPUT ===")
    print(f"Saved: {output_path}")
    print(f"Shape: {df.shape[0]:,} rows, {df.shape[1]} columns")
    
    print(f"\n=== Quick Stats ===")
    print(f"Total Cards: {len(df):,}")
    print(f"Unique Sets: {df['set_name'].nunique()}")
    print(f"Release Years: {df['release_year'].min()} - {df['release_year'].max()}")
    
    print(f"\nColor Distribution:")
    print(df['color_group'].value_counts())
    
    print(f"\nCard Types:")
    print(df['card_type'].value_counts())
    
    print(f"\nRarity Distribution:")
    print(df['rarity'].value_counts())
    
    print(f"\nEra Distribution:")
    print(df['era'].value_counts().sort_index())
    
    print(f"\nPrice Tiers (cards with prices):")
    print(df['price_tier'].value_counts().sort_index())


if __name__ == '__main__':
    print("=" * 60)
    print("MAGIC: THE GATHERING - SCRYFALL DATA FETCHER")
    print("=" * 60)
    
    cards = fetch_bulk_data()
    df = transform_cards(cards)
    save_data(df)
    
    print("\nData preparation complete! Open the file in Power BI")